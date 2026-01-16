import streamlit as st
import pandas as pd
from datetime import date, timedelta

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

# ======================
# Load helper
# ======================
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
    # Show first few rows for debugging
    # ======================
    with st.expander("🔍 Preview Data (First 10 rows)"):
        col_prev1, col_prev2 = st.columns(2)
        with col_prev1:
            st.write("**Signup File:**")
            st.dataframe(signup_df.head(10))
            st.write(f"📊 Total rows: **{len(signup_df):,}**")
            st.write(f"📋 Columns: {list(signup_df.columns)}")
        with col_prev2:
            st.write("**Reservation File:**")
            st.dataframe(res_df.head(10))
            st.write(f"📊 Total rows: **{len(res_df):,}**")
            st.write(f"📋 Columns: {list(res_df.columns)}")
    
    # ======================
    # Validate required columns
    # ======================
    required_signup_cols = ['hotel_short_name', 'city']
    required_res_cols = ['Hotel Name', 'City', 'tenant_id', 'Checkin']
    
    signup_missing = [col for col in required_signup_cols if col not in signup_df.columns]
    res_missing = [col for col in required_res_cols if col not in res_df.columns]
    
    if len(signup_df.columns) < 6:
        st.error("❌ Signup file must have at least 6 columns (A-F)")
        st.write(f"Current columns: {signup_df.columns.tolist()}")
        st.stop()
    
    if signup_missing or res_missing:
        st.error(f"❌ Missing required columns:")
        if signup_missing:
            st.write(f"Signup file missing: {signup_missing}")
        if res_missing:
            st.write(f"Reservation file missing: {res_missing}")
        st.stop()
    
    # ======================
    # Assign column names (0-indexed)
    # ======================
    SIGNUP_HOTEL_COL = 'hotel_short_name'
    SIGNUP_CITY_COL = 'city'
    SIGNUP_DATE_COL = signup_df.columns[4]  # Column E (index 4)
    SIGNUP_COUNT_COL = signup_df.columns[5]  # Column F (index 5)
    
    RES_HOTEL_COL = 'Hotel Name'
    RES_CITY_COL = 'City'
    RES_TENANT_COL = 'tenant_id'
    RES_DATE_COL = 'Checkin'
    
    st.divider()
    st.subheader("🔍 Auto-Detected Columns")
    
    col_detect1, col_detect2 = st.columns(2)
    
    with col_detect1:
        st.write("**Signup File Mapping:**")
        st.write(f"✓ Hotel: `{SIGNUP_HOTEL_COL}`")
        st.write(f"✓ City: `{SIGNUP_CITY_COL}`")
        st.write(f"✓ Check-in Date: `{SIGNUP_DATE_COL}` (Column E)")
        st.write(f"✓ Signup Count: `{SIGNUP_COUNT_COL}` (Column F)")
        
    with col_detect2:
        st.write("**Reservation File Mapping:**")
        st.write(f"✓ Hotel: `{RES_HOTEL_COL}`")
        st.write(f"✓ City: `{RES_CITY_COL}`")
        st.write(f"✓ Tenatn ID: `{RES_TENANT_COL}`")
        st.write(f"✓ Check-in Date: `{RES_DATE_COL}`")
    
    # ======================
    # Data preprocessing
    # ======================
    # Normalize hotel names for better matching
    signup_df['hotel_normalized'] = signup_df[SIGNUP_HOTEL_COL].str.strip().str.lower()
    res_df['hotel_normalized'] = res_df[RES_HOTEL_COL].str.strip().str.lower()
    
    # Parse dates
    signup_df[SIGNUP_DATE_COL] = pd.to_datetime(signup_df[SIGNUP_DATE_COL], errors="coerce")
    res_df[RES_DATE_COL] = pd.to_datetime(res_df[RES_DATE_COL], errors="coerce")
    
    # Convert signup count to numeric
    signup_df[SIGNUP_COUNT_COL] = pd.to_numeric(signup_df[SIGNUP_COUNT_COL], errors='coerce').fillna(0)
    
    # Remove rows with invalid dates
    signup_before = len(signup_df)
    res_before = len(res_df)
    
    signup_df = signup_df.dropna(subset=[SIGNUP_DATE_COL])
    res_df = res_df.dropna(subset=[RES_DATE_COL])
    
    if len(signup_df) < signup_before:
        st.warning(f"⚠️ Removed {signup_before - len(signup_df)} signup rows with invalid dates")
    if len(res_df) < res_before:
        st.warning(f"⚠️ Removed {res_before - len(res_df)} reservation rows with invalid dates")
    
    # ======================
    # Date range filter
    # ======================
    st.divider()
    st.subheader("📅 Select Date Range")
    
    # Get date range from both files
    min_date_signup = signup_df[SIGNUP_DATE_COL].min().date()
    max_date_signup = signup_df[SIGNUP_DATE_COL].max().date()
    min_date_res = res_df[RES_DATE_COL].min().date()
    max_date_res = res_df[RES_DATE_COL].max().date()
    
    overall_min = min(min_date_signup, min_date_res)
    overall_max = max(max_date_signup, max_date_res)
    
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        st.info(f"📅 Signup data: {min_date_signup} to {max_date_signup}")
    with col_date2:
        st.info(f"📅 Reservation data: {min_date_res} to {max_date_res}")
    
    date_range = st.date_input(
        "Select Check-in Date Range to Analyze",
        value=(overall_min, overall_max),
        min_value=overall_min,
        max_value=overall_max
    )
    
    if len(date_range) == 2:
        from_date, to_date = date_range
    else:
        from_date = to_date = date_range[0]
    
    # ✅ Filter BOTH files by the SAME date range
    res_filtered = res_df[
        (res_df[RES_DATE_COL].dt.date >= from_date) &
        (res_df[RES_DATE_COL].dt.date <= to_date)
    ].copy()
    
    signup_filtered = signup_df[
        (signup_df[SIGNUP_DATE_COL].dt.date >= from_date) &
        (signup_df[SIGNUP_DATE_COL].dt.date <= to_date)
    ].copy()
    
    st.success(f"✅ Analyzing data from **{from_date}** to **{to_date}**")
    
    # Show filtered record counts
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("Reservation Records", f"{len(res_filtered):,}")
    with col_info2:
        st.metric("Signup Records", f"{len(signup_filtered):,}")
    with col_info3:
        total_signup_value = signup_filtered[SIGNUP_COUNT_COL].sum()
        st.metric("Total Signups (Sum of Col F)", f"{int(total_signup_value):,}")
    
    if len(res_filtered) == 0:
        st.error("❌ No reservation data in selected date range!")
        st.stop()
    
    if len(signup_filtered) == 0:
        st.warning("⚠️ No signup data in selected date range!")
    
    # ======================
    # Calculate metrics
    # ======================
    
    # 1. Count UNIQUE guests per hotel (from reservation)
    checkin_df = (
        res_filtered
        .groupby(['hotel_normalized', RES_CITY_COL])[RES_TENANT_COL]
        .nunique()
        .reset_index(name="checkin_count")
    )

    
    # Keep original hotel name for display
    hotel_name_map = res_filtered.groupby('hotel_normalized')[RES_HOTEL_COL].first().to_dict()
    checkin_df['hotel_display'] = checkin_df['hotel_normalized'].map(hotel_name_map)
    
    # 2. Sum signup counts per hotel (Column F from filtered signup data)
    recruit_df = (
        signup_filtered
        .groupby('hotel_normalized')[SIGNUP_COUNT_COL]
        .sum()
        .reset_index(name="recruit_count")
    )
    
    # 3. Merge check-ins with recruits
    final_df = checkin_df.merge(
        recruit_df,
        on='hotel_normalized',
        how='left'
    )
    
    final_df['recruit_count'] = final_df['recruit_count'].fillna(0).astype(int)
    
    # 4. Calculate Conversion Rate
    final_df['CR'] = (final_df['recruit_count'] / final_df['checkin_count']).round(4)
    final_df['CR_percent'] = (final_df['CR'] * 100).round(2)
    
    # ======================
    # Data Quality Checks
    # ======================
    st.divider()
    
    # Check for CR > 100%
    high_cr_hotels = final_df[final_df['CR_percent'] > 100]
    if len(high_cr_hotels) > 0:
        st.error(f"🚨 Found **{len(high_cr_hotels)}** hotels with CR > 100%")
        st.write("**Possible reasons:**")
        st.write("1. Hotel names don't match exactly between files")
        st.write("2. Signup data has duplicate entries")
        st.write("3. Date filtering issue")
        
        with st.expander("⚠️ Hotels with CR > 100%"):
            problem_hotels = high_cr_hotels[['hotel_display', 'checkin_count', 'recruit_count', 'CR_percent']].copy()
            problem_hotels.columns = ['Hotel', 'Check-ins', 'Signups', 'CR %']
            st.dataframe(problem_hotels, use_container_width=True)
    
    # Check for hotels with 0 signups
    zero_signup = final_df[final_df['recruit_count'] == 0]
    if len(zero_signup) > 0:
        st.info(f"ℹ️ **{len(zero_signup)}** hotels have 0 signups in this period")
    
    # ======================
    # Overall Summary
    # ======================
    st.divider()
    st.subheader("📊 Overall Summary")
    
    total_checkins = final_df['checkin_count'].sum()
    total_recruits = final_df['recruit_count'].sum()
    overall_cr = (total_recruits / total_checkins * 100) if total_checkins > 0 else 0
    
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    
    with metric_col1:
        st.metric("Unique Guests", f"{int(total_checkins):,}")
    
    with metric_col2:
        st.metric("Total Signups", f"{int(total_recruits):,}")
    
    with metric_col3:
        st.metric("Overall CR", f"{overall_cr:.2f}%")
    
    with metric_col4:
        num_hotels = len(final_df)
        st.metric("Hotels Analyzed", f"{num_hotels}")
    
    # ======================
    # Overall Hotel Ranking
    # ======================
    st.divider()
    st.subheader("🏆 Hotel Ranking (Overall)")
    
    overall_rank = (
        final_df
        .groupby(['hotel_normalized', 'hotel_display'])
        .agg({
            'checkin_count': 'sum',
            'recruit_count': 'sum'
        })
        .reset_index()
    )
    
    overall_rank['CR'] = (overall_rank['recruit_count'] / overall_rank['checkin_count']).round(4)
    overall_rank['CR_percent'] = (overall_rank['CR'] * 100).round(2)
    overall_rank = overall_rank.sort_values('CR', ascending=False).reset_index(drop=True)
    overall_rank['Rank'] = range(1, len(overall_rank) + 1)
    
    # Display table
    display_overall = overall_rank[[
        'Rank',
        'hotel_display',
        'checkin_count',
        'recruit_count',
        'CR_percent'
    ]].copy()
    
    display_overall.columns = ['Rank', 'Hotel', 'Check-ins (Unique)', 'Signups', 'CR %']
    
    # Color coding for CR
    def highlight_cr(row):
        cr = row['CR %']
        if cr > 100:
            return ['background-color: #ffcccc'] * len(row)  # Red for > 100%
        elif cr > 50:
            return ['background-color: #ccffcc'] * len(row)  # Green for good CR
        elif cr > 20:
            return ['background-color: #ffffcc'] * len(row)  # Yellow for medium CR
        else:
            return [''] * len(row)
    
    st.dataframe(
        display_overall,
        use_container_width=True,
        hide_index=True
    )
    
    # ======================
    # Ranking by City
    # ======================
    st.divider()
    st.subheader("🌆 Hotel Ranking by City")
    
    available_cities = sorted(final_df[RES_CITY_COL].dropna().unique())
    
    if len(available_cities) > 0:
        selected_city = st.selectbox("Select City", available_cities)
        
        city_rank = final_df[final_df[RES_CITY_COL] == selected_city].copy()
        city_rank = city_rank.sort_values('CR', ascending=False).reset_index(drop=True)
        city_rank['Rank'] = range(1, len(city_rank) + 1)
        
        # City summary
        city_checkins = city_rank['checkin_count'].sum()
        city_recruits = city_rank['recruit_count'].sum()
        city_cr = (city_recruits / city_checkins * 100) if city_checkins > 0 else 0
        
        city_col1, city_col2, city_col3 = st.columns(3)
        with city_col1:
            st.metric(f"{selected_city} - Check-ins", f"{int(city_checkins):,}")
        with city_col2:
            st.metric(f"{selected_city} - Signups", f"{int(city_recruits):,}")
        with city_col3:
            st.metric(f"{selected_city} - CR", f"{city_cr:.2f}%")
        
        display_city = city_rank[[
            'Rank',
            'hotel_display',
            'checkin_count',
            'recruit_count',
            'CR_percent'
        ]].copy()
        
        display_city.columns = ['Rank', 'Hotel', 'Check-ins (Unique)', 'Signups', 'CR %']
        
        st.dataframe(
            display_city,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("No city data available")
    
    # ======================
    # Download Section
    # ======================
    st.divider()
    st.subheader("⬇️ Download Reports")
    
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        overall_download = overall_rank[[
            'Rank',
            'hotel_display',
            'checkin_count',
            'recruit_count',
            'CR_percent'
        ]].copy()
        overall_download.columns = ['Rank', 'Hotel', 'Check-ins', 'Signups', 'CR %']
        
        csv_overall = overall_download.to_csv(index=False).encode('utf-8-sig')  # UTF-8 with BOM for Excel
        
        st.download_button(
            "📥 Download Overall Ranking",
            csv_overall,
            file_name=f"hotel_cr_overall_{from_date}_to_{to_date}.csv",
            mime="text/csv"
        )
    
    with col_dl2:
        if len(available_cities) > 0:
            city_download = display_city.copy()
            csv_city = city_download.to_csv(index=False).encode('utf-8-sig')
            
            st.download_button(
                f"📥 Download {selected_city} Ranking",
                csv_city,
                file_name=f"hotel_cr_{selected_city}_{from_date}_to_{to_date}.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Please upload both files to begin analysis")
    
    with st.expander("📋 Required File Format"):
        st.write("**Signup File Structure:**")
        st.code("""
Column A: hotel_short_name
Column B: city
Column C: ...
Column D: ...
Column E: Check-in date (ngày signup được tạo)
Column F: Số lượng signup của hotel tại ngày đó
        """)
        
        st.write("**Reservation File Structure:**")
        st.code("""
Hotel Name: Tên khách sạn
City: Thành phố
Guest Name: Tên khách (sẽ count unique)
Date: Ngày check-in
        """)
        
        st.write("**Logic:**")
        st.write("- Filter cả 2 files theo cùng date range")
        st.write("- Đếm UNIQUE guests từ reservation")
        st.write("- Tổng signup count (Column F) từ signup file")
        st.write("- CR = Signups / Unique Guests × 100%")