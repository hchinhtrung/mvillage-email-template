import streamlit as st
import pandas as pd
import io
import os
import zipfile
import re

st.set_page_config(page_title="CSV Reservation Processor", page_icon="🧹")
st.title("🧹 CSV Reservation Processor Tool")
st.write("Upload nhiều CSV → đổi cột AL thành 'reservation code', giữ & sắp xếp cột, sau đó sort theo 'row id'.")

uploaded_files = st.file_uploader(
    "Chọn file CSV",
    accept_multiple_files=True,
    type=["csv"]
)

def normalize(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"[\s_\-]+", " ", s)
    return s

CANON = {
    "row id": "row id",
    "group id": "group id",
    "hotel": "hotel",
    "room type": "room type",
    "check in": "check in",
    "check out": "check out",
    "price": "price",
    "reservation code": "reservation code",
}

DESIRED_ORDER = [
    "row id",
    "reservation code",
    "group id",
    "hotel",
    "room type",
    "check in",
    "check out",
    "price",
]

def fix_headers_and_select(df: pd.DataFrame) -> pd.DataFrame:
    # 1️⃣ Đổi tên cột AL (vị trí 38 → index 37) thành reservation code nếu có
    if len(df.columns) >= 38:
        al_name_old = df.columns[37]
        if str(al_name_old).strip() != "reservation code":
            df = df.rename(columns={al_name_old: "reservation code"})

    # 2️⃣ Chuẩn hoá tên cột
    col_map = {}
    for c in df.columns:
        key = normalize(c)
        if key in CANON:
            col_map[c] = CANON[key]
        if "reservation" in key and "code" in key:
            col_map[c] = "reservation code"
    df = df.rename(columns=col_map)

    # 3️⃣ Giữ lại các cột cần thiết
    keep_cols = [c for c in CANON.values() if c in df.columns]
    df = df[keep_cols]

    # 4️⃣ Sắp xếp lại thứ tự
    ordered = [c for c in DESIRED_ORDER if c in df.columns]
    df = df[ordered]

    # 5️⃣ Sort theo row id (tự phát hiện kiểu dữ liệu)
    if "row id" in df.columns:
        try:
            df["row id"] = pd.to_numeric(df["row id"], errors="ignore")
            df = df.sort_values(by="row id", ascending=True)
        except Exception:
            pass

    return df

if uploaded_files:
    processed_files = []
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in uploaded_files:
            try:
                df = pd.read_csv(file, dtype=str, keep_default_na=False, encoding="utf-8")
                cleaned = fix_headers_and_select(df)

                base_name, _ = os.path.splitext(file.name)
                new_filename = f"{base_name} (processed).csv"

                csv_buffer = io.StringIO()
                cleaned.to_csv(csv_buffer, index=False)
                zipf.writestr(new_filename, csv_buffer.getvalue())

                st.success(f"✅ Đã xử lý & sort: {file.name}")
                st.download_button(
                    label=f"⬇️ Tải {new_filename}",
                    data=csv_buffer.getvalue(),
                    file_name=new_filename,
                    mime="text/csv",
                    key=f"dl_{new_filename}"
                )

                with st.expander(f"👀 Preview {new_filename}"):
                    st.dataframe(cleaned.head(5))

                processed_files.append(new_filename)
            except Exception as e:
                st.error(f"❌ Lỗi khi xử lý file {file.name}: {e}")

    if processed_files:
        zip_buffer.seek(0)
        st.info(f"🎉 Hoàn tất! Đã xử lý & sort {len(processed_files)} file CSV.")
        st.download_button(
            label="📦 Tải tất cả (processed).zip",
            data=zip_buffer,
            file_name="processed_files.zip",
            mime="application/zip"
        )
else:
    st.caption("📂 Hãy chọn ít nhất 1 file CSV để bắt đầu.")