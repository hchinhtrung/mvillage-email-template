import streamlit as st
import pandas as pd

st.set_page_config(page_title="Daily Recruit Funnel", layout="wide")
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
    st.stop()

res_df = load_file(res_file)
signup_df = load_file(signup_file)

st.success("✅ Files uploaded successfully")

# ======================
# Parse dates
# ======================
res_df["date"] = pd.to_datetime(res_df["Checkin"], errors="coerce").dt.date
signup_df["date"] = pd.to_datetime(signup_df["checkin"], errors="coerce").dt.date

# Column E (index 4) = signup count
signup_df["signup_count"] = pd.to_numeric(
    signup_df.iloc[:, 4], errors="coerce"
).fillna(0)

# ======================
# DATE FILTER
# ======================
min_date = max(res_df["date"].min(), signup_df["date"].min())
max_date = min(res_df["date"].max(), signup_df["date"].max())

date_range = st.date_input(
    "Select Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

from_date, to_date = date_range

res_df = res_df[(res_df["date"] >= from_date) & (res_df["date"] <= to_date)]
signup_df = signup_df[(signup_df["date"] >= from_date) & (signup_df["date"] <= to_date)]

# ======================
# RESERVATION METRICS
# ======================
res_pivot = (
    res_df
    .groupby(["date", "City", "Sign-up Status"])
    .size()
    .reset_index(name="count")
)

chua_signup = res_pivot[
    res_pivot["Sign-up Status"] == "Chưa Sign-up"
].pivot_table(
    index="date", columns="City", values="count", aggfunc="sum"
).fillna(0)

member = res_pivot[
    res_pivot["Sign-up Status"] == "Đã Sign-up từ trước"
].pivot_table(
    index="date", columns="City", values="count", aggfunc="sum"
).fillna(0)

# ======================
# SIGNUP (NEW RECRUIT)
# ======================
new_recruit = (
    signup_df
    .groupby(["date", "city"])["signup_count"]
    .sum()
    .reset_index()
    .pivot(index="date", columns="city", values="signup_count")
    .fillna(0)
)

total_new_recruit = new_recruit.sum(axis=1)

# ======================
# FINAL TABLE
# ======================
final = pd.DataFrame(index=sorted(res_df["date"].unique()))

for city in ["HCM", "HN", "DN"]:
    final[f"{city}_Chua_Signup"] = chua_signup.get(city, 0)
    final[f"{city}_Member"] = member.get(city, 0)
    final[f"{city}_New_recruit"] = new_recruit.get(city, 0)

final["Total new recruit"] = total_new_recruit
final = final.fillna(0).astype(int).reset_index()

# ======================
# DISPLAY
# ======================
st.subheader("📊 Daily Recruit Funnel Table")
st.dataframe(final, use_container_width=True)

# ======================
# DOWNLOAD
# ======================
csv = final.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "⬇️ Download CSV",
    csv,
    "daily_recruit_funnel.csv",
    "text/csv"
)
