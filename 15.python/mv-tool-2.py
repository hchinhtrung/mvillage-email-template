import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ======================
# Page config
# ======================
st.set_page_config(page_title="Weekly Ranking Comparison", layout="wide")
st.title("📊 Weekly Ranking Comparison Dashboard")

# ======================
# Upload files
# ======================
c1, c2 = st.columns(2)
with c1:
    signup_file = st.file_uploader("📤 Upload Signup File", type=["csv", "xlsx"])
with c2:
    reservation_file = st.file_uploader("📤 Upload Reservation File", type=["csv", "xlsx"])

def load_file(file):
    return pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)

if not signup_file or not reservation_file:
    st.info("👆 Upload both Signup & Reservation files to start")
    st.stop()

signup_df = load_file(signup_file)
res_df = load_file(reservation_file)

# ======================
# Column mapping
# ======================
SIGNUP_HOTEL = "hotel_short_name"
SIGNUP_DATE = signup_df.columns[4]
SIGNUP_COUNT = signup_df.columns[5]

RES_HOTEL = "Hotel Name"
RES_CITY = "City"
RES_DATE = "Checkin"
RES_TENANT = "tenant_id"
BRAND_MODEL = res_df.columns[1]

CITY_ORDER = ["HCM", "HN", "DN"]
BRAND_ORDER = ["savvy", "signature", "hotel", "living", "express"]


# ======================
# Preprocessing
# ======================
signup_df["hotel_key"] = signup_df[SIGNUP_HOTEL].str.lower().str.strip()
res_df["hotel_key"] = res_df[RES_HOTEL].str.lower().str.strip()

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

signup_df = signup_df.dropna(subset=[SIGNUP_DATE])
res_df = res_df.dropna(subset=[RES_DATE])

def filter_period(df, col, start, end):
    return df[
        (df[col].dt.date >= start) &
        (df[col].dt.date <= end)
    ]

# ======================
# Date selector (AUTO DEFAULT)
# ======================
st.subheader("📅 Compare Time Ranges")

today = pd.Timestamp.today().normalize()

# Default logic
# Last: D-14 → D-8
last_from_default = (today - pd.Timedelta(days=14)).date()
last_to_default   = (today - pd.Timedelta(days=8)).date()

# Current: D-7 → D-1
current_from_default = (today - pd.Timedelta(days=7)).date()
current_to_default   = (today - pd.Timedelta(days=1)).date()

c1, c2 = st.columns(2)
with c1:
    last_from, last_to = st.date_input(
        "Last Period",
        value=(last_from_default, last_to_default)
    )

with c2:
    current_from, current_to = st.date_input(
        "Current Period",
        value=(current_from_default, current_to_default)
    )


# ======================
# Metric builder
# ======================
def build_metric(res, signup):
    checkin = (
        res.groupby(["hotel_key", RES_CITY, BRAND_MODEL])[RES_TENANT]
        .nunique()
        .reset_index(name="checkin")
    )

    signup = (
        signup.groupby("hotel_key")[SIGNUP_COUNT]
        .sum()
        .reset_index(name="signup")
    )

    df = checkin.merge(signup, on="hotel_key", how="left").fillna(0)

    df["cr"] = np.where(
        df["checkin"] == 0, 0,
        (df["signup"] / df["checkin"] * 100).round(2)
    )
    return df

last_df = build_metric(
    filter_period(res_df, RES_DATE, last_from, last_to),
    filter_period(signup_df, SIGNUP_DATE, last_from, last_to)
)

current_df = build_metric(
    filter_period(res_df, RES_DATE, current_from, current_to),
    filter_period(signup_df, SIGNUP_DATE, current_from, current_to)
)

# ======================
# Ranking helpers
# ======================
def add_global_rank(df):
    df = df.copy()
    df["rank"] = df["cr"].rank(ascending=False, method="dense")
    return df

def add_city_rank(df):
    df = df.copy()
    df["rank"] = df.groupby(RES_CITY)["cr"].rank(ascending=False, method="dense")
    return df

