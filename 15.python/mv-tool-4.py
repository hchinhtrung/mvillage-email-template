import streamlit as st
import pandas as pd
import altair as alt

# =====================================================
# Page config
# =====================================================
st.set_page_config(
    page_title="Executive BI – Weekly Signup Performance",
    layout="wide"
)

st.title("📊 Executive BI – Weekly Signup Performance")

# =====================================================
# Helpers
# =====================================================
def load_file(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)


def preprocess_signup(df):
    HOTEL_COL = "hotel_short_name"
    CITY_COL = "city"
    DATE_COL = df.columns[4]
    COUNT_COL = df.columns[5]

    df = df.copy()

    df["hotel_display"] = df[HOTEL_COL].astype(str).str.strip()
    df["hotel_normalized"] = df["hotel_display"].str.lower()
    df[CITY_COL] = df[CITY_COL].astype(str).str.strip()

    if "brand_model" not in df.columns:
        df["brand_model"] = "All"

    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df[COUNT_COL] = pd.to_numeric(df[COUNT_COL], errors="coerce").fillna(0)

    df = df.dropna(subset=[DATE_COL])

    df["week"] = (
        df[DATE_COL]
        .dt.to_period("W-MON")
        .apply(lambda r: r.start_time)
    )

    return df, CITY_COL, COUNT_COL


def build_weekly(df, city_col, count_col):
    weekly = (
        df
        .groupby(
            ["week", "hotel_display", city_col, "brand_model"]
        )[count_col]
        .sum()
        .reset_index(name="signup_count")
    )

    weekly["Rank"] = (
        weekly
        .groupby("week")["signup_count"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    return weekly


def wow_metrics(weekly):
    weekly = weekly.sort_values(["hotel_display", "week"])
    weekly["signup_wow"] = weekly.groupby("hotel_display")["signup_count"].pct_change() * 100
    weekly["rank_wow"] = weekly.groupby("hotel_display")["Rank"].diff() * -1
    return weekly


# =====================================================
# Upload
# =====================================================
signup_file = st.file_uploader("📤 Upload Signup File", type=["csv", "xlsx"])
if not signup_file:
    st.info("👆 Upload Signup file to start")
    st.stop()

df = load_file(signup_file)
df, CITY_COL, COUNT_COL = preprocess_signup(df)

# =====================================================
# Date range
# =====================================================
min_w, max_w = df["week"].min().date(), df["week"].max().date()

from_date, to_date = st.date_input(
    "📅 Select Week Range",
    value=(min_w, max_w),
    min_value=min_w,
    max_value=max_w
)

df = df[
    (df["week"].dt.date >= from_date) &
    (df["week"].dt.date <= to_date)
]

weekly = build_weekly(df, CITY_COL, COUNT_COL)
weekly = wow_metrics(weekly)

latest_week = weekly["week"].max()
prev_week = latest_week - pd.Timedelta(days=7)

latest_df = weekly[weekly["week"] == latest_week]
prev_df = weekly[weekly["week"] == prev_week]

# =====================================================
# 1️⃣ EXECUTIVE SCORECARDS
# =====================================================
st.divider()
st.subheader("🧭 Executive Overview")

c1, c2, c3, c4, c5 = st.columns(5)

total_signup = latest_df["signup_count"].sum()
prev_signup = prev_df["signup_count"].sum()

wow_total = ((total_signup - prev_signup) / prev_signup * 100) if prev_signup > 0 else 0

c1.metric("Total Signups (This Week)", f"{int(total_signup):,}", f"{wow_total:.1f}% WoW")
c2.metric("Active Hotels", latest_df["hotel_display"].nunique())
c3.metric("Active Cities", latest_df[CITY_COL].nunique())
c4.metric("Top City", latest_df.groupby(CITY_COL)["signup_count"].sum().idxmax())
c5.metric(
    "% Hotels Improving",
    f"{(latest_df['rank_wow'].gt(0).mean()*100):.0f}%"
)

# =====================================================
# 2️⃣ MACRO TREND
# =====================================================
st.divider()
st.subheader("📈 Weekly Signup Trend")

weekly_total = weekly.groupby("week")["signup_count"].sum().reset_index()

trend_chart = (
    alt.Chart(weekly_total)
    .mark_line(point=True)
    .encode(
        x="week:T",
        y="signup_count:Q",
        tooltip=["week:T", "signup_count:Q"]
    )
    .properties(height=300)
)

st.altair_chart(trend_chart, use_container_width=True)

# =====================================================
# 3️⃣ CITY PERFORMANCE HEATMAP
# =====================================================
st.divider()
st.subheader("🏙️ City Performance Heatmap")

city_week = (
    weekly
    .groupby(["week", CITY_COL])["signup_count"]
    .sum()
    .reset_index()
)

heatmap = (
    alt.Chart(city_week)
    .mark_rect()
    .encode(
        x="week:T",
        y=f"{CITY_COL}:N",
        color=alt.Color("signup_count:Q", scale=alt.Scale(scheme="greenblue")),
        tooltip=["week:T", CITY_COL, "signup_count:Q"]
    )
    .properties(height=350)
)

st.altair_chart(heatmap, use_container_width=True)

# =====================================================
# 4️⃣ TOP / BOTTOM MOVERS
# =====================================================
st.divider()
st.subheader("🚀 Top / Bottom Movers (WoW)")

m1, m2 = st.columns(2)

with m1:
    st.markdown("**⬆️ Top 5 Rank Gainers**")
    st.dataframe(
        latest_df.sort_values("rank_wow", ascending=False)
        [["hotel_display", CITY_COL, "rank_wow", "signup_count"]]
        .head(5),
        hide_index=True
    )

with m2:
    st.markdown("**⬇️ Top 5 Rank Losers**")
    st.dataframe(
        latest_df.sort_values("rank_wow")
        [["hotel_display", CITY_COL, "rank_wow", "signup_count"]]
        .head(5),
        hide_index=True
    )

# =====================================================
# 5️⃣ DEEP DIVE – RANK TREND
# =====================================================
st.divider()
st.subheader("🔍 Hotel Ranking Trend")

f1, f2 = st.columns(2)

with f1:
    city_filter = st.multiselect(
        "City",
        options=sorted(weekly[CITY_COL].unique()),
        default=sorted(weekly[CITY_COL].unique())
    )

with f2:
    hotel_filter = st.multiselect(
        "Hotels",
        options=sorted(
            weekly[weekly[CITY_COL].isin(city_filter)]["hotel_display"].unique()
        ),
        default=sorted(
            weekly[weekly[CITY_COL].isin(city_filter)]["hotel_display"].unique()
        )[:5]
    )

chart_df = weekly[
    (weekly[CITY_COL].isin(city_filter)) &
    (weekly["hotel_display"].isin(hotel_filter))
]

rank_chart = (
    alt.Chart(chart_df)
    .mark_line(point=True)
    .encode(
        x="week:T",
        y=alt.Y("Rank:Q", scale=alt.Scale(reverse=True)),
        color="hotel_display:N",
        tooltip=["hotel_display", "week:T", "Rank:Q", "signup_count:Q"]
    )
    .properties(height=450)
)

st.altair_chart(rank_chart, use_container_width=True)

# =====================================================
# 6️⃣ DETAIL TABLE
# =====================================================
with st.expander("📋 Detailed Weekly Table"):
    st.dataframe(
        weekly.sort_values(["week", "Rank"]),
        use_container_width=True,
        hide_index=True
    )
