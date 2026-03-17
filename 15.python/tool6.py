import streamlit as st
import pandas as pd

st.set_page_config(page_title="Hotel Price Availability Analyzer", layout="wide")
st.title("Hotel Price Availability Analyzer")

PRICE_COLS = ["price_w1", "price_w2", "price_w3", "price_w4", "price_w5", "price_w6"]

uploaded_files = st.file_uploader("Upload CSV files", type=["csv"], accept_multiple_files=True)

if uploaded_files:
    dfs = [pd.read_csv(f, keep_default_na=False) for f in uploaded_files]
    df = pd.concat(dfs, ignore_index=True)

    # Normalize: strip whitespace
    for col in PRICE_COLS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    total_cells = len(df) * len(PRICE_COLS)

    # Count per cell
    def count_status(df, status):
        mask = df[PRICE_COLS].apply(lambda col: col.str.upper() == status.upper())
        return mask.sum().sum()

    na_count = count_status(df, "NA")
    sold_out_count = count_status(df, "SOLD OUT")
    available_count = total_cells - na_count - sold_out_count

    na_rate = na_count / total_cells * 100
    sold_out_rate = sold_out_count / total_cells * 100
    available_rate = available_count / total_cells * 100

    # --- Summary metrics ---
    st.subheader("Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Price Cells", total_cells)
    c2.metric("NA", f"{na_count} ({na_rate:.1f}%)")
    c3.metric("SOLD OUT", f"{sold_out_count} ({sold_out_rate:.1f}%)")
    c4.metric("Available", f"{available_count} ({available_rate:.1f}%)")

    st.divider()

    # --- Per-file breakdown ---
    st.subheader("NA & Sold Out Rate by File")

    file_rows = []
    for f, file_df in zip(uploaded_files, dfs):
        for col in PRICE_COLS:
            if col in file_df.columns:
                file_df[col] = file_df[col].astype(str).str.strip()

        file_total = len(file_df) * len(PRICE_COLS)
        if file_total == 0:
            continue

        file_na = 0
        file_sold_out = 0
        for col in PRICE_COLS:
            if col in file_df.columns:
                vals = file_df[col].str.upper()
                file_na += (vals == "NA").sum()
                file_sold_out += (vals == "SOLD OUT").sum()

        file_available = file_total - file_na - file_sold_out
        na_pct = file_na / file_total * 100
        sold_out_pct = file_sold_out / file_total * 100
        available_pct = file_available / file_total * 100

        file_rows.append({
            "File": f.name,
            "Total Cells": file_total,
            "NA": int(file_na),
            "NA %": round(na_pct, 1),
            "Sold Out": int(file_sold_out),
            "Sold Out %": round(sold_out_pct, 1),
            "NA + Sold Out %": round(na_pct + sold_out_pct, 1),
            "Available": int(file_available),
            "Available %": round(available_pct, 1),
        })

    file_summary_df = pd.DataFrame(file_rows)
    file_summary_df = file_summary_df.sort_values("NA + Sold Out %", ascending=False).reset_index(drop=True)

    # Format percentage columns for display
    display_df = file_summary_df.copy()
    display_df["NA %"] = display_df["NA %"].apply(lambda x: f"{x:.1f}%")
    display_df["Sold Out %"] = display_df["Sold Out %"].apply(lambda x: f"{x:.1f}%")
    display_df["NA + Sold Out %"] = display_df["NA + Sold Out %"].apply(lambda x: f"{x:.1f}%")
    display_df["Available %"] = display_df["Available %"].apply(lambda x: f"{x:.1f}%")

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.divider()

    # --- Per-hotel breakdown ---
    st.subheader("Detail by Hotel")

    rows = []
    for _, row in df.iterrows():
        values = [str(row[col]).strip() for col in PRICE_COLS if col in df.columns]
        na = sum(1 for v in values if v.upper() == "NA")
        sold_out = sum(1 for v in values if v.upper() == "SOLD OUT")
        total = len(values)
        available = total - na - sold_out
        rows.append({
            "Hotel": row.get("hotel_name", ""),
            "Room Type": row.get("room_type", ""),
            "Total Weeks": total,
            "NA": na,
            "NA %": f"{na/total*100:.0f}%",
            "Sold Out": sold_out,
            "Sold Out %": f"{sold_out/total*100:.0f}%",
            "Available": available,
        })

    detail_df = pd.DataFrame(rows)

    # Filter
    filter_col, _ = st.columns([2, 5])
    with filter_col:
        filter_opt = st.selectbox("Filter", ["All", "Has NA", "Has Sold Out", "No Price Available"])

    if filter_opt == "Has NA":
        detail_df = detail_df[detail_df["NA"] > 0]
    elif filter_opt == "Has Sold Out":
        detail_df = detail_df[detail_df["Sold Out"] > 0]
    elif filter_opt == "No Price Available":
        detail_df = detail_df[detail_df["Available"] == 0]

    st.dataframe(detail_df, use_container_width=True, hide_index=True)

    st.divider()

    # --- Per-week breakdown ---
    st.subheader("Detail by Week")

    week_rows = []
    for col in PRICE_COLS:
        if col not in df.columns:
            continue
        values = df[col].astype(str).str.strip()
        total = len(values)
        na = (values.str.upper() == "NA").sum()
        sold_out = (values.str.upper() == "SOLD OUT").sum()
        available = total - na - sold_out
        week_rows.append({
            "Week": col,
            "Total": total,
            "NA": int(na),
            "NA %": f"{na/total*100:.0f}%",
            "Sold Out": int(sold_out),
            "Sold Out %": f"{sold_out/total*100:.0f}%",
            "Available": int(available),
        })

    st.dataframe(pd.DataFrame(week_rows), use_container_width=True, hide_index=True)

    st.divider()

    # --- Raw data ---
    with st.expander("View Raw Data"):
        st.dataframe(df, use_container_width=True, hide_index=True)
