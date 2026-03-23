import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import io

st.set_page_config(
    page_title="Company Churn Analysis",
    page_icon="🏨",
    layout="wide"
)

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
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
st.markdown("Upload the **Reservation file** and **Partner/Company file** to analyze the churn status of each company.")

# ── Helper ────────────────────────────────────────────────────────────────────
def classify_churn(months_since: float) -> str:
    if months_since < 3:
        return "Active"
    elif months_since < 6:
        return "Churn 6M"
    elif months_since < 9:
        return "Churn 9M"
    elif months_since < 12:
        return "Churn 12M"
    else:
        return "Lost (>12M)"

def months_diff(from_date: date, to_date: date) -> float:
    return (to_date - from_date).days / 30.44

def highlight_status(val):
    color_map = {
        "Active":          "background-color:#d4edda;color:#155724;font-weight:600",
        "Churn 6M":        "background-color:#fff3cd;color:#856404;font-weight:600",
        "Churn 9M":        "background-color:#f8d7da;color:#721c24;font-weight:600",
        "Churn 12M":       "background-color:#e2d9f3;color:#432874;font-weight:600",
        "Lost (>12M)":     "background-color:#d6d8db;color:#1b1e21;font-weight:600",
        "No Reservation":  "background-color:#f1f3f4;color:#888;font-weight:600",
    }
    return color_map.get(val, "")

def highlight_row(row):
    color_map = {
        "Active":          "background-color:#d4edda;color:#1a1a1a;font-weight:600",
        "Churn 6M":        "background-color:#fff3cd;color:#1a1a1a;font-weight:600",
        "Churn 9M":        "background-color:#f8d7da;color:#1a1a1a;font-weight:600",
        "Churn 12M":       "background-color:#e2d9f3;color:#1a1a1a;font-weight:600",
        "Lost (>12M)":     "background-color:#d6d8db;color:#1a1a1a;font-weight:600",
        "No Reservation":  "background-color:#f1f3f4;color:#1a1a1a;font-weight:600",
    }
    c = color_map.get(row["Status"], "color:#1a1a1a")
    return [c] * len(row)

# ── Sidebar – File Upload ─────────────────────────────────────────────────────
with st.sidebar:
    st.header("📂 Upload Files")
    res_file     = st.file_uploader("Reservation file (CSV)", type=["csv"], key="res")
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

# ── Load files ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading files...")
def load_csv(file_bytes, name):
    return pd.read_csv(io.BytesIO(file_bytes))

res_bytes     = res_file.read()
partner_bytes = partner_file.read()
df_res        = load_csv(res_bytes,     res_file.name)
df_partner    = load_csv(partner_bytes, partner_file.name)

# ── Column selection ──────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Reservation file")
    res_company_col = st.selectbox(
        "Company name column",
        df_res.columns.tolist(),
        index=df_res.columns.tolist().index("Company (VAT)") if "Company (VAT)" in df_res.columns else 0,
        key="res_company"
    )
    res_date_col = st.selectbox(
        "Create Date column",
        df_res.columns.tolist(),
        index=df_res.columns.tolist().index("Create Date") if "Create Date" in df_res.columns else 0,
        key="res_date"
    )

    res_revenue_col = st.selectbox(
        "Revenue column",
        ["(none)"] + df_res.columns.tolist(),
        index=(["(none)"] + df_res.columns.tolist()).index("Revenue") if "Revenue" in df_res.columns else 0,
        key="res_revenue"
    )

    st.subheader("Partner file")
    partner_name_col = st.selectbox(
        "Company name column",
        df_partner.columns.tolist(),
        index=df_partner.columns.tolist().index("Display Name") if "Display Name" in df_partner.columns else 0,
        key="partner_name"
    )

# ── Data processing ───────────────────────────────────────────────────────────
df_res[res_date_col] = pd.to_datetime(df_res[res_date_col], errors="coerce", dayfirst=False)
df_res_clean = df_res.dropna(subset=[res_date_col, res_company_col]).copy()
df_res_clean[res_company_col] = df_res_clean[res_company_col].astype(str).str.strip()

