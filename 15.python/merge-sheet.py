import pandas as pd
import os

file_path = "/Users/hchinhtrung/Documents/GitHub/mvillage-email-template/15.python/ota2025.xlsx"

print("Opening Excel file...")

xls = pd.ExcelFile(file_path, engine="openpyxl")

dfs = []

for sheet in xls.sheet_names:

    if sheet == "Total":
        continue

    print(f"Reading sheet: {sheet}")

    df = pd.read_excel(xls, sheet_name=sheet)

    if not df.empty:
        df["sheet_name"] = sheet
        dfs.append(df)

print("Combining sheets...")

dfs = [df for df in dfs if not df.empty]

merged = pd.concat(dfs, ignore_index=True)

output_path = os.path.join(os.path.dirname(__file__), "merged_output.csv")

print("Writing output file...")

merged.to_csv(output_path, index=False)

print(f"Merge completed. File saved at: {output_path}")