def add_city_brand_rank(df):
    df = df.copy()
    df["rank"] = df.groupby([RES_CITY, BRAND_MODEL])["cr"].rank(
        ascending=False, method="dense"
    )
    return df

# ======================
# Compare helper
# ======================
def build_compare(last, current):
    df = last.merge(
        current,
        on=["hotel_key", RES_CITY, BRAND_MODEL],
        suffixes=("_last", "_current"),
        how="outer"
    ).fillna(0)

    df["rank_change"] = df["rank_last"] - df["rank_current"]

    for col in ["checkin", "signup", "cr"]:
        df[f"{col}_change_%"] = np.where(
            df[f"{col}_last"] == 0,
            0,
            (df[f"{col}_current"] / df[f"{col}_last"]) - 1
        )

    return df

# ======================
# Column ordering
# ======================
def reorder_columns(df):
    df = df.copy()
    df["hotel_key"] = df["hotel_key"].str.upper()

    cols = [
        "hotel_key", RES_CITY, BRAND_MODEL,
        "rank_last", "rank_current", "rank_change",
        "checkin_last", "checkin_current", "checkin_change_%",
        "signup_last", "signup_current", "signup_change_%",
        "cr_last", "cr_current", "cr_change_%"
    ]
    return df[[c for c in cols if c in df.columns]]

# ======================
# Styling
# ======================
def color_change(val):
    try:
        val = float(val)
    except:
        return ""

    if val <= -0.3:
        return "background-color:#e74c3c;color:white;"
    elif val <= -0.05:
        return "background-color:#f39c12;"
    elif val < 0.05:
        return ""
    elif val < 0.3:
        return "background-color:#2ecc71;"
    else:
        return "background-color:#27ae60;color:white;"

def style_df(df):
    styler = df.style.format({
        "rank_last": "{:.0f}",
        "rank_current": "{:.0f}",
        "rank_change": "{:.0f}",
        "checkin_last": "{:.0f}",
        "checkin_current": "{:.0f}",
        "checkin_change_%": "{:.2%}",
        "signup_last": "{:.0f}",
        "signup_current": "{:.0f}",
        "signup_change_%": "{:.2%}",
        "cr_last": "{:.2f}",
        "cr_current": "{:.2f}",
        "cr_change_%": "{:.2%}",
    })

    return styler.applymap(color_change, subset=["cr_change_%"])

# ======================================================
# TABS
# ======================================================
tab_global, tab_city_overview, tab_city_rank, tab_city_brand, tab_chart, tab_insight = st.tabs([
    "📊 Global Ranking",
    "🏙️ City Performance Overview",
    "🏙️ City-level Ranking",
    "🏷️ City × Brand Model Ranking",
    "📈 Chart",
    "💡 Insight"
])


# ======================
# TAB 1 – Global
# ======================
with tab_global:
    df = reorder_columns(
        build_compare(
            add_global_rank(last_df),
            add_global_rank(current_df)
        ).sort_values("rank_current")
    )
    st.dataframe(style_df(df), use_container_width=True, hide_index=True)
    
# ======================
# TAB 2 – City Overview
# ======================
with tab_city_overview:
    st.subheader("🏙️ City Performance Overview (Last vs Current)")

    city_last = (
        last_df
        .groupby(RES_CITY)[["checkin", "signup"]]
        .sum()
        .reset_index()
    )

    city_cur = (
        current_df
        .groupby(RES_CITY)[["checkin", "signup"]]
        .sum()
        .reset_index()
    )

    city = (
        city_last
        .merge(city_cur, on=RES_CITY, suffixes=("_last", "_current"))
        .fillna(0)
    )

    city["cr_last"] = np.where(
        city["checkin_last"] == 0, 0,
        city["signup_last"] / city["checkin_last"] * 100
    )

    city["cr_current"] = np.where(
        city["checkin_current"] == 0, 0,
        city["signup_current"] / city["checkin_current"] * 100
    )

    city["cr_change_%"] = np.where(
        city["cr_last"] == 0, 0,
        (city["cr_current"] / city["cr_last"]) - 1
    )

    # 👉 FORCE CITY ORDER
    city[RES_CITY] = (
        city[RES_CITY]
        .astype(str)
        .str.upper()
    )

    city[RES_CITY] = pd.Categorical(
        city[RES_CITY],
        categories=CITY_ORDER,
        ordered=True
    )

    city = city.sort_values(RES_CITY)

    st.dataframe(
        style_df(city),
        use_container_width=True,
        hide_index=True
    )


