import streamlit as st
import pandas as pd

st.set_page_config(page_title="Recruit CR Analyzer", layout="wide")
st.title("🏨 Recruit Signup & CR Analyzer")

# ======================
# Upload files
# ======================
col1, col2 = st.columns(2)

with col1:
    signup_file = st.file_uploader("📤 Upload Signup File", type=["csv", "xlsx"])
with col2:
    reservation_file = st.file_uploader("📤 Upload Reservation File", type=["csv", "xlsx"])


def load_file(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)


# ======================
# MAIN
# ======================
if signup_file and reservation_file:
    signup_df = load_file(signup_file)
    res_df = load_file(reservation_file)

    st.success("✅ Files uploaded successfully!")

    # ======================
    # Validate base columns
    # ======================
    if len(res_df.columns) < 5:
        st.error("❌ Reservation file must have at least 5 columns (A–E)")
        st.stop()

    required_signup = ['hotel_short_name', 'city']
    required_res = ['Hotel Name', 'City', 'tenant_id', 'Checkin']

    if any(c not in signup_df.columns for c in required_signup):
        st.error("❌ Signup file missing required columns")
        st.stop()

    if any(c not in res_df.columns for c in required_res):
        st.error("❌ Reservation file missing required columns")
        st.stop()

    if len(signup_df.columns) < 6:
        st.error("❌ Signup file must have at least 6 columns (A–F)")
        st.stop()

    # ======================
    # Column mapping
    # ======================
    SIGNUP_HOTEL = 'hotel_short_name'
    SIGNUP_CITY = 'city'
    SIGNUP_DATE = signup_df.columns[4]
    SIGNUP_COUNT = signup_df.columns[5]

    RES_HOTEL = 'Hotel Name'
    RES_CITY = 'City'
    RES_TENANT = 'tenant_id'
    RES_DATE = 'Checkin'

    BRAND_MODEL_COL = res_df.columns[1]  # Column B

    # ======================
    # Preprocessing
    # ======================
    signup_df['hotel_normalized'] = signup_df[SIGNUP_HOTEL].str.strip().str.lower()
    res_df['hotel_normalized'] = res_df[RES_HOTEL].str.strip().str.lower()

    res_df['brand_model'] = (
        res_df[BRAND_MODEL_COL]
        .astype(str)
        .str.strip()
        .replace({'nan': 'Unknown'})
    )

    signup_df[SIGNUP_DATE] = pd.to_datetime(signup_df[SIGNUP_DATE], errors="coerce")
    res_df[RES_DATE] = pd.to_datetime(res_df[RES_DATE], errors="coerce")

    signup_df[SIGNUP_COUNT] = pd.to_numeric(
        signup_df[SIGNUP_COUNT], errors="coerce"
    ).fillna(0)

    signup_df = signup_df.dropna(subset=[SIGNUP_DATE])
    res_df = res_df.dropna(subset=[RES_DATE])

    # ======================
    # Date range
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
    # Metrics
    # ======================
    checkin_df = (
        res_f
        .groupby(['hotel_normalized', RES_CITY, 'brand_model'])[RES_TENANT]
        .nunique()
        .reset_index(name='checkin_count')
    )

    hotel_name_map = (
        res_f.groupby('hotel_normalized')[RES_HOTEL]
        .first()
        .to_dict()
    )
    checkin_df['hotel_display'] = checkin_df['hotel_normalized'].map(hotel_name_map)

    recruit_df = (
        signup_f
        .groupby(['hotel_normalized', SIGNUP_CITY])[SIGNUP_COUNT]
        .sum()
        .reset_index(name='recruit_count')
    )

    final_df = checkin_df.merge(
        recruit_df,
        on='hotel_normalized',
        how='left'
    )

    final_df['recruit_count'] = final_df['recruit_count'].fillna(0).astype(int)
    final_df['CR_percent'] = (
        final_df['recruit_count'] / final_df['checkin_count'] * 100
    ).round(2)

    # ======================
    # Overall Summary
    # ======================
    st.divider()
    st.subheader("📊 Overall Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique Guests", f"{int(final_df.checkin_count.sum()):,}")
    c2.metric("Total Signups", f"{int(final_df.recruit_count.sum()):,}")
    c3.metric(
        "Overall CR",
        f"{(final_df.recruit_count.sum()/final_df.checkin_count.sum()*100):.2f}%"
    )
    c4.metric("Hotels", final_df.hotel_normalized.nunique())

    # ======================
    # Overall Ranking
    # ======================
    st.divider()
    st.subheader("🏆 Hotel Ranking (Overall)")

    overall = (
        final_df
        .groupby(['hotel_display', 'brand_model', RES_CITY])
        .agg({'checkin_count': 'sum', 'recruit_count': 'sum'})
        .reset_index()
    )

    overall['CR_percent'] = (
        overall.recruit_count / overall.checkin_count * 100
    ).round(2)

    overall = overall.sort_values('CR_percent', ascending=False).reset_index(drop=True)
    overall['Rank'] = range(1, len(overall) + 1)

    st.dataframe(
        overall.rename(columns={
            'hotel_display': 'Hotel',
            'brand_model': 'Brand Model',
            RES_CITY: 'City',
            'checkin_count': 'Check-ins',
            'recruit_count': 'Signups',
            'CR_percent': 'CR %'
        })[['Rank', 'Hotel', 'Brand Model', 'City', 'Check-ins', 'Signups', 'CR %']],
        use_container_width=True,
        hide_index=True
    )

    # ======================
    # Ranking by City
    # ======================
    st.divider()
    st.subheader("🌆 Hotel Ranking by City")

    for city, city_df in final_df.groupby(RES_CITY):
        st.markdown(f"### 📍 {city}")

        city_rank = (
            city_df
            .groupby(['hotel_display', 'brand_model'])
            .agg({'checkin_count': 'sum', 'recruit_count': 'sum'})
            .reset_index()
        )

        city_rank['CR_percent'] = (
            city_rank.recruit_count / city_rank.checkin_count * 100
        ).round(2)

        city_rank = city_rank.sort_values('CR_percent', ascending=False).reset_index(drop=True)
        city_rank['Rank'] = range(1, len(city_rank) + 1)

        s1, s2, s3 = st.columns(3)
        s1.metric("Check-ins", f"{int(city_rank.checkin_count.sum()):,}")
        s2.metric("Signups", f"{int(city_rank.recruit_count.sum()):,}")
        s3.metric(
            "CR",
            f"{(city_rank.recruit_count.sum()/city_rank.checkin_count.sum()*100):.2f}%"
        )

        st.dataframe(
            city_rank.rename(columns={
                'hotel_display': 'Hotel',
                'brand_model': 'Brand Model',
                'checkin_count': 'Check-ins',
                'recruit_count': 'Signups',
                'CR_percent': 'CR %'
            })[['Rank', 'Hotel', 'Brand Model', 'Check-ins', 'Signups', 'CR %']],
            use_container_width=True,
            hide_index=True
        )

    # ======================
    # Ranking by Brand Model
    # ======================
    st.divider()
    st.subheader("🏷️ Hotel Ranking by Brand Model")

    for brand_model, bm_df in final_df.groupby('brand_model'):
        st.markdown(f"### 🏷️ {brand_model}")

        bm_rank = (
            bm_df
            .groupby(['hotel_display', RES_CITY])
            .agg({'checkin_count': 'sum', 'recruit_count': 'sum'})
            .reset_index()
        )

        bm_rank['CR_percent'] = (
            bm_rank.recruit_count / bm_rank.checkin_count * 100
        ).round(2)

        bm_rank = bm_rank.sort_values('CR_percent', ascending=False).reset_index(drop=True)
        bm_rank['Rank'] = range(1, len(bm_rank) + 1)

        s1, s2, s3 = st.columns(3)
        s1.metric("Check-ins", f"{int(bm_rank.checkin_count.sum()):,}")
        s2.metric("Signups", f"{int(bm_rank.recruit_count.sum()):,}")
        s3.metric(
            "CR",
            f"{(bm_rank.recruit_count.sum()/bm_rank.checkin_count.sum()*100):.2f}%"
        )

        st.dataframe(
            bm_rank.rename(columns={
                'hotel_display': 'Hotel',
                RES_CITY: 'City',
                'checkin_count': 'Check-ins',
                'recruit_count': 'Signups',
                'CR_percent': 'CR %'
            })[['Rank', 'Hotel', 'City', 'Check-ins', 'Signups', 'CR %']],
            use_container_width=True,
            hide_index=True
        )

else:
    st.info("👆 Upload both Signup & Reservation files to start analysis")
