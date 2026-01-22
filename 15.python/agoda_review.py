import streamlit as st
import requests
import pandas as pd
from typing import List

# =========================
# Page Config
# =========================
st.set_page_config(
    page_title="Agoda Guest Type Analyzer",
    layout="wide"
)

st.title("🏨 Agoda Guest Type Analyzer")
st.caption("API-based • No scraping • No propertyId required")

# =========================
# Constants
# =========================
AGODA_REVIEW_OVERVIEW_API = "https://www.agoda.com/api/cronos/property/review/overview"

TRAVELLER_TYPE_MAP = {
    1: "Solo traveler",
    2: "Couple",
    3: "Family with young children",
    4: "Family with older children",
    5: "Group",
    6: "Business traveler"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.agoda.com",
    "Referer": "https://www.agoda.com/"
}

# =========================
# API Logic
# =========================
def fetch_guest_types_from_url(hotel_url: str) -> dict:
    payload = {
        "hotelUrl": hotel_url,
        "languageId": 38,      # Vietnamese
        "currencyCode": "VND"
    }

    response = requests.post(
        AGODA_REVIEW_OVERVIEW_API,
        json=payload,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()
    data = response.json()

    result = {}
    for item in data.get("travellerTypeCounts", []):
        label = TRAVELLER_TYPE_MAP.get(item["travellerType"], "Other")
        result[label] = item["count"]

    return result


def analyze_urls(urls: List[str]) -> pd.DataFrame:
    rows = []

    for url in urls:
        url = url.strip()
        if not url:
            continue

        try:
            guest_types = fetch_guest_types_from_url(url)

            row = {"Hotel URL": url}
            row.update(guest_types)
            rows.append(row)

        except Exception as e:
            rows.append({
                "Hotel URL": url,
                "Error": str(e)
            })

    df = pd.DataFrame(rows).fillna(0)

    # Ensure consistent columns
    for col in TRAVELLER_TYPE_MAP.values():
        if col not in df.columns:
            df[col] = 0

    return df


# =========================
# Streamlit UI
# =========================
st.subheader("🔗 Input Agoda Hotel Links")

urls_text = st.text_area(
    label="Paste Agoda hotel URLs (1 per line)",
    height=200,
    placeholder="https://www.agoda.com/vi-vn/...\nhttps://www.agoda.com/vi-vn/..."
)

run_btn = st.button("🚀 Analyze Guest Types")

if run_btn:
    if not urls_text.strip():
        st.warning("Please input at least one Agoda hotel URL.")
    else:
        urls = urls_text.splitlines()

        with st.spinner("Calling Agoda review API..."):
            df = analyze_urls(urls)

        st.success("Done!")

        # =========================
        # Results
        # =========================
        st.subheader("📊 Guest Type Breakdown")
        st.dataframe(df, use_container_width=True)

        # =========================
        # Insight Layer (PM-friendly)
        # =========================
        if "Error" not in df.columns:
            insight_df = df.copy()

            insight_df["Total Reviews"] = insight_df[list(TRAVELLER_TYPE_MAP.values())].sum(axis=1)
            insight_df["Couple %"] = (insight_df["Couple"] / insight_df["Total Reviews"] * 100).round(1)
            insight_df["Business %"] = (insight_df["Business traveler"] / insight_df["Total Reviews"] * 100).round(1)

            def classify(row):
                if row["Couple %"] >= 40:
                    return "Couple-driven"
                if row["Business %"] >= 35:
                    return "Business-heavy"
                return "Mixed"

            insight_df["Primary Guest Mix"] = insight_df.apply(classify, axis=1)

            st.subheader("🧠 Guest Mix Insight")
            st.dataframe(
                insight_df[
                    ["Hotel URL", "Total Reviews", "Couple %", "Business %", "Primary Guest Mix"]
                ],
                use_container_width=True
            )

            st.caption(
                "💡 Use this to align pricing, room types, loyalty perks, and CRM messaging."
            )

        # =========================
        # Export
        # =========================
        st.download_button(
            "⬇️ Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name="agoda_guest_type_analysis.csv",
            mime="text/csv"
        )
