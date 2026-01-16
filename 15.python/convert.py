import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Hotel Signup Ranking Movement",
    layout="wide"
)

st.title("🏨 Hotel Signup Ranking – Weekly Movement")

st.markdown("""
So sánh **ranking signup theo hotel** giữa 2 tuần  
File input **không cần chuẩn hoá column**
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
        "Signups": "signup_count",
        "Check-ins": "checkin_count"
    }

    df = df.rename(columns=column_map)

    required = {"rank", "hotel_name", "signup_count"}
    if not required.issubset(df.columns):
        st.error("❌ File thiếu column bắt buộc: Rank, Hotel, Signups")
        st.stop()

    return df


# ======================
# Process
# ======================
if before_file and after_file:
    before_df = pd.read_csv(before_file)
    after_df = pd.read_csv(after_file)

    before_df = normalize_df(before_df)
    after_df = normalize_df(after_df)

    # Rename for comparison
    before_df = before_df.rename(columns={
        "rank": "last_rank",
        "signup_count": "last_signup"
    })

    after_df = after_df.rename(columns={
        "rank": "current_rank",
        "signup_count": "current_signup"
    })

    # ======================
    # Merge (key = hotel_name)
    # ======================
    df = after_df.merge(
        before_df[["hotel_name", "last_rank", "last_signup"]],
        on="hotel_name",
        how="left"
    )

    # ======================
    # Rank movement
    # ======================
    df["rank_change"] = df["last_rank"] - df["current_rank"]

    def movement(row):
        if pd.isna(row["last_rank"]):
            return "🆕 New"
        if row["rank_change"] > 0:
            return f"↑ +{int(row['rank_change'])}"
        if row["rank_change"] < 0:
            return f"↓ {int(row['rank_change'])}"
        return "→ 0"

    df["movement"] = df.apply(movement, axis=1)

    # Signup growth
    df["signup_growth_%"] = (
        (df["current_signup"] - df["last_signup"]) / df["last_signup"] * 100
    ).round(1)

    # Sort
    df = df.sort_values("current_rank")

    # ======================
    # Display
    # ======================
    st.subheader("📊 Ranking Movement Result")

    st.dataframe(
        df[
            [
                "hotel_name",
                "last_rank",
                "current_rank",
                "movement",
                "last_signup",
                "current_signup",
                "signup_growth_%"
            ]
        ],
        use_container_width=True
    )

    # ======================
    # Download
    # ======================
    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇️ Download Ranking Movement CSV",
        data=csv,
        file_name="hotel_ranking_movement.csv",
        mime="text/csv"
    )

else:
    st.info("⬆️ Vui lòng upload đầy đủ Before & After file")
