import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI, RateLimitError, AuthenticationError, APIConnectionError

# ======================
# Page config
# ======================
st.set_page_config(page_title="Weekly Ranking Comparison", layout="wide")
st.title("📊 Weekly Ranking Comparison Dashboard")

# ======================
# Upload files
# ======================
c1, c2 = st.columns(2)
with c1:
    signup_file = st.file_uploader("📤 Upload Signup File", type=["csv", "xlsx"])
with c2:
    reservation_file = st.file_uploader("📤 Upload Reservation File", type=["csv", "xlsx"])

def load_file(file):
    return pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)

if not signup_file or not reservation_file:
    st.info("👆 Upload both Signup & Reservation files to start")
    st.stop()

signup_df = load_file(signup_file)
res_df = load_file(reservation_file)

# ======================
# Column mapping
# ======================
SIGNUP_HOTEL = "hotel_short_name"
SIGNUP_DATE = signup_df.columns[4]
SIGNUP_COUNT = signup_df.columns[5]

RES_HOTEL = "Hotel Name"
RES_CITY = "City"
RES_DATE = "Checkin"
RES_TENANT = "tenant_id"
BRAND_MODEL = res_df.columns[1]

CITY_ORDER = ["HCM", "HN", "DN"]
BRAND_ORDER = ["savvy", "signature", "hotel", "living", "express"]


# ======================
# Preprocessing
# ======================
signup_df["hotel_key"] = signup_df[SIGNUP_HOTEL].str.lower().str.strip()
res_df["hotel_key"] = res_df[RES_HOTEL].str.lower().str.strip()

signup_df[SIGNUP_DATE] = (
    signup_df[SIGNUP_DATE]
    .astype(str)
    .str.strip()
    .pipe(lambda s: pd.to_datetime(s, format="%b %d, %Y", errors="coerce"))
)

res_df[RES_DATE] = pd.to_datetime(res_df[RES_DATE], errors="coerce")

signup_df[SIGNUP_COUNT] = pd.to_numeric(
    signup_df[SIGNUP_COUNT], errors="coerce"
).fillna(0)

signup_df = signup_df.dropna(subset=[SIGNUP_DATE])
res_df = res_df.dropna(subset=[RES_DATE])

def filter_period(df, col, start, end):
    return df[
        (df[col].dt.date >= start) &
        (df[col].dt.date <= end)
    ]

# ======================
# Date selector (AUTO DEFAULT)
# ======================
st.subheader("📅 Compare Time Ranges")

today = pd.Timestamp.today().normalize()

# Default logic
# Last: D-14 → D-8
last_from_default = (today - pd.Timedelta(days=14)).date()
last_to_default   = (today - pd.Timedelta(days=8)).date()

# Current: D-7 → D-1
current_from_default = (today - pd.Timedelta(days=7)).date()
current_to_default   = (today - pd.Timedelta(days=1)).date()

c1, c2 = st.columns(2)
with c1:
    last_from, last_to = st.date_input(
        "Last Period",
        value=(last_from_default, last_to_default)
    )

with c2:
    current_from, current_to = st.date_input(
        "Current Period",
        value=(current_from_default, current_to_default)
    )


# ======================
# Metric builder
# ======================
def build_metric(res, signup):
    # Find Guest Country column
    guest_country_col = next((col for col in res.columns if "guest" in col.lower() and "country" in col.lower()), None)
    
    # Base checkin aggregation
    checkin_agg = res.groupby(["hotel_key", RES_CITY, BRAND_MODEL])
    
    checkin_total = checkin_agg[RES_TENANT].nunique().reset_index(name="checkin")

    # DOM/INT checkin
    if guest_country_col:
        res_copy = res.copy()
        res_copy["_is_dom"] = res_copy[guest_country_col].astype(str).str.lower().str.strip() == "vietnam"
        
        dom_checkin = (
            res_copy[res_copy["_is_dom"]]
            .groupby(["hotel_key", RES_CITY, BRAND_MODEL])[RES_TENANT]
            .nunique()
            .reset_index(name="dom")
        )
        
        int_checkin = (
            res_copy[~res_copy["_is_dom"]]
            .groupby(["hotel_key", RES_CITY, BRAND_MODEL])[RES_TENANT]
            .nunique()
            .reset_index(name="int")
        )
        
        checkin = checkin_total.merge(dom_checkin, on=["hotel_key", RES_CITY, BRAND_MODEL], how="left")
        checkin = checkin.merge(int_checkin, on=["hotel_key", RES_CITY, BRAND_MODEL], how="left").fillna(0)
    else:
        checkin = checkin_total
        checkin["dom"] = 0
        checkin["int"] = 0

    signup = (
        signup.groupby("hotel_key")[SIGNUP_COUNT]
        .sum()
        .reset_index(name="signup")
    )

    df = checkin.merge(signup, on="hotel_key", how="left").fillna(0)

    df["cr"] = np.where(
        df["checkin"] == 0, 0,
        (df["signup"] / df["checkin"] * 100).round(2)
    )
    return df

last_df = build_metric(
    filter_period(res_df, RES_DATE, last_from, last_to),
    filter_period(signup_df, SIGNUP_DATE, last_from, last_to)
)

current_df = build_metric(
    filter_period(res_df, RES_DATE, current_from, current_to),
    filter_period(signup_df, SIGNUP_DATE, current_from, current_to)
)

# ======================
# Ranking helpers
# ======================
def add_global_rank(df):
    df = df.copy()
    df["rank"] = df["cr"].rank(ascending=False, method="dense")
    return df

def add_city_rank(df):
    df = df.copy()
    df["rank"] = df.groupby(RES_CITY)["cr"].rank(ascending=False, method="dense")
    return df

def add_city_brand_rank(df):
    df = df.copy()
    df["rank"] = df.groupby([RES_CITY, BRAND_MODEL])["cr"].rank(
        ascending=False, method="dense"
    )
    return df

# ======================
# Compare helper
# ======================
def build_compare(last, current):
    df = last.merge(
        current,
        on=["hotel_key", RES_CITY, BRAND_MODEL],
        suffixes=("_last", "_current"),
        how="outer"
    ).fillna(0)

    df["rank_change"] = df["rank_last"] - df["rank_current"]

    for col in ["checkin", "signup", "cr", "dom", "int"]:
        if f"{col}_last" in df.columns:
            df[f"{col}_change_%"] = np.where(
                df[f"{col}_last"] == 0,
                0,
                (df[f"{col}_current"] / df[f"{col}_last"]) - 1
            )

    return df

# ======================
# Column ordering
# ======================
def reorder_columns(df):
    df = df.copy()
    df["hotel_key"] = df["hotel_key"].str.upper()

    cols = [
        "hotel_key", RES_CITY, BRAND_MODEL,
        "rank_last", "rank_current", "rank_change",
        "checkin_last", "checkin_current", "checkin_change_%",
        "dom_last", "dom_current", "dom_change_%",
        "int_last", "int_current", "int_change_%",
        "signup_last", "signup_current", "signup_change_%",
        "cr_last", "cr_current", "cr_change_%"
    ]
    return df[[c for c in cols if c in df.columns]]

# ======================
# Styling
# ======================
def color_change(val):
    try:
        val = float(val)
    except:
        return ""

    if val <= -0.3:
        return "background-color:#e74c3c;color:white;"
    elif val <= -0.05:
        return "background-color:#f39c12;"
    elif val < 0.05:
        return ""
    elif val < 0.3:
        return "background-color:#2ecc71;"
    else:
        return "background-color:#27ae60;color:white;"

def style_df(df):
    styler = df.style.format({
        "rank_last": "{:.0f}",
        "rank_current": "{:.0f}",
        "rank_change": "{:.0f}",
        "checkin_last": "{:.0f}",
        "checkin_current": "{:.0f}",
        "checkin_change_%": "{:.2%}",
        "signup_last": "{:.0f}",
        "signup_current": "{:.0f}",
        "signup_change_%": "{:.2%}",
        "cr_last": "{:.2f}",
        "cr_current": "{:.2f}",
        "cr_change_%": "{:.2%}",
        "dom_last": "{:.0f}",
        "dom_current": "{:.0f}",
        "dom_change_%": "{:.2%}",
        "int_last": "{:.0f}",
        "int_current": "{:.0f}",
        "int_change_%": "{:.2%}",
    })

    # Apply color highlighting to ALL change columns that exist in the dataframe
    change_cols = [c for c in df.columns if "_change_%" in c]
    if change_cols:
        return styler.applymap(color_change, subset=change_cols)
    return styler

# ======================================================
# STYLING - Sticky Tabs
# ======================================================
st.markdown("""
    <style>
    /* Target the tab container and make it visible for sticky positioning */
    div[data-testid="stTabs"] {
        overflow: visible !important;
    }
    
    /* Target the tab list (buttons) and make it sticky */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        position: sticky;
        top: 0px;
        background-color: #0e1117; /* Match Streamlit dark background */
        z-index: 1000;
        padding-top: 5px;
        padding-bottom: 5px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Ensure tab text is visible and buttons are clickable */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] button {
        padding-top: 10px;
        padding-bottom: 10px;
        background-color: transparent !important;
        color: white !important;
    }

    /* Active tab style */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #E24D14 !important; /* Primary color from user request history */
    }

    /* Fix for potential overlap with sidebar or other elements */
    [data-testid="stHeader"] {
        z-index: 1001; /* Ensure streamlit header is above our sticky tabs */
    }
    </style>
    """, unsafe_allow_html=True)

