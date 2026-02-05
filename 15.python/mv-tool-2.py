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
tab_global, tab_city_overview, tab_city_rank, tab_city_brand, tab_insight = st.tabs([
    "📊 Global Ranking",
    "🏙️ City Performance Overview",
    "🏙️ City-level Ranking",
    "🏷️ City × Brand Model Ranking",
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
    # Line Chart Visualization
    # ======================
    st.subheader("📈 Metrics Trend Visualization")
    
    # Hotel selection
    available_hotels = sorted(df["hotel_key"].unique())
    selected_hotels = st.multiselect(
        "Select hotels to visualize:",
        options=available_hotels,
        default=available_hotels[:3] if len(available_hotels) >= 3 else available_hotels
    )
    
    if selected_hotels:
        # Prepare daily data for selected hotels
        def build_daily_metrics(res, signup, date_col_res, date_col_signup):
            """Build daily metrics for checkin, signup, and CR"""
            # Daily checkin
            daily_checkin = (
                res.groupby(["hotel_key", date_col_res])[RES_TENANT]
                .nunique()
                .reset_index(name="checkin")
            )
            daily_checkin["date"] = daily_checkin[date_col_res]
            
            # Daily signup
            daily_signup = (
                signup.groupby(["hotel_key", date_col_signup])[SIGNUP_COUNT]
                .sum()
                .reset_index(name="signup")
            )
            daily_signup["date"] = daily_signup[date_col_signup]
            
            # Merge
            daily = daily_checkin.merge(
                daily_signup[["hotel_key", "date", "signup"]], 
                on=["hotel_key", "date"], 
                how="outer"
            ).fillna(0)
            
            # Calculate CR
            daily["cr"] = np.where(
                daily["checkin"] == 0, 0,
                (daily["signup"] / daily["checkin"] * 100)
            )
            
            return daily[["hotel_key", "date", "checkin", "signup", "cr"]]
        
        # Get daily data for last period
        last_res = filter_period(res_df, RES_DATE, last_from, last_to)
        last_signup = filter_period(signup_df, SIGNUP_DATE, last_from, last_to)
        last_daily = build_daily_metrics(last_res, last_signup, RES_DATE, SIGNUP_DATE)
        last_daily["period"] = "last"
        
        # Get daily data for current period
        current_res = filter_period(res_df, RES_DATE, current_from, current_to)
        current_signup = filter_period(signup_df, SIGNUP_DATE, current_from, current_to)
        current_daily = build_daily_metrics(current_res, current_signup, RES_DATE, SIGNUP_DATE)
        current_daily["period"] = "current"
        
        # Combine both periods
        combined_daily = pd.concat([last_daily, current_daily], ignore_index=True)
        
        # Filter for selected hotels
        chart_data = combined_daily[combined_daily["hotel_key"].isin([h.lower() for h in selected_hotels])].copy()
        
        # Calculate cumulative metrics for smoother visualization
        chart_data = chart_data.sort_values(["hotel_key", "date"])
        
        # Calculate percentage changes (comparing to baseline - first day of last period)
        chart_list = []
        for hotel in chart_data["hotel_key"].unique():
            hotel_data = chart_data[chart_data["hotel_key"] == hotel].copy()
            hotel_data = hotel_data.sort_values("date")
            
            # Get baseline (average of first 3 days of last period or first day if less)
            baseline_data = hotel_data[hotel_data["period"] == "last"].head(3)
            if len(baseline_data) == 0:
                continue
                
            baseline_checkin = baseline_data["checkin"].mean() if baseline_data["checkin"].mean() > 0 else 1
            baseline_signup = baseline_data["signup"].mean() if baseline_data["signup"].mean() > 0 else 1
            baseline_cr = baseline_data["cr"].mean() if baseline_data["cr"].mean() > 0 else 1
            
            # Calculate percentage change from baseline
            hotel_data["checkin_change_%"] = ((hotel_data["checkin"] / baseline_checkin) - 1) * 100
            hotel_data["signup_change_%"] = ((hotel_data["signup"] / baseline_signup) - 1) * 100
            hotel_data["cr_change_%"] = ((hotel_data["cr"] / baseline_cr) - 1) * 100
            
            chart_list.append(hotel_data)
        
        if chart_list:
            chart_data = pd.concat(chart_list, ignore_index=True)
            chart_data["hotel_key"] = chart_data["hotel_key"].str.upper()
            
            # Create the line chart with Plotly
            fig = go.Figure()
            
            # Define colors for each metric type
            metric_colors = {
                "checkin": "#3498db",  # Blue
                "signup": "#2ecc71",   # Green
                "cr": "#e67e22"        # Orange
            }
            
            for idx, hotel in enumerate(sorted(chart_data["hotel_key"].unique())):
                hotel_data = chart_data[chart_data["hotel_key"] == hotel].sort_values("date")
                
                # Checkin change line
                fig.add_trace(go.Scatter(
                    x=hotel_data["date"],
                    y=hotel_data["checkin_change_%"],
                    name=f"{hotel} - Checkin Change",
                    mode="lines+markers",
                    line=dict(color=metric_colors["checkin"], width=2),
                    marker=dict(size=6),
                    legendgroup="checkin",
                    legendgrouptitle_text="Checkin Change",
                    customdata=hotel_data[["checkin", "signup", "cr"]].values,
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>" +
                        "Date: %{x|%Y-%m-%d}<br>" +
                        "Change: %{y:.2f}%<br>" +
                        "Checkin: %{customdata[0]:.0f}<br>" +
                        "Signup: %{customdata[1]:.0f}<br>" +
                        "CR: %{customdata[2]:.2f}%<br>" +
                        "<extra></extra>"
                    )
                ))
                
                # Signup change line
                fig.add_trace(go.Scatter(
                    x=hotel_data["date"],
                    y=hotel_data["signup_change_%"],
                    name=f"{hotel} - Signup Change",
                    mode="lines+markers",
                    line=dict(color=metric_colors["signup"], width=2),
                    marker=dict(size=6),
                    legendgroup="signup",
                    legendgrouptitle_text="Signup Change",
                    customdata=hotel_data[["checkin", "signup", "cr"]].values,
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>" +
                        "Date: %{x|%Y-%m-%d}<br>" +
                        "Change: %{y:.2f}%<br>" +
                        "Checkin: %{customdata[0]:.0f}<br>" +
                        "Signup: %{customdata[1]:.0f}<br>" +
                        "CR: %{customdata[2]:.2f}%<br>" +
                        "<extra></extra>"
                    )
                ))
                
                # CR change line
                fig.add_trace(go.Scatter(
                    x=hotel_data["date"],
                    y=hotel_data["cr_change_%"],
                    name=f"{hotel} - CR Change",
                    mode="lines+markers",
                    line=dict(color=metric_colors["cr"], width=2),
                    marker=dict(size=6),
                    legendgroup="cr",
                    legendgrouptitle_text="CR Change",
                    customdata=hotel_data[["checkin", "signup", "cr"]].values,
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>" +
                        "Date: %{x|%Y-%m-%d}<br>" +
                        "Change: %{y:.2f}%<br>" +
                        "Checkin: %{customdata[0]:.0f}<br>" +
                        "Signup: %{customdata[1]:.0f}<br>" +
                        "CR: %{customdata[2]:.2f}%<br>" +
                        "<extra></extra>"
                    )
                ))
            
            # Add vertical line to separate periods
            if len(last_daily) > 0 and len(current_daily) > 0:
                last_end = pd.to_datetime(last_daily["date"].max())
                # Use add_shape instead of add_vline to avoid datetime issues
                fig.add_shape(
                    type="line",
                    x0=last_end,
                    x1=last_end,
                    y0=0,
                    y1=1,
                    yref="paper",
                    line=dict(color="gray", width=2, dash="dash")
                )
                # Add annotation separately
                fig.add_annotation(
                    x=last_end,
                    y=1,
                    yref="paper",
                    text="Period Boundary",
                    showarrow=False,
                    yshift=10
                )
            
            # Update layout
            fig.update_layout(
                title="Metrics Change Over Time (% change from baseline)",
                xaxis_title="Date",
                yaxis_title="Change (%)",
                hovermode="x unified",
                height=600,
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                )
            )
            
            # Add zero line
            fig.add_hline(y=0, line_dash="solid", line_color="black", line_width=1, opacity=0.3)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Add legend explanation
            st.caption("📊 **Chart Legend:** 🔵 Blue = Checkin Change | 🟢 Green = Signup Change | 🟠 Orange = CR Change")
        else:
            st.warning("No data available for the selected hotels in the chosen date range.")
    else:
        st.info("👆 Please select at least one hotel to visualize the metrics.")

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
# TAB 5 – Insight
# ======================
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
