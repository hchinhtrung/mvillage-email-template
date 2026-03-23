import streamlit as st
import pandas as pd

st.set_page_config(page_title="Reservation Lookup Tool", layout="wide")

st.title("Reservation Data Lookup & Fill Tool")

st.markdown("""
Upload 2 files:
1. Template file (file cần fill)
2. Master data file (file lookup ~400k rows)
""")

# Config
KEY_COLUMN = "Reservation No"

COLUMNS_TO_FILL = [
    "Guest Country",
    "tenant_id",
    "Hotel Name",
    "City",
    "Brand Sub Segment",
    "Booking Source",
    "Create Date",
    "Checkin"
]

# Upload files
template_file = st.file_uploader("Upload Template File", type=["xlsx", "csv"])
master_file = st.file_uploader("Upload Master File", type=["xlsx", "csv"])


def read_file(file):
    if file.name.endswith('.csv'):
        return pd.read_csv(file, dtype={KEY_COLUMN: str})
    else:
        return pd.read_excel(file, dtype={KEY_COLUMN: str})


def normalize_key(df, key):
    df[key] = df[key].astype(str).str.strip().str.lower()
    return df

if template_file and master_file:
    df_template = read_file(template_file)
    df_master = read_file(master_file)

    # Normalize key
    df_template = normalize_key(df_template, KEY_COLUMN)
    df_master = normalize_key(df_master, KEY_COLUMN)

    st.subheader("Preview Template")
    st.dataframe(df_template.head())

    st.subheader("Preview Master")
    st.dataframe(df_master.head())

    # Validate columns
    missing_cols = [col for col in COLUMNS_TO_FILL + [KEY_COLUMN] if col not in df_master.columns]

    if missing_cols:
        st.error(f"Missing columns in master file: {missing_cols}")
    else:
        if st.button("Run Lookup"):
            try:
                # Match rate check
                matched = df_template[KEY_COLUMN].isin(df_master[KEY_COLUMN]).sum()
                total = len(df_template)
                st.info(f"Match rate: {matched}/{total} ({matched/total:.2%})")

                # Remove duplicates (keep latest by Create Date if exists)
                if "Create Date" in df_master.columns:
                    df_master_clean = df_master.sort_values(by="Create Date").drop_duplicates(
                        subset=[KEY_COLUMN], keep='last'
                    )
                else:
                    df_master_clean = df_master.drop_duplicates(subset=[KEY_COLUMN], keep='last')

                # Drop old columns to avoid _x _y
                df_template_clean = df_template.drop(columns=COLUMNS_TO_FILL, errors='ignore')

                # Use join (faster for large data)
                df_master_clean = df_master_clean.set_index(KEY_COLUMN)

                df_result = df_template_clean.join(
                    df_master_clean[COLUMNS_TO_FILL],
                    on=KEY_COLUMN
                )

                st.success("Lookup completed")
                st.dataframe(df_result.head())

                # Missing rows
                missing_data = df_result[df_result[COLUMNS_TO_FILL].isna().any(axis=1)]
                st.warning(f"Missing rows: {len(missing_data)}")

                if len(missing_data) > 0:
                    st.subheader("Sample Missing Reservations")
                    st.dataframe(missing_data.head(50))

                # Export
                output_file = "filled_reservations.xlsx"
                df_result.to_excel(output_file, index=False)

                with open(output_file, "rb") as f:
                    st.download_button(
                        label="Download Result",
                        data=f,
                        file_name=output_file,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            except Exception as e:
                st.error(f"Error: {e}")

else:
    st.info("Upload both files to start")
