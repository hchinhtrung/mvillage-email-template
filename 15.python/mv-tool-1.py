import streamlit as st
import pandas as pd

st.set_page_config(page_title="Tool 1: Recruit Signup & CR Analyzer", layout="wide")
st.title("Tool 1: Recruit Signup & CR Analyzer")

# ======================
# Upload files
# ======================
c1, c2 = st.columns(2)
with c1:
    signup_file = st.file_uploader("📤 Upload Signup File", type=["csv", "xlsx"])
with c2:
    res_file = st.file_uploader("📤 Upload Reservation File", type=["csv", "xlsx"])


def load_file(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)


# ======================
# MAIN
# ======================
if signup_file and res_file:
    signup_df = load_file(signup_file)
    res_df = load_file(res_file)

    st.success("✅ Files uploaded successfully!")

    # ======================
    # COLUMN DEFINITIONS (EXPLICIT)
    # ======================
    SIGNUP_CITY = "city"
    SIGNUP_HOTEL = "hotel_short_name"
    SIGNUP_DATE = "checkin"
    SIGNUP_COUNT = "Unnamed: 5"

    RES_CITY = "City"
    RES_HOTEL = "Hotel Name"
    RES_DATE = "Checkin"
    RES_TENANT = "tenant_id"
    RES_BRAND_MODEL = "Brand Model"

    # ======================
    # Normalize text
    # ======================
    def norm(s):
        return (
            s.astype(str)
             .str.strip()
             .str.upper()
        )

    signup_df["hotel_normalized"] = norm(signup_df[SIGNUP_HOTEL])
    res_df["hotel_normalized"] = norm(res_df[RES_HOTEL])

    signup_df[SIGNUP_CITY] = norm(signup_df[SIGNUP_CITY])
    res_df[RES_CITY] = norm(res_df[RES_CITY])

    # ======================
    # Date parsing
    # ======================
    signup_df[SIGNUP_DATE] = pd.to_datetime(signup_df[SIGNUP_DATE], errors="coerce")
    res_df[RES_DATE] = pd.to_datetime(res_df[RES_DATE], errors="coerce")

    signup_df = signup_df.dropna(subset=[SIGNUP_DATE])
    res_df = res_df.dropna(subset=[RES_DATE])

    signup_df[SIGNUP_COUNT] = pd.to_numeric(
        signup_df[SIGNUP_COUNT], errors="coerce"
    ).fillna(0)

    # ======================
    # Date range (CHECK-IN BASED)
    # ======================
    min_date = min(signup_df[SIGNUP_DATE].min(), res_df[RES_DATE].min()).date()
    max_date = max(signup_df[SIGNUP_DATE].max(), res_df[RES_DATE].max()).date()

    from_date, to_date = st.date_input(
        "📅 Select Check-in Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    signup_f = signup_df[
        (signup_df[SIGNUP_DATE].dt.date >= from_date) &
        (signup_df[SIGNUP_DATE].dt.date <= to_date)
    ]

    res_f = res_df[
        (res_df[RES_DATE].dt.date >= from_date) &
        (res_df[RES_DATE].dt.date <= to_date)
    ]

    # ======================
    # CHECK-IN METRIC
    # ======================
    checkin_df = (
        res_f
        .groupby(["hotel_normalized", RES_CITY, RES_BRAND_MODEL])[RES_TENANT]
        .nunique()
        .reset_index(name="checkin_count")
    )

    hotel_name_map = (
        res_f.groupby("hotel_normalized")[RES_HOTEL]
        .first()
        .to_dict()
    )
    checkin_df["hotel_display"] = checkin_df["hotel_normalized"].map(hotel_name_map)

    # ======================
    # SIGNUP METRIC
    # ======================
    recruit_df = (
        signup_f
        .groupby(["hotel_normalized", SIGNUP_CITY])[SIGNUP_COUNT]
        .sum()
        .reset_index(name="recruit_count")
    )

    # ======================
    # MERGE (CORRECT KEY)
    # ======================
    final_df = checkin_df.merge(
        recruit_df,
        left_on=["hotel_normalized", RES_CITY],
        right_on=["hotel_normalized", SIGNUP_CITY],
        how="left"
    )

    final_df["recruit_count"] = final_df["recruit_count"].fillna(0).astype(int)

    final_df["CR_percent"] = (
        final_df["recruit_count"]
        .where(final_df["checkin_count"] > 0, 0)
        / final_df["checkin_count"]
        * 100
    ).round(2)

    # ======================
    # OVERALL SUMMARY
    # ======================
    st.divider()
    st.subheader("📊 Overall Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique Guests", f"{final_df.checkin_count.sum():,}")
    c2.metric("Total Signups", f"{final_df.recruit_count.sum():,}")
    c3.metric(
        "Overall CR",
        f"{(final_df.recruit_count.sum()/final_df.checkin_count.sum()*100):.2f}%"
    )
    c4.metric("Hotels", final_df.hotel_normalized.nunique())

    # ======================
    # RANKING
    # ======================
    st.divider()
    st.subheader("🏆 Hotel Ranking (Overall)")

    overall = (
        final_df
        .groupby(["hotel_display", RES_BRAND_MODEL, RES_CITY])
        .agg({"checkin_count": "sum", "recruit_count": "sum"})
        .reset_index()
    )

    overall["CR_percent"] = (
        overall.recruit_count / overall.checkin_count * 100
    ).round(2)

    overall = overall.sort_values("CR_percent", ascending=False).reset_index(drop=True)
    overall["Rank"] = range(1, len(overall) + 1)

    st.dataframe(
        overall.rename(columns={
            "hotel_display": "Hotel",
            RES_BRAND_MODEL: "Brand Model",
            RES_CITY: "City",
            "checkin_count": "Check-ins",
            "recruit_count": "Signups",
            "CR_percent": "CR %"
        })[["Rank", "Hotel", "Brand Model", "City", "Check-ins", "Signups", "CR %"]],
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("👆 Upload both Signup & Reservation files to start analysis")
