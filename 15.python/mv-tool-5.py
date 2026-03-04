import streamlit as st
import pandas as pd

TIER_ORDER = ["New Citizen", "Silver Citizen", "Gold Citizen", "Platinum Citizen"]

st.title("Revenue by Guest Tier")

uploaded_file = st.file_uploader("Upload raw data", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df["Stay Date"] = pd.to_datetime(df["Stay Date"])

    st.subheader("Select date range")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start date", df["Stay Date"].min())
    with col2:
        end_date = st.date_input("End date", df["Stay Date"].max())

    filtered_df = df[
        (df["Stay Date"] >= pd.to_datetime(start_date))
        & (df["Stay Date"] <= pd.to_datetime(end_date))
    ]

    tier_revenue = (
        filtered_df
        .groupby("Guest Citizen Level")["Revenue"]
        .sum()
        .reset_index()
    )

    tier_revenue["Guest Citizen Level"] = pd.Categorical(
        tier_revenue["Guest Citizen Level"],
        categories=TIER_ORDER,
        ordered=True,
    )
    tier_revenue = tier_revenue.sort_values("Guest Citizen Level")

    total_revenue = tier_revenue["Revenue"].sum()
    tier_revenue["contribution_%"] = (
        tier_revenue["Revenue"] / total_revenue * 100
    ).round(2)

    tier_revenue.columns = ["tier", "revenue", "contribution_%"]

    display_df = tier_revenue.copy()
    display_df["revenue"] = display_df["revenue"].apply(lambda x: f"{x:,.0f}")
    display_df["contribution_%"] = display_df["contribution_%"].apply(lambda x: f"{x}%")

    st.subheader("Revenue by Tier")
    st.dataframe(display_df, use_container_width=True)
    st.metric("Total Revenue", f"{total_revenue:,.0f}")

    st.subheader("Revenue Distribution")
    st.bar_chart(tier_revenue.set_index("tier")["revenue"])

    # --- Section 2: KPI by Tier ---
    st.divider()
    st.subheader("KPI by Tier")

    tier_kpi = (
        filtered_df
        .groupby("Guest Citizen Level")
        .agg(
            bookings=("Reservation No", "nunique"),
            total_revenue=("Revenue", "sum"),
            total_room_nights=("Room Night", "sum"),
        )
        .reindex(TIER_ORDER)
        .reset_index()
    )
    tier_kpi["avg_revenue_per_booking"] = (
        tier_kpi["total_revenue"] / tier_kpi["bookings"]
    ).round(0)
    tier_kpi["avg_room_night"] = (
        tier_kpi["total_room_nights"] / tier_kpi["bookings"]
    ).round(1)

    display_kpi = tier_kpi.copy()
    display_kpi.columns = [
        "Tier", "Bookings", "Total Revenue",
        "Room Nights", "Avg Revenue/Booking", "Avg Room Night",
    ]
    for col in ["Total Revenue", "Avg Revenue/Booking"]:
        display_kpi[col] = display_kpi[col].apply(lambda x: f"{x:,.0f}")
    st.dataframe(display_kpi, use_container_width=True, hide_index=True)

    # --- Section 3: Revenue Breakdown by Tier ---
    st.divider()
    st.subheader("Revenue Breakdown by Tier")

    rev_cols = {
        "Room rent only": "Room Rent",
        "Total Service Cost": "Service",
        "Total Breakfast Cost": "Breakfast",
        "Other Revenue": "Other",
    }
    rev_breakdown = (
        filtered_df
        .groupby("Guest Citizen Level")[list(rev_cols.keys())]
        .sum()
        .reindex(TIER_ORDER)
        .reset_index()
    )
    rev_breakdown.columns = ["Tier"] + list(rev_cols.values())

    display_rev = rev_breakdown.copy()
    for col in rev_cols.values():
        display_rev[col] = display_rev[col].apply(lambda x: f"{x:,.0f}")
    st.dataframe(display_rev, use_container_width=True, hide_index=True)

    chart_rev = rev_breakdown.set_index("Tier")
    st.bar_chart(chart_rev)

    # --- Section 4: Guest Return Status by Tier ---
    st.divider()
    st.subheader("New vs Returning Guests by Tier")

    return_df = (
        filtered_df
        .groupby(["Guest Citizen Level", "Guest Return Status"])["Reservation No"]
        .nunique()
        .unstack(fill_value=0)
        .reindex(TIER_ORDER)
        .reset_index()
    )
    return_df.rename(columns={"Guest Citizen Level": "Tier"}, inplace=True)

    display_return = return_df.copy()
    total_per_tier = display_return.select_dtypes("number").sum(axis=1)
    for col in display_return.columns[1:]:
        pct = (display_return[col] / total_per_tier * 100).round(1)
        display_return[col] = display_return[col].astype(str) + " (" + pct.astype(str) + "%)"
    st.dataframe(display_return, use_container_width=True, hide_index=True)

    # --- Section 5: Booking Channel by Tier ---
    st.divider()
    st.subheader("Booking Channel by Tier")

    channel_df = (
        filtered_df
        .groupby(["Guest Citizen Level", "Booking Source"])["Revenue"]
        .sum()
        .unstack(fill_value=0)
        .reindex(TIER_ORDER)
        .reset_index()
    )
    channel_df.rename(columns={"Guest Citizen Level": "Tier"}, inplace=True)

    display_channel = channel_df.copy()
    for col in display_channel.columns[1:]:
        display_channel[col] = display_channel[col].apply(lambda x: f"{x:,.0f}")
    st.dataframe(display_channel, use_container_width=True, hide_index=True)

    chart_channel = channel_df.set_index("Tier")
    st.bar_chart(chart_channel)

    # --- Section 6: Revenue Trend by Tier (Monthly) ---
    st.divider()
    st.subheader("Monthly Revenue Trend by Tier")

    filtered_df["Month"] = filtered_df["Stay Date"].dt.to_period("M").astype(str)
    trend_df = (
        filtered_df
        .groupby(["Month", "Guest Citizen Level"])["Revenue"]
        .sum()
        .unstack(fill_value=0)
        .reindex(columns=TIER_ORDER)
    )
    st.line_chart(trend_df)

    # --- Section 7: Hotel Performance by Tier ---
    st.divider()
    st.subheader("Top Hotels by Tier Revenue")

    hotel_tier = (
        filtered_df
        .groupby(["Hotel Name", "Guest Citizen Level"])["Revenue"]
        .sum()
        .unstack(fill_value=0)
        .reindex(columns=TIER_ORDER)
        .reset_index()
    )
    hotel_tier["Total"] = hotel_tier[TIER_ORDER].sum(axis=1)
    hotel_tier = hotel_tier.sort_values("Total", ascending=False)

    display_hotel = hotel_tier.copy()
    for col in TIER_ORDER + ["Total"]:
        display_hotel[col] = display_hotel[col].apply(lambda x: f"{x:,.0f}")
    st.dataframe(display_hotel, use_container_width=True, hide_index=True)
