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

# ======================
# Upload files
# ======================
col1, col2 = st.columns(2)

with col1:
    before_file = st.file_uploader("⬆️ Upload LAST WEEK file", type=["csv"])
with col2:
    after_file = st.file_uploader("⬆️ Upload THIS WEEK file", type=["csv"])


# ======================
# Normalize columns
# ======================
def normalize_df(df):
    return df.rename(columns={
        "Rank": "rank",
        "Hotel": "hotel_name",
        "Brand Model": "brand_model",
        "City": "city",
        "Signups": "signup_count",
        "Check-ins": "checkin_count"
    })


if before_file and after_file:

    before = normalize_df(pd.read_csv(before_file))
    after = normalize_df(pd.read_csv(after_file))

    before = before.rename(columns={
        "signup_count": "last_signup",
        "checkin_count": "last_checkin"
    })

    after = after.rename(columns={
        "signup_count": "current_signup",
        "checkin_count": "current_checkin"
    })

    # ======================
    # Merge
    # ======================
    df = after.merge(
        before[["hotel_name", "last_signup", "last_checkin"]],
        on="hotel_name",
        how="left"
    )

    # ======================
    # CR calculation (%)
    # ======================
    df["last_cr_%"] = np.where(
        df["last_checkin"] > 0,
        (df["last_signup"] / df["last_checkin"]) * 100,
        np.nan
    ).round(2)

    df["current_cr_%"] = np.where(
        df["current_checkin"] > 0,
        (df["current_signup"] / df["current_checkin"]) * 100,
        np.nan
    ).round(2)

    df["cr_change_%"] = np.where(
        df["last_cr_%"] > 0,
        ((df["current_cr_%"] / df["last_cr_%"]) - 1) * 100,
        np.nan
    ).round(2)

    # ======================
    # Weekly Ranking (GLOBAL)
    # ======================
    st.subheader("📊 Weekly Ranking Comparison (Global)")

    st.dataframe(
        df.sort_values("current_signup", ascending=False)[
            [
                "hotel_name",
                "brand_model",
                "city",
                "current_signup",
                "current_cr_%",
                "cr_change_%"
            ]
        ],
        use_container_width=True
    )

    # ======================
    # City-level Ranking (INTERNAL CITY RANK)
    # ======================
    st.subheader("🏙️ City-level Ranking (Current Week)")

    for city, city_df in df.groupby("city"):

        # Current city rank
        city_df = city_df.sort_values(
            "current_signup", ascending=False
        ).copy()
        city_df["current_rank"] = range(1, len(city_df) + 1)

        # Last city rank
        city_df_last = city_df.sort_values(
            "last_signup", ascending=False
        ).copy()
        city_df_last["last_rank"] = range(1, len(city_df_last) + 1)

        city_df["last_rank"] = city_df_last["last_rank"].values
        city_df["rank_change"] = city_df["last_rank"] - city_df["current_rank"]

        def movement(x):
            if pd.isna(x):
                return "🆕 New Entry"
            if x > 0:
                return f"↑ Up {x}"
            if x < 0:
                return f"↓ Down {abs(x)}"
            return "→ No Change"

        city_df["movement"] = city_df["rank_change"].apply(movement)

        st.markdown(f"### 📍 {city}")

        st.dataframe(
            city_df[
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

else:
    st.info("⬆️ Upload both files to continue.")
