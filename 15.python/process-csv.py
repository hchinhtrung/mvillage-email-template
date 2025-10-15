import streamlit as st
import pandas as pd
import io
import os
import zipfile

st.set_page_config(page_title="CSV Processor", page_icon="🧹")
st.title("🧹 CSV Reservation Processor Tool")
st.write("Upload nhiều file CSV → Tool sẽ giữ lại và sắp xếp các cột cần thiết, đồng thời thêm header 'reservation code'.")

uploaded_files = st.file_uploader(
    "Chọn file CSV",
    accept_multiple_files=True,
    type=["csv"]
)

if uploaded_files:
    processed_files = []
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in uploaded_files:
            try:
                df = pd.read_csv(file)

                # 1️⃣ Thêm cột AL với header 'reservation code' nếu chưa có
                if 'reservation code' not in df.columns:
                    df['reservation code'] = ""

                # 2️⃣ Giữ lại các cột cần thiết
                keep_cols = [
                    "row id",
                    "group id",
                    "hotel",
                    "room type",
                    "check in",
                    "check out",
                    "price",
                    "reservation code"
                ]
                existing_cols = [col for col in keep_cols if col in df.columns]
                cleaned_df = df[existing_cols]

                # 3️⃣ Sắp xếp lại thứ tự cột
                desired_order = [
                    "row id",
                    "reservation code",
                    "group id",
                    "hotel",
                    "room type",
                    "check in",
                    "check out",
                    "price"
                ]
                final_cols = [c for c in desired_order if c in cleaned_df.columns]
                cleaned_df = cleaned_df[final_cols]

                # Xuất ra file processed
                base_name, _ = os.path.splitext(file.name)
                new_filename = f"{base_name} (processed).csv"

                buffer = io.StringIO()
                cleaned_df.to_csv(buffer, index=False)
                zipf.writestr(new_filename, buffer.getvalue())

                processed_files.append(new_filename)

            except Exception as e:
                st.error(f"❌ Lỗi khi xử lý file {file.name}: {e}")

    if processed_files:
        zip_buffer.seek(0)
        st.success(f"🎉 Hoàn tất! Đã xử lý {len(processed_files)} file CSV.")
        st.download_button(
            label="⬇️ Tải tất cả file (processed).zip",
            data=zip_buffer,
            file_name="processed_files.zip",
            mime="application/zip"
        )
else:
    st.caption("📂 Hãy chọn ít nhất 1 file CSV để bắt đầu.")