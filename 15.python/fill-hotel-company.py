"""
Company Hotel Lookup Tool - M Village
Enrich res_partner with hotel & city stay history from reservations.
Output = deduplicated res_partner + 2 new columns (Hotels, Cities).
"""

import streamlit as st
import pandas as pd
import io

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Company Hotel Lookup",
    page_icon="🏨",
    layout="wide",
)

# ─────────────────────────────────────────────
# STYLE
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .kpi-box { background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px 20px; text-align:center; }
    .kpi-num { font-size:2rem; font-weight:700; color:#1e40af; }
    .kpi-lbl { font-size:0.82rem; color:#64748b; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIDEBAR – FILE UPLOAD + COLUMN MAPPING
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("📂 Upload Files")
    partner_file = st.file_uploader("res_partner (Company list)", type=["csv"])
    res_file     = st.file_uploader("Reservations", type=["csv"])

    st.divider()
    st.header("⚙️ Column Mapping")

    with st.expander("res_partner columns", expanded=True):
        col_partner_name    = st.text_input("Company Name column",  value="Display Name")
        col_partner_created = st.text_input("Created Date column",  value="Created on")

    with st.expander("Reservation columns", expanded=True):
        col_res_company = st.text_input("Company Name column", value="Company (VAT)", key="r_co")
        col_res_hotel   = st.text_input("Hotel column",        value="Hotel Name")
        col_res_city    = st.text_input("City column",         value="City")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def normalize(s) -> str:
    if pd.isna(s):
        return ""
    return str(s).strip().upper()


@st.cache_data(show_spinner=False)
def load_csv(file_bytes: bytes, filename: str) -> pd.DataFrame:
    try:
        return pd.read_csv(io.BytesIO(file_bytes), dtype=str)
    except Exception as e:
        st.error(f"Failed to read {filename}: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def enrich_partners(
    partner_bytes: bytes,
    res_bytes: bytes,
    col_p_name: str,
    col_p_created: str,
    col_r_company: str,
    col_r_hotel: str,
    col_r_city: str,
):
    """
    1. Load both CSVs
    2. Deduplicate res_partner by company name
    3. Build hotel/city lookup from reservations (vectorised)
    4. Left-join onto partner → append Hotels & Cities columns
    """
    partner_df = pd.read_csv(io.BytesIO(partner_bytes), dtype=str)
    res_df     = pd.read_csv(io.BytesIO(res_bytes), dtype=str)

    # --- Validate columns ---
    if col_p_name not in partner_df.columns:
        return None, None, f"Column '{col_p_name}' not found in res_partner. Available: {partner_df.columns.tolist()}"
    for c in [col_r_company, col_r_hotel, col_r_city]:
        if c not in res_df.columns:
            return None, None, f"Column '{c}' not found in reservations. Available: {res_df.columns.tolist()}"

    # --- Deduplicate partner by normalised name ---
    partner_df["_norm"] = partner_df[col_p_name].apply(normalize)
    before_dedup = len(partner_df)
    partner_df = partner_df.drop_duplicates(subset="_norm", keep="first")
    partner_df = partner_df[partner_df["_norm"] != ""]
    after_dedup = len(partner_df)

    # --- Build unique hotel-city pairs per company from reservations ---
    res_df["_norm"] = res_df[col_r_company].apply(normalize)

    hotel_pairs = (
        res_df[["_norm", col_r_hotel, col_r_city]]
        .drop_duplicates()
        .rename(columns={col_r_hotel: "Stay Hotel", col_r_city: "Stay City"})
    )

    # --- Merge: one row per partner × hotel (left join keeps unmatched partners) ---
    result = partner_df.merge(hotel_pairs, on="_norm", how="left")
    result["Stay Hotel"] = result["Stay Hotel"].fillna("")
    result["Stay City"]  = result["Stay City"].fillna("")

    # --- Company State: NEW if created <= 7 days ago, else OLD ---
    now = pd.Timestamp.now()
    if col_p_created in result.columns:
        created_dt = pd.to_datetime(result[col_p_created], errors="coerce")
        result["Company State"] = created_dt.apply(
            lambda d: "NEW" if pd.notna(d) and (now - d).days <= 7 else "OLD"
        )
    else:
        result["Company State"] = "OLD"

    result.drop(columns=["_norm"], inplace=True)

    matched_companies = partner_df["_norm"].isin(hotel_pairs["_norm"].unique()).sum()

    # Count NEW/OLD on deduplicated partners (before hotel expansion)
    now = pd.Timestamp.now()
    if col_p_created in partner_df.columns:
        p_created = pd.to_datetime(partner_df[col_p_created], errors="coerce")
        new_count = int(p_created.apply(lambda d: pd.notna(d) and (now - d).days <= 7).sum())
    else:
        new_count = 0

    stats = {
        "total":      after_dedup,
        "duplicates": before_dedup - after_dedup,
        "matched":    int(matched_companies),
        "no_match":   after_dedup - int(matched_companies),
        "rows":       len(result),
        "new":        new_count,
        "old":        after_dedup - new_count,
    }

    return result, stats, None


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
st.title("🏨 Company Hotel Lookup")
st.caption("Enrich your company list with hotel & city stay history")

if not partner_file or not res_file:
    st.info("👈 Upload **res_partner** and **Reservation** CSV files from the sidebar to get started.")
    st.stop()

partner_bytes = partner_file.read()
res_bytes     = res_file.read()

with st.spinner("Processing..."):
    result_df, stats, error = enrich_partners(
        partner_bytes, res_bytes,
        col_partner_name, col_partner_created,
        col_res_company, col_res_hotel, col_res_city,
    )

if error:
    st.error(error)
    st.stop()

# ── KPI ROW ─────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num">{stats["total"]}</div><div class="kpi-lbl">Companies (after dedup)</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#8b5cf6">{stats["duplicates"]}</div><div class="kpi-lbl">Duplicates Removed</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#059669">{stats["matched"]}</div><div class="kpi-lbl">With Stay History</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626">{stats["no_match"]}</div><div class="kpi-lbl">No History</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0284c7">{stats["rows"]}</div><div class="kpi-lbl">Total Output Rows</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── KPI ROW 2: Company State ────────────────
s1, s2 = st.columns(2)
with s1:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#0d9488">{stats["new"]}</div><div class="kpi-lbl">NEW Companies (≤ 7 days)</div></div>', unsafe_allow_html=True)
with s2:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#94a3b8">{stats["old"]}</div><div class="kpi-lbl">OLD Companies (> 7 days)</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── FILTER ──────────────────────────────────
with st.sidebar:
    st.divider()
    st.header("🔍 Filters")
    search_name = st.text_input("Search by company name", "")
    show_only_matched = st.checkbox("Show only companies with stay history", value=False)

filtered = result_df
if search_name:
    filtered = filtered[filtered[col_partner_name].str.contains(search_name, case=False, na=False)]
if show_only_matched:
    filtered = filtered[filtered["Stay Hotel"] != ""]

# ── TABLE ───────────────────────────────────
st.markdown(f"**{len(filtered):,} rows** (after filters)")

st.dataframe(filtered, use_container_width=True, height=520)

# ── EXPORT ──────────────────────────────────
st.divider()
export_bytes = filtered.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "⬇️ Export Results (CSV)",
    data=export_bytes,
    file_name="company_hotel_lookup.csv",
    mime="text/csv",
)

# ═════════════════════════════════════════════
# ANALYTICS SECTIONS
# ═════════════════════════════════════════════
res_df = load_csv(res_bytes, res_file.name)
if not res_df.empty:
    res_df["_norm"] = res_df[col_res_company].apply(normalize)

    # ── #1: TOP COMPANIES BY REVENUE ────────────
    col_revenue = "Revenue"
    col_room_nights = "Room Night"
    col_company_type = "Company Type (VAT)"

    def render_top_revenue(df, title, emoji):
        """Render a top-20 revenue chart + table for a filtered subset of reservations."""
        st.divider()
        st.subheader(f"{emoji} {title}")

        if col_revenue not in df.columns or df.empty:
            st.info("No data available for this section.")
            return

        rev = df[["_norm", col_res_company, col_revenue]].copy()
        rev[col_revenue] = pd.to_numeric(rev[col_revenue], errors="coerce")
        rev = rev.dropna(subset=[col_revenue])

        if rev.empty:
            st.info("No revenue data found.")
            return

        top = (
            rev.groupby("_norm", sort=False)
            .agg(Company=(col_res_company, "first"), Total_Revenue=(col_revenue, "sum"))
            .sort_values("Total_Revenue", ascending=False)
            .head(20)
            .reset_index(drop=True)
        )

        if col_room_nights in df.columns:
            rn = df[["_norm", col_room_nights]].copy()
            rn[col_room_nights] = pd.to_numeric(rn[col_room_nights], errors="coerce")
            rn_map = rn.groupby("_norm")[col_room_nights].sum()
            top["Room Nights"] = top["Company"].apply(lambda c: int(rn_map.get(normalize(c), 0)))

        # Chart (numeric) + Table (formatted)
        chart_data = (
            rev.groupby(col_res_company, sort=False)[col_revenue]
            .sum().sort_values(ascending=False).head(20)
        )

        top_display = top.copy()
        top_display["Total_Revenue"] = top_display["Total_Revenue"].apply(lambda x: f"{x:,.0f}")
        top_display.index = range(1, len(top_display) + 1)
        top_display.index.name = "#"

        col_chart, col_table = st.columns([2, 1])
        with col_chart:
            st.bar_chart(chart_data, use_container_width=True, height=400)
        with col_table:
            st.dataframe(top_display, use_container_width=True, height=400)

    if col_revenue in res_df.columns:
        if col_company_type in res_df.columns:
            corp_df = res_df[res_df[col_company_type].str.lower().str.strip() == "corporate"]
            ta_df   = res_df[res_df[col_company_type].str.lower().str.strip() == "travel_agent"]

            render_top_revenue(corp_df, "Top Corporate Companies by Revenue", "🏢")
            render_top_revenue(ta_df,   "Top Travel Agents by Revenue",      "✈️")
        else:
            # Fallback: show all if Company Type column not found
            render_top_revenue(res_df, "Top Companies by Revenue", "💰")
    else:
        st.info(f"Column `{col_revenue}` not found in reservation data. Skipping revenue analysis.")

    # ── #4: CHURN ALERT ─────────────────────────
    st.divider()
    st.subheader("🚨 Churn Alert")
    st.caption("Companies flagged as churned in reservation data — consider re-engagement")

    col_churn = "company churn status"
    if col_churn in res_df.columns:
        churned_res = res_df[res_df[col_churn].str.contains("churn", case=False, na=False)]
        churned_companies = (
            churned_res.groupby("_norm", sort=False)
            .agg(
                Company=(col_res_company, "first"),
                Churn_Status=(col_churn, "first"),
                Last_Hotel=(col_res_hotel, "last"),
                Last_City=(col_res_city, "last"),
            )
            .reset_index(drop=True)
        )

        # Add revenue if available
        if col_revenue in res_df.columns:
            rev_by_company = rev_df.groupby("_norm")[col_revenue].sum()
            churned_norms = churned_res.groupby("_norm")[col_res_company].first()
            churned_companies["Total Revenue"] = churned_companies["Company"].apply(
                lambda c: f"{rev_by_company.get(normalize(c), 0):,.0f}"
            )

        churn_count = len(churned_companies)

        ch1, ch2 = st.columns([1, 3])
        with ch1:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#ef4444">{churn_count}</div>'
                f'<div class="kpi-lbl">Churned Companies</div></div>',
                unsafe_allow_html=True,
            )
        with ch2:
            st.dataframe(churned_companies, use_container_width=True, height=350)

        churn_csv = churned_companies.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Export Churn List (CSV)",
            data=churn_csv,
            file_name="churn_alert_companies.csv",
            mime="text/csv",
        )
    else:
        st.info(f"Column `{col_churn}` not found in reservation data. Skipping churn analysis.")

    # ── #5: NEW COMPANY PIPELINE ────────────────
    st.divider()
    st.subheader("🌱 New Company Pipeline")
    st.caption("Companies created in the last 7 days with NO booking history — prioritize outreach")

    new_no_history = result_df[
        (result_df["Company State"] == "NEW") & (result_df["Stay Hotel"] == "")
    ]

    # Deduplicate for display (one row per company)
    display_cols = [c for c in [col_partner_name, "Company State", "Created on", "Email", "Phone", "Mobile", "Industry"]
                    if c in new_no_history.columns]
    pipeline = new_no_history[display_cols].drop_duplicates(subset=[col_partner_name]) if display_cols else new_no_history

    pipe_count = len(pipeline)

    p1, p2 = st.columns([1, 3])
    with p1:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-num" style="color:#0d9488">{pipe_count}</div>'
            f'<div class="kpi-lbl">New Leads (no bookings)</div></div>',
            unsafe_allow_html=True,
        )
    with p2:
        st.dataframe(pipeline, use_container_width=True, height=350)

    pipeline_csv = pipeline.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Export Pipeline (CSV)",
        data=pipeline_csv,
        file_name="new_company_pipeline.csv",
        mime="text/csv",
    )