df_partner_clean  = df_partner[[partner_name_col]].copy()
df_partner_clean[partner_name_col] = df_partner_clean[partner_name_col].astype(str).str.strip()
df_partner_unique = df_partner_clean.drop_duplicates(subset=[partner_name_col])

has_revenue = res_revenue_col != "(none)" and res_revenue_col in df_res_clean.columns
if has_revenue:
    df_res_clean[res_revenue_col] = pd.to_numeric(df_res_clean[res_revenue_col], errors="coerce").fillna(0)
    agg = df_res_clean.groupby(res_company_col).agg(
        last_booking   = (res_date_col,    "max"),
        first_booking  = (res_date_col,    "min"),
        total_bookings = (res_date_col,    "count"),
        total_revenue  = (res_revenue_col, "sum"),
    ).reset_index()
    agg.columns = ["company_name", "last_booking", "first_booking", "total_bookings", "total_revenue"]
else:
    agg = df_res_clean.groupby(res_company_col).agg(
        last_booking   = (res_date_col, "max"),
        first_booking  = (res_date_col, "min"),
        total_bookings = (res_date_col, "count"),
    ).reset_index()
    agg.columns = ["company_name", "last_booking", "first_booking", "total_bookings"]
    agg["total_revenue"] = np.nan

agg["last_booking_date"] = agg["last_booking"].dt.date
agg["months_since"]      = agg["last_booking_date"].apply(lambda d: months_diff(d, today_input))
agg["churn_status"]      = agg["months_since"].apply(classify_churn)

df_partner_unique = df_partner_unique.rename(columns={partner_name_col: "company_name"})
df_merged = df_partner_unique.merge(agg, on="company_name", how="left")
df_merged["churn_status"]   = df_merged["churn_status"].fillna("No Reservation")
df_merged["total_bookings"] = df_merged["total_bookings"].fillna(0).astype(int)
df_merged["months_since"]   = df_merged["months_since"].fillna(np.nan)
df_merged["total_revenue"]  = df_merged["total_revenue"].fillna(0)

# ── KPI Cards ─────────────────────────────────────────────────────────────────
st.markdown("### 📊 Overview")

total   = len(df_merged)
active  = (df_merged["churn_status"] == "Active").sum()
churn6  = (df_merged["churn_status"] == "Churn 6M").sum()
churn9  = (df_merged["churn_status"] == "Churn 9M").sum()
churn12 = (df_merged["churn_status"] == "Churn 12M").sum()
lost    = (df_merged["churn_status"] == "Lost (>12M)").sum()
no_res  = (df_merged["churn_status"] == "No Reservation").sum()

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
kpis = [
    (c1, total,  "#495057", "Total Companies"),
    (c2, active, "#28a745", "✅ Active"),
    (c3, churn6, "#fd7e14", "⚠️ Churn 6M"),
    (c4, churn9, "#dc3545", "🔴 Churn 9M"),
    (c5, churn12,"#6f42c1", "🟣 Churn 12M"),
    (c6, lost,   "#343a40", "⛔ Lost >12M"),
    (c7, no_res, "#adb5bd", "❓ No Reservation"),
]
for col, val, color, label in kpis:
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value" style="color:{color};">{val}</p>
            <p class="metric-label">{label}</p>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📋 Company Details", "📈 Status Distribution", "🔍 Filter & Search"])

