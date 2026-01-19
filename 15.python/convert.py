import streamlit as st
import pandas as pd
import numpy as np

# ======================
# Page config
# ======================
st.set_page_config(
    page_title="Hotel Signup Ranking Movement",
    layout="wide"
)

st.title("🏨 Hotel Signup Ranking – Weekly Movement")

st.markdown("""
This tool compares **hotel signup rankings** between two weeks to track:
- Rank movement (Up / Down / No change)
- Signup & CR (Conversion Rate) performance
- City-level competitive ranking
""")

# ======================
# Upload files
# ======================
col1, col2 = st.columns(2)

with col1:
    before_file = st.file_uploader(
        "⬆️ Upload LAST WEEK file (Before)",
        type=["csv"],
        key="before"
    )

with col2:
    after_file = st.file_uploader(
        "⬆️ Upload THIS WEEK file (After)",
        type=["csv"],
        key="after"
    )

# ======================
# Helper: normalize columns
# ======================
def normalize_df(df):
    column_map = {
        "Rank": "rank",
        "Hotel": "hotel_name",
        "Brand Model": "brand_model",
        "City": "city",
        "Signups": "signup_count",
        "Check-ins": "checkin_count"
    }

    df = df.rename(columns=column_map)

    required_cols = {
        "rank",
        "hotel_name",
        "brand_model",
        "city",
        "signup_count"
    }

    if not required_cols.issubset(df.columns):
        st.error(
            "❌ Missing required columns.\n\n"
            "Required columns:\n"
            "- Rank\n- Hotel\n- Brand Model\n- City\n- Signups"
        )
        st.stop()

    return df


# ======================
# Process files
# ======================
if before_file and after_file:

    before_df = normalize_df(pd.read_csv(before_file))
    after_df = normalize_df(pd.read_csv(after_file))

    # Rename columns
    before_df = before_df.rename(columns={
        "rank": "last_rank",
        "signup_count": "last_signup",
        "checkin_count": "last_checkin"
    })

    after_df = after_df.rename(columns={
        "rank": "current_rank",
        "signup_count": "current_signup",
        "checkin_count": "current_checkin"
    })

    # ======================
    # Merge data
    # ======================
    df = after_df.merge(
        before_df[
            [
                "hotel_name",
                "last_rank",
                "last_signup",
                "last_checkin"
            ]
        ],
        on="hotel_name",
        how="left"
    )

    # ======================
    # Rank movement
    # ======================
    df["rank_change"] = df["last_rank"] - df["current_rank"]

    def movement(row):
        if pd.isna(row["last_rank"]):
            return "🆕 New Entry"
        if row["rank_change"] > 0:
            return f"↑ Up {int(row['rank_change'])}"
        if row["rank_change"] < 0:
            return f"↓ Down {abs(int(row['rank_change']))}"
        return "→ No Change"

    df["movement"] = df.apply(movement, axis=1)

    # ======================
    # CR calculation (decimal)
    # ======================
    df["last_cr"] = np.where(
        df["last_checkin"] > 0,
        df["last_signup"] / df["last_checkin"],
        np.nan
    )

    df["current_cr"] = np.where(
        df["current_checkin"] > 0,
        df["current_signup"] / df["current_checkin"],
        np.nan
    )

    # ======================
    # CR format (%)
    # ======================
    df["last_cr_%"] = (df["last_cr"] * 100).round(1)
    df["current_cr_%"] = (df["current_cr"] * 100).round(1)

    # ======================
    # CR WoW change (%)
    # Formula: (current / last) - 1
    # ======================
    df["cr_change_%"] = np.where(
        df["last_cr_%"] > 0,
        ((df["current_cr_%"] / df["last_cr_%"]) - 1) * 100,
        np.nan
    ).round(1)

    # ======================
    # Weekly Ranking Comparison
    # ======================
    st.subheader("📊 Weekly Ranking Comparison")

    df = df.sort_values("current_rank")

    st.dataframe(
        df[
            [
                "hotel_name",
                "brand_model",
                "city",
                "last_rank",
                "current_rank",
                "movement",
                "last_signup",
                "current_signup",
                "last_cr_%",
                "current_cr_%",
                "cr_change_%"
            ]
        ],
        use_container_width=True
    )

    # ======================
    # City-level Ranking (1 table per city)
    # ======================
    st.subheader("🏙️ City-level Ranking (Current Week)")

    city_rank_df = (
        df
        .sort_values(["city", "current_rank"])
        .assign(city_rank=lambda x: x.groupby("city").cumcount() + 1)
    )

    for city, city_df in city_rank_df.groupby("city"):
        st.markdown(f"### 📍 {city}")

        st.dataframe(
            city_df[
                [
                    "city_rank",
                    "hotel_name",
                    "brand_model",
                    "current_rank",
                    "current_signup",
                    "current_cr_%"
                ]
            ],
            use_container_width=True
        )

    # ======================
    # Download
    # ======================
    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇️ Download Ranking Movement (CSV)",
        data=csv,
        file_name="hotel_ranking_movement.csv",
        mime="text/csv"
    )

else:
    st.info("⬆️ Please upload both LAST WEEK and THIS WEEK files to continue.")
