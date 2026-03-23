import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
import io

st.set_page_config(page_title="Company Churn Analysis", page_icon="🏨", layout="wide")

st.markdown("""
<style>
    .metric-card { background:white; border-radius:10px; padding:20px;
                   text-align:center; box-shadow:0 2px 8px rgba(0,0,0,0.08); }
    .metric-value { font-size:2rem; font-weight:700; margin:0; }
    .metric-label { font-size:0.85rem; color:#666; margin:0; }
    div[data-testid="stDataFrame"] { border-radius:8px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

st.title("🏨 Company Churn Analysis")
st.markdown("Upload the **Reservation file** and **Partner/Company file** to analyze churn status of each company.")

# ── Helpers ────────────────────────────────────────────────────────────────────
STATUS_ORDER = ["Active", "Churn 6M", "Churn 9M", "Churn 12M", "Lost (>12M)", "No Reservation"]
STATUS_STYLE = {
    "Active":          ("#d4edda", "#155724"),
    "Churn 6M":        ("#fff3cd", "#856404"),
    "Churn 9M":        ("#f8d7da", "#721c24"),
    "Churn 12M":       ("#e2d9f3", "#432874"),
    "Lost (>12M)":     ("#d6d8db", "#1b1e21"),
    "No Reservation":  ("#f1f3f4", "#888888"),
    "TOTAL":           ("#2c2c2c", "#ffffff"),
}

def classify_churn(m):
    if pd.isna(m): return "No Reservation"
    if m < 3:  return "Active"
    if m < 6:  return "Churn 6M"
    if m < 9:  return "Churn 9M"
    if m < 12: return "Churn 12M"
    return "Lost (>12M)"

def months_diff(from_date, to_date):
    return (to_date - from_date).days / 30.44

def fmt_rev(x):
    try:
        v = float(x)
        return f"{v:,.0f}" if v != 0 else "—"
    except:
        return "—"

def hl_cell(val):
    bg, fg = STATUS_STYLE.get(str(val), ("", "#333"))
    return f"background-color:{bg};color:{fg};font-weight:600" if bg else ""

def hl_row(row, scol="Status"):
    bg, _ = STATUS_STYLE.get(str(row.get(scol, "")), ("", ""))
    s = f"background-color:{bg};color:#1a1a1a;font-weight:600" if bg else "color:#1a1a1a"
    return [s] * len(row)

def col_idx(df, name, offset=0):
    cols = df.columns.tolist()
    return cols.index(name) + offset if name in cols else 0

def safe_selectbox(label, options, default_name, key, offset=0):
    opts = (["(none)"] + list(options)) if offset else list(options)
    idx = col_idx_list(opts, default_name)
    return st.selectbox(label, opts, index=idx, key=key)

def col_idx_list(lst, name):
    return lst.index(name) if name in lst else 0

# ── Sidebar upload ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📂 Upload Files")
    res_file     = st.file_uploader("Reservation file (CSV)",       type=["csv"], key="res")
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
def load_csv(b, n):
    return pd.read_csv(io.BytesIO(b))

df_res     = load_csv(res_file.read(),     res_file.name)
df_partner = load_csv(partner_file.read(), partner_file.name)

res_cols     = df_res.columns.tolist()
partner_cols = df_partner.columns.tolist()

# ── Column mapping sidebar ─────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Reservation file")
    res_company_col = st.selectbox("Company name column",      res_cols, index=col_idx(df_res, "Company (VAT)"),       key="rc")
    res_date_col    = st.selectbox("Create Date column",       res_cols, index=col_idx(df_res, "Create Date"),         key="rd")
    res_revenue_col = st.selectbox("Revenue column",           ["(none)"]+res_cols, index=col_idx_list(["(none)"]+res_cols, "Revenue"),          key="rr")
    res_city_col    = st.selectbox("City column",              ["(none)"]+res_cols, index=col_idx_list(["(none)"]+res_cols, "City"),              key="rci")
    res_source_col  = st.selectbox("Booking Source column",    ["(none)"]+res_cols, index=col_idx_list(["(none)"]+res_cols, "Booking Source"),    key="rs")
    res_seg_col     = st.selectbox("Segment Room Type column", ["(none)"]+res_cols, index=col_idx_list(["(none)"]+res_cols, "Segment Room Type"), key="rseg")
    res_occ_col     = st.selectbox("Partner Occupation column",["(none)"]+res_cols, index=col_idx_list(["(none)"]+res_cols, "Partner Occupation"),key="rocc")

    st.subheader("Partner file")
    partner_name_col = st.selectbox("Company name column", partner_cols, index=col_idx(df_partner, "Display Name"), key="pn")
    partner_ind_col  = st.selectbox("Industry column",  ["(none)"]+partner_cols, index=col_idx_list(["(none)"]+partner_cols, "Industry"),  key="pi")
    partner_ta_col   = st.selectbox("TA Type column",   ["(none)"]+partner_cols, index=col_idx_list(["(none)"]+partner_cols, "TA Type"),   key="pt")

# ── Core data processing ───────────────────────────────────────────────────────
has_revenue = res_revenue_col != "(none)"

df_res = df_res.copy()
df_res["_date"]    = pd.to_datetime(df_res[res_date_col], errors="coerce", dayfirst=False)
df_res["_company"] = df_res[res_company_col].astype(str).str.strip()
df_res_clean       = df_res.dropna(subset=["_date"]).copy()
df_res_clean       = df_res_clean[df_res_clean["_company"].str.len() > 0]
df_res_clean["_revenue"] = pd.to_numeric(df_res_clean[res_revenue_col], errors="coerce").fillna(0) if has_revenue else 0.0

# Partner lookup for company-level dims (Industry, TA Type)
partner_join_cols = {"_company": partner_name_col}
extra_partner_cols = {}
for key, col in [("Industry", partner_ind_col), ("TA Type", partner_ta_col)]:
    if col != "(none)" and col in df_partner.columns:
        extra_partner_cols[key] = col

df_partner = df_partner.copy()
df_partner["_company"] = df_partner[partner_name_col].astype(str).str.strip()
lookup_src_cols = ["_company"] + [v for v in extra_partner_cols.values()]
df_partner_lookup = df_partner[lookup_src_cols].copy().drop_duplicates(subset=["_company"])
# rename to internal dim keys
rename_map = {v: k for k, v in extra_partner_cols.items()}
df_partner_lookup = df_partner_lookup.rename(columns=rename_map)

# Merge partner dims into res
df_res_clean = df_res_clean.merge(df_partner_lookup, on="_company", how="left")

# Aggregate per company
agg = df_res_clean.groupby("_company").agg(
    last_booking   = ("_date",    "max"),
    first_booking  = ("_date",    "min"),
    total_bookings = ("_date",    "count"),
    total_revenue  = ("_revenue", "sum"),
).reset_index()
agg.columns = ["company_name", "last_booking", "first_booking", "total_bookings", "total_revenue"]
agg["last_booking_date"] = agg["last_booking"].dt.date
agg["months_since"]      = agg["last_booking_date"].apply(lambda d: months_diff(d, today_input))
agg["churn_status"]      = agg["months_since"].apply(classify_churn)

# Partner unique list → df_merged (company-level)
df_partner_unique = df_partner[["_company"]].drop_duplicates().rename(columns={"_company": "company_name"})
df_merged = df_partner_unique.merge(agg, on="company_name", how="left")
df_merged["churn_status"]   = df_merged["churn_status"].fillna("No Reservation")
df_merged["total_bookings"] = df_merged["total_bookings"].fillna(0).astype(int)
df_merged["total_revenue"]  = df_merged["total_revenue"].fillna(0)

# Add Occupation to company-level: first non-null value per company from res
if res_occ_col != "(none)" and res_occ_col in df_res_clean.columns:
    occ_lookup = (
        df_res_clean[df_res_clean[res_occ_col].notna()]
        .drop_duplicates(subset=["_company"])
        [["_company", res_occ_col]]
        .rename(columns={"_company": "company_name", res_occ_col: "_occupation"})
    )
    df_merged = df_merged.merge(occ_lookup, on="company_name", how="left")
else:
    df_merged["_occupation"] = np.nan

# Enrich res rows with churn_status → booking-level df for breakdown
company_status_map = agg.set_index("company_name")["churn_status"].to_dict()
df_res_clean["churn_status"] = df_res_clean["_company"].map(company_status_map).fillna("No Reservation")

# Build df_rows: one row per booking, with all dim columns
dim_config = []  # list of (display_label, source_col_in_res_clean)

# res-side dims — map from internal col names already in df_res_clean
for label, col in [
    ("City",               res_city_col),
    ("Booking Source",     res_source_col),
    ("Segment Room Type",  res_seg_col),
    ("Partner Occupation", res_occ_col),
]:
    if col != "(none)" and col in df_res_clean.columns:
        dim_config.append((label, col))

# partner-side dims — already merged into df_res_clean as their key names
for key in extra_partner_cols.keys():
    if key in df_res_clean.columns:
        dim_config.append((key, key))

df_rows = df_res_clean[["_company", "_revenue", "churn_status"]].copy()
df_rows.columns = ["company_col", "revenue", "churn_status"]
df_rows["bookings"] = 1

for label, src_col in dim_config:
    df_rows[label] = df_res_clean[src_col].values

available_dims = [label for label, _ in dim_config]
total_rev_all  = df_rows["revenue"].sum() if has_revenue else 0

# ── KPI ────────────────────────────────────────────────────────────────────────
st.markdown("### 📊 Overview")
total   = len(df_merged)
active  = (df_merged["churn_status"] == "Active").sum()
churn6  = (df_merged["churn_status"] == "Churn 6M").sum()
churn9  = (df_merged["churn_status"] == "Churn 9M").sum()
churn12 = (df_merged["churn_status"] == "Churn 12M").sum()
lost    = (df_merged["churn_status"] == "Lost (>12M)").sum()
no_res  = (df_merged["churn_status"] == "No Reservation").sum()

for col, val, color, label in zip(
    st.columns(7),
    [total, active, churn6, churn9, churn12, lost, no_res],
    ["#495057","#28a745","#fd7e14","#dc3545","#6f42c1","#343a40","#adb5bd"],
    ["Total Companies","✅ Active","⚠️ Churn 6M","🔴 Churn 9M","🟣 Churn 12M","⛔ Lost >12M","❓ No Reservation"]
):
    with col:
        st.markdown(f'<div class="metric-card"><p class="metric-value" style="color:{color};">{val}</p><p class="metric-label">{label}</p></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📋 Company Details", "📈 Status Distribution", "🔍 Filter & Search", "💡 Insights"])

# ══ TAB 1 ══════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("#### All Companies")
    d = df_merged.copy()
    d["Months Since Last Booking"] = d["months_since"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
    d["Last Booking"]  = d["last_booking_date"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—")
    d["First Booking"] = d["first_booking"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—")
    d["Occupation"] = d["_occupation"].fillna("—")
    out = d[["company_name","churn_status","Occupation","Months Since Last Booking","Last Booking","First Booking","total_bookings"]].rename(columns={
        "company_name":"Company Name","churn_status":"Status","total_bookings":"Total Bookings"})
    st.dataframe(out.style.applymap(hl_cell, subset=["Status"]), use_container_width=True, height=500)
    st.download_button("⬇️ Download Results (CSV)",
        data=out.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
        file_name=f"churn_analysis_{today_input.strftime('%Y%m%d')}.csv", mime="text/csv")

# ══ TAB 2 ══════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("#### Churn Status Distribution")

    # Summary table
    sc = df_merged.groupby("churn_status").agg(
        num_companies=("company_name","count"), revenue=("total_revenue","sum")).reset_index()
    sc.columns = ["Status","No. of Companies","Revenue"]
    sc["Status"] = pd.Categorical(sc["Status"], categories=STATUS_ORDER, ordered=True)
    sc = sc.sort_values("Status").reset_index(drop=True)
    total_rev_sum = sc["Revenue"].sum()
    total_companies_sum = sc["No. of Companies"].sum()
    sc["% of Companies"] = (sc["No. of Companies"] / total * 100).round(1).apply(lambda x: f"{x}%")
    sc["% of Revenue"]   = sc["Revenue"].apply(lambda x: f"{x/total_rev_sum*100:.1f}%" if (has_revenue and total_rev_sum>0) else "—")
    if has_revenue:
        sc["Revenue"] = sc["Revenue"].apply(fmt_rev)
    else:
        sc["Revenue"] = "—"; sc["% of Revenue"] = "—"

    # Add TOTAL row
    total_row = pd.DataFrame([{
        "Status": "TOTAL",
        "No. of Companies": total_companies_sum,
        "Revenue": fmt_rev(total_rev_sum) if has_revenue else "—",
        "% of Companies": "100.0%",
        "% of Revenue": "100.0%" if (has_revenue and total_rev_sum > 0) else "—",
    }])
    sc = pd.concat([sc, total_row], ignore_index=True)

    col_sum, col_chart = st.columns([3,2])
    with col_sum:
        st.dataframe(sc.style.apply(hl_row, axis=1), use_container_width=True, hide_index=True)
    with col_chart:
        st.bar_chart(df_merged["churn_status"].value_counts().reindex(STATUS_ORDER).dropna())

    st.divider()

    # ── Breakdown section ──────────────────────────────────────────────────────
    st.markdown("#### 🔍 Breakdown by Dimension")

    if not available_dims:
        st.info("No breakdown dimensions available. Please map dimension columns in the sidebar.")
    else:
        bc1, bc2 = st.columns([2,2])
        with bc1:
            sel_dim    = st.selectbox("Breakdown dimension", available_dims, key="bd_dim")
        with bc2:
            sel_status = st.selectbox("Filter by status", ["All statuses"] + STATUS_ORDER, key="bd_status")

        df_bd = df_rows if sel_status == "All statuses" else df_rows[df_rows["churn_status"] == sel_status]

        if df_bd.empty:
            st.info(f"No booking data for status: **{sel_status}**")
        elif sel_dim not in df_bd.columns:
            st.warning(f"Column **{sel_dim}** not found in data. Please check column mapping in sidebar.")
        else:
            # Clean dim values
            df_bd = df_bd.copy()
            df_bd[sel_dim] = df_bd[sel_dim].fillna("(blank)").astype(str).str.strip()
            df_bd[sel_dim] = df_bd[sel_dim].replace({"nan":"(blank)", "":"(blank)"})

            if sel_status == "All statuses":
                # Pivot: rows = dim values, cols = statuses — show Companies + Revenue
                piv_comp = df_bd.pivot_table(
                    index=sel_dim, columns="churn_status",
                    values="company_col", aggfunc="nunique", fill_value=0
                )
                existing = [s for s in STATUS_ORDER if s in piv_comp.columns]
                piv_comp = piv_comp.reindex(columns=existing, fill_value=0)
                piv_comp["Total"] = piv_comp.sum(axis=1)
                piv_comp = piv_comp.sort_values("Total", ascending=False)
                piv_comp.index.name = sel_dim

                st.markdown("**Unique companies per dimension × status**")
                st.dataframe(piv_comp, use_container_width=True)

                if has_revenue:
                    piv_rev = df_bd.pivot_table(
                        index=sel_dim, columns="churn_status",
                        values="revenue", aggfunc="sum", fill_value=0
                    )
                    piv_rev = piv_rev.reindex(columns=existing, fill_value=0)
                    piv_rev["Total Revenue"] = piv_rev.sum(axis=1)
                    piv_rev = piv_rev.sort_values("Total Revenue", ascending=False)
                    piv_rev.index.name = sel_dim

                    # Format numbers
                    piv_rev_fmt = piv_rev.copy()
                    for c in piv_rev_fmt.columns:
                        piv_rev_fmt[c] = piv_rev_fmt[c].apply(fmt_rev)

                    st.markdown("**Revenue per dimension × status**")
                    st.dataframe(piv_rev_fmt, use_container_width=True)

                    # % Revenue contribution table
                    st.markdown("**% Revenue contribution per dimension × status**")
                    grand_total = piv_rev["Total Revenue"].sum()
                    piv_pct = piv_rev.copy()
                    if grand_total > 0:
                        for c in piv_pct.columns:
                            piv_pct[c] = (piv_pct[c] / grand_total * 100).round(1).apply(lambda x: f"{x}%")
                    piv_pct.index.name = sel_dim
                    # Style: highlight rows with highest total % contribution
                    def style_pct_table(df):
                        styles = pd.DataFrame("", index=df.index, columns=df.columns)
                        total_col = "Total Revenue"
                        if total_col in df.columns:
                            vals = df[total_col].str.replace("%","").astype(float)
                            max_v = vals.max()
                            for idx in df.index:
                                v = float(df.loc[idx, total_col].replace("%",""))
                                if v >= max_v * 0.7:
                                    styles.loc[idx, total_col] = "background-color:#28a74533;color:#28a745;font-weight:700"
                                elif v >= max_v * 0.4:
                                    styles.loc[idx, total_col] = "background-color:#fd7e1433;color:#fd7e14;font-weight:600"
                                else:
                                    styles.loc[idx, total_col] = "color:#888"
                        return styles
                    st.dataframe(piv_pct.style.apply(style_pct_table, axis=None), use_container_width=True)

            else:
                # Flat table for single status
                grp = df_bd.groupby(sel_dim).agg(
                    Companies = ("company_col", "nunique"),
                    Bookings  = ("bookings",    "sum"),
                    Revenue   = ("revenue",     "sum"),
                ).reset_index()
                grp = grp.sort_values("Revenue" if has_revenue else "Companies", ascending=False).reset_index(drop=True)
                grp["% of Companies"] = (grp["Companies"] / grp["Companies"].sum() * 100).round(1).apply(lambda x: f"{x}%")
                if has_revenue and total_rev_all > 0:
                    grp["% of Revenue"] = (grp["Revenue"] / total_rev_all * 100).round(1).apply(lambda x: f"{x}%")
                    grp["Revenue"]      = grp["Revenue"].apply(fmt_rev)
                else:
                    grp["Revenue"]      = "—"
                    grp["% of Revenue"] = "—"

                st.dataframe(grp, use_container_width=True, hide_index=True)

    # No reservation expander
    if no_res > 0:
        st.divider()
        with st.expander(f"❓ {no_res} companies with no reservation", expanded=False):
            st.dataframe(
                df_merged[df_merged["churn_status"]=="No Reservation"][["company_name"]].rename(columns={"company_name":"Company Name"}),
                use_container_width=True, height=250, hide_index=True)

# ══ TAB 3 ══════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### Filter & Search")
    cf1, cf2, cf3 = st.columns(3)
    with cf1: search_text    = st.text_input("🔍 Search company name", placeholder="Enter company name...")
    with cf2: sel_st         = st.selectbox("Filter by status", ["All"] + STATUS_ORDER)
    with cf3: min_bk         = st.number_input("Minimum bookings", min_value=0, value=0)

    f = df_merged.copy()
    if search_text: f = f[f["company_name"].str.contains(search_text, case=False, na=False)]
    if sel_st != "All": f = f[f["churn_status"] == sel_st]
    f = f[f["total_bookings"] >= min_bk]
    st.markdown(f"**{len(f)} companies** matched")

    fd = f.copy()
    fd["Last Booking"]             = fd["last_booking_date"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—")
    fd["Months Since Last Booking"]= fd["months_since"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
    fd["Occupation"] = fd["_occupation"].fillna("—")
    out2 = fd[["company_name","churn_status","Occupation","Months Since Last Booking","Last Booking","total_bookings"]].rename(columns={
        "company_name":"Company Name","churn_status":"Status","total_bookings":"Total Bookings"})
    st.dataframe(out2.style.applymap(hl_cell, subset=["Status"]), use_container_width=True, height=450, hide_index=True)


# ══ TAB 4 – INSIGHTS ═══════════════════════════════════════════════════════════
with tab4:
    st.markdown("#### 💡 AI-Generated Insights")
    st.markdown("Enter your OpenAI API key and generate strategic insights to help **increase B2B booking rates** based on your data.")

    # ── API Key ────────────────────────────────────────────────────────────────
    api_key = st.text_input("🔑 OpenAI API Key", type="password", placeholder="sk-...", key="oai_key")

    # ── Focus area selector ────────────────────────────────────────────────────
    st.markdown("##### 🎯 Insight Focus Areas")
    focus_cols = st.columns(3)
    with focus_cols[0]:
        focus_churn    = st.checkbox("Churn recovery strategy",    value=True)
        focus_active   = st.checkbox("Grow active companies",      value=True)
    with focus_cols[1]:
        focus_city     = st.checkbox("City-level opportunities",   value=True)
        focus_source   = st.checkbox("Booking source performance", value=True)
    with focus_cols[2]:
        focus_occ      = st.checkbox("Occupation / industry mix",  value=True)
        focus_segment  = st.checkbox("Room segment upsell",        value=True)

    # ── Build data summary for prompt ─────────────────────────────────────────
    def build_summary():
        lines = []

        # Status distribution
        lines.append("=== CHURN STATUS DISTRIBUTION ===")
        sc_raw = df_merged.groupby("churn_status").agg(
            companies=("company_name","count"), revenue=("total_revenue","sum")
        ).reset_index()
        sc_raw["status_order"] = sc_raw["churn_status"].map({s:i for i,s in enumerate(STATUS_ORDER)})
        sc_raw = sc_raw.sort_values("status_order")
        total_rev_s = sc_raw["revenue"].sum()
        for _, row in sc_raw.iterrows():
            pct_c = row["companies"]/total*100
            pct_r = row["revenue"]/total_rev_s*100 if total_rev_s > 0 else 0
            lines.append(f"  {row['churn_status']}: {row['companies']} companies ({pct_c:.1f}%), Revenue: {row['revenue']:,.0f} ({pct_r:.1f}% of total)")

        # City breakdown
        if focus_city and "City" in df_rows.columns:
            lines.append("\n=== CITY BREAKDOWN (bookings & revenue) ===")
            city_g = df_rows.groupby("City").agg(companies=("company_col","nunique"), bookings=("bookings","sum"), revenue=("revenue","sum")).sort_values("revenue", ascending=False).head(10)
            for dim, row in city_g.iterrows():
                lines.append(f"  {dim}: {row['companies']} companies, {row['bookings']} bookings, Revenue: {row['revenue']:,.0f}")

        # Booking source
        if focus_source and "Booking Source" in df_rows.columns:
            lines.append("\n=== BOOKING SOURCE BREAKDOWN ===")
            src_g = df_rows.groupby("Booking Source").agg(companies=("company_col","nunique"), bookings=("bookings","sum"), revenue=("revenue","sum")).sort_values("revenue", ascending=False).head(10)
            for dim, row in src_g.iterrows():
                lines.append(f"  {dim}: {row['companies']} companies, {row['bookings']} bookings, Revenue: {row['revenue']:,.0f}")

        # Occupation
        if focus_occ and "Partner Occupation" in df_rows.columns:
            lines.append("\n=== PARTNER OCCUPATION BREAKDOWN (top 15) ===")
            occ_g = df_rows.groupby("Partner Occupation").agg(companies=("company_col","nunique"), revenue=("revenue","sum")).sort_values("revenue", ascending=False).head(15)
            for dim, row in occ_g.iterrows():
                lines.append(f"  {dim}: {row['companies']} companies, Revenue: {row['revenue']:,.0f}")

        # Segment room type
        if focus_segment and "Segment Room Type" in df_rows.columns:
            lines.append("\n=== ROOM SEGMENT BREAKDOWN ===")
            seg_g = df_rows.groupby("Segment Room Type").agg(companies=("company_col","nunique"), bookings=("bookings","sum"), revenue=("revenue","sum")).sort_values("revenue", ascending=False)
            for dim, row in seg_g.iterrows():
                lines.append(f"  {dim}: {row['companies']} companies, {row['bookings']} bookings, Revenue: {row['revenue']:,.0f}")

        # Churn × City pivot
        if focus_churn and focus_city and "City" in df_rows.columns:
            lines.append("\n=== CHURN STATUS × CITY (companies) ===")
            piv = df_rows.pivot_table(index="City", columns="churn_status", values="company_col", aggfunc="nunique", fill_value=0)
            existing = [s for s in STATUS_ORDER if s in piv.columns]
            piv = piv[existing]
            lines.append(piv.to_string())

        return "\n".join(lines)

    # ── Focus instructions builder ─────────────────────────────────────────────
    def build_focus_instructions():
        areas = []
        if focus_churn:   areas.append("- Churn recovery: strategies to re-engage Churn 6M/9M/12M companies before they become Lost")
        if focus_active:  areas.append("- Active company growth: how to increase booking frequency and revenue from already-active companies")
        if focus_city:    areas.append("- City opportunities: which cities have the most untapped potential or highest churn risk")
        if focus_source:  areas.append("- Booking source: which channels to invest in or optimize")
        if focus_occ:     areas.append("- Occupation/industry targeting: which business types to prioritize for B2B outreach")
        if focus_segment: areas.append("- Room segment upsell: how to shift companies toward higher-value room tiers")
        return "\n".join(areas) if areas else "General B2B booking growth"

    # ── Generate button ────────────────────────────────────────────────────────
    st.divider()
    col_gen1, col_gen2 = st.columns([2,1])
    with col_gen1:
        model_choice = st.selectbox("GPT Model", ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"], index=1)
    with col_gen2:
        lang_choice  = st.selectbox("Output language", ["English", "Vietnamese"], index=0)

    if st.button("🚀 Generate Insights", type="primary", use_container_width=True):
        if not api_key or not api_key.startswith("sk-"):
            st.error("Please enter a valid OpenAI API key (starts with sk-).")
        else:
            with st.spinner("Analyzing data and generating insights..."):
                try:
                    import requests, json

                    data_summary    = build_summary()
                    focus_instruct  = build_focus_instructions()
                    lang_note       = "Respond entirely in Vietnamese." if lang_choice == "Vietnamese" else "Respond in English."

                    system_prompt = f"""You are a senior hospitality revenue strategy consultant specializing in B2B corporate hotel bookings.
You are analyzing data from M Village — a hotel group operating in Vietnam (Hanoi, Da Nang, Ho Chi Minh City).
Your goal is to provide actionable, specific, data-driven insights to increase B2B booking rates and revenue.
{lang_note}
Format your response with clear sections using markdown headers (##), bullet points, and bold text for key numbers.
Be specific and reference actual numbers from the data provided."""

                    user_prompt = f"""Here is the current B2B booking data summary:

{data_summary}

Please generate strategic insights covering the following focus areas:
{focus_instruct}

Structure your response as:
## Executive Summary (2-3 sentences on the overall situation)
## Key Findings (bullet points with specific data references)
## Priority Action Plan (ranked list of specific actions, most impactful first)
## Quick Wins (actions that can be implemented within 30 days)
## Long-term Strategy (3-6 month initiatives)

Be specific: reference company counts, revenue figures, city names, and percentages from the data."""

                    response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": model_choice,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user",   "content": user_prompt}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 2000,
                        },
                        timeout=60
                    )

                    if response.status_code == 200:
                        result = response.json()
                        insight_text = result["choices"][0]["message"]["content"]
                        st.session_state["last_insight"] = insight_text
                        st.session_state["last_prompt"]  = user_prompt
                    else:
                        err = response.json().get("error", {}).get("message", response.text)
                        st.error(f"OpenAI API error ({response.status_code}): {err}")

                except requests.exceptions.Timeout:
                    st.error("Request timed out. Try gpt-4o-mini for faster response.")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # ── Display result ─────────────────────────────────────────────────────────
    if "last_insight" in st.session_state:
        st.divider()
        st.markdown(st.session_state["last_insight"])

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "⬇️ Download Insights (TXT)",
                data=st.session_state["last_insight"].encode("utf-8"),
                file_name=f"mv_insights_{today_input.strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
        with col_dl2:
            with st.expander("🔍 View raw data sent to GPT"):
                st.text(st.session_state.get("last_prompt", ""))

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption(f"M Village · Churn Analysis Tool · Reference date: {today_input.strftime('%Y-%m-%d')}")