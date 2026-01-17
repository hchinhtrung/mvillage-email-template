import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Daily Recruit Funnel + WoW", layout="wide")
st.title("🏨 Daily Recruit Funnel Dashboard")

# ======================
# Upload files
# ======================
col1, col2 = st.columns(2)
with col1:
    res_file = st.file_uploader("Upload Reservation File", type=["csv", "xlsx"])
with col2:
    signup_file = st.file_uploader("Upload Signup File", type=["csv", "xlsx"])

def load_file(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

if not res_file or not signup_file:
    st.info("👆 Upload both files to start")
    st.stop()

res_df = load_file(res_file)
signup_df = load_file(signup_file)

st.success("✅ Files uploaded successfully")

# ======================
# COLUMN MAPPING (FIXED)
# ======================
RES_DATE = "Checkin"
RES_CITY = "City"
RES_STATUS = "Sign-up Status"

SIGNUP_DATE = "checkin"
SIGNUP_CITY = "city"
SIGNUP_COUNT_COL_INDEX = 4  # Column E (no header)

# ======================
# PARSE DATA
# ======================
res_df["date"] = pd.to_datetime(res_df[RES_DATE], errors="coerce").dt.date
signup_df["date"] = pd.to_datetime(signup_df[SIGNUP_DATE], errors="coerce").dt.date

signup_df["signup_count"] = pd.to_numeric(
    signup_df.iloc[:, SIGNUP_COUNT_COL_INDEX],
    errors="coerce"
).fillna(0)

# ======================
# DATE FILTER (DAILY VIEW)
# ======================
min_date = max(res_df["date"].min(), signup_df["date"].min())
max_date = min(res_df["date"].max(), signup_df["date"].max())

date_range = st.date_input(
    "Select Date Range (Daily View)",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

from_date, to_date = date_range

res_daily = res_df[(res_df["date"] >= from_date) & (res_df["date"] <= to_date)]
signup_daily = signup_df[(signup_df["date"] >= from_date) & (signup_df["date"] <= to_date)]

# ======================
# DAILY – RESERVATION METRICS
# ======================
res_pivot = (
    res_daily
    .groupby(["date", RES_CITY, RES_STATUS])
    .size()
    .reset_index(name="count")
)

chua_signup = res_pivot[
    res_pivot[RES_STATUS] == "Chưa Sign-up"
].pivot_table(
    index="date", columns=RES_CITY, values="count", aggfunc="sum"
).fillna(0)

member = res_pivot[
    res_pivot[RES_STATUS] == "Đã Sign-up từ trước"
].pivot_table(
    index="date", columns=RES_CITY, values="count", aggfunc="sum"
).fillna(0)

# ======================
# DAILY – NEW RECRUIT (SIGNUP FILE)
# ======================
new_recruit = (
    signup_daily
    .groupby(["date", SIGNUP_CITY])["signup_count"]
    .sum()
    .reset_index()
    .pivot(index="date", columns=SIGNUP_CITY, values="signup_count")
    .fillna(0)
)

total_new_recruit = new_recruit.sum(axis=1)

# ======================
# DAILY FINAL TABLE
# ======================
final_daily = pd.DataFrame(index=sorted(res_daily["date"].unique()))

for city in ["HCM", "HN", "DN"]:
    final_daily[f"{city}_Chua_Signup"] = chua_signup.get(city, 0)
    final_daily[f"{city}_Member"] = member.get(city, 0)
    final_daily[f"{city}_New_recruit"] = new_recruit.get(city, 0)

final_daily["Total new recruit"] = total_new_recruit
final_daily = final_daily.fillna(0).astype(int).reset_index()

# ======================
# DISPLAY DAILY
# ======================
st.subheader("📊 Daily Recruit Funnel")
st.dataframe(final_daily, use_container_width=True)

# ======================
# DOWNLOAD DAILY
# ======================
csv_daily = final_daily.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "⬇️ Download Daily Funnel CSV",
    csv_daily,
    "daily_recruit_funnel.csv",
    "text/csv"
)

# ======================================================
# ====================== WoW SECTION ===================
# ======================================================
st.divider()
st.subheader("📈 Week-over-Week New Recruit (Signup only)")

report_date = date.today()
weekday = report_date.weekday()  # Monday = 0

last_week_end = report_date - timedelta(days=weekday + 1)
last_week_start = last_week_end - timedelta(days=6)

prev_week_end = last_week_start - timedelta(days=1)
prev_week_start = prev_week_end - timedelta(days=6)

st.caption(
    f"Last week: {last_week_start} → {last_week_end} | "
    f"Previous week: {prev_week_start} → {prev_week_end}"
)

# ======================
# FILTER SIGNUP FOR WoW
# ======================
last_week_df = signup_df[
    (signup_df["date"] >= last_week_start) &
    (signup_df["date"] <= last_week_end)
]

prev_week_df = signup_df[
    (signup_df["date"] >= prev_week_start) &
    (signup_df["date"] <= prev_week_end)
]

# ======================
# AGGREGATE
# ======================
last_week_sum = last_week_df.groupby(SIGNUP_CITY)["signup_count"].sum()
prev_week_sum = prev_week_df.groupby(SIGNUP_CITY)["signup_count"].sum()

wow_df = pd.DataFrame({
    "Prev week": prev_week_sum,
    "Last week": last_week_sum
}).fillna(0)

wow_df["WoW %"] = (
    (wow_df["Last week"] - wow_df["Prev week"]) /
    wow_df["Prev week"].replace(0, pd.NA)
) * 100

wow_df["WoW %"] = wow_df["WoW %"].round(1)

# ======================
# TOTAL ROW
# ======================
total_prev = prev_week_df["signup_count"].sum()
total_last = last_week_df["signup_count"].sum()

total_wow = (
    (total_last - total_prev) / total_prev * 100
    if total_prev > 0 else None
)

wow_df.loc["Total"] = [
    total_prev,
    total_last,
    round(total_wow, 1) if total_wow is not None else None
]

# ======================
# DISPLAY WoW
# ======================
st.dataframe(
    wow_df.reset_index().rename(columns={"index": "City"}),
    use_container_width=True
)

# ======================
# DOWNLOAD WoW
# ======================
csv_wow = wow_df.reset_index().rename(columns={"index": "City"}) \
    .to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "⬇️ Download WoW CSV",
    csv_wow,
    "wow_new_recruit.csv",
    "text/csv"
)
