import streamlit as st
import pandas as pd
from datetime import date, timedelta

# ======================
# PAGE CONFIG
# ======================
st.set_page_config(page_title="Tool 1: Recruit CR Analyzer", layout="wide")
st.title("Tool 1: Recruit Signup & CR Analyzer")

# ======================
# UPLOAD FILES
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
    # VALIDATION
    # ======================
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
    # COLUMN MAPPING
    # ======================
    SIGNUP_HOTEL = 'hotel_short_name'
    SIGNUP_CITY = 'city'
    SIGNUP_DATE = signup_df.columns[4]
    SIGNUP_COUNT = signup_df.columns[5]

    RES_HOTEL = 'Hotel Name'
    RES_CITY = 'City'
    RES_TENANT = 'tenant_id'
    RES_DATE = 'Checkin'
    BRAND_MODEL_COL = res_df.columns[1]

    # ======================
    # PREPROCESSING
    # ======================
    signup_df['hotel_normalized'] = signup_df[SIGNUP_HOTEL].astype(str).str.strip().str.lower()
    res_df['hotel_normalized'] = res_df[RES_HOTEL].astype(str).str.strip().str.lower()

    signup_df[SIGNUP_DATE] = (
        signup_df[SIGNUP_DATE]
        .astype(str)
        .str.strip()
        .pipe(lambda s: pd.to_datetime(s, format="%b %d, %Y", errors="coerce"))
    )

    res_df[RES_DATE] = pd.to_datetime(res_df[RES_DATE], errors="coerce")

    signup_df[SIGNUP_COUNT] = pd.to_numeric(
        signup_df[SIGNUP_COUNT], errors="coerce"
    ).fillna(0)

    res_df['brand_model'] = (
        res_df[BRAND_MODEL_COL]
        .astype(str)
        .str.strip()
        .replace({'nan': 'Unknown'})
    )

    signup_df = signup_df.dropna(subset=[SIGNUP_DATE])
    res_df = res_df.dropna(subset=[RES_DATE])

    # ======================
    # DATE RANGE (DEFAULT = CURRENT MONTH)
    # ======================
    today = date.today()

    current_month_start = today.replace(day=1)
    next_month = (current_month_start + timedelta(days=32)).replace(day=1)
    current_month_end = next_month - timedelta(days=1)

    data_min_date = min(
        signup_df[SIGNUP_DATE].min().date(),
        res_df[RES_DATE].min().date()
    )
    data_max_date = max(
        signup_df[SIGNUP_DATE].max().date(),
        res_df[RES_DATE].max().date()
    )

    default_from = max(current_month_start, data_min_date)
    default_to = min(current_month_end, data_max_date)

    from_date, to_date = st.date_input(
        "📅 Select Check-in Date Range",
        value=(default_from, default_to),
        min_value=data_min_date,
        max_value=data_max_date
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
    # METRICS
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

    final_df = checkin_df.merge(recruit_df, on='hotel_normalized', how='left')
    final_df['recruit_count'] = final_df['recruit_count'].fillna(0).astype(int)
    final_df['CR_percent'] = (
        final_df['recruit_count'] / final_df['checkin_count'] * 100
    ).round(2)

    # ======================
    # ORDER CONFIG
    # ======================
    CITY_ORDER = ["HCM", "HN", "DN"]
    BRAND_MODEL_ORDER = ["savvy", "signature", "hotel", "living", "express"]

    final_df[RES_CITY] = final_df[RES_CITY].str.upper()
    final_df['brand_model_norm'] = final_df['brand_model'].str.lower()

    # ======================
    # TABS
    # ======================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overall Summary",
        "🏆 Overall Ranking",
        "🌆 Ranking by City",
        "🏷️ Ranking by Brand Model",
        "🗺️ Ranking by City Group"
    ])

    # TAB 1 – SUMMARY
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Unique Guests", f"{int(final_df.checkin_count.sum()):,}")
        c2.metric("Total Signups", f"{int(final_df.recruit_count.sum()):,}")
        c3.metric(
            "Overall CR",
            f"{(final_df.recruit_count.sum()/final_df.checkin_count.sum()*100):.2f}%"
        )
        c4.metric("Hotels", final_df.hotel_normalized.nunique())

    # TAB 2 – OVERALL RANKING
    with tab2:
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

    # TAB 3 – BY CITY
    with tab3:
        for city in CITY_ORDER:
            city_df = final_df[final_df[RES_CITY] == city]
            if city_df.empty:
                continue

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

    # TAB 4 – BY BRAND MODEL
    with tab4:
        for bm in BRAND_MODEL_ORDER:
            bm_df = final_df[final_df['brand_model_norm'] == bm]
            if bm_df.empty:
                continue

            st.markdown(f"### 🏷️ {bm.capitalize()}")

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

    # TAB 5 – BY CITY GROUP
    with tab5:
        # ── HCM ──────────────────────────────────────────────────────────────
        hcm_df = final_df[final_df[RES_CITY] == "HCM"].copy()

        if not hcm_df.empty:
            st.markdown("### 📍 HCM")

            # Define sub-groups for HCM
            HCM_GROUPS = {
                "Savvy & Signature": ["savvy", "signature"],
                "Express & Living":  ["express", "living"],
                "Hotel":             ["hotel"],
            }

            for group_name, brands in HCM_GROUPS.items():
                grp_df = hcm_df[hcm_df['brand_model_norm'].isin(brands)]
                if grp_df.empty:
                    continue

                st.markdown(f"#### 🏷️ {group_name}")

                grp_rank = (
                    grp_df
                    .groupby(['hotel_display', 'brand_model'])
                    .agg({'checkin_count': 'sum', 'recruit_count': 'sum'})
                    .reset_index()
                )
                grp_rank['CR_percent'] = (
                    grp_rank.recruit_count / grp_rank.checkin_count * 100
                ).round(2)
                grp_rank = grp_rank.sort_values('CR_percent', ascending=False).reset_index(drop=True)
                grp_rank['Rank'] = range(1, len(grp_rank) + 1)

                st.dataframe(
                    grp_rank.rename(columns={
                        'hotel_display': 'Hotel',
                        'brand_model': 'Brand Model',
                        'checkin_count': 'Check-ins',
                        'recruit_count': 'Signups',
                        'CR_percent': 'CR %'
                    })[['Rank', 'Hotel', 'Brand Model', 'Check-ins', 'Signups', 'CR %']],
                    use_container_width=True,
                    hide_index=True
                )

        # ── DN & HN ──────────────────────────────────────────────────────────
        for city in ["DN", "HN"]:
            city_df = final_df[final_df[RES_CITY] == city].copy()
            if city_df.empty:
                continue

            st.markdown(f"### 📍 {city}")

            city_grp = (
                city_df
                .groupby(['hotel_display', 'brand_model'])
                .agg({'checkin_count': 'sum', 'recruit_count': 'sum'})
                .reset_index()
            )
            city_grp['CR_percent'] = (
                city_grp.recruit_count / city_grp.checkin_count * 100
            ).round(2)
            city_grp = city_grp.sort_values('CR_percent', ascending=False).reset_index(drop=True)
            city_grp['Rank'] = range(1, len(city_grp) + 1)

            st.dataframe(
                city_grp.rename(columns={
                    'hotel_display': 'Hotel',
                    'brand_model': 'Brand Model',
                    'checkin_count': 'Check-ins',
                    'recruit_count': 'Signups',
                    'CR_percent': 'CR %'
                })[['Rank', 'Hotel', 'Brand Model', 'Check-ins', 'Signups', 'CR %']],
                use_container_width=True,
                hide_index=True
            )

else:
    st.info("👆 Upload both Signup & Reservation files to start analysis")
