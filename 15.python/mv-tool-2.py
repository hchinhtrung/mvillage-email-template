import streamlit as st
import pandas as pd
import numpy as np

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
    checkin = (
        res.groupby(["hotel_key", RES_CITY, BRAND_MODEL])[RES_TENANT]
        .nunique()
        .reset_index(name="checkin")
    )

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

    for col in ["checkin", "signup", "cr"]:
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
    })

    return styler.applymap(color_change, subset=["cr_change_%"])

# ======================================================
# TABS
# ======================================================
tab_global, tab_city_overview, tab_city_rank, tab_city_brand = st.tabs([
    "📊 Global Ranking",
    "🏙️ City Performance Overview",
    "🏙️ City-level Ranking",
    "🏷️ City × Brand Model Ranking"
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
        .groupby(RES_CITY)[["checkin", "signup"]]
        .sum()
        .reset_index()
    )

    city_cur = (
        current_df
        .groupby(RES_CITY)[["checkin", "signup"]]
        .sum()
        .reset_index()
    )

    city = (
        city_last
        .merge(city_cur, on=RES_CITY, suffixes=("_last", "_current"))
        .fillna(0)
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

    st.dataframe(
        style_df(city),
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
