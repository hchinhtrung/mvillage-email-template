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
        col_partner_name = st.text_input("Company Name column", value="Display Name")

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
    result.drop(columns=["_norm"], inplace=True)

    matched_companies = partner_df["_norm"].isin(hotel_pairs["_norm"].unique()).sum()
    stats = {
        "total":      after_dedup,
        "duplicates": before_dedup - after_dedup,
        "matched":    int(matched_companies),
        "no_match":   after_dedup - int(matched_companies),
        "rows":       len(result),
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
        col_partner_name, col_res_company, col_res_hotel, col_res_city,
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