# ======================================================
# TABS
# ======================================================
tab_global, tab_city_overview, tab_city_rank, tab_city_brand, tab_country, tab_chart, tab_insight = st.tabs([
    "📊 Global Ranking",
    "🏙️ City Performance Overview",
    "🏙️ City-level Ranking",
    "🏷️ City × Brand Model Ranking",
    "🌍 Country",
    "📈 Chart",
    "💡 Insight"
])


# ======================
# TAB 1 – Global
# ======================
with tab_global:
    df = reorder_columns(
        build_compare(
            add_global_rank(last_df),
            add_global_rank(current_df)
        ).sort_values("rank_current")
    )
    st.dataframe(style_df(df), use_container_width=True, hide_index=True)
    
# ======================
# TAB 2 – City Overview
# ======================
with tab_city_overview:
    st.subheader("🏙️ City Performance Overview (Last vs Current)")

    city_last = (
        last_df
        .groupby(RES_CITY)[["checkin", "signup", "dom", "int"]]
        .sum()
        .reset_index()
    )

    city_cur = (
        current_df
        .groupby(RES_CITY)[["checkin", "signup", "dom", "int"]]
        .sum()
        .reset_index()
    )

    city = (
        city_last
        .merge(city_cur, on=RES_CITY, suffixes=("_last", "_current"))
        .fillna(0)
    )

    city["checkin_change_%"] = np.where(
        city["checkin_last"] == 0, 0,
        (city["checkin_current"] / city["checkin_last"]) - 1
    )

    city["signup_change_%"] = np.where(
        city["signup_last"] == 0, 0,
        (city["signup_current"] / city["signup_last"]) - 1
    )

    city["cr_last"] = np.where(
        city["checkin_last"] == 0, 0,
        city["signup_last"] / city["checkin_last"] * 100
    )

    city["cr_current"] = np.where(
        city["checkin_current"] == 0, 0,
        city["signup_current"] / city["checkin_current"] * 100
    )

    city["cr_change_%"] = np.where(
        city["cr_last"] == 0, 0,
        (city["cr_current"] / city["cr_last"]) - 1
    )

    city["dom_change_%"] = np.where(
        city["dom_last"] == 0, 0,
        (city["dom_current"] / city["dom_last"]) - 1
    )

    city["int_change_%"] = np.where(
        city["int_last"] == 0, 0,
        (city["int_current"] / city["int_last"]) - 1
    )

    # 👉 FORCE CITY ORDER
    city[RES_CITY] = (
        city[RES_CITY]
        .astype(str)
        .str.upper()
    )

    city[RES_CITY] = pd.Categorical(
        city[RES_CITY],
        categories=CITY_ORDER,
        ordered=True
    )

    city = city.sort_values(RES_CITY)

    # --- ADD GRAND TOTAL ---
    grand_total = pd.DataFrame([{
        RES_CITY: "GRAND TOTAL",
        "checkin_last": city["checkin_last"].sum(),
        "checkin_current": city["checkin_current"].sum(),
        "signup_last": city["signup_last"].sum(),
        "signup_current": city["signup_current"].sum(),
        "dom_last": city["dom_last"].sum(),
        "dom_current": city["dom_current"].sum(),
        "int_last": city["int_last"].sum(),
        "int_current": city["int_current"].sum(),
    }])
    
    # Recalculate derived metrics for grand total
    grand_total["checkin_change_%"] = np.where(grand_total["checkin_last"] == 0, 0, (grand_total["checkin_current"] / grand_total["checkin_last"]) - 1)
    grand_total["signup_change_%"] = np.where(grand_total["signup_last"] == 0, 0, (grand_total["signup_current"] / grand_total["signup_last"]) - 1)
    grand_total["cr_last"] = np.where(grand_total["checkin_last"] == 0, 0, grand_total["signup_last"] / grand_total["checkin_last"] * 100)
    grand_total["cr_current"] = np.where(grand_total["checkin_current"] == 0, 0, grand_total["signup_current"] / grand_total["checkin_current"] * 100)
    grand_total["cr_change_%"] = np.where(grand_total["cr_last"] == 0, 0, (grand_total["cr_current"] / grand_total["cr_last"]) - 1)
    grand_total["dom_change_%"] = np.where(grand_total["dom_last"] == 0, 0, (grand_total["dom_current"] / grand_total["dom_last"]) - 1)
    grand_total["int_change_%"] = np.where(grand_total["int_last"] == 0, 0, (grand_total["int_current"] / grand_total["int_last"]) - 1)
    
    city = pd.concat([city, grand_total], ignore_index=True)

    # Reorder columns to group metrics together
    cols_order = [
         RES_CITY, 
         "checkin_last", "checkin_current", "checkin_change_%",
         "dom_last", "dom_current", "dom_change_%",
         "int_last", "int_current", "int_change_%",
         "signup_last", "signup_current", "signup_change_%",
         "cr_last", "cr_current", "cr_change_%"
    ]
    
    # Styling for Grand Total
    def style_grand_total(row):
        if row[RES_CITY] == "GRAND TOTAL":
            return ["font-weight: bold; background-color: #1e2129; color: #ffffff; border-top: 2px solid #E24D14;"] * len(row)
        return [""] * len(row)

    st.dataframe(
        style_df(city[cols_order]).apply(style_grand_total, axis=1),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    st.subheader("🏷️ Breakdown by Brand Model")

    # Group by City + Brand
    cb_last = (
        last_df
        .groupby([RES_CITY, BRAND_MODEL])[["checkin", "signup", "dom", "int"]]
        .sum()
        .reset_index()
    )

    cb_cur = (
        current_df
        .groupby([RES_CITY, BRAND_MODEL])[["checkin", "signup", "dom", "int"]]
        .sum()
        .reset_index()
    )
    
    # Merge
    cb = (
        cb_last
        .merge(cb_cur, on=[RES_CITY, BRAND_MODEL], suffixes=("_last", "_current"))
        .fillna(0)
    )

    # Calculate Metrics and Change
    cb["checkin_change_%"] = np.where(
        cb["checkin_last"] == 0, 0,
        (cb["checkin_current"] / cb["checkin_last"]) - 1
    )

    cb["signup_change_%"] = np.where(
        cb["signup_last"] == 0, 0,
        (cb["signup_current"] / cb["signup_last"]) - 1
    )

    cb["cr_last"] = np.where(
        cb["checkin_last"] == 0, 0,
        cb["signup_last"] / cb["checkin_last"] * 100
    )

    cb["cr_current"] = np.where(
        cb["checkin_current"] == 0, 0,
        cb["signup_current"] / cb["checkin_current"] * 100
    )

    cb["cr_change_%"] = np.where(
        cb["cr_last"] == 0, 0,
        (cb["cr_current"] / cb["cr_last"]) - 1
    )

    cb["dom_change_%"] = np.where(
        cb["dom_last"] == 0, 0,
        (cb["dom_current"] / cb["dom_last"]) - 1
    )

    cb["int_change_%"] = np.where(
        cb["int_last"] == 0, 0,
        (cb["int_current"] / cb["int_last"]) - 1
    )

    # Calculate city totals to add as subtotal rows
    city_totals = cb.groupby(RES_CITY).agg({
        "checkin_last": "sum",
        "checkin_current": "sum",
        "signup_last": "sum",
        "signup_current": "sum",
        "dom_last": "sum",
        "dom_current": "sum",
        "int_last": "sum",
        "int_current": "sum"
    }).reset_index()
    city_totals[BRAND_MODEL] = "TOTAL"
    
    # Recalculate derived metrics for totals
    city_totals["checkin_change_%"] = np.where(city_totals["checkin_last"] == 0, 0, (city_totals["checkin_current"] / city_totals["checkin_last"]) - 1)
    city_totals["signup_change_%"] = np.where(city_totals["signup_last"] == 0, 0, (city_totals["signup_current"] / city_totals["signup_last"]) - 1)
    city_totals["cr_last"] = np.where(city_totals["checkin_last"] == 0, 0, city_totals["signup_last"] / city_totals["checkin_last"] * 100)
    city_totals["cr_current"] = np.where(city_totals["checkin_current"] == 0, 0, city_totals["signup_current"] / city_totals["checkin_current"] * 100)
    city_totals["cr_change_%"] = np.where(city_totals["cr_last"] == 0, 0, (city_totals["cr_current"] / city_totals["cr_last"]) - 1)
    city_totals["dom_change_%"] = np.where(city_totals["dom_last"] == 0, 0, (city_totals["dom_current"] / city_totals["dom_last"]) - 1)
    city_totals["int_change_%"] = np.where(city_totals["int_last"] == 0, 0, (city_totals["int_current"] / city_totals["int_last"]) - 1)
    
    # Append totals and filter/sort
    cb = pd.concat([cb, city_totals], ignore_index=True)

    # Filtering/Ordering
    # Normalize strings
    cb[RES_CITY] = cb[RES_CITY].astype(str).str.upper().str.strip()
    cb[BRAND_MODEL] = cb[BRAND_MODEL].astype(str).str.lower().str.strip()

    # Categorical sort - include TOTAL at the end of each city group
    EXTENDED_BRAND_ORDER = BRAND_ORDER + ["total"]
    cb[RES_CITY] = pd.Categorical(cb[RES_CITY], categories=CITY_ORDER, ordered=True)
    cb[BRAND_MODEL] = pd.Categorical(cb[BRAND_MODEL], categories=EXTENDED_BRAND_ORDER, ordered=True)

    cb = cb.sort_values([RES_CITY, BRAND_MODEL])
    
    # Reorder columns for display
    cols_order = [
         RES_CITY, BRAND_MODEL,
         "checkin_last", "checkin_current", "checkin_change_%",
         "dom_last", "dom_current", "dom_change_%",
         "int_last", "int_current", "int_change_%",
         "signup_last", "signup_current", "signup_change_%",
         "cr_last", "cr_current", "cr_change_%"
    ]
    # Keep only what exists
    cols_order = [c for c in cols_order if c in cb.columns]
    
    # Custom styling to bold the TOTAL rows
    def bold_total(row):
        if row[BRAND_MODEL] == "total":
            return ["font-weight: bold; background-color: #1e2129; color: #ffffff; border-bottom: 1px solid #E24D14;"] * len(row)
        return [""] * len(row)

    st.dataframe(
        style_df(cb[cols_order]).apply(bold_total, axis=1), 
        use_container_width=True,
        hide_index=True
    )


# ======================
# TAB 3 – City Ranking
# ======================
with tab_city_rank:
    st.subheader("🏙️ City-level Ranking (Current Week)")

    df = build_compare(
        add_city_rank(last_df),
        add_city_rank(current_df)
    )

    # normalize city
    df[RES_CITY] = (
        df[RES_CITY]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df[RES_CITY] = pd.Categorical(
        df[RES_CITY],
        categories=CITY_ORDER,
        ordered=True
    )

    for city, cdf in (
        df
        .sort_values(RES_CITY)
        .groupby(RES_CITY, sort=False)
    ):
        st.markdown(f"### 📍 {city}")
        st.dataframe(
            style_df(
                reorder_columns(
                    cdf.sort_values("rank_current")
                )
            ),
            use_container_width=True,
            hide_index=True
        )


# ======================
# TAB 4 – City × Brand
# ======================
with tab_city_brand:
    st.subheader("🏷️ City × Brand Model Ranking (Current Week)")

    df = build_compare(
        add_city_brand_rank(last_df),
        add_city_brand_rank(current_df)
    ).copy()

    # normalize
    df[RES_CITY] = (
        df[RES_CITY]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df[BRAND_MODEL] = (
        df[BRAND_MODEL]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    # 👉 FORCE ORDER
    df[RES_CITY] = pd.Categorical(
        df[RES_CITY],
        categories=CITY_ORDER,
        ordered=True
    )

    df[BRAND_MODEL] = pd.Categorical(
        df[BRAND_MODEL],
        categories=BRAND_ORDER,
        ordered=True
    )

    for city, city_df in (
        df
        .sort_values(RES_CITY)
        .groupby(RES_CITY, sort=False)
    ):
        st.markdown(f"## 📍 {city}")

        city_df = city_df.sort_values([BRAND_MODEL, "rank_current"])

        for bm, bm_df in city_df.groupby(BRAND_MODEL, sort=False):
            if bm_df["checkin_current"].sum() == 0:
                continue

            st.markdown(f"### 🏷️ Brand Model: {bm}")
            st.dataframe(
                style_df(reorder_columns(bm_df)),
                use_container_width=True,
                hide_index=True
            )


# ======================
# TAB – Country
# ======================
with tab_country:
    st.subheader("🌍 Analysis by Guest Country (Current Period)")
    
    # --- Filter Logic for Country Tab ---
    fc1, fc2 = st.columns(2)
    with fc1:
        # Brand Filter
        all_brands = sorted(res_df[BRAND_MODEL].astype(str).unique()) if BRAND_MODEL in res_df.columns else []
        selected_brands = st.multiselect("🏷️ Filter by Brand Model", options=all_brands, key="country_brand_filter")
    
    with fc2:
        # Hotel Filter
        hotel_options_df = res_df.copy()
        if selected_brands:
            hotel_options_df = hotel_options_df[hotel_options_df[BRAND_MODEL].astype(str).isin(selected_brands)]
        
        all_hotels_options = sorted(hotel_options_df[RES_HOTEL].unique())
        selected_hotels = st.multiselect("🏨 Filter by Hotel", options=all_hotels_options, key="country_hotel_filter")

    # Auto-find columns
    guest_country_col = next((col for col in res_df.columns if "guest" in col.lower() and "country" in col.lower()), None)
    signup_status_col = next((col for col in res_df.columns if "sign" in col.lower() and "status" in col.lower() and "v2" in col.lower()), None)
    
    if guest_country_col and signup_status_col:
        # Filter data for both periods
        current_res_country = filter_period(res_df, RES_DATE, current_from, current_to).copy()
        last_res_country = filter_period(res_df, RES_DATE, last_from, last_to).copy()

        # Apply Brand/Hotel Filters
        for df_tmp in [current_res_country, last_res_country]:
            if selected_brands:
                df_tmp.drop(df_tmp[~df_tmp[BRAND_MODEL].astype(str).isin(selected_brands)].index, inplace=True)
            if selected_hotels:
                df_tmp.drop(df_tmp[~df_tmp[RES_HOTEL].isin(selected_hotels)].index, inplace=True)

        if current_res_country.empty and last_res_country.empty:
            st.warning("No data found for the selected filters.")
        else:
            # Normalize status strings
            for df_tmp in [current_res_country, last_res_country]:
                if not df_tmp.empty:
                    df_tmp[signup_status_col] = (
                        df_tmp[signup_status_col]
                        .astype(str)
                        .str.replace("\xa0", " ", regex=False)
                        .str.strip()
                    )

            target_statuses = [
                "Chưa Sign-up",
                "Đã Sign-up từ trước",
                "Sign up trước 2 ngày check in",
                "Sign up trước 1 ngày check in",
                "Sign-up sau C/I"
            ]
            target_statuses_norm = [s.replace("\xa0", " ").strip() for s in target_statuses]

            def build_pivot(df):
                if df.empty:
                    pivot = pd.DataFrame(columns=target_statuses_norm)
                    pivot.index.name = guest_country_col
                    return pivot
                stats = df.groupby([guest_country_col, signup_status_col])[RES_TENANT].nunique().reset_index(name="count")
                pivot = stats.pivot_table(index=guest_country_col, columns=signup_status_col, values="count", fill_value=0)
                for s in target_statuses_norm:
                    if s not in pivot.columns:
                        pivot[s] = 0
                return pivot[target_statuses_norm]

            pivot_current = build_pivot(current_res_country)
            pivot_last = build_pivot(last_res_country)

            # Union of all countries
            all_countries = sorted(set(pivot_current.index) | set(pivot_last.index))
            pivot_current = pivot_current.reindex(all_countries, fill_value=0)
            pivot_last = pivot_last.reindex(all_countries, fill_value=0)

            # Build combined display: LAST | CURRENT | %change for each status, then Total
            display_cols = []
            change_cols = []
            for i, status in enumerate(target_statuses):
                status_norm = target_statuses_norm[i]
                col_last = f"{status} LAST"
                col_cur = f"{status} CURRENT"
                col_chg = f"{status} %"
                display_cols.extend([col_last, col_cur, col_chg])
                change_cols.append(col_chg)

            display_df = pd.DataFrame(index=all_countries)
            for i, status in enumerate(target_statuses):
                status_norm = target_statuses_norm[i]
                col_last = f"{status} LAST"
                col_cur = f"{status} CURRENT"
                col_chg = f"{status} %"
                display_df[col_last] = pivot_last[status_norm]
                display_df[col_cur] = pivot_current[status_norm]
                # % change: (current - last) / last
                display_df[col_chg] = display_df.apply(
                    lambda row, cl=col_last, cc=col_cur: (row[cc] - row[cl]) / row[cl] if row[cl] != 0 else (float('inf') if row[cc] > 0 else 0.0),
                    axis=1
                )

            # Total columns
            last_total_cols = [f"{s} LAST" for s in target_statuses]
            cur_total_cols = [f"{s} CURRENT" for s in target_statuses]
            display_df["Total LAST"] = display_df[last_total_cols].sum(axis=1)
            display_df["Total CURRENT"] = display_df[cur_total_cols].sum(axis=1)
            display_df["Total %"] = display_df.apply(
                lambda row: (row["Total CURRENT"] - row["Total LAST"]) / row["Total LAST"] if row["Total LAST"] != 0 else (float('inf') if row["Total CURRENT"] > 0 else 0.0),
                axis=1
            )
            change_cols.append("Total %")

            # Sort by Total CURRENT
            display_df = display_df.sort_values("Total CURRENT", ascending=False)

            # Grand Total
            grand_total = pd.DataFrame(index=["GRAND TOTAL"])
            for col in display_df.columns:
                if col in change_cols:
                    # Recalculate % from summed values
                    base_col = col.replace(" %", " LAST")
                    cur_col = col.replace(" %", " CURRENT")
                    s_last = display_df[base_col].sum() if base_col in display_df.columns else 0
                    s_cur = display_df[cur_col].sum() if cur_col in display_df.columns else 0
                    grand_total[col] = [(s_cur - s_last) / s_last if s_last != 0 else (float('inf') if s_cur > 0 else 0.0)]
                else:
                    grand_total[col] = [display_df[col].sum()]
            display_df = pd.concat([display_df, grand_total])

            # Replace inf with a large number for display
            display_df = display_df.replace([float('inf'), float('-inf')], [9.99, -9.99])

            # Format dict
            fmt = {}
            for col in display_df.columns:
                if col in change_cols:
                    fmt[col] = "{:.2%}"
                else:
                    fmt[col] = "{:.0f}"

            # Styling: Grand Total row + color_change on % columns
            def style_country_df(row):
                styles = [''] * len(row)
                is_total = row.name == "GRAND TOTAL"
                for i, col in enumerate(row.index):
                    if is_total:
                        styles[i] = "font-weight: bold; background-color: #1e2129; color: #ffffff; border-top: 2px solid #E24D14;"
                    if col in change_cols:
                        chg_style = color_change(row[col])
                        if is_total:
                            styles[i] += chg_style
                        else:
                            styles[i] = chg_style
                return styles

            st.dataframe(
                display_df.style.apply(style_country_df, axis=1).format(fmt),
                use_container_width=True,
                height=600
            )

            # --- AI Summary for Country Tab ---
            st.markdown("---")
            st.subheader("🤖 AI Country Insight Generator")
            
            # API Key Input (try to use session state to share with Insight tab)
            if 'openai_api_key' not in st.session_state:
                st.session_state.openai_api_key = ""
                
            api_key_country = st.text_input(
                "🔑 Enter OpenAI API Key (Required)", 
                value=st.session_state.openai_api_key,
                type="password",
                key="country_tab_api_key"
            )
            
            # Update session state
            if api_key_country:
                st.session_state.openai_api_key = api_key_country
                
            if st.button("✨ Generate Country Insight"):
                if not api_key_country:
                    st.error("Please provide an OpenAI API Key to continue.")
                else:
                    try:
                        client = OpenAI(api_key=api_key_country)
                        
                        # 1. Prepare data for comparison
                        last_res_country = filter_period(res_df, RES_DATE, last_from, last_to).copy()
                        
                        # Apply Brand/Hotel Filters to Last Period as well for fair comparison
                        if selected_brands:
                            last_res_country = last_res_country[last_res_country[BRAND_MODEL].astype(str).isin(selected_brands)]
                        if selected_hotels:
                            last_res_country = last_res_country[last_res_country[RES_HOTEL].isin(selected_hotels)]
                            
                        # Normalize status for both
                        for df in [last_res_country, current_res_country]:
                            if not df.empty:
                                df[signup_status_col] = df[signup_status_col].astype(str).str.replace("\xa0", " ").str.strip()
                        
                        # Define Sign-up Success (using Group 3 from Insight tab logic)
                        success_statuses = ["Sign-up sau C/I", "Sign up trước 1 ngày check in", "Sign up trước 2 ngày check in"]
                        success_statuses_norm = [s.replace("\xa0", " ").strip() for s in success_statuses]
                        
                        def aggregate_country_data(df, period_name):
                            if df.empty:
                                return pd.DataFrame()
                                
                            # Total Guests per Country
                            total = df.groupby(guest_country_col)[RES_TENANT].nunique().reset_index(name="Total_Guests")
                            
                            # Success Signups per Country
                            success = df[df[signup_status_col].isin(success_statuses_norm)].groupby(guest_country_col)[RES_TENANT].nunique().reset_index(name="Signup_Count")
                            
                            merged = total.merge(success, on=guest_country_col, how="left").fillna(0)
                            merged["Period"] = period_name
                            return merged
                            
                        last_agg = aggregate_country_data(last_res_country, "Last")
                        cur_agg = aggregate_country_data(current_res_country, "Current")
                        
                        comparison_agg = pd.concat([last_agg, cur_agg])
                        
                        # Pivot for easy AI reading
                        pivot_ai = comparison_agg.pivot_table(
                            index=guest_country_col,
                            columns="Period",
                            values=["Total_Guests", "Signup_Count"],
                            fill_value=0
                        ).reset_index()
                        
                        # Flatten columns
                        pivot_ai.columns = [f"{col[0]}_{col[1]}" if col[1] else col[0] for col in pivot_ai.columns]
                        
                        csv_data_country = pivot_ai.to_csv(index=False)
                        
                        # 2. Construct Prompt
                        prompt_country = f"""
                        You are a Senior BI Strategy Consultant at MVillage.
                        Analyze the Sign-up (membership registration) performance based on Guest Country for the current period vs the last period.

                        --- DATA (CSV format) ---
                        {csv_data_country}
                        
                        --- REQUIREMENTS ---
                        1. Identify the TOP 5 countries with the highest growth in Sign-ups (absolute numbers).
                        2. Identify any significant drops in either total guests or signup rates for major markets.
                        3. Compare the "Signup Efficiency" (Signup_Count / Total_Guests) between periods.
                        4. Provide sharp, actionable insights for the marketing or operations team based on these country trends.
                        5. Use absolute numbers and percentages clearly.
                        6. Format: Use professional business headings and bullet points. English language only.
                        """
                        
                        with st.spinner("🤖 AI is analyzing country trends..."):
                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "system", "content": "You are a strategic BI analyst expert in hospitality and guest behavior. You provide concise yet high-impact insights."},
                                    {"role": "user", "content": prompt_country}
                                ]
                            )
                            
                            country_insight = response.choices[0].message.content
                            st.success("Country Analysis Complete!")
                            st.markdown(country_insight)
                            
                            with st.expander("📋 Copy Raw Country Analysis"):
                                st.code(country_insight, language="markdown")
                                
                    except Exception as e:
                        st.error(f"Error generating insight: {str(e)}")

            # ======================
            # DOM / INT Sign-up Tables
            # ======================
            st.markdown("---")

            # Define successful sign-up statuses
            signup_success = [
                "Sign up trước 2 ngày check in",
                "Sign up trước 1 ngày check in",
                "Sign-up sau C/I"
            ]
            signup_success_norm = [s.replace("\xa0", " ").strip() for s in signup_success]

            # Classify DOM / INT
            for df_tmp in [current_res_country, last_res_country]:
                if not df_tmp.empty:
                    df_tmp["_is_dom"] = df_tmp[guest_country_col].astype(str).str.lower().str.strip() == "vietnam"
                    df_tmp["_is_signup"] = df_tmp[signup_status_col].isin(signup_success_norm)

            def calc_signup_dom_int(df, group_cols):
                """Count unique sign-up tenants by DOM/INT, grouped by group_cols."""
                if df.empty:
                    return pd.DataFrame(columns=group_cols + ["dom_signup", "int_signup"])
                signup_df_tmp = df[df["_is_signup"]]
                dom = signup_df_tmp[signup_df_tmp["_is_dom"]].groupby(group_cols)[RES_TENANT].nunique().reset_index(name="dom_signup")
                intl = signup_df_tmp[~signup_df_tmp["_is_dom"]].groupby(group_cols)[RES_TENANT].nunique().reset_index(name="int_signup")
                result = dom.merge(intl, on=group_cols, how="outer").fillna(0)
                return result

            def pct_change_safe(cur, last):
                """Calculate % change, return 0 if last is 0."""
                if last == 0:
                    return float('inf') if cur > 0 else 0.0
                return (cur - last) / last

            def build_dom_int_table(last_agg, cur_agg, index_cols):
                """Build combined LAST/CURRENT/% table for DOM and INT."""
                # Merge
                merged = cur_agg.merge(last_agg, on=index_cols, how="outer", suffixes=("_cur", "_last")).fillna(0)

                result = pd.DataFrame()
                for col_name in index_cols:
                    result[col_name] = merged[col_name]

                result["DOM Sign-up LAST"] = merged["dom_signup_last"]
                result["DOM Sign-up CURRENT"] = merged["dom_signup_cur"]
                result["DOM %"] = merged.apply(lambda r: pct_change_safe(r["dom_signup_cur"], r["dom_signup_last"]), axis=1)

                result["INT Sign-up LAST"] = merged["int_signup_last"]
                result["INT Sign-up CURRENT"] = merged["int_signup_cur"]
                result["INT %"] = merged.apply(lambda r: pct_change_safe(r["int_signup_cur"], r["int_signup_last"]), axis=1)

                result["TOTAL Sign-up LAST"] = result["DOM Sign-up LAST"] + result["INT Sign-up LAST"]
                result["TOTAL Sign-up CURRENT"] = result["DOM Sign-up CURRENT"] + result["INT Sign-up CURRENT"]
                result["TOTAL %"] = result.apply(lambda r: pct_change_safe(r["TOTAL Sign-up CURRENT"], r["TOTAL Sign-up LAST"]), axis=1)

                return result

            pct_cols_dom_int = ["DOM %", "INT %", "TOTAL %"]

            def add_total_row(df, label="TOTAL", index_col=None):
                """Add a total row to the dataframe."""
                total = {}
                for col in df.columns:
                    if col in pct_cols_dom_int:
                        # Recalculate % from sums
                        base = col.replace(" %", " Sign-up LAST")
                        cur = col.replace(" %", " Sign-up CURRENT")
                        s_last = df[base].sum() if base in df.columns else 0
                        s_cur = df[cur].sum() if cur in df.columns else 0
                        total[col] = pct_change_safe(s_cur, s_last)
                    elif df[col].dtype in ['float64', 'int64', 'int32', 'float32']:
                        total[col] = df[col].sum()
                    else:
                        total[col] = label
                total_row = pd.DataFrame([total])
                return pd.concat([df, total_row], ignore_index=True)

            def style_dom_int_table(row, total_labels, pct_cols, city_total_labels=None):
                styles = [''] * len(row)
                is_grand = False
                is_city_total = False

                # Check if this is a total row
                for col in row.index:
                    val = row[col]
                    if isinstance(val, str):
                        if val in total_labels:
                            is_grand = True
                        if city_total_labels and val in city_total_labels:
                            is_city_total = True

                for i, col in enumerate(row.index):
                    if is_grand:
                        styles[i] = "font-weight: bold; background-color: #1e2129; color: #ffffff; border-top: 2px solid #E24D14;"
                    elif is_city_total:
                        styles[i] = "font-weight: bold; background-color: #fffb91; color: #000000;"

                    if col in pct_cols:
                        chg_style = color_change(row[col])
                        if is_grand or is_city_total:
                            styles[i] += chg_style
                        else:
                            styles[i] = chg_style

                return styles

            def fmt_dom_int(df, pct_cols):
                fmt = {}
                for col in df.columns:
                    if col in pct_cols:
                        fmt[col] = "{:.2%}"
                    elif df[col].dtype in ['float64', 'int64', 'int32', 'float32']:
                        fmt[col] = "{:.0f}"
                return fmt

            # ---- TABLE 1: BY CITY ----
            st.subheader("🏙️ Sign-up by City (DOM / INT)")
            group_city = [RES_CITY]
            cur_city = calc_signup_dom_int(current_res_country, group_city)
            last_city = calc_signup_dom_int(last_res_country, group_city)
            city_table = build_dom_int_table(last_city, cur_city, group_city)

            # Sort by CITY_ORDER
            city_order_map = {c: i for i, c in enumerate(CITY_ORDER)}
            city_table["_sort"] = city_table[RES_CITY].map(city_order_map).fillna(99)
            city_table = city_table.sort_values("_sort").drop(columns=["_sort"])

            city_table = city_table.replace([float('inf'), float('-inf')], [9.99, -9.99])
            city_table = add_total_row(city_table, label="TOTAL", index_col=RES_CITY)

            st.dataframe(
                city_table.style.apply(
                    style_dom_int_table, axis=1,
                    total_labels=["TOTAL"], pct_cols=pct_cols_dom_int
                ).format(fmt_dom_int(city_table, pct_cols_dom_int)),
                use_container_width=True,
                hide_index=True
            )

            # ---- TABLE 2: SEGMENT (City × Brand) ----
            st.subheader("🏷️ Sign-up by Segment (DOM / INT)")
            group_seg = [RES_CITY, BRAND_MODEL]
            cur_seg = calc_signup_dom_int(current_res_country, group_seg)
            last_seg = calc_signup_dom_int(last_res_country, group_seg)
            seg_table = build_dom_int_table(last_seg, cur_seg, group_seg)

            # Sort by CITY_ORDER then BRAND_ORDER
            brand_order_map = {b: i for i, b in enumerate(BRAND_ORDER)}
            seg_table["_city_sort"] = seg_table[RES_CITY].map(city_order_map).fillna(99)
            seg_table["_brand_sort"] = seg_table[BRAND_MODEL].astype(str).str.lower().map(brand_order_map).fillna(99)
            seg_table = seg_table.sort_values(["_city_sort", "_brand_sort"]).drop(columns=["_city_sort", "_brand_sort"])

            # Add city subtotals
            city_total_labels = []
            seg_rows = []
            for city in seg_table[RES_CITY].unique():
                city_data = seg_table[seg_table[RES_CITY] == city]
                seg_rows.append(city_data)
                # City subtotal
                subtotal = {}
                label = f"TOTAL {city}"
                city_total_labels.append(label)
                for col in seg_table.columns:
                    if col == RES_CITY:
                        subtotal[col] = label
                    elif col == BRAND_MODEL:
                        subtotal[col] = ""
                    elif col in pct_cols_dom_int:
                        base = col.replace(" %", " Sign-up LAST")
                        cur_col = col.replace(" %", " Sign-up CURRENT")
                        s_last = city_data[base].sum() if base in city_data.columns else 0
                        s_cur = city_data[cur_col].sum() if cur_col in city_data.columns else 0
                        subtotal[col] = pct_change_safe(s_cur, s_last)
                    elif city_data[col].dtype in ['float64', 'int64', 'int32', 'float32']:
                        subtotal[col] = city_data[col].sum()
                    else:
                        subtotal[col] = ""
                seg_rows.append(pd.DataFrame([subtotal]))

            seg_table_final = pd.concat(seg_rows, ignore_index=True)
            seg_table_final = seg_table_final.replace([float('inf'), float('-inf')], [9.99, -9.99])

            # Grand total
            grand = {}
            for col in seg_table_final.columns:
                if col == RES_CITY:
                    grand[col] = "GRAND TOTAL"
                elif col == BRAND_MODEL:
                    grand[col] = ""
                elif col in pct_cols_dom_int:
                    # Sum from original seg_table (not subtotals)
                    base = col.replace(" %", " Sign-up LAST")
                    cur_col = col.replace(" %", " Sign-up CURRENT")
                    s_last = seg_table[base].sum() if base in seg_table.columns else 0
                    s_cur = seg_table[cur_col].sum() if cur_col in seg_table.columns else 0
                    grand[col] = pct_change_safe(s_cur, s_last)
                elif seg_table[col].dtype in ['float64', 'int64', 'int32', 'float32']:
                    grand[col] = seg_table[col].sum()
                else:
                    grand[col] = ""
            seg_table_final = pd.concat([seg_table_final, pd.DataFrame([grand])], ignore_index=True)
            seg_table_final = seg_table_final.replace([float('inf'), float('-inf')], [9.99, -9.99])

            # Rename columns for display
            seg_display = seg_table_final.rename(columns={RES_CITY: "CITY", BRAND_MODEL: "SEGMENT"})

            st.dataframe(
                seg_display.style.apply(
                    style_dom_int_table, axis=1,
                    total_labels=["GRAND TOTAL"], pct_cols=pct_cols_dom_int,
                    city_total_labels=city_total_labels
                ).format(fmt_dom_int(seg_display, pct_cols_dom_int)),
                use_container_width=True,
                hide_index=True,
                height=600
            )

            # ---- TABLE 3: BREAK BY BRANCH ----
            st.subheader("🏨 Sign-up Break by Branch (DOM / INT)")
            group_hotel = [RES_HOTEL]
            cur_hotel = calc_signup_dom_int(current_res_country, group_hotel)
            last_hotel = calc_signup_dom_int(last_res_country, group_hotel)
            hotel_table = build_dom_int_table(last_hotel, cur_hotel, group_hotel)

            # Sort by TOTAL CURRENT descending
            hotel_table = hotel_table.sort_values("TOTAL Sign-up CURRENT", ascending=False)
            hotel_table = hotel_table.replace([float('inf'), float('-inf')], [9.99, -9.99])
            hotel_table = add_total_row(hotel_table, label="TOTAL", index_col=RES_HOTEL)

            hotel_display = hotel_table.rename(columns={RES_HOTEL: "Hotel Name"})

            st.dataframe(
                hotel_display.style.apply(
                    style_dom_int_table, axis=1,
                    total_labels=["TOTAL"], pct_cols=pct_cols_dom_int
                ).format(fmt_dom_int(hotel_display, pct_cols_dom_int)),
                use_container_width=True,
                hide_index=True,
                height=600
            )

    else:
        st.error(f"Could not find required columns in Reservation File. Looking for columns containing 'Guest Country' and 'Sign-up Status v2'. Available columns: {', '.join(res_df.columns)}")


# ======================
# TAB (New) – Chart
# ======================
with tab_chart:
    st.subheader("📈 Performance Charts (Last + Current Period)")

    # --- Filter Logic ---
    c1, c2, c3 = st.columns(3)
    
    # 1. City Filter
    with c1:
        all_cities = sorted(res_df[RES_CITY].dropna().unique()) if not res_df.empty else []
        selected_cities = st.multiselect("🏙️ Filter by City", options=all_cities)

    # 2. Brand Filter
    with c2:
        all_brands = []
        if not res_df.empty and BRAND_MODEL in res_df.columns:
            all_brands = sorted(res_df[BRAND_MODEL].astype(str).dropna().unique())
        selected_brands = st.multiselect("🏷️ Filter by Brand", options=all_brands)

    # 3. Hotel Mapping
    hotels_map = {}
    city_hotel_map = {} 
    brand_hotel_map = {}

    if not res_df.empty:
        # Get hotel mapping and associations
        cols = [RES_HOTEL, "hotel_key", RES_CITY]
        if BRAND_MODEL in res_df.columns:
            cols.append(BRAND_MODEL)
            
        temp = res_df[cols].drop_duplicates("hotel_key")
        hotels_map.update(dict(zip(temp["hotel_key"], temp[RES_HOTEL])))
        city_hotel_map.update(dict(zip(temp["hotel_key"], temp[RES_CITY])))
        
        if BRAND_MODEL in res_df.columns:
            brand_hotel_map.update(dict(zip(temp["hotel_key"], temp[BRAND_MODEL].astype(str))))

    if not signup_df.empty:
        temp = signup_df[[SIGNUP_HOTEL, "hotel_key"]].drop_duplicates("hotel_key")
        for k, v in zip(temp["hotel_key"], temp[SIGNUP_HOTEL]):
            if k not in hotels_map:
                hotels_map[k] = v
                
    all_hotel_keys = sorted(hotels_map.keys())
    
    # 4. Filter Constraints (Intersection)
    available_hotel_keys = all_hotel_keys
    
    if selected_cities:
        available_hotel_keys = [
            k for k in available_hotel_keys 
            if city_hotel_map.get(k) in selected_cities
        ]
        
    if selected_brands:
        available_hotel_keys = [
            k for k in available_hotel_keys 
            if brand_hotel_map.get(k) in selected_brands
        ]

    with c3:
        selected_hotels = st.multiselect(
            "🏨 Filter by Hotel",
            options=available_hotel_keys,
            format_func=lambda x: hotels_map.get(x, x.title())
        )
    
    # 5. Determine Final Filter Mask
    final_filter_hotels = []
    if selected_hotels:
        final_filter_hotels = selected_hotels
    elif selected_cities or selected_brands:
        final_filter_hotels = available_hotel_keys
    
    # --------------------
    
    # Define Date Ranges
    # We want a continuous view from min(last_from) to max(current_to)
    chart_start = last_from
    chart_end = current_to
    
    # Display date range
    st.info(f"📅 Visualizing Data from: **{chart_start}** → **{chart_end}**")
    
    # Get daily data
    # --- Data Processing for DOM/INT ---
    # Find Guest Country column
    guest_country_col = None
    for col in res_df.columns:
        if "guest" in col.lower() and "country" in col.lower():
            guest_country_col = col
            break
            
    # Checkins
    res_range = filter_period(res_df, RES_DATE, chart_start, chart_end)
    
    if final_filter_hotels:
        res_range = res_range[res_range["hotel_key"].isin(final_filter_hotels)]

    # 1. Total Checkin
    daily_res = (
        res_range.groupby(res_range[RES_DATE].dt.date)[RES_TENANT]
        .nunique()
        .reset_index(name="checkin")
    )
    daily_res.columns = ["date", "checkin"]
    
    # 2. DOM/INT Breakdown
    daily_dom_int = pd.DataFrame()
    if guest_country_col:
        # Create temp column for classification
        res_range["_market_temp"] = np.where(
            res_range[guest_country_col].astype(str).str.lower().str.strip() == "vietnam",
            "DOM", "INT"
        )
        
        # Aggregate
        daily_breakdown = (
            res_range.groupby([res_range[RES_DATE].dt.date, "_market_temp"])[RES_TENANT]
            .nunique()
            .reset_index(name="count")
        )
        # Pivot: date | DOM | INT
        daily_dom_int = daily_breakdown.pivot(index=RES_DATE, columns="_market_temp", values="count").fillna(0).reset_index()
        daily_dom_int.columns = ["date", "checkin_dom", "checkin_int"]
        
    # Signups
    signup_range = filter_period(signup_df, SIGNUP_DATE, chart_start, chart_end)
    
    if final_filter_hotels:
        signup_range = signup_range[signup_range["hotel_key"].isin(final_filter_hotels)]

    daily_signup = (
        signup_range.groupby(signup_range[SIGNUP_DATE].dt.date)[SIGNUP_COUNT]
        .sum()
        .reset_index(name="signup")
    )
    daily_signup.columns = ["date", "signup"]
    
    # Merge all
    chart_df = pd.merge(daily_res, daily_signup, on="date", how="outer").fillna(0)
    
    if not daily_dom_int.empty:
        chart_df = pd.merge(chart_df, daily_dom_int, on="date", how="left").fillna(0)
    else:
        chart_df["checkin_dom"] = 0
        chart_df["checkin_int"] = 0
        
    chart_df["date"] = pd.to_datetime(chart_df["date"])
    chart_df = chart_df.sort_values("date")
    
    if not chart_df.empty:
        chart_df["cr"] = np.where(
            chart_df["checkin"] > 0, 
            (chart_df["signup"] / chart_df["checkin"] * 100), 
            0
        )
        
        # Determine Period Boundary (End of Last Period)
        # Use timestamp (milliseconds) to avoid Plotly calculation errors with strings/Timestamps
        period_boundary = pd.to_datetime(last_to).timestamp() * 1000
        
        # CHART 1: Checkin & Signup
        fig1 = go.Figure()
        
        # Checkin Trace with DOM/INT Hover
        fig1.add_trace(go.Scatter(
            x=chart_df["date"], y=chart_df["checkin"], 
            name="Checkin", mode="lines+markers+text",
            line=dict(color="#3498db", width=3),
            text=chart_df["checkin"].apply(lambda x: f"{int(x)}" if x > 0 else ""),
            textposition="top center",
            customdata=chart_df[["checkin_dom", "checkin_int"]],
            hovertemplate=(
                "<b>Checkin: %{y}</b><br>" +
                "DOM: %{customdata[0]}<br>" +
                "INT: %{customdata[1]}<extra></extra>"
            )
        ))
        
        fig1.add_trace(go.Scatter(
            x=chart_df["date"], y=chart_df["signup"], 
            name="Signup", mode="lines+markers+text",
            line=dict(color="#2ecc71", width=3),
            text=chart_df["signup"].apply(lambda x: f"{int(x)}" if x > 0 else ""),
            textposition="top center",
            hovertemplate="<b>Signup: %{y}</b><extra></extra>"
        ))
        
        # Add Boundary Line
        fig1.add_vline(
            x=period_boundary, line_width=2, line_dash="dash", line_color="#bdc3c7",
            annotation_text="End of Last Period", 
            annotation_position="top left"
        )
        
        fig1.update_layout(
            title="📊 Daily Check-in & Sign-up",
            xaxis_title="Date",
            yaxis_title="Count",
            hovermode="x unified",
            xaxis=dict(
                tickmode="linear",
                dtick=86400000.0, # 1 day
                tickformat="%d-%b"
            ),
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        st.markdown("---")
        
        # CHART 2: Conversion Rate (CR)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=chart_df["date"], y=chart_df["cr"], 
            name="CR %", mode="lines+markers+text",
            line=dict(color="#e67e22", width=3),
            text=chart_df["cr"].apply(lambda x: f"{x:.1f}%" if x > 0 else ""),
            textposition="top center"
        ))
        
        # Add Boundary Line
        fig2.add_vline(
            x=period_boundary, line_width=2, line_dash="dash", line_color="#bdc3c7",
            annotation_text="End of Last Period", 
            annotation_position="top left"
        )
        
        fig2.update_layout(
            title="📉 Daily Conversion Rate (CR)",
            xaxis_title="Date",
            yaxis_title="CR (%)",
            hovermode="x unified",
            xaxis=dict(
                tickmode="linear",
                dtick=86400000.0, # 1 day
                tickformat="%d-%b"
            ),
            height=500
        )
        st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown("---")
        
        # CHART 3: DOM vs INT Check-in
        if guest_country_col:
            fig3 = go.Figure()
            
            # DOM Line
            fig3.add_trace(go.Scatter(
                x=chart_df["date"], y=chart_df["checkin_dom"], 
                name="DOM", mode="lines+markers+text",
                line=dict(color="#9b59b6", width=3),
                text=chart_df["checkin_dom"].apply(lambda x: f"{int(x)}" if x > 0 else ""),
                textposition="top center"
            ))
            
            # INT Line
            fig3.add_trace(go.Scatter(
                x=chart_df["date"], y=chart_df["checkin_int"], 
                name="INT", mode="lines+markers+text",
                line=dict(color="#e74c3c", width=3),
                text=chart_df["checkin_int"].apply(lambda x: f"{int(x)}" if x > 0 else ""),
                textposition="top center"
            ))
            
            # Add Boundary Line
            fig3.add_vline(
                x=period_boundary, line_width=2, line_dash="dash", line_color="#bdc3c7",
                annotation_text="End of Last Period", 
                annotation_position="top left"
            )
            
            fig3.update_layout(
                title="🌍 DOM vs INT Check-in Trends",
                xaxis_title="Date",
                yaxis_title="Count",
                hovermode="x unified",
                xaxis=dict(
                    tickmode="linear",
                    dtick=86400000.0, # 1 day
                    tickformat="%d-%b"
                ),
                height=500,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.warning("⚠️ Cannot generate DOM/INT chart: 'Guest Country' column not found.")
        
    else:
        st.warning("No data found for the selected date range.")


# ======================
# TAB 5 – Insight
# ======================
with tab_insight:
    st.subheader("� Analysis by Brand × Booking Source (Last vs Current)")
    
    # Check if required columns exist in res_df
    booking_source_col = None
    signup_status_col = None
    guest_country_col = None
    
    # Try to find the columns
    for col in res_df.columns:
        col_lower = col.lower()
        if "booking" in col_lower and "source" in col_lower:
            booking_source_col = col
        if "sign" in col_lower and "status" in col_lower and "v2" in col_lower:
            signup_status_col = col
        if "guest" in col_lower and "country" in col_lower:
            guest_country_col = col
    
    # Show column finder
    st.markdown("#### 📋 Column Mapping")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        booking_source_col = st.selectbox(
            "Booking Source Column",
            options=res_df.columns.tolist(),
            index=res_df.columns.tolist().index(booking_source_col) if booking_source_col else 0,
            key="insight_booking_source"
        )
    
    with col2:
        signup_status_col = st.selectbox(
            "Sign-up Status v2 Column",
            options=res_df.columns.tolist(),
            index=res_df.columns.tolist().index(signup_status_col) if signup_status_col else 0,
            key="insight_signup_status"
        )
    
    with col3:
        guest_country_col = st.selectbox(
            "Guest Country Column",
            options=res_df.columns.tolist(),
            index=res_df.columns.tolist().index(guest_country_col) if guest_country_col else 0,
            key="insight_guest_country"
        )
    
    st.markdown("---")
    
    if booking_source_col and signup_status_col and guest_country_col:
        
        # Display date ranges
        st.info(f"📅 **Date Range Comparison:**\n\n**Last Period:** {last_from} → {last_to}\n\n**Current Period:** {current_from} → {current_to}")
        
        def build_comparison_table(last_df, current_df, status_filter, title):
            """Build comparison table with Last vs Current for specific status group"""
            
            st.markdown(f"### {title}")
           
            # Debug: Show available statuses if no data found
            # st.write(f"DEBUG: Searching for {status_filter}")
            # st.write(f"DEBUG: Available statuses in Last: {last_df[signup_status_col].unique()}")
            # st.write(f"DEBUG: Available statuses in Current: {current_df[signup_status_col].unique()}")
            
            # Filter by status (with loose matching)
            def loose_filter(df, statuses):
                # Optimize: Check if column is string type
                if df[signup_status_col].dtype == object:
                    # Create normalized version for matching:
                    # 1. Convert to string
                    # 2. Replace non-breaking space (\xa0) with regular space
                    # 3. Strip leading/trailing whitespace
                    normalized_status = (
                        df[signup_status_col]
                        .astype(str)
                        .str.replace("\xa0", " ", regex=False)
                        .str.strip()
                    )
                    
                    # Normalize target statuses as well
                    target_statuses = [s.replace("\xa0", " ").strip() for s in statuses]
                    
                    mask = normalized_status.isin(target_statuses)
                else:
                    mask = df[signup_status_col].isin(statuses)
                return df[mask].copy()

            last_filtered = loose_filter(last_df, status_filter)
            current_filtered = loose_filter(current_df, status_filter)
            
            if len(last_filtered) == 0 and len(current_filtered) == 0:
                st.warning(f"No data available for statuses: {', '.join(status_filter)}")
                st.info(f"💡 Hint: Check exact spelling. Found in data: {sorted(list(set(last_df[signup_status_col].unique()) | set(current_df[signup_status_col].unique())))}")
                return
            
            def prepare_data(df):
                if len(df) == 0:
                    return pd.DataFrame()
                
                df = df.copy()
                
                # Create DOM/INT column
                df["Market"] = df[guest_country_col].apply(
                    lambda x: "DOM" if str(x).strip().lower() == "vietnam" else "INT"
                )
                
                # Normalize Brand Model
                df[BRAND_MODEL] = df[BRAND_MODEL].astype(str).str.lower().str.strip()
                
                # Normalize Booking Source - handle NaN
                df[booking_source_col] = df[booking_source_col].fillna("Unknown").astype(str)
                
                # Count unique tenants
                pivot_data = (
                    df.groupby([BRAND_MODEL, booking_source_col, "Market"])[RES_TENANT]
                    .nunique()
                    .reset_index(name="count")
                )
                
                # Create pivot table
                pivot_table = pivot_data.pivot_table(
                    index=[BRAND_MODEL, booking_source_col],
                    columns="Market",
                    values="count",
                    aggfunc="sum",
                    fill_value=0
                )
                
                # Ensure DOM and INT columns exist
                if "DOM" not in pivot_table.columns:
                    pivot_table["DOM"] = 0
                if "INT" not in pivot_table.columns:
                    pivot_table["INT"] = 0
                
                pivot_table["Total"] = pivot_table["DOM"] + pivot_table["INT"]
                
                return pivot_table
            
            last_pivot = prepare_data(last_filtered)
            current_pivot = prepare_data(current_filtered)
            
            # Merge last and current
            if len(last_pivot) == 0 and len(current_pivot) == 0:
                st.warning("No data after processing")
                return
                
            if len(last_pivot) == 0:
                last_pivot = pd.DataFrame(columns=["DOM", "INT", "Total"])
            if len(current_pivot) == 0:
                current_pivot = pd.DataFrame(columns=["DOM", "INT", "Total"])
            
            # Get all unique indices
            all_indices = last_pivot.index.union(current_pivot.index)
            
            # Reindex both dataframes
            last_pivot = last_pivot.reindex(all_indices, fill_value=0)
            current_pivot = current_pivot.reindex(all_indices, fill_value=0)
            
            # Create comparison dataframe
            comparison_df = pd.DataFrame({
                "DOM_last": last_pivot["DOM"],
                "DOM_current": current_pivot["DOM"],
                "INT_last": last_pivot["INT"],
                "INT_current": current_pivot["INT"],
                "Total_last": last_pivot["Total"],
                "Total_current": current_pivot["Total"]
            })
            
            # Calculate changes
            comparison_df["DOM_change_%"] = np.where(
                comparison_df["DOM_last"] == 0, 0,
                (comparison_df["DOM_current"] / comparison_df["DOM_last"]) - 1
            )
            comparison_df["INT_change_%"] = np.where(
                comparison_df["INT_last"] == 0, 0,
                (comparison_df["INT_current"] / comparison_df["INT_last"]) - 1
            )
            comparison_df["Total_change_%"] = np.where(
                comparison_df["Total_last"] == 0, 0,
                (comparison_df["Total_current"] / comparison_df["Total_last"]) - 1
            )
            
            # Reset index
            display_df = comparison_df.reset_index()
            
            # Force categorical ordering for Brand Model
            display_df[BRAND_MODEL] = pd.Categorical(
                display_df[BRAND_MODEL],
                categories=BRAND_ORDER,
                ordered=True
            )
            display_df = display_df.sort_values(BRAND_MODEL)
            
            display_df.columns = [
                "Brand Segment", "Booking Source",
                "DOM_last", "DOM_current", "INT_last", "INT_current",
                "Total_last", "Total_current",
                "DOM_change_%", "INT_change_%", "Total_change_%"
            ]
            
            # Reorder columns
            display_df = display_df[[
                "Brand Segment", "Booking Source",
                "DOM_last", "DOM_current", "DOM_change_%",
                "INT_last", "INT_current", "INT_change_%",
                "Total_last", "Total_current", "Total_change_%"
            ]]
            
            # Add subtotals
            final_rows = []
            
            # Calculate Grand Total first
            total_last_sum_all = display_df["Total_last"].sum()
            total_current_sum_all = display_df["Total_current"].sum()
            
            for brand in display_df["Brand Segment"].unique():
                brand_df = display_df[display_df["Brand Segment"] == brand].copy()
                if len(brand_df) == 0: continue
                    
                final_rows.append(brand_df)
                
                # Calculate brand totals
                dom_last_sum = brand_df["DOM_last"].sum()
                dom_current_sum = brand_df["DOM_current"].sum()
                int_last_sum = brand_df["INT_last"].sum()
                int_current_sum = brand_df["INT_current"].sum()
                total_last_sum = brand_df["Total_last"].sum()
                total_current_sum = brand_df["Total_current"].sum()
                
                total_row = pd.DataFrame({
                    "Brand Segment": [f"📊 {brand} Total"],
                    "Booking Source": [""],
                    "DOM_last": [dom_last_sum],
                    "DOM_current": [dom_current_sum],
                    "DOM_change_%": [(dom_current_sum / dom_last_sum - 1) if dom_last_sum > 0 else 0],
                    "INT_last": [int_last_sum],
                    "INT_current": [int_current_sum],
                    "INT_change_%": [(int_current_sum / int_last_sum - 1) if int_last_sum > 0 else 0],
                    "Total_last": [total_last_sum],
                    "Total_current": [total_current_sum],
                    "Total_change_%": [(total_current_sum / total_last_sum - 1) if total_last_sum > 0 else 0]
                })
                final_rows.append(total_row)
            
            if not final_rows:
                st.warning("No data rows generated.")
                return

            final_df = pd.concat(final_rows, ignore_index=True)
            
            # Style functions
            def highlight_totals(row):
                if "Total" in str(row["Brand Segment"]):
                    return ["background-color: #2c3e50; font-weight: bold;"] * len(row)
                return [""] * len(row)
            
            def color_change(val):
                try:
                    val = float(val)
                except:
                    return ""
                if pd.isna(val): return ""
                if val <= -0.3:
                    return "background-color:#e74c3c;color:white;"
                elif val <= -0.05:
                    return "background-color:#f39c12;"
                elif val < 0.05:
                    return ""
                elif val < 0.3:
                    return "background-color:#2ecc71;"
                else:
                    return "background-color:#27ae60;color:white;"
            
            styled_df = final_df.style.apply(highlight_totals, axis=1).format({
                "DOM_last": "{:.0f}",
                "DOM_current": "{:.0f}",
                "DOM_change_%": "{:.1%}",
                "INT_last": "{:.0f}",
                "INT_current": "{:.0f}",
                "INT_change_%": "{:.1%}",
                "Total_last": "{:.0f}",
                "Total_current": "{:.0f}",
                "Total_change_%": "{:.1%}"
            }, na_rep="0").applymap(
                color_change,
                subset=["DOM_change_%", "INT_change_%", "Total_change_%"]
            )
            
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                height=500
            )
            
            return final_df
        
        # Filter data for Last and Current periods
        last_res = filter_period(res_df, RES_DATE, last_from, last_to)
        current_res = filter_period(res_df, RES_DATE, current_from, current_to)
        
        # Store tables for insight generation
        insight_data = {}
        
        # Get unique cities and sort them
        unique_cities = res_df[RES_CITY].dropna().unique()
        sorted_cities = sorted(unique_cities, key=lambda x: CITY_ORDER.index(x) if x in CITY_ORDER else 999)

        for city in sorted_cities:
            st.markdown(f"## 🏙️ City: {city}")
            
            # Filter data for this city
            city_last_res = last_res[last_res[RES_CITY] == city]
            city_current_res = current_res[current_res[RES_CITY] == city]
            
            if city_last_res.empty and city_current_res.empty:
                st.warning(f"No data for city: {city}")
                continue

            # Table 1: Chưa Sign-up
            df1 = build_comparison_table(city_last_res, city_current_res, ["Chưa Sign-up"], f"1️⃣ {city} - Chưa Sign-up")
            if df1 is not None:
                insight_data[f"{city}_Chưa Sign-up"] = df1
                
            st.markdown("---")
            
            # Table 2: Đã Sign-up từ trước
            df2 = build_comparison_table(city_last_res, city_current_res, ["Đã Sign-up từ trước"], f"2️⃣ {city} - Đã Sign-up từ trước")
            if df2 is not None:
                insight_data[f"{city}_Đã Sign-up từ trước"] = df2
                
            st.markdown("---")
            
            # Table 3: Sign-up related to Check-in
            group3 = ["Sign-up sau C/I", "Sign up trước 1 ngày check in", "Sign up trước 2 ngày check in"]
            df3 = build_comparison_table(city_last_res, city_current_res, group3, f"3️⃣ {city} - Sign-up liên quan Check-in")
            if df3 is not None:
                insight_data[f"{city}_Sign-up liên quan Check-in"] = df3
            
            st.markdown("<br><br>", unsafe_allow_html=True)

            
        # Prepare extra data for analysis
        # 1. Hotel Mapping
        hotel_map = res_df[["hotel_key", RES_CITY, BRAND_MODEL]].drop_duplicates("hotel_key").set_index("hotel_key")

        # 2. City Sign-up Trends
        def get_signup_metrics(s_df):
            tmp = s_df.merge(hotel_map, on="hotel_key", how="left")
            return tmp.groupby(RES_CITY)[SIGNUP_COUNT].sum()

        last_signup_df = filter_period(signup_df, SIGNUP_DATE, last_from, last_to)
        cur_signup_df = filter_period(signup_df, SIGNUP_DATE, current_from, current_to)

        last_city_signup = get_signup_metrics(last_signup_df)
        cur_city_signup = get_signup_metrics(cur_signup_df)

        city_diff = pd.DataFrame({"Last": last_city_signup, "Current": cur_city_signup}).fillna(0)
        city_diff["Diff"] = city_diff["Current"] - city_diff["Last"]
        # Add to insight data
        insight_data["4️⃣ City Sign-up Trends (WoW)"] = city_diff

        # 3. Daily Low Point Analysis (Current Period)
        cur_daily = cur_signup_df.groupby(cur_signup_df[SIGNUP_DATE].dt.date)[SIGNUP_COUNT].sum().reset_index()
        cur_daily.columns = ["Date", "Signups"]
        cur_daily = cur_daily.sort_values("Signups")
        insight_data["5️⃣ Daily Sign-up Trend (Lowest Days)"] = cur_daily

        st.markdown("---")
        st.subheader("🤖 AI Insight Generator")
        
        # API Key Input
        api_key = st.text_input("🔑 Enter OpenAI API Key (Required)", type="password")
            
        if st.button("✨ Generate Insight"):
            if not api_key:
                st.error("Please provide an OpenAI API Key to continue.")
            else:
                try:
                    client = OpenAI(api_key=api_key)
                    
                    # --- 1. PREPARE AGGREGATED DATA FOR AI ---
                    # We need a consolidated view: City | Brand | Source | Market | Checkin (Last/Cur) | Signup (Last/Cur)
                    
                    # Combine Period Data
                    last_res_proc = last_res.copy()
                    last_res_proc['Period'] = 'Last'
                    
                    current_res_proc = current_res.copy()
                    current_res_proc['Period'] = 'Current'
                    
                    full_df = pd.concat([last_res_proc, current_res_proc])
                    
                    # Normalize Columns
                    full_df[RES_CITY] = full_df[RES_CITY].astype(str).str.upper().str.strip()
                    full_df[BRAND_MODEL] = full_df[BRAND_MODEL].astype(str).str.lower().str.strip()
                    full_df[booking_source_col] = full_df[booking_source_col].fillna("Unknown").astype(str).str.strip()
                    
                    # Market (DOM/INT)
                    full_df["Market"] = full_df[guest_country_col].apply(
                        lambda x: "DOM" if str(x).strip().lower() == "vietnam" else "INT"
                    )
                    
                    # Define Sign-up Success (using Group 3)
                    # Normalize status for matching
                    full_df[signup_status_col] = full_df[signup_status_col].astype(str).str.replace("\xa0", " ").str.strip()
                    target_signup_statuses = [s.replace("\xa0", " ").strip() for s in group3]
                    
                    full_df['Is_Signup'] = full_df[signup_status_col].isin(target_signup_statuses).astype(int)
                    
                    # Aggregation: Group by Dimensions and Count Unique Tenants
                    # 1. Check-ins (All tenants)
                    metrics_checkin = full_df.groupby(
                        [RES_CITY, BRAND_MODEL, booking_source_col, "Market", "Period"]
                    )[RES_TENANT].nunique().reset_index(name="Checkin_Count")
                    
                    # 2. Sign-ups (Only Success tenants)
                    metrics_signup = full_df[full_df['Is_Signup'] == 1].groupby(
                        [RES_CITY, BRAND_MODEL, booking_source_col, "Market", "Period"]
                    )[RES_TENANT].nunique().reset_index(name="Signup_Count")
                    
                    # Merge Metrics
                    metrics_df = metrics_checkin.merge(
                        metrics_signup,
                        on=[RES_CITY, BRAND_MODEL, booking_source_col, "Market", "Period"],
                        how="left"
                    ).fillna(0)
                    
                    # Pivot to separate Last/Current columns
                    pivot_df = metrics_df.pivot_table(
                        index=[RES_CITY, BRAND_MODEL, booking_source_col, "Market"],
                        columns='Period',
                        values=['Checkin_Count', 'Signup_Count'],
                        fill_value=0
                    ).reset_index()
                    
                    # Flatten Column Names (e.g., Checkin_Count_Last, Signup_Count_Current)
                    pivot_df.columns = [
                        f"{col[0]}_{col[1]}" if col[1] else col[0] 
                        for col in pivot_df.columns
                    ]
                    
                    # Convert to CSV for Prompt
                    csv_data = pivot_df.to_csv(index=False)
                    
                    # --- 2. CONSTRUCT PROMPT ---
                    prompt = f"""
                    You are a Senior BI Strategy Consultant at MVillage.
                    Your mission is to provide an analysis of the changes in Sign-up (membership registration) volume compared to the previous period.

                    YOUR RESPONSE MUST BE DIVIDED INTO TWO DISTINCT SECTIONS:
                    
                    ---
                    ### SECTION 1: DETAILED BUSINESS ANALYSIS
                    This section is for deep-dive understanding.
                    - Provide a DETAILED and EDUCATIONAL explanation for each City (HCM, HN, DN...).
                    - **IMPORTANT: Use absolute numbers for all changes** (e.g., +10, -5, from X to Y).
                    - Explain causality (e.g., "Check-ins dropped by -X, which led to Sign-ups dropping by -Y").
                    - Breakdown by Brand Model, Booking Source, and Market (DOM vs INT).
                    - Provide sharp actionable recommendations at the end of each city or the section.
                    
                    ---
                    ### SECTION 2: EXECUTIVE SUMMARY (SHORTENED & CLEAR)
                    This section is a summary of the key findings from SECTION 1.
                    - Provide a very concise bullet-point list summarizing the "Bottom Line" for each city.
                    - Distill the core insights from Section 1 into 1-2 powerful sentences or bullet points per city.
                    - Highlight only the MOST CRITICAL impact per city (e.g., "HCM summary: Sign-ups dropped by -20 primarily due to a -50 drop in OTA Check-ins; staff conversion efficiency remained stable.").
                    - Use absolute numbers only. Keep it sharp and punchy.
                    
                    ---
                    Văn phong chuyên nghiệp, English language only. 
                    STYLING: Use bullet points and bold text for key metrics.
                    
                    --- DATA ---
                    {csv_data}
                    """
                    
                    # --- 3. CALL API ---
                    with st.spinner("🤖 AI is performing a detailed analysis per City... please wait..."):
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "You are a dedicated BI consultant who explains complex data in simple, detailed, and actionable English stories."},
                                {"role": "user", "content": prompt}
                            ]
                        )
                        
                        insight_text = response.choices[0].message.content
                        
                        st.success("Analysis Complete!")
                        st.markdown(insight_text)
                        
                        # Add a copyable version of the text
                        with st.expander("📋 Click to copy the Raw Analysis"):
                            st.code(insight_text, language="markdown")
                        
                except RateLimitError:
                    st.error("🚫 API Quota Exceeded (429). The provided API Key has run out of credits.")
                except AuthenticationError:
                    st.error("🚫 Invalid API Key (401). Please check that your key is correct.")
                except APIConnectionError:
                    st.error("🚫 Connection Error. Please check your internet connection.")
                except Exception as e:
                    st.error(f"An unexpected error occurred: {str(e)}")
        
    else:
        st.warning("⚠️ Please select the required columns to generate the insight tables.")