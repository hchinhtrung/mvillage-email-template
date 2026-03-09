import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import re

# ======================
# PAGE CONFIG
# ======================
st.set_page_config(
    page_title="Tool 3: Daily Recruit Funnel + WoW",
    layout="wide"
)
st.title("Tool 3: Daily Recruit Funnel Dashboard")

# ======================
# UPLOAD FILES
# ======================
c1, c2 = st.columns(2)
with c1:
    signup_file = st.file_uploader("📤 Upload Signup File", type=["csv", "xlsx"])
with c2:
    reservation_file = st.file_uploader("📤 Upload Reservation File", type=["csv", "xlsx"])

def load_file(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

if not signup_file or not reservation_file:
    st.info("👆 Upload both Signup & Reservation files to start")
    st.stop()

df = load_file(signup_file)
res_df = load_file(reservation_file)
st.success("✅ Files uploaded successfully")

# ======================
# COLUMN MAPPING - Signup
# ======================
DATE_COL = "checkin"
CITY_COL = "city"
STATUS_COL = "Sign up status v2"
COUNT_COL_INDEX = 4

# ======================
# COLUMN MAPPING - Reservation
# ======================
RES_HOTEL = "Hotel Name"
RES_CITY = "City"
RES_DATE = "Checkin"
RES_TENANT = "tenant_id"

CITY_ORDER = ["HCM", "HN", "DN"]

# ======================
# DATE NORMALIZATION - Signup
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
    st.error("❌ No valid daily check-in date found in Signup file")
    st.stop()

if invalid_rows > 0:
    st.warning(f"ℹ️ {invalid_rows} non-daily rows were removed from Signup file")

# ======================
# PREPROCESSING - Reservation
# ======================
res_df[RES_DATE] = pd.to_datetime(res_df[RES_DATE], errors="coerce")
res_df = res_df.dropna(subset=[RES_DATE])
res_df["date"] = res_df[RES_DATE].dt.date

# ======================
# SIGNUP COUNT
# ======================
df["signup_count"] = pd.to_numeric(
    df.iloc[:, COUNT_COL_INDEX],
    errors="coerce"
).fillna(0)

# ======================
# STATUS NORMALIZATION
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
# STATUS GROUPS
# ======================
STATUS_MAP = {
    "đã sign up từ trước": "MEMBER",
    "sign up sau c/i": "NEW_RECRUIT",
    "sign up trước 2 ngày check in": "NEW_RECRUIT",
    "sign up trước 1 ngày check in": "NEW_RECRUIT",
    "chưa sign up": "CHUA_SIGNUP",
}

def map_status(norm_val):
    for key, group in STATUS_MAP.items():
        if key in norm_val:
            return group
    return "OTHER"

daily_df = daily_df.copy()
daily_df["_status_group"] = daily_df["_status_norm"].apply(map_status)

def agg_status(group_name):
    mask = daily_df["_status_group"] == group_name
    return (
        daily_df[mask]
        .groupby(["date", CITY_COL])["signup_count"]
        .sum()
        .reset_index()
        .pivot(index="date", columns=CITY_COL, values="signup_count")
        .fillna(0)
    )

chua_signup = agg_status("CHUA_SIGNUP")
member = agg_status("MEMBER")
new_recruit = agg_status("NEW_RECRUIT")

# ======================
# RESERVATION: Daily checkin count per city (nunique tenant_id)
# ======================
res_filtered = res_df[
    (res_df["date"] >= from_date) &
    (res_df["date"] <= to_date)
]

daily_checkin = (
    res_filtered
    .groupby(["date", RES_CITY])[RES_TENANT]
    .nunique()
    .reset_index(name="checkin_count")
    .pivot(index="date", columns=RES_CITY, values="checkin_count")
    .fillna(0)
)

# ======================
# FINAL DAILY TABLE
# ======================
all_dates = sorted(daily_df["date"].unique())
final_daily = pd.DataFrame(index=all_dates)

for city in CITY_ORDER:
    final_daily[f"{city}_Chua_Signup"] = chua_signup.get(city, 0)
    final_daily[f"{city}_Member"] = member.get(city, 0)
    final_daily[f"{city}_New_recruit"] = new_recruit.get(city, 0)

    # CR per city = New recruit / checkin from reservation
    city_checkin = daily_checkin.get(city, pd.Series(0, index=all_dates))
    city_nr = final_daily[f"{city}_New_recruit"].fillna(0)
    city_ci = city_checkin.reindex(all_dates).fillna(0)

    final_daily[f"{city}_CR"] = np.where(
        city_ci > 0,
        (city_nr / city_ci * 100).round(2),
        0.0
    )

# Total new recruit = sum of all cities' new recruit
final_daily["Total_New_Recruit"] = (
    final_daily[[f"{c}_New_recruit" for c in CITY_ORDER]].sum(axis=1)
)

# Total checkin from reservation (all cities)
total_checkin = daily_checkin.reindex(all_dates).fillna(0).sum(axis=1)

# CR TOTAL = Total new recruit / total checkin
final_daily["CR_TOTAL"] = np.where(
    total_checkin > 0,
    (final_daily["Total_New_Recruit"] / total_checkin * 100).round(2),
    0.0
)

final_daily = final_daily.fillna(0).reset_index().rename(columns={"index": "Date"})

# Convert numeric columns to int (except CR columns)
int_cols = [c for c in final_daily.columns if c != "Date" and "_CR" not in c and "CR_" not in c]
for c in int_cols:
    final_daily[c] = final_daily[c].astype(int)

# ======================
# STYLING
# ======================
def _short_label(col):
    mapping = {
        "Date": "Số lượng khách check-in",
    }
    if col in mapping:
        return mapping[col]
    for city in CITY_ORDER:
        col = col.replace(f"{city}_", "")
    col = col.replace("Chua_Signup", "Chưa Sign-up")
    col = col.replace("New_recruit", "New recruit")
    col = col.replace("Total_New_Recruit", "Total new recruit")
    col = col.replace("CR_TOTAL", "CR TOTAL")
    col = col.replace("_CR", "")
    return col

def color_cr(val):
    """Color CR cells based on value."""
    try:
        val = float(val)
    except:
        return ""
    if val == 0:
        return ""
    if val >= 15:
        return "background-color: #27ae60; color: white;"
    elif val >= 10:
        return "background-color: #2ecc71;"
    elif val >= 5:
        return "background-color: #f9e79f;"
    else:
        return "background-color: #f5b7b1;"

def style_table(df):
    cr_cols = [c for c in df.columns if "_CR" in c or "CR_" in c]
    fmt = {}
    for c in df.columns:
        if "_CR" in c or "CR_" in c:
            fmt[c] = "{:.2f}%"
        elif c != "Date":
            fmt[c] = "{:.0f}"

    styler = df.style.format(fmt)
    if cr_cols:
        styler = styler.applymap(color_cr, subset=cr_cols)
    return styler

# ======================
# DISPLAY TABLE
# ======================
st.subheader("📊 Daily Recruit Funnel")

# Column config for headers
col_config = {}
for col in final_daily.columns:
    label = _short_label(col)
    col_config[col] = st.column_config.Column(label=label, help=col)

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

    styled = style_table(final_daily)
    st.dataframe(
        styled,
        use_container_width=True,
        height=table_height,
        hide_index=True,
        column_config=col_config
    )

else:
    chart_df = final_daily[
        [
            "Date",
            "HCM_New_recruit",
            "HN_New_recruit",
            "DN_New_recruit",
            "Total_New_Recruit"
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

df["_status_group"] = df["_status_norm"].apply(map_status)
nr_df = df[df["_status_group"] == "NEW_RECRUIT"]

last_week_df = nr_df[
    (nr_df["date"] >= last_week_start) &
    (nr_df["date"] <= last_week_end)
]
prev_week_df = nr_df[
    (nr_df["date"] >= prev_week_start) &
    (nr_df["date"] <= prev_week_end)
]

wow_df = pd.DataFrame({
    "Last week": prev_week_df.groupby(CITY_COL)["signup_count"].sum(),
    "This week": last_week_df.groupby(CITY_COL)["signup_count"].sum()
}).fillna(0)

wow_df["WoW %"] = (
    (wow_df["This week"] - wow_df["Last week"]) /
    wow_df["Last week"].replace(0, pd.NA)
* 100).round(2)

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
