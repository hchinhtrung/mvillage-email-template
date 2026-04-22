"""
B2B Lead Checker - M Village
Check if a B2B lead already has bookings in the reservation system.
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
    page_title="B2B Lead Checker",
    page_icon="🔍",
    layout="wide",
)

# ─────────────────────────────────────────────
# STYLE
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
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


def parse_lead_text(text: str) -> dict:
    """Parse lead info from pasted text."""
    result = {"email": "", "contact": "", "company": "", "create_date": ""}
    
    for line in text.strip().split("\n"):
        line = line.strip()
        # Remove leading emoji arrows
        line = re.sub(r'^[👉🔹•\-\s]+', '', line).strip()
        
        low = line.lower()
        if "email" in low:
            match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', line)
            if match:
                result["email"] = match.group(0).strip().lower()
        elif "contact" in low or "person" in low or ("name" in low and "company" not in low):
            parts = re.split(r':\s*', line, maxsplit=1)
            if len(parts) > 1:
                result["contact"] = parts[1].strip()
        elif "company" in low or "công ty" in low or "cty" in low:
            parts = re.split(r':\s*', line, maxsplit=1)
            if len(parts) > 1:
                result["company"] = parts[1].strip()
        elif "create" in low or "date" in low or "ngày" in low:
            parts = re.split(r':\s*', line, maxsplit=1)
            if len(parts) > 1:
                result["create_date"] = parts[1].strip()
    
    # Fallback: try to find email anywhere
    if not result["email"]:
        match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', text)
        if match:
            result["email"] = match.group(0).strip().lower()
    
    return result


@st.cache_data(show_spinner=False)
def load_res(file_bytes: bytes) -> pd.DataFrame:
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
    res_file = st.file_uploader("Upload CSV to override", type=["csv"])
    
    st.divider()
    st.header("⚙️ Settings")
    
    with st.expander("Column Mapping", expanded=False):
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
    
    fuzzy_threshold = st.slider("Fuzzy match threshold (%)", 60, 100, 80)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🔍 B2B Lead Checker</h1>
    <p>Paste lead info → instantly check existing bookings in M Village system</p>
</div>
""", unsafe_allow_html=True)

# Load reservation data — uploaded file takes priority, else default
if res_file:
    res_bytes = res_file.read()
    res_df = load_res(res_bytes)
elif DEFAULT_DB.exists():
    res_bytes = DEFAULT_DB.read_bytes()
    res_df = load_res(res_bytes)
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
# INPUT
# ─────────────────────────────────────────────
st.subheader("📋 Paste Lead Info")
st.caption("Supports multiple leads at once — each block starts with `👉 Work Email`")

lead_text = st.text_area(
    "Paste the lead information below:",
    height=200,
    placeholder="👉 Work Email: a@company.vn\n👉 Contact Person: Nguyen A\n👉 Company Name: COMPANY A\n👉 Create Date: Apr 20, 2026\n👉 Work Email: b@company.vn\n👉 Contact Person: Nguyen B\n👉 Company Name: COMPANY B\n👉 Create Date: Apr 18, 2026",
)

if not lead_text.strip():
    st.stop()

# ─────────────────────────────────────────────
# SPLIT & PARSE MULTIPLE LEADS
# ─────────────────────────────────────────────
def split_leads(text: str) -> list[str]:
    """Split pasted text into individual lead blocks using '👉 Work Email' as delimiter."""
    blocks = re.split(r'(?=👉\s*Work Email)', text.strip())
    if len(blocks) <= 1:
        blocks = re.split(r'(?=(?:👉|🔹|•|\*)\s*Work Email)', text.strip())
    blocks = [b.strip() for b in blocks if b.strip()]
    return blocks if blocks else [text.strip()]

lead_blocks = split_leads(lead_text)
leads = []
for block in lead_blocks:
    parsed = parse_lead_text(block)
    if parsed["email"] or parsed["company"]:
        parsed["domain"] = extract_domain(parsed["email"])
        leads.append(parsed)

if not leads:
    st.warning("Could not parse any leads from the pasted text.")
    st.stop()

st.info(f"🔢 Detected **{len(leads)}** lead(s)")

# ─────────────────────────────────────────────
# PROCESS ALL LEADS
# ─────────────────────────────────────────────
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
    # Parse lead create date
    lead_create_dt = None
    if lead.get("create_date"):
        lead_create_dt = pd.to_datetime(lead["create_date"], errors="coerce", dayfirst=False)
    
    if total_res_count == 0:
        status = "❌ NO"
    elif lead_create_dt is not None and pd.notna(lead_create_dt) and col_create_date in all_matched.columns:
        res_dates = pd.to_datetime(all_matched[col_create_date], errors="coerce")
        has_after = (res_dates >= lead_create_dt).any()
        if has_after:
            status = "✅ YES"
        else:
            status = "⚠️ BEFORE"
    elif total_res_count > 0:
        # No lead create date provided → just mark as YES if any booking exists
        status = "✅ YES"
    else:
        status = "❌ NO"
    
    summary_rows.append({
        "No.": idx + 1,
        "Email": lead["email"] or "—",
        "Domain": lead["domain"] or "—",
        "Company": lead["company"] or "—",
        "Contact": lead["contact"] or "—",
        "Lead Create Date": lead.get("create_date", "—") or "—",
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

yes_count = len([r for r in summary_rows if r["Status"] == "✅ YES"])
before_count = len([r for r in summary_rows if r["Status"] == "⚠️ BEFORE"])
no_count = len([r for r in summary_rows if r["Status"] == "❌ NO"])

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#38bdf8">{len(summary_rows)}</div><div class="kpi-lbl">Total Leads</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#10b981">{yes_count}</div><div class="kpi-lbl">Booked After Lead ✅</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#f59e0b">{before_count}</div><div class="kpi-lbl">Booked Before Lead ⚠️</div></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#ef4444">{no_count}</div><div class="kpi-lbl">No Bookings ❌</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.dataframe(display_summary, use_container_width=True, hide_index=True)

# ── Detail per lead ─────────────────────────
st.markdown("---")
st.subheader("🔎 Lead Details")

for row in summary_rows:
    matches = row["_matches"]
    all_matched = row["_all_matched"]
    label = f'{row["Status"]} #{row["No."]} — {row["Company"]} ({row["Email"]}) — {row["Reservations"]} res'
    
    with st.expander(label, expanded=(row["Reservations"] > 0)):
        # Parsed info
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
            st.markdown(f'<div class="parsed-box">📅 <b>Lead Date:</b><br><code>{row["Lead Create Date"]}</code></div>', unsafe_allow_html=True)
        
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
            desc = "All bookings were created BEFORE the lead date."
        else:
            color_class = "result-found"
            desc = "Bookings found after the lead creation date."
        
        st.markdown(f"""
        <div class="{color_class}">
            <h3>{status_msg} — {row["Reservations"]} reservation(s) found</h3>
            <p>Room Nights: <b>{row["Room Nights"]}</b> | Revenue: <b>{row["Revenue"]} VND</b> | Hotels: <b>{row["Hotels"]}</b></p>
            <p>Match by: <b>{row["Match By"]}</b> | {desc}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Show match details
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
export_summary = display_summary.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "⬇️ Export Summary (CSV)",
    data=export_summary,
    file_name="lead_check_summary.csv",
    mime="text/csv",
)
