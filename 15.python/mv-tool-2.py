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
SIGNUP_DATE = signup_df.columns[4]   # checkin (TEXT: "Jan 7, 2026")
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

# ---------- FIX SIGNUP CHECKIN DATE ----------
signup_df[SIGNUP_DATE] = (
    signup_df[SIGNUP_DATE]
    .astype(str)
    .str.strip()
)

# Try strict format first: "Jan 7, 2026"
signup_df[SIGNUP_DATE] = pd.to_datetime(
    signup_df[SIGNUP_DATE],
    format="%b %d, %Y",
    errors="coerce"
)

# Fallback parse (other formats if exist)
mask = signup_df[SIGNUP_DATE].isna()
if mask.any():
    signup_df.loc[mask, SIGNUP_DATE] = pd.to_datetime(
        signup_df.loc[mask, SIGNUP_DATE],
        errors="coerce"
    )

invalid_dates = signup_df[SIGNUP_DATE].isna().sum()
if invalid_dates > 0:
    st.warning(f"⚠️ {invalid_dates} signup rows have invalid checkin date format")

signup_df = signup_df.dropna(subset=[SIGNUP_DATE])

# ---------- RESERVATION DATE ----------
res_df[RES_DATE] = pd.to_datetime(res_df[RES_DATE], errors="coerce")
res_df = res_df.dropna(subset=[RES_DATE])

# ---------- NUMERIC ----------
signup_df[SIGNUP_COUNT] = (
    pd.to_numeric(signup_df[SIGNUP_COUNT], errors="coerce")
    .fillna(0)
)

# ======================
# Date selector
# ======================
st.subheader("📅 Compare Time Ranges")

min_date = min(
    signup_df[SIGNUP_DATE].min(),
    res_df[RES_DATE].min()
).date()

max_date = max(
    signup_df[SIGNUP_DATE].max(),
    res_df[RES_DATE].max()
).date()

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
        df["checkin"] == 0,
        0,
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
    df["rank"] = df.groupby(RES_CITY)["cr"].rank(
        ascending=False, method="dense"
    )
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
# Global Ranking
# ======================
st.divider()
st.subheader("📊 Weekly Ranking Comparison (Global)")

global_df = (
    build_compare(
        add_global_rank(last_df),
        add_global_rank(current_df)
    )
    .sort_values("rank_current")
)

st.dataframe(global_df, use_container_width=True, hide_index=True)
