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

# ======================
# Preprocessing
# ======================
signup_df["hotel_key"] = signup_df[SIGNUP_HOTEL].str.lower().str.strip()
res_df["hotel_key"] = res_df[RES_HOTEL].str.lower().str.strip()

signup_df[SIGNUP_DATE] = pd.to_datetime(signup_df[SIGNUP_DATE], errors="coerce")
res_df[RES_DATE] = pd.to_datetime(res_df[RES_DATE], errors="coerce")

signup_df[SIGNUP_COUNT] = pd.to_numeric(signup_df[SIGNUP_COUNT], errors="coerce").fillna(0)

signup_df = signup_df.dropna(subset=[SIGNUP_DATE])
res_df = res_df.dropna(subset=[RES_DATE])

# ======================
# Date selector
# ======================
st.subheader("📅 Compare Time Ranges")

min_date = min(signup_df[SIGNUP_DATE].min(), res_df[RES_DATE].min()).date()
max_date = max(signup_df[SIGNUP_DATE].max(), res_df[RES_DATE].max()).date()

c1, c2 = st.columns(2)
with c1:
    last_from, last_to = st.date_input("Last Period", value=(min_date, min_date))
with c2:
    current_from, current_to = st.date_input("Current Period", value=(max_date, max_date))

def filter_period(df, col, start, end):
    return df[(df[col].dt.date >= start) & (df[col].dt.date <= end)]

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
# Ranking functions
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

    df["checkin_change_%"] = np.where(
        df["checkin_last"] == 0, 0,
        (df["checkin_current"] / df["checkin_last"]) - 1
    )

    df["signup_change_%"] = np.where(
        df["signup_last"] == 0, 0,
        (df["signup_current"] / df["signup_last"]) - 1
    )

    df["cr_change_%"] = np.where(
        df["cr_last"] == 0, 0,
        (df["cr_current"] / df["cr_last"]) - 1
    )

    return df

# ======================
# Column ordering
# ======================
def reorder_columns(df):
    df = df.copy()

    # ======================
    # FORMAT hotel_key
    # ======================
    if "hotel_key" in df.columns:
        df["hotel_key"] = df["hotel_key"].str.upper()

    cols = [
        # Dimensions
        "hotel_key", RES_CITY, BRAND_MODEL,

        # Rank
        "rank_last", "rank_current", "rank_change",

        # Checkin
        "checkin_last", "checkin_current", "checkin_change_%",

        # Signup
        "signup_last", "signup_current", "signup_change_%",

        # CR
        "cr_last", "cr_current", "cr_change_%"
    ]

    return df[[c for c in cols if c in df.columns]]

# ======================
# Styling helpers
# ======================
def color_change(val):
    try:
        val = float(val)
    except:
        return ""

    if val <= -0.3:
        return "background-color:#e74c3c;color:white;"
    elif val <= -0.05:
        return "background-color:#f39c12;color:black;"
    elif val < 0.05:
        return "background-color:#ffffff;color:black;"
    elif val < 0.3:
        return "background-color:#2ecc71;color:black;"
    else:
        return "background-color:#27ae60;color:white;"

