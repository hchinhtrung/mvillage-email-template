import streamlit as st
import pandas as pd
from datetime import date, timedelta
import re

# ======================
# PAGE CONFIG
# ======================
st.set_page_config(
    page_title="Tool 3: Daily Recruit Funnel + WoW",
    layout="wide"
)
st.title("Tool 3: Daily Recruit Funnel Dashboard (Signup file only)")

# ======================
# UPLOAD FILE
# ======================
signup_file = st.file_uploader("Upload Signup File", type=["csv", "xlsx"])

def load_file(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

if not signup_file:
    st.info("👆 Upload signup file to start")
    st.stop()

df = load_file(signup_file)
st.success("✅ File uploaded successfully")

# ======================
# COLUMN MAPPING
# ======================
DATE_COL = "checkin"
CITY_COL = "city"
STATUS_COL = "Sign up status v2"
COUNT_COL_INDEX = 4

# ======================
# DATE NORMALIZATION
# ======================
DATE_REGEX = re.compile(r"^[A-Za-z]+ \d{1,2}, \d{4}$")

def normalize_checkin(val):
    if pd.isna(val):
        return None
    val = str(val).strip()
    if not DATE_REGEX.match(val):
        return None
    return pd.to_datetime(val).date()

df["date"] = df[DATE_COL].apply(normalize_checkin)

invalid_rows = df["date"].isna().sum()
df = df.dropna(subset=["date"])

if df.empty:
    st.error("❌ No valid daily check-in date found")
    st.stop()

if invalid_rows > 0:
    st.warning(f"ℹ️ {invalid_rows} non-daily rows were removed")

# ======================
# SIGNUP COUNT
# ======================
df["signup_count"] = pd.to_numeric(
    df.iloc[:, COUNT_COL_INDEX],
    errors="coerce"
).fillna(0)

# ======================
# STATUS NORMALIZATION (FIX MEMBER = 0)
# ======================
def normalize_status(val):
    if pd.isna(val):
        return ""
    val = str(val).strip().lower()
    val = re.sub(r"\s+", " ", val)
    val = val.replace("-", " ")
    return val

df["_status_norm"] = df[STATUS_COL].apply(normalize_status)

# ======================
# DATE FILTER (D-13 → D+3)
# ======================
min_date = df["date"].min()
max_date = df["date"].max()

today = date.today()
default_from = max(today - timedelta(days=13), min_date)
default_to = min(today + timedelta(days=3), max_date)

date_range = st.date_input(
    "Select Date Range (Daily View)",
    value=(default_from, default_to),
    min_value=min_date,
    max_value=max_date
)

from_date, to_date = date_range

daily_df = df[
    (df["date"] >= from_date) &
    (df["date"] <= to_date)
]

# ======================
# STATUS GROUPS (LOGIC GIỮ NGUYÊN)
# ======================
STATUS_CHUA_SIGNUP = ["chưa"]
STATUS_MEMBER = ["đã", "trước"]
STATUS_NEW_RECRUIT = ["sau", "trước 1", "trước 2"]

def agg_status(keyword_list):
    mask = daily_df["_status_norm"].apply(
        lambda x: any(k in x for k in keyword_list)
    )

    return (
        daily_df[mask]
        .groupby(["date", CITY_COL])["signup_count"]
        .sum()
        .reset_index()
        .pivot(index="date", columns=CITY_COL, values="signup_count")
        .fillna(0)
    )

chua_signup = agg_status(STATUS_CHUA_SIGNUP)
member = agg_status(STATUS_MEMBER)
new_recruit = agg_status(STATUS_NEW_RECRUIT)

# ======================
# FINAL DAILY TABLE
# ======================
final_daily = pd.DataFrame(index=sorted(daily_df["date"].unique()))

for city in ["HCM", "HN", "DN"]:
    final_daily[f"{city}_Chua_Signup"] = chua_signup.get(city, 0)
    final_daily[f"{city}_Member"] = member.get(city, 0)
    final_daily[f"{city}_New_recruit"] = new_recruit.get(city, 0)

final_daily["Total New Recruit"] = new_recruit.sum(axis=1)

final_daily = (
    final_daily.fillna(0)
    .astype(int)
    .reset_index()
    .rename(columns={"index": "Date"})
)

# ======================
# DAILY VIEW SWITCH
# ======================
st.subheader("📊 Daily Recruit Funnel")

view_mode = st.radio(
    "View mode",
    ["📋 Table", "📈 Chart"],
    horizontal=True,
    label_visibility="collapsed"
)

if view_mode == "📋 Table":
    ROW_HEIGHT = 35
    MAX_ROWS = 30
    table_height = ROW_HEIGHT * (min(len(final_daily), MAX_ROWS) + 1)

    st.dataframe(
        final_daily,
        use_container_width=True,
        height=table_height
    )

else:
    chart_df = final_daily[
        [
            "Date",
            "HCM_New_recruit",
            "HN_New_recruit",
            "DN_New_recruit",
            "Total New Recruit"
        ]
    ].set_index("Date")

    st.line_chart(chart_df, height=420)

st.download_button(
    "⬇️ Download Daily Funnel CSV",
    final_daily.to_csv(index=False).encode("utf-8-sig"),
    "daily_recruit_funnel.csv",
    "text/csv"
)

# ======================
# STATUS DEBUG (OPTIONAL)
# ======================
with st.expander("🔍 Status Debug"):
    st.write(
        df["_status_norm"]
        .value_counts()
        .reset_index()
        .rename(columns={"index": "Status (normalized)", "_status_norm": "Count"})
    )

# ======================================================
# ====================== WoW SECTION ===================
# ======================================================
st.divider()
st.subheader("📈 Week-over-Week New Recruit")

report_date = date.today()
weekday = report_date.weekday()

last_week_end = report_date - timedelta(days=weekday + 1)
last_week_start = last_week_end - timedelta(days=6)

prev_week_end = last_week_start - timedelta(days=1)
prev_week_start = prev_week_end - timedelta(days=6)

nr_df = df[df["_status_norm"].apply(
    lambda x: any(k in x for k in STATUS_NEW_RECRUIT)
)]

last_week_df = nr_df[
    (nr_df["date"] >= last_week_start) &
    (nr_df["date"] <= last_week_end)
]

prev_week_df = nr_df[
    (nr_df["date"] >= prev_week_start) &
    (nr_df["date"] <= prev_week_end)
]

wow_df = pd.DataFrame({
    "Prev week": prev_week_df.groupby(CITY_COL)["signup_count"].sum(),
    "This week": last_week_df.groupby(CITY_COL)["signup_count"].sum()
}).fillna(0)

wow_df["WoW %"] = (
    (wow_df["This week"] - wow_df["Prev week"]) /
    wow_df["Prev week"].replace(0, pd.NA)
) * 100

wow_df["WoW %"] = wow_df["WoW %"].round(2)

total_prev = prev_week_df["signup_count"].sum()
total_last = last_week_df["signup_count"].sum()

wow_df.loc["Total"] = [
    total_prev,
    total_last,
    round((total_last - total_prev) / total_prev * 100, 2)
    if total_prev > 0 else None
]

st.dataframe(
    wow_df.reset_index().rename(columns={"index": "City"}),
    use_container_width=True
)

st.download_button(
    "⬇️ Download WoW CSV",
    wow_df.reset_index()
    .rename(columns={"index": "City"})
    .to_csv(index=False)
    .encode("utf-8-sig"),
    "wow_new_recruit.csv",
    "text/csv"
)
