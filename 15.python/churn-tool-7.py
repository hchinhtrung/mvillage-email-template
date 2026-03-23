import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
import io

st.set_page_config(page_title="Company Churn Analysis", page_icon="🏨", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .metric-value { font-size: 2rem; font-weight: 700; margin: 0; }
    .metric-label { font-size: 0.85rem; color: #666; margin: 0; }
    div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("🏨 Company Churn Analysis")
st.markdown("Upload the **Reservation file** and **Partner/Company file** to analyze churn status of each company.")

# ── Helpers ───────────────────────────────────────────────────────────────────
STATUS_ORDER = ["Active", "Churn 6M", "Churn 9M", "Churn 12M", "Lost (>12M)", "No Reservation"]

STATUS_STYLE = {
    "Active":          ("background-color:#d4edda", "#155724"),
    "Churn 6M":        ("background-color:#fff3cd", "#856404"),
    "Churn 9M":        ("background-color:#f8d7da", "#721c24"),
    "Churn 12M":       ("background-color:#e2d9f3", "#432874"),
    "Lost (>12M)":     ("background-color:#d6d8db", "#1b1e21"),
    "No Reservation":  ("background-color:#f1f3f4", "#888888"),
}

def classify_churn(months_since):
    if pd.isna(months_since): return "No Reservation"
    if months_since < 3:  return "Active"
    if months_since < 6:  return "Churn 6M"
    if months_since < 9:  return "Churn 9M"
    if months_since < 12: return "Churn 12M"
    return "Lost (>12M)"

def months_diff(from_date, to_date):
    return (to_date - from_date).days / 30.44

def fmt_rev(x):
    return f"{x:,.0f}" if pd.notna(x) and x != 0 else "—"

def highlight_status_cell(val):
    bg, fg = STATUS_STYLE.get(val, ("", "#333"))
    return f"{bg};color:{fg};font-weight:600" if bg else ""

def highlight_status_row(row, status_col="Status"):
    bg, fg = STATUS_STYLE.get(row[status_col], ("", "#1a1a1a"))
    style = f"{bg};color:#1a1a1a;font-weight:600" if bg else "color:#1a1a1a"
    return [style] * len(row)

def make_breakdown_table(df_rows, group_col, has_revenue, total_rev_all):
    """Given booking-level rows (already filtered to a status), group by group_col."""
    grp = df_rows.groupby(group_col, dropna=False)
    agg_dict = {"company_col": ("company_col", "nunique"), "bookings": ("bookings", "sum")}
    if has_revenue:
        agg_dict["revenue"] = ("revenue", "sum")

    tbl = df_rows.groupby(group_col, dropna=False).agg(
        companies = ("company_col", "nunique"),
        bookings  = ("bookings",    "sum"),
        revenue   = ("revenue",     "sum") if has_revenue else ("bookings", "sum"),
    ).reset_index()
    tbl.columns = [group_col, "Companies", "Bookings", "Revenue"]
    tbl = tbl.sort_values("Revenue" if has_revenue else "Companies", ascending=False).reset_index(drop=True)

    tbl["% Companies"] = (tbl["Companies"] / tbl["Companies"].sum() * 100).round(1).apply(lambda x: f"{x}%")
    tbl["% Revenue"]   = tbl["Revenue"].apply(
        lambda x: f"{x / total_rev_all * 100:.1f}%" if (has_revenue and total_rev_all > 0) else "—"
    )
    if not has_revenue:
        tbl["Revenue"]   = "—"
        tbl["% Revenue"] = "—"
    else:
        tbl["Revenue"] = tbl["Revenue"].apply(fmt_rev)

    tbl[group_col] = tbl[group_col].fillna("(blank)").astype(str)
    return tbl

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📂 Upload Files")
    res_file     = st.file_uploader("Reservation file (CSV)",      type=["csv"], key="res")
    partner_file = st.file_uploader("Partner / Company file (CSV)", type=["csv"], key="partner")
    st.divider()
    st.header("⚙️ Settings")
    today_input = st.date_input("Reference date", value=date.today())
    st.divider()
    st.header("🔗 Column Mapping")
    st.caption("Select the correct column from each file")

if res_file is None or partner_file is None:
    st.info("👈 Please upload both files in the sidebar to start the analysis.")
    st.stop()

@st.cache_data(show_spinner="Loading files...")
def load_csv(b, name):
    return pd.read_csv(io.BytesIO(b))

df_res     = load_csv(res_file.read(),     res_file.name)
df_partner = load_csv(partner_file.read(), partner_file.name)

# ── Column mapping ─────────────────────────────────────────────────────────────
def col_idx(df, name, offset=0):
    cols = df.columns.tolist()
    return cols.index(name) + offset if name in cols else 0

with st.sidebar:
    st.subheader("Reservation file")
    res_company_col = st.selectbox("Company name column",    df_res.columns.tolist(), index=col_idx(df_res, "Company (VAT)"),    key="res_company")
    res_date_col    = st.selectbox("Create Date column",     df_res.columns.tolist(), index=col_idx(df_res, "Create Date"),       key="res_date")
    res_revenue_col = st.selectbox("Revenue column",         ["(none)"] + df_res.columns.tolist(), index=col_idx(df_res, "Revenue", 1), key="res_revenue")
    res_city_col    = st.selectbox("City column",            ["(none)"] + df_res.columns.tolist(), index=col_idx(df_res, "City", 1),    key="res_city")
    res_source_col  = st.selectbox("Booking Source column",  ["(none)"] + df_res.columns.tolist(), index=col_idx(df_res, "Booking Source", 1), key="res_source")
    res_seg_col     = st.selectbox("Segment Room Type column",["(none)"] + df_res.columns.tolist(), index=col_idx(df_res, "Segment Room Type", 1), key="res_seg")

    st.subheader("Partner file")
    partner_name_col  = st.selectbox("Company name column",  df_partner.columns.tolist(), index=col_idx(df_partner, "Display Name"),  key="partner_name")
    partner_occ_col   = st.selectbox("Occupation column",    ["(none)"] + df_partner.columns.tolist(), index=col_idx(df_partner, "Occupation", 1),  key="partner_occ")
    partner_ind_col   = st.selectbox("Industry column",      ["(none)"] + df_partner.columns.tolist(), index=col_idx(df_partner, "Industry", 1),    key="partner_ind")
    partner_ta_col    = st.selectbox("TA Type column",       ["(none)"] + df_partner.columns.tolist(), index=col_idx(df_partner, "TA Type", 1),     key="partner_ta")

# ── Data processing ────────────────────────────────────────────────────────────
has_revenue = res_revenue_col != "(none)" and res_revenue_col in df_res.columns

df_res["_date"]    = pd.to_datetime(df_res[res_date_col], errors="coerce", dayfirst=False)
df_res["_company"] = df_res[res_company_col].astype(str).str.strip()
df_res_clean = df_res.dropna(subset=["_date", "_company"]).copy()
if has_revenue:
    df_res_clean["_revenue"] = pd.to_numeric(df_res_clean[res_revenue_col], errors="coerce").fillna(0)
else:
    df_res_clean["_revenue"] = 0.0

# Partner dimension columns
partner_dim_cols = {}
for col, key in [(partner_occ_col, "Occupation"), (partner_ind_col, "Industry"), (partner_ta_col, "TA Type")]:
    if col != "(none)" and col in df_partner.columns:
        partner_dim_cols[key] = col

df_partner["_company"] = df_partner[partner_name_col].astype(str).str.strip()
partner_lookup_cols = ["_company"] + [v for v in partner_dim_cols.values()]
df_partner_lookup = df_partner[partner_lookup_cols].drop_duplicates(subset=["_company"])

# Merge partner dims into res
df_res_clean = df_res_clean.merge(df_partner_lookup, on="_company", how="left")

# Churn status per company (based on last booking date)
agg_rev = df_res_clean.groupby("_company")["_revenue"].sum().reset_index()
agg_rev.columns = ["company_name", "total_revenue"]

agg_core = df_res_clean.groupby("_company").agg(
    last_booking   = ("_date", "max"),
    first_booking  = ("_date", "min"),
    total_bookings = ("_date", "count"),
).reset_index()
agg_core.columns = ["company_name", "last_booking", "first_booking", "total_bookings"]
agg_core = agg_core.merge(agg_rev, on="company_name", how="left")
agg_core["last_booking_date"] = agg_core["last_booking"].dt.date
agg_core["months_since"]      = agg_core["last_booking_date"].apply(lambda d: months_diff(d, today_input))
agg_core["churn_status"]      = agg_core["months_since"].apply(classify_churn)

# Partner unique list
df_partner_unique = df_partner_lookup.rename(columns={"_company": "company_name"})
df_merged = df_partner_unique.merge(agg_core, on="company_name", how="left")
df_merged["churn_status"]   = df_merged["churn_status"].fillna("No Reservation")
df_merged["total_bookings"] = df_merged["total_bookings"].fillna(0).astype(int)
df_merged["total_revenue"]  = df_merged["total_revenue"].fillna(0)

# Enrich res rows with churn_status of their company
company_status = agg_core[["company_name", "churn_status"]].copy()
df_res_enriched = df_res_clean.merge(company_status, left_on="_company", right_on="company_name", how="left")
df_res_enriched["churn_status"] = df_res_enriched["churn_status"].fillna("No Reservation")

# Build booking-level helper for breakdown
df_rows = df_res_enriched[["_company", "_revenue", "churn_status"]].copy()
df_rows.columns = ["company_col", "revenue", "churn_status"]
df_rows["bookings"] = 1

# Attach res dimension columns to df_rows
for col_key, col_name in [("City", res_city_col), ("Booking Source", res_source_col), ("Segment Room Type", res_seg_col)]:
    if col_name != "(none)" and col_name in df_res_enriched.columns:
        df_rows[col_key] = df_res_enriched[col_name].values

# Attach partner dimension columns to df_rows
for dim_key, dim_col in partner_dim_cols.items():
    df_rows[dim_key] = df_res_enriched[dim_col].values

total_rev_all = df_rows["revenue"].sum() if has_revenue else 0

# ── KPI ────────────────────────────────────────────────────────────────────────
st.markdown("### 📊 Overview")
total   = len(df_merged)
active  = (df_merged["churn_status"] == "Active").sum()
churn6  = (df_merged["churn_status"] == "Churn 6M").sum()
churn9  = (df_merged["churn_status"] == "Churn 9M").sum()
churn12 = (df_merged["churn_status"] == "Churn 12M").sum()
lost    = (df_merged["churn_status"] == "Lost (>12M)").sum()
no_res  = (df_merged["churn_status"] == "No Reservation").sum()

cols = st.columns(7)
for col, val, color, label in zip(cols, [total, active, churn6, churn9, churn12, lost, no_res],
        ["#495057","#28a745","#fd7e14","#dc3545","#6f42c1","#343a40","#adb5bd"],
        ["Total Companies","✅ Active","⚠️ Churn 6M","🔴 Churn 9M","🟣 Churn 12M","⛔ Lost >12M","❓ No Reservation"]):
    with col:
        st.markdown(f'<div class="metric-card"><p class="metric-value" style="color:{color};">{val}</p><p class="metric-label">{label}</p></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📋 Company Details", "📈 Status Distribution", "🔍 Filter & Search"])

# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("#### All Companies")
    display_df = df_merged.copy()
    display_df["Months Since Last Booking"] = display_df["months_since"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
    display_df["Last Booking"]  = display_df["last_booking_date"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—")
    display_df["First Booking"] = display_df["first_booking"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—")

    col_map = {"company_name": "Company Name", "churn_status": "Status",
               "Months Since Last Booking": "Months Since Last Booking",
               "Last Booking": "Last Booking", "First Booking": "First Booking",
               "total_bookings": "Total Bookings"}
    out = display_df[list(col_map.keys())].rename(columns=col_map)
    st.dataframe(out.style.applymap(highlight_status_cell, subset=["Status"]), use_container_width=True, height=500)

    csv_out = out.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Download Results (CSV)", data=csv_out.encode("utf-8-sig"),
                       file_name=f"churn_analysis_{today_input.strftime('%Y%m%d')}.csv", mime="text/csv")

# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("#### Churn Status Distribution")

    # ── Summary table ──────────────────────────────────────────────────────────
    status_counts = df_merged.groupby("churn_status").agg(
        num_companies = ("company_name",  "count"),
        revenue       = ("total_revenue", "sum"),
    ).reset_index()
    status_counts.columns = ["Status", "No. of Companies", "Revenue"]
    status_counts["Status"] = pd.Categorical(status_counts["Status"], categories=STATUS_ORDER, ordered=True)
    status_counts = status_counts.sort_values("Status").reset_index(drop=True)

    total_rev_summary = status_counts["Revenue"].sum()
    status_counts["% of Companies"] = (status_counts["No. of Companies"] / total * 100).round(1).apply(lambda x: f"{x}%")
    status_counts["% of Revenue"]   = status_counts["Revenue"].apply(
        lambda x: f"{x/total_rev_summary*100:.1f}%" if (has_revenue and total_rev_summary > 0) else "—"
    )
    if has_revenue:
        status_counts["Revenue"] = status_counts["Revenue"].apply(fmt_rev)
    else:
        status_counts["Revenue"]   = "—"
        status_counts["% of Revenue"] = "—"

    col_summary, col_chart = st.columns([3, 2])
    with col_summary:
        st.dataframe(
            status_counts.style.apply(highlight_status_row, axis=1),
            use_container_width=True, hide_index=True
        )
    with col_chart:
        chart_data = df_merged["churn_status"].value_counts().reindex(STATUS_ORDER).dropna()
        st.bar_chart(chart_data)

    st.divider()

    # ── Breakdown section ──────────────────────────────────────────────────────
    st.markdown("#### 🔍 Breakdown by Dimension")

    # Build available dimensions list
    available_dims = []
    for dim, col in [("City", res_city_col), ("Booking Source", res_source_col), ("Segment Room Type", res_seg_col)]:
        if col != "(none)" and dim in df_rows.columns:
            available_dims.append(dim)
    for dim in partner_dim_cols.keys():
        if dim in df_rows.columns:
            available_dims.append(dim)

    if not available_dims:
        st.info("No breakdown dimensions available. Please map dimension columns in the sidebar.")
    else:
        bcol1, bcol2 = st.columns([2, 2])
        with bcol1:
            selected_dim = st.selectbox("Breakdown dimension", available_dims, key="breakdown_dim")
        with bcol2:
            selected_status_bd = st.selectbox(
                "Filter by status",
                ["All statuses"] + STATUS_ORDER,
                key="breakdown_status"
            )

        # Filter rows
        if selected_status_bd == "All statuses":
            df_bd = df_rows.copy()
            bd_title = f"All statuses — breakdown by **{selected_dim}**"
        else:
            df_bd = df_rows[df_rows["churn_status"] == selected_status_bd].copy()
            bd_title = f"**{selected_status_bd}** — breakdown by **{selected_dim}**"

        st.markdown(f"##### {bd_title}")

        if selected_status_bd == "All statuses":
            # Show pivoted table: rows = dimension values, cols = statuses
            pivot_companies = df_bd.pivot_table(
                index=selected_dim, columns="churn_status",
                values="company_col", aggfunc="nunique", fill_value=0
            )
            pivot_bookings = df_bd.pivot_table(
                index=selected_dim, columns="churn_status",
                values="bookings", aggfunc="sum", fill_value=0
            )
            pivot_revenue = df_bd.pivot_table(
                index=selected_dim, columns="churn_status",
                values="revenue", aggfunc="sum", fill_value=0
            ) if has_revenue else None

            # Reorder columns
            existing_statuses = [s for s in STATUS_ORDER if s in pivot_companies.columns]
            pivot_companies = pivot_companies.reindex(columns=existing_statuses, fill_value=0)
            pivot_bookings  = pivot_bookings.reindex(columns=existing_statuses, fill_value=0)

            pivot_companies.index = pivot_companies.index.fillna("(blank)").astype(str)
            pivot_companies["Total Companies"] = pivot_companies.sum(axis=1)
            pivot_companies = pivot_companies.sort_values("Total Companies", ascending=False)

            st.markdown("**Companies (unique) per dimension value × status**")
            st.dataframe(pivot_companies, use_container_width=True)

            if has_revenue and pivot_revenue is not None:
                pivot_revenue = pivot_revenue.reindex(columns=existing_statuses, fill_value=0)
                pivot_revenue.index = pivot_revenue.index.fillna("(blank)").astype(str)
                pivot_revenue["Total Revenue"] = pivot_revenue.sum(axis=1)
                pivot_revenue = pivot_revenue.sort_values("Total Revenue", ascending=False)
                pivot_revenue_fmt = pivot_revenue.applymap(fmt_rev)
                st.markdown("**Revenue per dimension value × status**")
                st.dataframe(pivot_revenue_fmt, use_container_width=True)
        else:
            # Single status — show flat breakdown table
            if df_bd.empty:
                st.info(f"No data for status: {selected_status_bd}")
            else:
                tbl = make_breakdown_table(df_bd, selected_dim, has_revenue, total_rev_all)
                st.dataframe(tbl, use_container_width=True, hide_index=True)

    # ── No Reservation list ────────────────────────────────────────────────────
    if no_res > 0:
        st.divider()
        with st.expander(f"❓ {no_res} companies with no reservation", expanded=False):
            no_res_df = df_merged[df_merged["churn_status"] == "No Reservation"][["company_name"]].rename(
                columns={"company_name": "Company Name"}
            )
            st.dataframe(no_res_df, use_container_width=True, height=250, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### Filter & Search")
    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        search_text = st.text_input("🔍 Search company name", placeholder="Enter company name...")
    with cf2:
        all_statuses = ["All"] + STATUS_ORDER
        selected_status = st.selectbox("Filter by status", all_statuses)
    with cf3:
        min_bookings = st.number_input("Minimum bookings", min_value=0, value=0)

    filtered = df_merged.copy()
    if search_text:
        filtered = filtered[filtered["company_name"].str.contains(search_text, case=False, na=False)]
    if selected_status != "All":
        filtered = filtered[filtered["churn_status"] == selected_status]
    filtered = filtered[filtered["total_bookings"] >= min_bookings]

    st.markdown(f"**{len(filtered)} companies** matched")

    disp = filtered.copy()
    disp["Last Booking"] = disp["last_booking_date"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—")
    disp["Months Since Last Booking"] = disp["months_since"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")

    out2 = disp[["company_name","churn_status","Months Since Last Booking","Last Booking","total_bookings"]].rename(columns={
        "company_name": "Company Name", "churn_status": "Status", "total_bookings": "Total Bookings"
    })
    st.dataframe(out2.style.applymap(highlight_status_cell, subset=["Status"]), use_container_width=True, height=450, hide_index=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption(f"M Village · Churn Analysis Tool · Reference date: {today_input.strftime('%Y-%m-%d')}")