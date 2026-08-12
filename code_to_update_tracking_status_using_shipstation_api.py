import requests
from requests.auth import HTTPBasicAuth
import mysql.connector
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import time
import random

# ============================================
# CONFIG ( CAN GET API'S FROM SHIPSATATION WEBSITE)
# ============================================
V1_API_KEY = "a9axxxxxxx"
V1_API_SECRET = "fxxxxxxxx"
V2_API_KEY = "JBbOxxxxxxxxxx"

# Reduced threads to avoid aggressive rate limiting
MAX_THREADS = 5 
CSV_PATH = r"C:\Users\navaj\Desktop\Code files\trackingsoutput.csv"

# ============================================
# DATABASE SETUP
# ============================================
def get_db_connection():
    return mysql.connector.connect(
        host="host",
        user="dbuser",
        password="password",
        database="database"
    )

def parse_date(date_str):
    if not date_str: 
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except:
        return None

# ============================================
# TRACKING FUNCTION (With Retry Logic)
# ============================================
def process_tracking(row):
    tracking_number = str(row["trackingnumber"]).strip()
    
    # [status, label_date, last_action, expected, delivered_at, tracking]
    res = ["Pending", None, None, None, None, tracking_number]
    
    local_session = requests.Session()
    
    for attempt in range(3):
        try:
            # -------- V1 API --------
            r1 = local_session.get(
                "https://ssapi.shipstation.com/shipments",
                params={"trackingNumber": tracking_number, "pageSize": 100},
                auth=HTTPBasicAuth(V1_API_KEY, V1_API_SECRET),
                timeout=25
            )

            if r1.status_code == 429:
                time.sleep(random.uniform(2, 5))
                continue
            
            if r1.status_code != 200:
                res[0] = f"V1 Error {r1.status_code}"
                return res

            data = r1.json()
            shipments = data.get("shipments", [])

            if not shipments:
                res[0] = "Shipment Not Found in SS"
                return res

            shipment = shipments[0]
            label_id = f"se-{shipment['shipmentId']}"
            res[1] = shipment.get("shipDate")

            # -------- V2 API --------
            r2 = local_session.get(
                f"https://api.shipstation.com/v2/labels/{label_id}/track",
                headers={"API-Key": V2_API_KEY},
                timeout=25
            )

            if r2.status_code == 429:
                time.sleep(random.uniform(2, 5))
                continue

            if r2.status_code != 200:
                res[0] = "Carrier Status Not Available"
                return res

            tracking = r2.json()
            events = tracking.get("events", [])

            if not events:
                res[0] = "Label Created (No Events)"
                return res

            # Parse Events
            processed = []
            for e in events:
                e_time = e.get("event_time") or e.get("occurred_at") or e.get("created_at")
                processed.append({
                    "desc": e.get("description"),
                    "dt": parse_date(e_time)
                })

            processed.sort(key=lambda x: x["dt"] or datetime.min, reverse=True)

            res[0] = processed[0]["desc"]
            res[2] = processed[0]["dt"]
            res[3] = parse_date(tracking.get("estimated_delivery_date"))

            for event in processed:
                if event["desc"] and "deliver" in event["desc"].lower():
                    res[4] = event["dt"]
                    res[0] = "Delivered"
                    break
            
            return res

        except Exception as e:
            time.sleep(2)
            res[0] = f"Script Error: {str(e)[:20]}"
    
    return res

# ============================================
# MAIN EXECUTION
# ============================================
db = get_db_connection()
cursor = db.cursor(dictionary=True)

query = """
SELECT trackingnumber FROM shipped_orders_header
WHERE (deliverystatus NOT LIKE '%deliv%' AND deliverystatus NOT LIKE '%Refund%' OR deliverystatus IS NULL)
AND shipdate BETWEEN '2026-01-01' AND '2028-12-30' AND modifiedon <= NOW() - INTERVAL 1 DAY
ORDER BY id DESC LIMIT 500
"""

cursor.execute(query)
rows = cursor.fetchall()
print(f"🔎 Processing {len(rows)} shipments...")

results = []
with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    futures = [executor.submit(process_tracking, row) for row in rows]
    for future in as_completed(futures):
        res = future.result()
        results.append(res)
        print(f"📦 {res[5]} -> {res[0]}")

# ============================================
# DB UPDATE (ONE BY ONE + RECONNECT SAFE)
# ============================================
valid_for_db = [r for r in results if "Not Found" not in r[0] and "Error" not in r[0]]

update_sql = """
UPDATE shipped_orders_header 
SET deliverystatus=%s, 
    label_creation_date=%s, 
    last_action_date=%s, 
    expected_delivery_date=%s, 
    delivered_date=%s,
    modifiedon = current_timestamp()
WHERE trackingnumber=%s
"""

def safe_update(db, cursor, record):
    try:
        cursor.execute(update_sql, record)
        db.commit()
    except mysql.connector.Error as err:
        print(f"⚠️ DB Error: {err}, reconnecting...")

        try:
            db.reconnect(attempts=3, delay=2)
            cursor = db.cursor()
            cursor.execute(update_sql, record)
            db.commit()
        except Exception as e:
            print(f"❌ Failed again for {record[-1]}: {e}")

# --- LOOP ONE BY ONE ---
for r in valid_for_db:
    safe_update(db, cursor, r)

# ============================================
# CSV EXPORT
# ============================================
df = pd.DataFrame(results, columns=[
    'latestupdate', 'label_creation', 'updatedon', 
    'expected', 'delivered_at', 'trackingnumber'
])

df[['trackingnumber', 'latestupdate', 'updatedon']].to_csv(CSV_PATH, index=False)

cursor.close()
db.close()

print(f"\n🎯 Done. CSV saved to {CSV_PATH}")