def style_df(df):
    styler = df.style
    header_styles = []

    def header_style(cols, bg, text):
        for c in cols:
            if c in df.columns:
                idx = df.columns.get_loc(c)
                header_styles.append({
                    "selector": f"th.col_heading.col{idx}",
                    "props": [
                        ("background-color", bg),
                        ("color", text),
                        ("font-weight", "700"),
                        ("text-align", "center"),
                        ("border-bottom", "2px solid #333"),
                    ],
                })

    header_style(["rank_last","rank_current","rank_change"], "#e8f0fe", "#1a237e")
    header_style(["checkin_last","checkin_current","checkin_change_%"], "#f3e8ff", "#4a148c")
    header_style(["signup_last","signup_current","signup_change_%"], "#fff3e0", "#e65100")
    header_style(["cr_last","cr_current","cr_change_%"], "#e8f5e9", "#1b5e20")

    styler = styler.set_table_styles(header_styles, overwrite=False)

    styler = styler.format({
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

    styler = styler.applymap(color_change, subset=["cr_change_%"])
    return styler

# ======================================================
# SECTION 1 – Global Ranking
# ======================================================
st.divider()
st.subheader("📊 Weekly Ranking Comparison (Global)")

global_df = reorder_columns(
    build_compare(
        add_global_rank(last_df),
        add_global_rank(current_df)
    ).sort_values("rank_current")
)

st.dataframe(style_df(global_df), use_container_width=True, hide_index=True)





def build_city_overview(last_df, current_df):
    last_city = (
        last_df
        .groupby(RES_CITY)
        .agg(
            checkin_last=("checkin", "sum"),
            signup_last=("signup", "sum")
        )
        .reset_index()
    )

    last_city["cr_last"] = np.where(
        last_city["checkin_last"] == 0,
        0,
        (last_city["signup_last"] / last_city["checkin_last"] * 100).round(2)
    )

    current_city = (
        current_df
        .groupby(RES_CITY)
        .agg(
            checkin_current=("checkin", "sum"),
            signup_current=("signup", "sum")
        )
        .reset_index()
    )

    current_city["cr_current"] = np.where(
        current_city["checkin_current"] == 0,
        0,
        (current_city["signup_current"] / current_city["checkin_current"] * 100).round(2)
    )

    df = last_city.merge(current_city, on=RES_CITY, how="outer").fillna(0)

    df["checkin_change_%"] = np.where(
        df["checkin_last"] == 0, 0,
        (df["checkin_current"] / df["checkin_last"]) - 1
    )

    df["signup_change_%"] = np.where(
        df["signup_last"] == 0, 0,
        (df["signup_current"] / df["signup_last"]) - 1
    )

    df["cr_change_%"] = np.where(
        df["cr_last"] == 0, 0,
        (df["cr_current"] / df["cr_last"]) - 1
    )

    return df



# ======================================================
# SECTION – City Performance Overview
# ======================================================
st.divider()
st.subheader("🏙️ City Performance Overview (Last vs Current)")

city_overview_df = build_city_overview(last_df, current_df)

city_overview_df = city_overview_df[[
    RES_CITY,

    # Checkin
    "checkin_last", "checkin_current", "checkin_change_%",

    # Signup
    "signup_last", "signup_current", "signup_change_%",

    # CR
    "cr_last", "cr_current", "cr_change_%"
]].sort_values("cr_current", ascending=False)

st.dataframe(
    style_df(city_overview_df),
    use_container_width=True,
    hide_index=True
)


# ======================================================
# SECTION 2 – City-level Ranking
# ======================================================
st.divider()
st.subheader("🏙️ City-level Ranking (Current Week)")

city_df = build_compare(
    add_city_rank(last_df),
    add_city_rank(current_df)
)

for city, df in city_df.groupby(RES_CITY):
    st.markdown(f"### 📍 {city}")
    st.dataframe(
        style_df(reorder_columns(df.sort_values("rank_current"))),
        use_container_width=True,
        hide_index=True
    )

# ======================================================
# SECTION 3 – City-level Ranking by Brand Model
# ======================================================
st.divider()
st.subheader("🏙️ City-level Ranking by Brand Model (Current Week)")

cb_df = build_compare(
    add_city_brand_rank(last_df),
    add_city_brand_rank(current_df)
)

for city, city_df in cb_df.groupby(RES_CITY):
    st.markdown(f"## 📍 {city}")
    for bm, bm_df in city_df.groupby(BRAND_MODEL):
        st.markdown(f"### 🏷️ Brand Model: {bm}")
        st.dataframe(
            style_df(reorder_columns(bm_df.sort_values("rank_current"))),
            use_container_width=True,
            hide_index=True
        )



