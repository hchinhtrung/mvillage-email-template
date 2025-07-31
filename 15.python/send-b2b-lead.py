import csv
import requests
import time

API_URL = "https://api-user.mvillage.vn/api/me/notification/send-b2b-email"
HEADERS = {"Content-Type": "application/json"}
CSV_FILE = "/Users/chinhtrung/Documents/GitHub/mvillage-email-template/15.python/multi.csv"

# Đọc file CSV
with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        payload = {
            "work_email": row.get("Work Email", "").strip(),
            "contact_person": row.get("Contact Person", "").strip(),
            "company_name": row.get("Company Name", "").strip(),
            "phone_number": row.get("Phone Number", "").strip(),
            "hotel_city": row.get("Hotel City", "").strip(),
            "budget_per_night": row.get("Budget per Night", "").strip(),
            "message": row.get("Message", "").strip(),
            "created_at": row.get("Created Date", "").strip() or "test"
        }

        print(f"Sending to {payload['work_email']} ...")
        response = requests.post(API_URL, headers=HEADERS, json=payload)

        if response.status_code == 200:
            print(f"[SUCCESS] {payload['work_email']}")
        else:
            print(f"[FAILED] {payload['work_email']} - {response.status_code} - {response.text}")

        time.sleep(0.5)  # tránh spam API