import requests
from requests.auth import HTTPBasicAuth
import mysql.connector
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================
# CONFIG
# ============================================

V1_API_KEY = "xxxxxxxxx"
V1_API_SECRET = "xxxxxxxxxxxx"
V2_API_KEY = "xxxxxxxxxxxx"

MAX_THREADS = 10   # You can increase to 15 if server allows

# ============================================
# DATABASE CONNECTION
# ============================================


mydb = mysql.connector.connect(
    host="xxxxxx",
    user="xxxxxx",
    password="xxxxxxxxxx",
    database="sxxxxxxxxxx"
)

cursor = mydb.cursor(dictionary=True)

# ============================================
# FETCH SHIPMENTS
# ============================================

query = """
SELECT trackingnumber
FROM shipped_orders_header
WHERE  (deliverystatus IS NULL OR deliverystatus Not like '%Delivered%') AND 
shipdate BETWEEN '2025-12-01' AND '2026-02-28'
LIMIT 2000
"""

cursor.execute(query)
rows = cursor.fetchall()

print(f"🔎 Found {len(rows)} shipments to check.\n")

# ============================================
# SAFE DATE PARSER
# ============================================

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except:
        return None

# ============================================
# REUSABLE SESSION
# ============================================

session = requests.Session()

def get_tracking_details(tracking_number):

    try:
        # ---- V1 ----
        v1_url = "https://ssapi.shipstation.com/shipments"
        params = {"trackingNumber": tracking_number}

        v1_response = session.get(
            v1_url,
            params=params,
            auth=HTTPBasicAuth(V1_API_KEY, V1_API_SECRET),
            timeout=10
        )

        if v1_response.status_code != 200:
            return None

        v1_data = v1_response.json()
        if not v1_data.get("shipments"):
            return None

        shipment = v1_data["shipments"][0]
        shipment_id = shipment["shipmentId"]
        label_creation_date = shipment.get("shipDate")

        label_id = f"se-{shipment_id}"

        # ---- V2 ----
        v2_url = f"https://api.shipstation.com/v2/labels/{label_id}/track"
        headers = {"API-Key": V2_API_KEY}

        v2_response = session.get(v2_url, headers=headers, timeout=10)

        if v2_response.status_code != 200:
            return None

        tracking_data = v2_response.json()
        events = tracking_data.get("events", [])

        if not events:
            return (
                "No Tracking Events",
                label_creation_date,
                None,
                None,
                None,
                tracking_number
            )

        processed = []

        for event in events:
            event_time = (
                event.get("event_time") or
                event.get("occurred_at") or
                event.get("created_at")
            )

            processed.append({
                "description": event.get("description"),
                "datetime": parse_date(event_time)
            })

        processed.sort(
            key=lambda x: x["datetime"] or datetime.min,
            reverse=True
        )

        current_status = processed[0]["description"]
        last_action_date = processed[0]["datetime"]

        delivered_date = None
        for event in processed:
            if event["description"] and "deliver" in event["description"].lower():
                delivered_date = event["datetime"]
                current_status = "Delivered"
                break

        expected_delivery_date = parse_date(
            tracking_data.get("estimated_delivery_date")
        )

        return (
            current_status,
            label_creation_date,
            last_action_date,
            expected_delivery_date,
            delivered_date,
            tracking_number
        )

    except:
        return None

# ============================================
# MULTITHREADED PROCESSING
# ============================================

update_query = """
UPDATE shipped_orders_header
SET deliverystatus = %s,
    label_creation_date = %s,
    last_action_date = %s,
    expected_delivery_date = %s,
    delivered_date = %s
WHERE trackingnumber = %s
"""

results = []

with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    futures = [
        executor.submit(get_tracking_details, row["trackingnumber"])
        for row in rows
    ]

    for future in as_completed(futures):
        result = future.result()
        if result:
            results.append(result)

# ============================================
# BATCH UPDATE (VERY IMPORTANT)
# ============================================

if results:
    cursor.executemany(update_query, results)
    mydb.commit()

print(f"✅ Updated {len(results)} shipments.")
print("🎯 Process completed successfully.")

cursor.close()
mydb.close()
