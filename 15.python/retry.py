import csv
import requests

API_URL = "https://longstay.mvillage.vn/add-landlord-info"

with open("/Users/hchinhtrung/Documents/GitHub/mvillage-email-template/15.python/Landlord Landing Page - Production - fail.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        data = {
            "name": row["name"],
            "email": row["email"],
            "phone": row["phone"],
            "area": row["area"],
            "address": row["address"],
            "size": int(row["size"]),
            "room": int(row["room"])
        }
        print("Sending:", data)
        response = requests.post(API_URL, json=data)
        print(response.status_code, response.text)