"""Filter reservations by tenant IDs.

Usage:
  python "lookup tenant.py" --tenants tenant.csv --reservations reservation.csv --output matched_reservations.csv

The script reads tenant IDs from the tenants CSV (one ID per row or a column header),
checks only the reservation `tenant_id` field, and if that tenant ID is present in the
reservation it writes that reservation (all columns) to the output CSV and marks
which tenant matched in an additional column `matched_tenants`.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
from collections import defaultdict
from typing import List


def read_tenant_ids(path: pathlib.Path) -> List[str]:
	ids: List[str] = []
	with path.open("r", encoding="utf-8-sig", errors="replace") as f:
		reader = csv.reader(f)
		for row in reader:
			if not row:
				continue
			# Accept files that are single-column or have header like 'Tenant ID' and one column of values
			# Find first cell that looks numeric and use it.
			for cell in row:
				s = cell.strip()
				if s == "":
					continue
				# drop non-digit characters around and keep digits if the cell is numeric-like
				if re.search(r"\d", s):
					# keep only digits to normalize (tenant IDs in your provided file are plain numbers)
					normalized = re.sub(r"[^0-9]", "", s)
					if normalized:
						ids.append(normalized)
						break
	# unique while preserving order
	seen = set()
	result = []
	for i in ids:
		if i not in seen:
			seen.add(i)
			result.append(i)
	return result


def reservation_matches_tenants(row: dict, tenant_set: set) -> List[str]:
	# Match only on the reservation's tenant_id field.
	tenant_value = str(row.get("tenant_id", "")).strip()
	if tenant_value and tenant_value in tenant_set:
		return [tenant_value]
	return []


def main() -> None:
	ap = argparse.ArgumentParser(description="Filter reservations for a list of tenant IDs")
	ap.add_argument("--tenants", required=True, help="Path to tenant CSV (one ID per row)")
	ap.add_argument("--reservations", required=True, help="Path to reservations CSV")
	ap.add_argument("--output", default="matched_reservations.csv", help="Output CSV path")
	args = ap.parse_args()

	tenants_path = pathlib.Path(args.tenants)
	reservations_path = pathlib.Path(args.reservations)
	out_path = pathlib.Path(args.output)

	tenant_ids = read_tenant_ids(tenants_path)
	if not tenant_ids:
		print(f"No tenant IDs found in {tenants_path}")
		return
	tenant_set = set(tenant_ids)

	counts = defaultdict(int)
	total_rows = 0
	matched_rows = 0

	# Desired output columns (use these exactly, in order). Duplicate names are preserved once.
	desired_columns = [
		"Brand Model","Hotel Name","Reservation No","Room Name","Room Type","Guest Name",
		"Create Date","Guest Email","Guest Mobile","Guest Gender","Guest Country","Guest Citizen Level",
		"Guest Return Status","Guest Sign up Date","Type","Checkin","Checkout","Room rent only",
		"Total Service Cost","Total Breakfast Cost","Other Revenue","Room Night","Revenue","ADR",
		"Direct Channel","OTA Channel","Booking Source","Booking Type","Purpose of Stay","Company (VAT)",
		"Company Email (VAT)","Company Type (VAT)","Segment Room Type","Brand Segment","Brand Sub Segment",
		"Hotel Code","City","District","Partner Occupation","Booking Note","Room Discount","code",
		"Guest Sign up Date","Sign-up Status","industry_name","Lead From","property_model","b2b_lead_created_date",
		"Room Night","company churn status","TA Type",
		"matched_tenants",
	]

	# dedupe while preserving order (in case of duplicates like 'Room Night')
	seen_col = set()
	out_fieldnames = []
	for c in desired_columns:
		if c not in seen_col:
			seen_col.add(c)
			out_fieldnames.append(c)

	with reservations_path.open("r", encoding="utf-8-sig", errors="replace") as inf:
		reader = csv.DictReader(inf)
		fieldnames = reader.fieldnames or []

		with out_path.open("w", encoding="utf-8", newline="") as outf:
			writer = csv.DictWriter(outf, fieldnames=out_fieldnames)
			writer.writeheader()

			for row in reader:
				total_rows += 1
				matched = reservation_matches_tenants(row, tenant_set)
				if matched:
					matched_rows += 1
					for t in matched:
						counts[t] += 1
					# build output row using only desired columns (missing columns -> empty)
					row_out = {c: row.get(c, "") for c in out_fieldnames}
					row_out["matched_tenants"] = ",".join(matched)
					writer.writerow(row_out)

	print(f"Scanned {total_rows} reservation rows")
	print(f"Found {matched_rows} matching reservation rows")
	print("Matches per tenant:")
	for t in tenant_ids:
		if counts[t]:
			print(f"  {t}: {counts[t]}")


if __name__ == "__main__":
	main()

