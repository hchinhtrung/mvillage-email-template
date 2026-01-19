import streamlit as st
import pandas as pd
import numpy as np

# ======================
# Page config
# ======================
st.set_page_config(
    page_title="Tool 2: Hotel Signup Ranking Movement",
    layout="wide"
)

st.title("Tool 2: Hotel Signup Ranking – Weekly Movement")

# ======================
# Upload files
# ======================
col1, col2 = st.columns(2)

with col1:
    before_file = st.file_uploader("⬆️ Upload LAST WEEK file", type=["csv"])
with col2:
    after_file = st.file_uploader("⬆️ Upload THIS WEEK file", type=["csv"])

# ======================
# Helpers
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

def calc_cr(signup, checkin):
    return np.where(
        checkin > 0,
        (signup / checkin) * 100,
        np.nan
    )

def movement_label(x):
    if pd.isna(x):
        return "🆕 New Entry"
    if x > 0:
        return f"↑ Up {x}"
    if x < 0:
        return f"↓ Down {abs(x)}"
    return "→ No Change"

# ======================
# MAIN
# ======================
if before_file and after_file:

    # ------------------
    # Load & normalize
    # ------------------
    before = normalize_df(pd.read_csv(before_file))
    after = normalize_df(pd.read_csv(after_file))

    # ------------------
    # Rename columns
    # ------------------
    before = before.rename(columns={
        "rank": "last_rank",
        "signup_count": "last_signup",
        "checkin_count": "last_checkin"
    })

    after = after.rename(columns={
        "rank": "current_rank",
        "signup_count": "current_signup",
        "checkin_count": "current_checkin"
    })

    # ------------------
    # Merge
    # ------------------
    df = after.merge(
        before[
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
    # CR calculation (%)
    # ======================
    df["last_cr_%"] = calc_cr(
        df["last_signup"], df["last_checkin"]
    ).round(2)

    df["current_cr_%"] = calc_cr(
        df["current_signup"], df["current_checkin"]
    ).round(2)

    df["cr_change_%"] = np.where(
        df["last_cr_%"] > 0,
        ((df["current_cr_%"] / df["last_cr_%"]) - 1) * 100,
        np.nan
    ).round(2)

    # ======================
    # GLOBAL RANK MOVEMENT
    # ======================
    df["rank_change"] = df["last_rank"] - df["current_rank"]
    df["movement"] = df["rank_change"].apply(movement_label)

    # ======================
    # WEEKLY RANKING – GLOBAL
    # ======================
    st.subheader("📊 Weekly Ranking Comparison (Global)")

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
        ].sort_values("current_rank"),
        use_container_width=True
    )

    # ======================
    # CITY-LEVEL RANKING
    # ======================
    st.subheader("🏙️ City-level Ranking (Current Week)")

    for city in df["city"].dropna().unique():

        city_current = df[df["city"] == city][
            [
                "hotel_name",
                "brand_model",
                "city",
                "current_signup",
                "last_signup",
                "last_cr_%",
                "current_cr_%",
                "cr_change_%"
            ]
        ].copy()

        city_current = city_current.sort_values(
            "current_signup", ascending=False
        )
        city_current["current_rank"] = range(1, len(city_current) + 1)

        city_last = city_current.sort_values(
            "last_signup", ascending=False
        )
        city_last["last_rank"] = range(1, len(city_last) + 1)

        city_rank = city_current.merge(
            city_last[["hotel_name", "last_rank"]],
            on="hotel_name",
            how="left"
        )

        city_rank["rank_change"] = (
            city_rank["last_rank"] - city_rank["current_rank"]
        )
        city_rank["movement"] = city_rank["rank_change"].apply(movement_label)

        st.markdown(f"### 📍 {city}")

        st.dataframe(
            city_rank[
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
    # CITY-LEVEL RANKING BY BRAND MODEL (NEW)
    # ======================
    st.subheader("🏙️ City-level Ranking by Brand Model (Current Week)")

    for city in df["city"].dropna().unique():

        st.markdown(f"## 📍 {city}")
        city_df = df[df["city"] == city]

        for model in city_df["brand_model"].dropna().unique():

            model_df = city_df[
                city_df["brand_model"] == model
            ][
                [
                    "hotel_name",
                    "brand_model",
                    "city",
                    "current_signup",
                    "last_signup",
                    "last_cr_%",
                    "current_cr_%",
                    "cr_change_%"
                ]
            ].copy()

            model_current = model_df.sort_values(
                "current_signup", ascending=False
            )
            model_current["current_rank"] = range(
                1, len(model_current) + 1
            )

            model_last = model_df.sort_values(
                "last_signup", ascending=False
            )
            model_last["last_rank"] = range(
                1, len(model_last) + 1
            )

            model_rank = model_current.merge(
                model_last[["hotel_name", "last_rank"]],
                on="hotel_name",
                how="left"
            )

            model_rank["rank_change"] = (
                model_rank["last_rank"] - model_rank["current_rank"]
            )
            model_rank["movement"] = model_rank["rank_change"].apply(
                movement_label
            )
            model_rank = model_rank.sort_values(
                by="cr_change_%",
                ascending=False,
                na_position="last"
            )

            st.markdown(f"### 🏷️ Brand Model: **{model}**")

            st.dataframe(
                model_rank[
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
