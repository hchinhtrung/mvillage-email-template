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
DATE_COL = "checkin"          # col C
CITY_COL = "city"
STATUS_COL = "Sign up status v2"
COUNT_COL_INDEX = 4           # Column E

# ======================
# DATE NORMALIZATION (CHECKIN ONLY)
# ======================
DATE_REGEX = re.compile(r"^[A-Za-z]+ \d{1,2}, \d{4}$")

def normalize_checkin(val):
    if pd.isna(val):
        return None

    val = str(val).strip()

    # Only accept daily dates like "May 19, 2025"
    if not DATE_REGEX.match(val):
        return None

    return pd.to_datetime(val).date()

df["date"] = df[DATE_COL].apply(normalize_checkin)

invalid_rows = df["date"].isna().sum()
df = df.dropna(subset=["date"])

if df.empty:
    st.error("❌ No valid daily check-in date found in column 'checkin'")
    st.stop()

if invalid_rows > 0:
    st.warning(
        f"ℹ️ {invalid_rows} non-daily rows in 'checkin' column "
        "were removed (pivot headers / totals)"
    )

# ======================
# SIGNUP COUNT
# ======================
df["signup_count"] = pd.to_numeric(
    df.iloc[:, COUNT_COL_INDEX],
    errors="coerce"
).fillna(0)

# ======================
# DATE FILTER
# ======================
min_date = df["date"].min()
max_date = df["date"].max()

date_range = st.date_input(
    "Select Date Range (Daily View)",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

from_date, to_date = date_range

daily_df = df[
    (df["date"] >= from_date) &
    (df["date"] <= to_date)
]

# ======================
# STATUS GROUPS
# ======================
STATUS_CHUA_SIGNUP = ["Chưa Sign-up"]
STATUS_MEMBER = ["Đã Sign-up từ trước"]
STATUS_NEW_RECRUIT = [
    "Sign-up sau C/I",
    "Sign up trước 1 ngày check in",
    "Sign up trước 2 ngày check in"
]

# ======================
# DAILY AGGREGATION
# ======================
def agg_status(status_list):
    return (
        daily_df[daily_df[STATUS_COL].isin(status_list)]
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
# DISPLAY DAILY
# ======================
st.subheader("📊 Daily Recruit Funnel")
st.dataframe(final_daily, use_container_width=True)

st.download_button(
    "⬇️ Download Daily Funnel CSV",
    final_daily.to_csv(index=False).encode("utf-8-sig"),
    "daily_recruit_funnel.csv",
    "text/csv"
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

nr_df = df[df[STATUS_COL].isin(STATUS_NEW_RECRUIT)]

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
    "Last week": last_week_df.groupby(CITY_COL)["signup_count"].sum()
}).fillna(0)

wow_df["WoW %"] = (
    (wow_df["Last week"] - wow_df["Prev week"]) /
    wow_df["Prev week"].replace(0, pd.NA)
) * 100

wow_df["WoW %"] = wow_df["WoW %"].round(2)

# TOTAL
total_prev = prev_week_df["signup_count"].sum()
total_last = last_week_df["signup_count"].sum()

wow_df.loc["Total"] = [
    total_prev,
    total_last,
    round((total_last - total_prev) / total_prev * 100, 2)
    if total_prev > 0 else None
]

# DISPLAY WoW
st.dataframe(
    wow_df.reset_index().rename(columns={"index": "City"}),
    use_container_width=True
)

st.download_button(
    "⬇️ Download WoW CSV",
    wow_df.reset_index().rename(columns={"index": "City"})
    .to_csv(index=False).encode("utf-8-sig"),
    "wow_new_recruit.csv",
    "text/csv"
)
