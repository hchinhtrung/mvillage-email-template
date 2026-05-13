"""
B2B Lead Checker v2 - M Village
Upload a CSV of B2B leads → check if they already have bookings in the reservation system.
Matches by: email, email domain, company name (fuzzy ~80%).
"""

import streamlit as st
import pandas as pd
import re
import io
import os
from pathlib import Path
from rapidfuzz import fuzz, process

# ─────────────────────────────────────────────
# DEFAULT DB PATH (same folder as this script)
# ─────────────────────────────────────────────
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = SCRIPT_DIR / "checkb2b-res.csv"

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="B2B Lead Checker v2",
    page_icon="🔍",
    layout="wide",
)

# ─────────────────────────────────────────────
# STYLE
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap');
    
    .stApp { font-family: 'Inter', sans-serif; }
    
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%);
        border-radius: 16px; padding: 32px 40px; margin-bottom: 24px;
        border: 1px solid rgba(99,102,241,0.2);
    }
    .main-header h1 { color: #f8fafc; font-size: 2rem; margin: 0 0 4px 0; }
    .main-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }
    
    .result-found {
        background: linear-gradient(135deg, #064e3b, #065f46);
        border: 1px solid #10b981; border-radius: 14px;
        padding: 20px 24px; margin: 12px 0;
    }
    .result-found h3 { color: #6ee7b7; margin: 0 0 8px 0; font-size: 1.1rem; }
    .result-found p { color: #d1fae5; margin: 4px 0; font-size: 0.9rem; }
    
    .result-not-found {
        background: linear-gradient(135deg, #1c1917, #292524);
        border: 1px solid #78716c; border-radius: 14px;
        padding: 20px 24px; margin: 12px 0;
    }
    .result-not-found h3 { color: #a8a29e; margin: 0 0 8px 0; font-size: 1.1rem; }
    .result-not-found p { color: #d6d3d1; margin: 4px 0; font-size: 0.9rem; }
    
    .match-tag {
        display: inline-block; padding: 3px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600; margin-right: 6px;
    }
    .tag-email { background: #312e81; color: #a5b4fc; }
    .tag-domain { background: #4c1d95; color: #c4b5fd; }
    .tag-company { background: #164e63; color: #67e8f9; }
    
    .kpi-box {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155; border-radius: 12px;
        padding: 16px 20px; text-align: center;
    }
    .kpi-num { font-size: 2rem; font-weight: 800; }
    .kpi-lbl { font-size: 0.78rem; color: #94a3b8; margin-top: 2px; }
    
    .parsed-box {
        background: #1e293b; border: 1px solid #334155; border-radius: 10px;
        padding: 14px 18px; margin: 8px 0;
    }
    .parsed-box code { color: #38bdf8; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def normalize(s) -> str:
    if pd.isna(s) or not s:
        return ""
    return str(s).strip().upper()


def extract_domain(email: str) -> str:
    """Extract domain from email, skip generic providers."""
    if not email or "@" not in email:
        return ""
    domain = email.split("@")[1].strip().lower()
    generic = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
               "icloud.com", "live.com", "ymail.com", "protonmail.com",
               "noemail.mvillage.vn", "mail.com", "aol.com", "qq.com",
               "163.com", "126.com", "yeah.net"}
    if domain in generic:
        return ""
    return domain


@st.cache_data(show_spinner=False)
def load_csv(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(file_bytes), dtype=str)


def search_reservations(res_df: pd.DataFrame, parsed: dict,
                        col_company: str, col_company_email: str,
                        col_guest_email: str, fuzzy_threshold: int):
    """
    Search reservation DB for matches.
    Returns dict with match details.
    """
    email = parsed["email"].lower().strip()
    domain = extract_domain(email)
    company = parsed["company"].strip()
    
    matches = {"email": pd.DataFrame(), "domain": pd.DataFrame(), "company": pd.DataFrame()}
    
    # 1) Exact email match (guest email OR company email)
    if email:
        mask_guest = res_df[col_guest_email].str.lower().str.strip() == email
        mask_company_email = res_df[col_company_email].str.lower().str.strip() == email
        matches["email"] = res_df[mask_guest | mask_company_email]
    
    # 2) Domain match (company email domain)
    if domain:
        def get_domain(val):
            if pd.isna(val) or "@" not in str(val):
                return ""
            return str(val).split("@")[1].strip().lower()
        
        mask_d1 = res_df[col_company_email].apply(get_domain) == domain
        mask_d2 = res_df[col_guest_email].apply(get_domain) == domain
        domain_matches = res_df[mask_d1 | mask_d2]
        # Exclude already matched by exact email
        if not matches["email"].empty:
            domain_matches = domain_matches[~domain_matches.index.isin(matches["email"].index)]
        matches["domain"] = domain_matches
    
    # 3) Fuzzy company name match
    if company:
        company_norm = normalize(company)
        unique_companies = res_df["_norm_company"].dropna().unique().tolist()
        unique_companies = [c for c in unique_companies if c]
        
        if unique_companies:
            fuzzy_results = process.extract(
                company_norm, unique_companies,
                scorer=fuzz.token_sort_ratio,
                limit=5,
                score_cutoff=fuzzy_threshold
            )
            
            if fuzzy_results:
                matched_names = [r[0] for r in fuzzy_results]
                company_matches = res_df[res_df["_norm_company"].isin(matched_names)]
                # Exclude already matched
                already = set()
                if not matches["email"].empty:
                    already |= set(matches["email"].index)
                if not matches["domain"].empty:
                    already |= set(matches["domain"].index)
                if already:
                    company_matches = company_matches[~company_matches.index.isin(already)]
                matches["company"] = company_matches
    
    return matches


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("📂 Reservation DB")
    if DEFAULT_DB.exists():
        st.success(f"✅ Default DB: `{DEFAULT_DB.name}`")
    res_file = st.file_uploader("Upload CSV to override", type=["csv"], key="res_upload")
    
    st.divider()
    st.header("⚙️ Settings")
    
    with st.expander("Reservation Column Mapping", expanded=False):
        col_company = st.text_input("Company Name", value="Company (VAT)")
        col_company_email = st.text_input("Company Email", value="Company Email (VAT)")
        col_guest_email = st.text_input("Guest Email", value="Guest Email")
        col_hotel = st.text_input("Hotel Name", value="Hotel Name")
        col_res_no = st.text_input("Reservation No", value="Reservation No")
        col_city = st.text_input("City", value="City")
        col_room_night = st.text_input("Room Night", value="Room Night")
        col_revenue = st.text_input("Revenue", value="Revenue")
        col_checkin = st.text_input("Check-in", value="Checkin")
        col_booking_type = st.text_input("Booking Type", value="Booking Type")
        col_create_date = st.text_input("Booking Create Date", value="Create Date")
    
    with st.expander("Tab 1: Lead Column Mapping", expanded=False):
        lead_col_company = st.text_input("Lead: Company", value="Display Name")
        lead_col_display_name = st.text_input("Lead: Contact", value="Agent")
        lead_col_email = st.text_input("Lead: Email", value="Email")
        lead_col_created_on = st.text_input("Lead: Created on", value="Created on")
        lead_col_phone = st.text_input("Lead: Phone", value="Phone")
        lead_col_country = st.text_input("Lead: Country", value="Country")

    with st.expander("Tab 2: Rate Plan Column Mapping", expanded=False):
        rp_col_company = st.text_input("Rate Plan: Company", value="List company")
        rp_col_added_date = st.text_input("Rate Plan: Added Date", value="added date - rate plan")
    
    fuzzy_threshold = st.slider("Fuzzy match threshold (%)", 60, 100, 80)


# ─────────────────────────────────────────────
# UI COMPONENT FUNCTION
# ─────────────────────────────────────────────
def render_checker_ui(
    tab_key, 
    upload_label, 
    col_map_company,
    col_map_date,
    col_map_email=None,
    col_map_contact=None,
    col_map_phone=None,
    col_map_country=None,
    date_label="Lead Create Date"
):
    lead_file = st.file_uploader(
        upload_label,
        type=["csv"],
        key=f"upload_{tab_key}",
    )

    if lead_file is None:
        st.info("👆 Please upload a **CSV** file to start checking.")
        return

    # PARSE LEADS FROM CSV
    lead_bytes = lead_file.read()
    lead_df = load_csv(lead_bytes)

    # Show preview of uploaded CSV
    with st.expander("📋 Preview uploaded CSV", expanded=False):
        st.dataframe(lead_df.head(20), use_container_width=True, hide_index=True)
        st.caption(f"Total rows: **{len(lead_df)}**")

    # Build leads list from CSV rows
    leads = []
    for _, row in lead_df.iterrows():
        email = ""
        if col_map_email:
            email_val = row.get(col_map_email, "")
            email_raw = "" if pd.isna(email_val) else str(email_val).strip().lower()
            email_match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', email_raw)
            email = email_match.group(0) if email_match else ""
        
        company_val = row.get(col_map_company, "")
        company = "" if pd.isna(company_val) else str(company_val).strip()
        
        contact = ""
        if col_map_contact:
            contact_val = row.get(col_map_contact, "")
            contact = "" if pd.isna(contact_val) else str(contact_val).strip()
        
        create_date_val = row.get(col_map_date, "")
        create_date = "" if pd.isna(create_date_val) else str(create_date_val).strip()
        
        phone = ""
        if col_map_phone:
            phone_val = row.get(col_map_phone, "")
            phone = "" if pd.isna(phone_val) else str(phone_val).strip()
        
        country = ""
        if col_map_country:
            country_val = row.get(col_map_country, "")
            country = "" if pd.isna(country_val) else str(country_val).strip()
        
        # Skip rows with no email AND no company
        if not email and not company:
            continue
        
        domain = extract_domain(email)
        leads.append({
            "email": email,
            "domain": domain,
            "contact": contact,
            "company": company,
            "create_date": create_date,
            "phone": phone,
            "country": country,
        })

    if not leads:
        st.warning("No valid rows found in the uploaded CSV. Make sure the column names match the mapping in Settings.")
        return

    st.info(f"🔢 Loaded **{len(leads)}** row(s) from CSV")

    # PROCESS ALL LEADS
    st.markdown("---")
    st.subheader("📊 Summary")

    display_cols_list = [col_res_no, col_company, col_hotel, col_city,
                         col_guest_email, col_company_email,
                         col_create_date, col_checkin, col_room_night, col_revenue, col_booking_type]

    summary_rows = []

    for idx, lead in enumerate(leads):
        matches = search_reservations(res_df, lead, col_company, col_company_email,
                                      col_guest_email, fuzzy_threshold)
        
        non_empty = [m for m in matches.values() if not m.empty]
        if non_empty:
            all_matched = pd.concat(non_empty, ignore_index=False)
            all_matched = all_matched[~all_matched.index.duplicated(keep="first")]
        else:
            all_matched = pd.DataFrame()
        
        total_res_count = len(all_matched)
        total_rn = int(pd.to_numeric(all_matched[col_room_night], errors="coerce").sum()) if col_room_night in all_matched.columns and not all_matched.empty else 0
        total_rev = pd.to_numeric(all_matched[col_revenue], errors="coerce").sum() if col_revenue in all_matched.columns and not all_matched.empty else 0
        hotels_list = list(all_matched[col_hotel].dropna().unique()) if col_hotel in all_matched.columns and not all_matched.empty else []
        
        match_types = []
        if not matches["email"].empty:
            match_types.append("Email")
        if not matches["domain"].empty:
            match_types.append("Domain")
        if not matches["company"].empty:
            match_types.append("Company")
        
        # ── Status logic: YES / BEFORE / NO ──────
        lead_create_dt = None
        if lead.get("create_date"):
            lead_create_dt = pd.to_datetime(lead["create_date"], errors="coerce", dayfirst=False)
        
        if total_res_count == 0:
            status = "❌ NO"
        elif lead_create_dt is not None and pd.notna(lead_create_dt) and col_create_date in all_matched.columns:
            res_dates = pd.to_datetime(all_matched[col_create_date], errors="coerce")
            has_after = (res_dates >= lead_create_dt).any()
            if has_after:
                status = "✅ AFTER"
            else:
                status = "⚠️ BEFORE"
        elif total_res_count > 0:
            status = "✅ AFTER"
        else:
            status = "❌ NO"
        
        summary_rows.append({
            "No.": idx + 1,
            "Email": lead["email"] or "—",
            "Domain": lead["domain"] or "—",
            "Company": lead["company"] or "—",
            "Contact": lead["contact"] or "—",
            date_label: lead.get("create_date", "—") or "—",
            "Status": status,
            "Reservations": total_res_count,
            "Room Nights": total_rn,
            "Revenue": f"{total_rev:,.0f}" if total_rev else "0",
            "Hotels": ", ".join(hotels_list[:3]),
            "Match By": ", ".join(match_types) if match_types else "—",
            "_matches": matches,
            "_all_matched": all_matched,
        })

    # ── Summary table ───────────────────────────
    summary_df = pd.DataFrame(summary_rows)
    display_summary = summary_df.drop(columns=["_matches", "_all_matched"])

    yes_count = len([r for r in summary_rows if r["Status"] == "✅ AFTER"])
    before_count = len([r for r in summary_rows if r["Status"] == "⚠️ BEFORE"])
    no_count = len([r for r in summary_rows if r["Status"] == "❌ NO"])

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#38bdf8">{len(summary_rows)}</div><div class="kpi-lbl">Total Rows Checked</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#10b981">{yes_count}</div><div class="kpi-lbl">Booked After ✅</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#f59e0b">{before_count}</div><div class="kpi-lbl">Booked Before ⚠️</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#ef4444">{no_count}</div><div class="kpi-lbl">No Bookings ❌</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(display_summary, use_container_width=True, hide_index=True)

    # ── Booking Breakdown ───────────────────────
    st.markdown("---")
    st.subheader("📋 Booking Breakdown")

    breakdown_rows = []
    for row in summary_rows:
        if row["Reservations"] > 0:
            all_matched = row["_all_matched"]
            for _, match_row in all_matched.iterrows():
                breakdown_rows.append({
                    "No.": row["No."],
                    "Email": row["Email"],
                    "Company": row["Company"],
                    "Status": row["Status"],
                    "Reservation No": match_row.get(col_res_no, "—"),
                    "Company (VAT)": match_row.get(col_company, "—"),
                    "Hotel Name": match_row.get(col_hotel, "—"),
                    "City": match_row.get(col_city, "—"),
                    "Guest Email": match_row.get(col_guest_email, "—"),
                    "Company Email (VAT)": match_row.get(col_company_email, "—"),
                    "Create Date": match_row.get(col_create_date, "—"),
                    "Checkin": match_row.get(col_checkin, "—"),
                    "Room Night": match_row.get(col_room_night, "—"),
                    "Revenue": match_row.get(col_revenue, "—"),
                    "Booking Type": match_row.get(col_booking_type, "—")
                })

    if breakdown_rows:
        breakdown_df = pd.DataFrame(breakdown_rows)
        st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
    else:
        st.info("No bookings found for any rows.")

    # ── Detail per lead ─────────────────────────
    st.markdown("---")
    st.subheader("🔎 Details")

    for row in summary_rows:
        matches = row["_matches"]
        all_matched = row["_all_matched"]
        label = f'{row["Status"]} #{row["No."]} — {row["Company"]} ({row["Email"]}) — {row["Reservations"]} res'
        
        with st.expander(label, expanded=(row["Reservations"] > 0)):
            p1, p2, p3, p4, p5 = st.columns(5)
            with p1:
                st.markdown(f'<div class="parsed-box">📧 <b>Email:</b><br><code>{row["Email"]}</code></div>', unsafe_allow_html=True)
            with p2:
                st.markdown(f'<div class="parsed-box">🌐 <b>Domain:</b><br><code>{row["Domain"]}</code></div>', unsafe_allow_html=True)
            with p3:
                st.markdown(f'<div class="parsed-box">👤 <b>Contact:</b><br><code>{row["Contact"]}</code></div>', unsafe_allow_html=True)
            with p4:
                st.markdown(f'<div class="parsed-box">🏢 <b>Company:</b><br><code>{row["Company"]}</code></div>', unsafe_allow_html=True)
            with p5:
                st.markdown(f'<div class="parsed-box">📅 <b>Date:</b><br><code>{row[date_label]}</code></div>', unsafe_allow_html=True)
            
            if row["Reservations"] == 0:
                st.markdown("""
                <div class="result-not-found">
                    <h3>❌ No bookings found</h3>
                    <p>→ This could be a completely NEW customer!</p>
                </div>
                """, unsafe_allow_html=True)
                continue
            
            status_msg = row["Status"]
            if "BEFORE" in status_msg:
                color_class = "result-not-found"
                desc = "All bookings were created BEFORE the reference date."
            else:
                color_class = "result-found"
                desc = "Bookings found after the reference date."
            
            st.markdown(f"""
            <div class="{color_class}">
                <h3>{status_msg} — {row["Reservations"]} reservation(s) found</h3>
                <p>Room Nights: <b>{row["Room Nights"]}</b> | Revenue: <b>{row["Revenue"]} VND</b> | Hotels: <b>{row["Hotels"]}</b></p>
                <p>Match by: <b>{row["Match By"]}</b> | {desc}</p>
            </div>
            """, unsafe_allow_html=True)
            
            display_cols = [c for c in display_cols_list if c in all_matched.columns]
            if not matches["email"].empty:
                st.markdown(f'<span class="match-tag tag-email">📧 Email: {len(matches["email"])} res</span>', unsafe_allow_html=True)
            if not matches["domain"].empty:
                st.markdown(f'<span class="match-tag tag-domain">🌐 Domain: {len(matches["domain"])} res</span>', unsafe_allow_html=True)
            if not matches["company"].empty:
                st.markdown(f'<span class="match-tag tag-company">🏢 Company: {len(matches["company"])} res</span>', unsafe_allow_html=True)
            
            st.dataframe(all_matched[display_cols].reset_index(drop=True), use_container_width=True,
                          height=min(300, 35 * len(all_matched) + 38))

    # ── Export all ──────────────────────────────
    st.markdown("---")
    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        export_summary = display_summary.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            f"⬇️ Export Summary ({tab_key})",
            data=export_summary,
            file_name=f"{tab_key}_summary.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"exp_sum_{tab_key}"
        )

    with col_exp2:
        if 'breakdown_df' in locals() and not breakdown_df.empty:
            export_breakdown = breakdown_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                f"⬇️ Export Booking Breakdown ({tab_key})",
                data=export_breakdown,
                file_name=f"{tab_key}_booking_breakdown.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"exp_brk_{tab_key}"
            )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🔍 B2B Lead Checker v2</h1>
    <p>Upload lead CSV → instantly check existing bookings in M Village system</p>
</div>
""", unsafe_allow_html=True)

# Load reservation data — uploaded file takes priority, else default
if res_file:
    res_bytes = res_file.read()
    res_df = load_csv(res_bytes)
elif DEFAULT_DB.exists():
    res_bytes = DEFAULT_DB.read_bytes()
    res_df = load_csv(res_bytes)
else:
    st.info("👈 Upload a **Reservation CSV** from the sidebar, or place `checkb2b-res.csv` in the script folder.")
    st.stop()

# Validate columns
required_cols = [col_company, col_company_email, col_guest_email, col_hotel, col_res_no]
missing = [c for c in required_cols if c not in res_df.columns]
if missing:
    st.error(f"Missing columns in CSV: {missing}\n\nAvailable: {res_df.columns.tolist()}")
    st.stop()

# Pre-process
res_df[col_company_email] = res_df[col_company_email].fillna("")
res_df[col_guest_email] = res_df[col_guest_email].fillna("")
res_df["_norm_company"] = res_df[col_company].apply(normalize)

# Show DB stats
total_res = len(res_df)
unique_companies = res_df["_norm_company"].nunique()
c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#38bdf8">{total_res:,}</div><div class="kpi-lbl">Total Reservations Loaded</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#a78bfa">{unique_companies:,}</div><div class="kpi-lbl">Unique Companies</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2 = st.tabs(["Tab 1: Check B2B Leads", "Tab 2: Check Company Rate Plan"])

with tab1:
    st.subheader("📤 Upload Lead CSV")
    st.caption("Upload a CSV file with B2B leads. Required columns: `Display Name`, `Email`, `Company`, `Created on`")
    render_checker_ui(
        tab_key="leads",
        upload_label="Upload your B2B Lead CSV file:",
        col_map_company=lead_col_company,
        col_map_date=lead_col_created_on,
        col_map_email=lead_col_email,
        col_map_contact=lead_col_display_name,
        col_map_phone=lead_col_phone,
        col_map_country=lead_col_country,
        date_label="Lead Create Date"
    )

with tab2:
    st.subheader("📤 Upload Company Rate Plan CSV")
    st.caption("Upload a CSV file with Company Rate Plan. Required columns: `List company`, `added date - rate plan`")
    render_checker_ui(
        tab_key="rate_plan",
        upload_label="Upload your Company Rate Plan CSV file:",
        col_map_company=rp_col_company,
        col_map_date=rp_col_added_date,
        col_map_email=None,
        col_map_contact=None,
        col_map_phone=None,
        col_map_country=None,
        date_label="Added Date (Rate Plan)"
    )