# ======================
# TAB 3 – City Ranking
# ======================
with tab_city_rank:
    st.subheader("🏙️ City-level Ranking (Current Week)")

    df = build_compare(
        add_city_rank(last_df),
        add_city_rank(current_df)
    )

    # normalize city
    df[RES_CITY] = (
        df[RES_CITY]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df[RES_CITY] = pd.Categorical(
        df[RES_CITY],
        categories=CITY_ORDER,
        ordered=True
    )

    for city, cdf in (
        df
        .sort_values(RES_CITY)
        .groupby(RES_CITY, sort=False)
    ):
        st.markdown(f"### 📍 {city}")
        st.dataframe(
            style_df(
                reorder_columns(
                    cdf.sort_values("rank_current")
                )
            ),
            use_container_width=True,
            hide_index=True
        )


# ======================
# TAB 4 – City × Brand
# ======================
with tab_city_brand:
    st.subheader("🏷️ City × Brand Model Ranking (Current Week)")

    df = build_compare(
        add_city_brand_rank(last_df),
        add_city_brand_rank(current_df)
    ).copy()

    # normalize
    df[RES_CITY] = (
        df[RES_CITY]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df[BRAND_MODEL] = (
        df[BRAND_MODEL]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    # 👉 FORCE ORDER
    df[RES_CITY] = pd.Categorical(
        df[RES_CITY],
        categories=CITY_ORDER,
        ordered=True
    )

    df[BRAND_MODEL] = pd.Categorical(
        df[BRAND_MODEL],
        categories=BRAND_ORDER,
        ordered=True
    )

    for city, city_df in (
        df
        .sort_values(RES_CITY)
        .groupby(RES_CITY, sort=False)
    ):
        st.markdown(f"## 📍 {city}")

        city_df = city_df.sort_values([BRAND_MODEL, "rank_current"])

        for bm, bm_df in city_df.groupby(BRAND_MODEL, sort=False):
            if bm_df["checkin_current"].sum() == 0:
                continue

            st.markdown(f"### 🏷️ Brand Model: {bm}")
            st.dataframe(
                style_df(reorder_columns(bm_df)),
                use_container_width=True,
                hide_index=True
            )


# ======================
# TAB (New) – Chart
# ======================
with tab_chart:
    st.subheader("📈 Performance Charts (Last + Current Period)")

    # --- Filter Logic ---
    c1, c2 = st.columns(2)
    
    # 1. City Filter
    with c1:
        # Get unique cities from res_df
        all_cities = sorted(res_df[RES_CITY].dropna().unique()) if not res_df.empty else []
        selected_cities = st.multiselect("🏙️ Filter by City", options=all_cities)

    # 2. Hotel Mapping
    hotels_map = {}
    city_hotel_map = {} 

    if not res_df.empty:
        # Get hotel mapping and city association
        temp = res_df[[RES_HOTEL, "hotel_key", RES_CITY]].drop_duplicates("hotel_key")
        hotels_map.update(dict(zip(temp["hotel_key"], temp[RES_HOTEL])))
        city_hotel_map.update(dict(zip(temp["hotel_key"], temp[RES_CITY])))

    if not signup_df.empty:
        temp = signup_df[[SIGNUP_HOTEL, "hotel_key"]].drop_duplicates("hotel_key")
        for k, v in zip(temp["hotel_key"], temp[SIGNUP_HOTEL]):
            if k not in hotels_map:
                hotels_map[k] = v
                
    all_hotel_keys = sorted(hotels_map.keys())
    
    # 3. Filter Constraints
    if selected_cities:
        available_hotel_keys = [
            k for k in all_hotel_keys 
            if city_hotel_map.get(k) in selected_cities
        ]
    else:
        available_hotel_keys = all_hotel_keys

    with c2:
        selected_hotels = st.multiselect(
            "🏨 Filter by Hotel",
            options=available_hotel_keys,
            format_func=lambda x: hotels_map.get(x, x.title())
        )
    
    # 4. Determine Final Filter Mask
    final_filter_hotels = []
    if selected_hotels:
        final_filter_hotels = selected_hotels
    elif selected_cities:
        final_filter_hotels = available_hotel_keys
    
    # --------------------
    
    # Define Date Ranges
    # We want a continuous view from min(last_from) to max(current_to)
    chart_start = last_from
    chart_end = current_to
    
    # Display date range
    st.info(f"📅 Visualizing Data from: **{chart_start}** → **{chart_end}**")
    
    # Get daily data
    # Checkins
    res_range = filter_period(res_df, RES_DATE, chart_start, chart_end)
    
    if final_filter_hotels:
        res_range = res_range[res_range["hotel_key"].isin(final_filter_hotels)]

    daily_res = (
        res_range.groupby(res_range[RES_DATE].dt.date)[RES_TENANT]
        .nunique()
        .reset_index(name="checkin")
    )
    daily_res.columns = ["date", "checkin"]
    
    # Signups
    signup_range = filter_period(signup_df, SIGNUP_DATE, chart_start, chart_end)
    
    if final_filter_hotels:
        signup_range = signup_range[signup_range["hotel_key"].isin(final_filter_hotels)]

    daily_signup = (
        signup_range.groupby(signup_range[SIGNUP_DATE].dt.date)[SIGNUP_COUNT]
        .sum()
        .reset_index(name="signup")
    )
    daily_signup.columns = ["date", "signup"]
    
    # Merge
    chart_df = pd.merge(daily_res, daily_signup, on="date", how="outer").fillna(0)
    chart_df["date"] = pd.to_datetime(chart_df["date"])
    chart_df = chart_df.sort_values("date")
    
    if not chart_df.empty:
        chart_df["cr"] = np.where(
            chart_df["checkin"] > 0, 
            (chart_df["signup"] / chart_df["checkin"] * 100), 
            0
        )
        
        # Determine Period Boundary (End of Last Period)
        # Use timestamp (milliseconds) to avoid Plotly calculation errors with strings/Timestamps
        period_boundary = pd.to_datetime(last_to).timestamp() * 1000
        
        # CHART 1: Checkin & Signup
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=chart_df["date"], y=chart_df["checkin"], 
            name="Checkin", mode="lines+markers+text",
            line=dict(color="#3498db", width=3),
            text=chart_df["checkin"].apply(lambda x: f"{int(x)}" if x > 0 else ""),
            textposition="top center"
        ))
        fig1.add_trace(go.Scatter(
            x=chart_df["date"], y=chart_df["signup"], 
            name="Signup", mode="lines+markers+text",
            line=dict(color="#2ecc71", width=3),
            text=chart_df["signup"].apply(lambda x: f"{int(x)}" if x > 0 else ""),
            textposition="top center"
        ))
        
        # Add Boundary Line
        fig1.add_vline(
            x=period_boundary, line_width=2, line_dash="dash", line_color="#bdc3c7",
            annotation_text="End of Last Period", 
            annotation_position="top left"
        )
        
        fig1.update_layout(
            title="📊 Daily Check-in & Sign-up",
            xaxis_title="Date",
            yaxis_title="Count",
            hovermode="x unified",
            xaxis=dict(
                tickmode="linear",
                dtick=86400000.0, # 1 day
                tickformat="%d-%b"
            ),
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        st.markdown("---")
        
        # CHART 2: Conversion Rate (CR)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=chart_df["date"], y=chart_df["cr"], 
            name="CR %", mode="lines+markers+text",
            line=dict(color="#e67e22", width=3),
            text=chart_df["cr"].apply(lambda x: f"{x:.1f}%" if x > 0 else ""),
            textposition="top center"
        ))
        
        # Add Boundary Line
        fig2.add_vline(
            x=period_boundary, line_width=2, line_dash="dash", line_color="#bdc3c7",
            annotation_text="End of Last Period", 
            annotation_position="top left"
        )
        
        fig2.update_layout(
            title="📉 Daily Conversion Rate (CR)",
            xaxis_title="Date",
            yaxis_title="CR (%)",
            hovermode="x unified",
            xaxis=dict(
                tickmode="linear",
                dtick=86400000.0, # 1 day
                tickformat="%d-%b"
            ),
            height=500
        )
        st.plotly_chart(fig2, use_container_width=True)
        
    else:
        st.warning("No data found for the selected date range.")


