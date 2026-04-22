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
DEFAULT_DB = SCRIPT_DIR / "sample-res.csv"

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
    result = {"email": "", "contact": "", "company": ""}
    
    for line in text.strip().split("\n"):
        line = line.strip()
        # Remove leading emoji arrows
        line = re.sub(r'^[👉🔹•\-\s]+', '', line).strip()
        
        low = line.lower()
        if "email" in low:
            match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', line)
            if match:
                result["email"] = match.group(0).strip().lower()
        elif "contact" in low or "person" in low or "name" in low and "company" not in low:
            parts = re.split(r':\s*', line, maxsplit=1)
            if len(parts) > 1:
                result["contact"] = parts[1].strip()
        elif "company" in low or "công ty" in low or "cty" in low:
            parts = re.split(r':\s*', line, maxsplit=1)
            if len(parts) > 1:
                result["company"] = parts[1].strip()
    
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
    st.info("👈 Upload a **Reservation CSV** from the sidebar, or place `res.csv` in the script folder.")
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

lead_text = st.text_area(
    "Paste the lead information below:",
    height=120,
    placeholder="👉 Work Email: annh@hann.vn\n👉 Contact Person: Nguyễn Hồng Ân\n👉 Company Name: Công ty TNHH Phân Phối và Dịch vụ HANN",
)

if not lead_text.strip():
    st.stop()

# ─────────────────────────────────────────────
# PARSE
# ─────────────────────────────────────────────
parsed = parse_lead_text(lead_text)
domain = extract_domain(parsed["email"])

st.markdown("---")
st.subheader("🧩 Parsed Info")

p1, p2, p3, p4 = st.columns(4)
with p1:
    st.markdown(f'<div class="parsed-box">📧 <b>Email:</b><br><code>{parsed["email"] or "—"}</code></div>', unsafe_allow_html=True)
with p2:
    st.markdown(f'<div class="parsed-box">🌐 <b>Domain:</b><br><code>{domain or "—"}</code></div>', unsafe_allow_html=True)
with p3:
    st.markdown(f'<div class="parsed-box">👤 <b>Contact:</b><br><code>{parsed["contact"] or "—"}</code></div>', unsafe_allow_html=True)
with p4:
    st.markdown(f'<div class="parsed-box">🏢 <b>Company:</b><br><code>{parsed["company"] or "—"}</code></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────
st.markdown("---")
st.subheader("📊 Search Results")

matches = search_reservations(res_df, parsed, col_company, col_company_email,
                              col_guest_email, fuzzy_threshold)

non_empty = [m for m in matches.values() if not m.empty]
if non_empty:
    all_matched = pd.concat(non_empty, ignore_index=False)
    all_matched = all_matched[~all_matched.index.duplicated(keep="first")]
else:
    all_matched = pd.DataFrame()

total_matched_res = len(all_matched)

if total_matched_res == 0:
    st.markdown("""
    <div class="result-not-found">
        <h3>❌ Không tìm thấy booking nào</h3>
        <p>Lead này chưa có lịch sử đặt phòng tại M Village.</p>
        <p><b>→ Đây có thể là khách hàng MỚI hoàn toàn!</b></p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Summary KPIs ────────────────────────────
matched_companies = all_matched[col_company].dropna().unique()
total_rn = 0
total_rev = 0
if col_room_night in all_matched.columns:
    total_rn = int(pd.to_numeric(all_matched[col_room_night], errors="coerce").sum())
if col_revenue in all_matched.columns:
    total_rev = pd.to_numeric(all_matched[col_revenue], errors="coerce").sum()

st.markdown(f"""
<div class="result-found">
    <h3>✅ ĐÃ TÌM THẤY BOOKING!</h3>
    <p>Lead này đã có <b>{total_matched_res}</b> reservation(s) trong hệ thống M Village.</p>
    <p>Company: <b>{', '.join(matched_companies[:3])}</b></p>
</div>
""", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#10b981">{total_matched_res}</div><div class="kpi-lbl">Reservations Found</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#f59e0b">{total_rn:,}</div><div class="kpi-lbl">Total Room Nights</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#6ee7b7">{total_rev:,.0f}</div><div class="kpi-lbl">Total Revenue (VND)</div></div>', unsafe_allow_html=True)
with k4:
    hotels = all_matched[col_hotel].dropna().unique() if col_hotel in all_matched.columns else []
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#a78bfa">{len(hotels)}</div><div class="kpi-lbl">Hotels Stayed</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Match breakdown ─────────────────────────
def show_match_section(title, tag_class, tag_label, df):
    if df.empty:
        return
    st.markdown(f'**{title}** — <span class="match-tag {tag_class}">{tag_label}: {len(df)} res</span>', unsafe_allow_html=True)
    
    display_cols = [c for c in [col_res_no, col_company, col_hotel, col_city,
                                col_guest_email, col_company_email,
                                col_checkin, col_room_night, col_revenue, col_booking_type]
                    if c in df.columns]
    st.dataframe(df[display_cols].reset_index(drop=True), use_container_width=True, height=min(250, 35 * len(df) + 38))

show_match_section("📧 Email Match", "tag-email", "Email", matches["email"])
show_match_section("🌐 Domain Match", "tag-domain", "Domain", matches["domain"])
show_match_section("🏢 Company Name Match (Fuzzy)", "tag-company", "Company", matches["company"])

# ── Hotel breakdown ─────────────────────────
st.markdown("---")
st.subheader("🏨 Hotel Breakdown")

if col_hotel in all_matched.columns:
    hotel_summary = (
        all_matched.groupby(col_hotel, sort=False)
        .agg(
            Reservations=(col_res_no, "count"),
            **({f"Room Nights": (col_room_night, lambda x: int(pd.to_numeric(x, errors="coerce").sum()))} if col_room_night in all_matched.columns else {}),
            **({f"Revenue": (col_revenue, lambda x: pd.to_numeric(x, errors="coerce").sum())} if col_revenue in all_matched.columns else {}),
        )
        .sort_values("Reservations", ascending=False)
        .reset_index()
    )
    if "Revenue" in hotel_summary.columns:
        hotel_summary["Revenue"] = hotel_summary["Revenue"].apply(lambda x: f"{x:,.0f}")
    st.dataframe(hotel_summary, use_container_width=True)

# ── Export ──────────────────────────────────
st.markdown("---")
export_bytes = all_matched.drop(columns=["_norm_company"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "⬇️ Export Matched Reservations (CSV)",
    data=export_bytes,
    file_name=f"lead_check_{parsed['email'] or 'result'}.csv",
    mime="text/csv",
)