with tab1:
    st.markdown("#### All Companies")

    display_df = df_merged.copy()
    display_df["Months Since Last Booking"] = display_df["months_since"].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else "—"
    )
    display_df["Last Booking"] = display_df["last_booking_date"].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—"
    )
    display_df["First Booking"] = display_df["first_booking"].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—"
    )

    cols_show = {
        "company_name":              "Company Name",
        "churn_status":              "Status",
        "Months Since Last Booking": "Months Since Last Booking",
        "Last Booking":              "Last Booking",
        "First Booking":             "First Booking",
        "total_bookings":            "Total Bookings",
    }
    out = display_df[list(cols_show.keys())].rename(columns=cols_show)

    styled = out.style.applymap(highlight_status, subset=["Status"])
    st.dataframe(styled, use_container_width=True, height=500)

    csv_out = out.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "⬇️ Download Results (CSV)",
        data=csv_out.encode("utf-8-sig"),
        file_name=f"churn_analysis_{today_input.strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

with tab2:
    st.markdown("#### Churn Status Distribution")

    col_left, col_right = st.columns(2)

    with col_left:
        status_counts = df_merged.groupby("churn_status").agg(
            num_companies = ("company_name", "count"),
            revenue       = ("total_revenue", "sum"),
        ).reset_index()
        status_counts.columns = ["Status", "No. of Companies", "Revenue"]
        status_counts = status_counts.sort_values("No. of Companies", ascending=False).reset_index(drop=True)

        total_rev = status_counts["Revenue"].sum()
        status_counts["% of Companies"] = (status_counts["No. of Companies"] / total * 100).round(1).apply(lambda x: f"{x}%")
        status_counts["% of Revenue"]   = status_counts["Revenue"].apply(
            lambda x: f"{x/total_rev*100:.1f}%" if total_rev > 0 else "—"
        )
        if has_revenue:
            status_counts["Revenue"] = status_counts["Revenue"].apply(lambda x: f"{x:,.0f}")
        else:
            status_counts["Revenue"] = "—"
            status_counts["% of Revenue"] = "—"

        styled_counts = status_counts.style.apply(highlight_row, axis=1)
        st.dataframe(styled_counts, use_container_width=True, hide_index=True)

    with col_right:
        chart_data = df_merged["churn_status"].value_counts()
        st.bar_chart(chart_data)

    if no_res > 0:
        st.markdown("---")
        st.markdown(f"#### ❓ {no_res} companies with no reservation")
        no_res_df = df_merged[df_merged["churn_status"] == "No Reservation"][["company_name"]].rename(
            columns={"company_name": "Company Name"}
        )
        st.dataframe(no_res_df, use_container_width=True, height=200, hide_index=True)

with tab3:
    st.markdown("#### Filter & Search")

    col_filter1, col_filter2, col_filter3 = st.columns(3)
    with col_filter1:
        search_text = st.text_input("🔍 Search company name", placeholder="Enter company name...")
    with col_filter2:
        all_statuses = ["All"] + df_merged["churn_status"].unique().tolist()
        selected_status = st.selectbox("Filter by status", all_statuses)
    with col_filter3:
        min_bookings = st.number_input("Minimum bookings", min_value=0, value=0)

    filtered = df_merged.copy()
    if search_text:
        filtered = filtered[filtered["company_name"].str.contains(search_text, case=False, na=False)]
    if selected_status != "All":
        filtered = filtered[filtered["churn_status"] == selected_status]
    filtered = filtered[filtered["total_bookings"] >= min_bookings]

    st.markdown(f"**{len(filtered)} companies** matched")

    display_filtered = filtered.copy()
    display_filtered["Last Booking"] = display_filtered["last_booking_date"].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—"
    )
    display_filtered["Months Since Last Booking"] = display_filtered["months_since"].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else "—"
    )

    out2 = display_filtered[["company_name", "churn_status", "Months Since Last Booking", "Last Booking", "total_bookings"]].rename(columns={
        "company_name":   "Company Name",
        "churn_status":   "Status",
        "total_bookings": "Total Bookings",
    })

    styled2 = out2.style.applymap(highlight_status, subset=["Status"])
    st.dataframe(styled2, use_container_width=True, height=450, hide_index=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(f"M Village · Churn Analysis Tool · Reference date: {today_input.strftime('%Y-%m-%d')}")