# ======================
# TAB 5 – Insight
# ======================
with tab_insight:
    st.subheader("� Analysis by Brand × Booking Source (Last vs Current)")
    
    # Check if required columns exist in res_df
    booking_source_col = None
    signup_status_col = None
    guest_country_col = None
    
    # Try to find the columns
    for col in res_df.columns:
        col_lower = col.lower()
        if "booking" in col_lower and "source" in col_lower:
            booking_source_col = col
        if "sign" in col_lower and "status" in col_lower and "v2" in col_lower:
            signup_status_col = col
        if "guest" in col_lower and "country" in col_lower:
            guest_country_col = col
    
    # Show column finder
    st.markdown("#### 📋 Column Mapping")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        booking_source_col = st.selectbox(
            "Booking Source Column",
            options=res_df.columns.tolist(),
            index=res_df.columns.tolist().index(booking_source_col) if booking_source_col else 0,
            key="insight_booking_source"
        )
    
    with col2:
        signup_status_col = st.selectbox(
            "Sign-up Status v2 Column",
            options=res_df.columns.tolist(),
            index=res_df.columns.tolist().index(signup_status_col) if signup_status_col else 0,
            key="insight_signup_status"
        )
    
    with col3:
        guest_country_col = st.selectbox(
            "Guest Country Column",
            options=res_df.columns.tolist(),
            index=res_df.columns.tolist().index(guest_country_col) if guest_country_col else 0,
            key="insight_guest_country"
        )
    
    st.markdown("---")
    
    if booking_source_col and signup_status_col and guest_country_col:
        
        # Display date ranges
        st.info(f"📅 **Date Range Comparison:**\n\n**Last Period:** {last_from} → {last_to}\n\n**Current Period:** {current_from} → {current_to}")
        
        def build_comparison_table(last_df, current_df, status_filter, title):
            """Build comparison table with Last vs Current for specific status group"""
            
            st.markdown(f"### {title}")
           
            # Debug: Show available statuses if no data found
            # st.write(f"DEBUG: Searching for {status_filter}")
            # st.write(f"DEBUG: Available statuses in Last: {last_df[signup_status_col].unique()}")
            # st.write(f"DEBUG: Available statuses in Current: {current_df[signup_status_col].unique()}")
            
            # Filter by status (with loose matching)
            def loose_filter(df, statuses):
                # Optimize: Check if column is string type
                if df[signup_status_col].dtype == object:
                    # Create normalized version for matching:
                    # 1. Convert to string
                    # 2. Replace non-breaking space (\xa0) with regular space
                    # 3. Strip leading/trailing whitespace
                    normalized_status = (
                        df[signup_status_col]
                        .astype(str)
                        .str.replace("\xa0", " ", regex=False)
                        .str.strip()
                    )
                    
                    # Normalize target statuses as well
                    target_statuses = [s.replace("\xa0", " ").strip() for s in statuses]
                    
                    mask = normalized_status.isin(target_statuses)
                else:
                    mask = df[signup_status_col].isin(statuses)
                return df[mask].copy()

            last_filtered = loose_filter(last_df, status_filter)
            current_filtered = loose_filter(current_df, status_filter)
            
            if len(last_filtered) == 0 and len(current_filtered) == 0:
                st.warning(f"No data available for statuses: {', '.join(status_filter)}")
                st.info(f"💡 Hint: Check exact spelling. Found in data: {sorted(list(set(last_df[signup_status_col].unique()) | set(current_df[signup_status_col].unique())))}")
                return
            
            def prepare_data(df):
                if len(df) == 0:
                    return pd.DataFrame()
                
                df = df.copy()
                
                # Create DOM/INT column
                df["Market"] = df[guest_country_col].apply(
                    lambda x: "DOM" if str(x).strip().lower() == "vietnam" else "INT"
                )
                
                # Normalize Brand Model
                df[BRAND_MODEL] = df[BRAND_MODEL].astype(str).str.lower().str.strip()
                
                # Normalize Booking Source - handle NaN
                df[booking_source_col] = df[booking_source_col].fillna("Unknown").astype(str)
                
                # Count unique tenants
                pivot_data = (
                    df.groupby([BRAND_MODEL, booking_source_col, "Market"])[RES_TENANT]
                    .nunique()
                    .reset_index(name="count")
                )
                
                # Create pivot table
                pivot_table = pivot_data.pivot_table(
                    index=[BRAND_MODEL, booking_source_col],
                    columns="Market",
                    values="count",
                    aggfunc="sum",
                    fill_value=0
                )
                
                # Ensure DOM and INT columns exist
                if "DOM" not in pivot_table.columns:
                    pivot_table["DOM"] = 0
                if "INT" not in pivot_table.columns:
                    pivot_table["INT"] = 0
                
                pivot_table["Total"] = pivot_table["DOM"] + pivot_table["INT"]
                
                return pivot_table
            
            last_pivot = prepare_data(last_filtered)
            current_pivot = prepare_data(current_filtered)
            
            # Merge last and current
            if len(last_pivot) == 0 and len(current_pivot) == 0:
                st.warning("No data after processing")
                return
                
            if len(last_pivot) == 0:
                last_pivot = pd.DataFrame(columns=["DOM", "INT", "Total"])
            if len(current_pivot) == 0:
                current_pivot = pd.DataFrame(columns=["DOM", "INT", "Total"])
            
            # Get all unique indices
            all_indices = last_pivot.index.union(current_pivot.index)
            
            # Reindex both dataframes
            last_pivot = last_pivot.reindex(all_indices, fill_value=0)
            current_pivot = current_pivot.reindex(all_indices, fill_value=0)
            
            # Create comparison dataframe
            comparison_df = pd.DataFrame({
                "DOM_last": last_pivot["DOM"],
                "DOM_current": current_pivot["DOM"],
                "INT_last": last_pivot["INT"],
                "INT_current": current_pivot["INT"],
                "Total_last": last_pivot["Total"],
                "Total_current": current_pivot["Total"]
            })
            
            # Calculate changes
            comparison_df["DOM_change_%"] = np.where(
                comparison_df["DOM_last"] == 0, 0,
                (comparison_df["DOM_current"] / comparison_df["DOM_last"]) - 1
            )
            comparison_df["INT_change_%"] = np.where(
                comparison_df["INT_last"] == 0, 0,
                (comparison_df["INT_current"] / comparison_df["INT_last"]) - 1
            )
            comparison_df["Total_change_%"] = np.where(
                comparison_df["Total_last"] == 0, 0,
                (comparison_df["Total_current"] / comparison_df["Total_last"]) - 1
            )
            
            # Reset index
            display_df = comparison_df.reset_index()
            
            # Force categorical ordering for Brand Model
            display_df[BRAND_MODEL] = pd.Categorical(
                display_df[BRAND_MODEL],
                categories=BRAND_ORDER,
                ordered=True
            )
            display_df = display_df.sort_values(BRAND_MODEL)
            
            display_df.columns = [
                "Brand Segment", "Booking Source",
                "DOM_last", "DOM_current", "INT_last", "INT_current",
                "Total_last", "Total_current",
                "DOM_change_%", "INT_change_%", "Total_change_%"
            ]
            
            # Reorder columns
            display_df = display_df[[
                "Brand Segment", "Booking Source",
                "DOM_last", "DOM_current", "DOM_change_%",
                "INT_last", "INT_current", "INT_change_%",
                "Total_last", "Total_current", "Total_change_%"
            ]]
            
            # Add subtotals
            final_rows = []
            
            # Calculate Grand Total first
            total_last_sum_all = display_df["Total_last"].sum()
            total_current_sum_all = display_df["Total_current"].sum()
            
            for brand in display_df["Brand Segment"].unique():
                brand_df = display_df[display_df["Brand Segment"] == brand].copy()
                if len(brand_df) == 0: continue
                    
                final_rows.append(brand_df)
                
                # Calculate brand totals
                dom_last_sum = brand_df["DOM_last"].sum()
                dom_current_sum = brand_df["DOM_current"].sum()
                int_last_sum = brand_df["INT_last"].sum()
                int_current_sum = brand_df["INT_current"].sum()
                total_last_sum = brand_df["Total_last"].sum()
                total_current_sum = brand_df["Total_current"].sum()
                
                total_row = pd.DataFrame({
                    "Brand Segment": [f"📊 {brand} Total"],
                    "Booking Source": [""],
                    "DOM_last": [dom_last_sum],
                    "DOM_current": [dom_current_sum],
                    "DOM_change_%": [(dom_current_sum / dom_last_sum - 1) if dom_last_sum > 0 else 0],
                    "INT_last": [int_last_sum],
                    "INT_current": [int_current_sum],
                    "INT_change_%": [(int_current_sum / int_last_sum - 1) if int_last_sum > 0 else 0],
                    "Total_last": [total_last_sum],
                    "Total_current": [total_current_sum],
                    "Total_change_%": [(total_current_sum / total_last_sum - 1) if total_last_sum > 0 else 0]
                })
                final_rows.append(total_row)
            
            if not final_rows:
                st.warning("No data rows generated.")
                return

            final_df = pd.concat(final_rows, ignore_index=True)
            
            # Style functions
            def highlight_totals(row):
                if "Total" in str(row["Brand Segment"]):
                    return ["background-color: #2c3e50; font-weight: bold;"] * len(row)
                return [""] * len(row)
            
            def color_change(val):
                try:
                    val = float(val)
                except:
                    return ""
                if pd.isna(val): return ""
                if val <= -0.3:
                    return "background-color:#e74c3c;color:white;"
                elif val <= -0.05:
                    return "background-color:#f39c12;"
                elif val < 0.05:
                    return ""
                elif val < 0.3:
                    return "background-color:#2ecc71;"
                else:
                    return "background-color:#27ae60;color:white;"
            
            styled_df = final_df.style.apply(highlight_totals, axis=1).format({
                "DOM_last": "{:.0f}",
                "DOM_current": "{:.0f}",
                "DOM_change_%": "{:.1%}",
                "INT_last": "{:.0f}",
                "INT_current": "{:.0f}",
                "INT_change_%": "{:.1%}",
                "Total_last": "{:.0f}",
                "Total_current": "{:.0f}",
                "Total_change_%": "{:.1%}"
            }, na_rep="0").applymap(
                color_change,
                subset=["DOM_change_%", "INT_change_%", "Total_change_%"]
            )
            
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                height=500
            )
        
        # Filter data for Last and Current periods
        last_res = filter_period(res_df, RES_DATE, last_from, last_to)
        current_res = filter_period(res_df, RES_DATE, current_from, current_to)
        
        # Define status groups
        # Table 1: Chưa Sign-up
        build_comparison_table(last_res, current_res, ["Chưa Sign-up"], "1️⃣ Chưa Sign-up")
        st.markdown("---")
        
        # Table 2: Đã Sign-up từ trước
        build_comparison_table(last_res, current_res, ["Đã Sign-up từ trước"], "2️⃣ Đã Sign-up từ trước")
        st.markdown("---")
        
        # Table 3: Sign-up related to Check-in
        group3 = ["Sign-up sau C/I", "Sign up trước 1 ngày check in", "Sign up trước 2 ngày check in"]
        build_comparison_table(last_res, current_res, group3, "3️⃣ Sign-up liên quan Check-in")
        
    else:
        st.warning("⚠️ Please select the required columns to generate the insight tables.")
