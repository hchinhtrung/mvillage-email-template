import pandas as pd

# đường dẫn file Excel local
file_path = "/Users/hchinhtrung/Documents/GitHub/mvillage-email-template/15.python/Copy of Weekly Loyalty Insights Data Collection 2025.xlsx"

# đọc toàn bộ sheet
xls = pd.ExcelFile(file_path)

dfs = []

for sheet_name in xls.sheet_names:

    if sheet_name == "Total":
        continue

    df = pd.read_excel(file_path, sheet_name=sheet_name)

    if not df.empty:
        dfs.append(df)

merged = pd.concat(dfs, ignore_index=True)

merged.to_csv("merged_guest_data.csv", index=False)

print("Merge completed!")