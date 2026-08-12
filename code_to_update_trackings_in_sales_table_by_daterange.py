import requests
import mysql.connector
from datetime import datetime, timedelta, timezone

# ==== DATABASE CONFIG ====
DB_CONFIG = {
    'host': 'xxxx',
    'user': 'xxxxxxxx',
    'password': 'Nova@2026',
    'database': 'xxxxx'
}

# ==== SHOPIFY CONFIG ====
SHOP_NAME = "xxxxxx"
ACCESS_TOKEN = "shpaxxxx"
API_VERSION = "2024-07"


start_date = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
end_date = datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc)

url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{API_VERSION}/orders.json"
headers = {
    "X-Shopify-Access-Token": ACCESS_TOKEN,
    "Content-Type": "application/json"
}
params = {
    "status": "any",
    "created_at_min": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
    "created_at_max": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
    "limit": 250
}

orders = []

while url:
    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Shopify API Error: {response.status_code}")
        print(response.text)
        break

    orders.extend(response.json().get("orders", []))
    params = {}

    next_url = None
    link = response.headers.get("Link")
    if link:
        for part in link.split(","):
            if 'rel="next"' in part:
                next_url = part.split(";")[0].strip()[1:-1]
                break
    url = next_url

if not orders:
    print("No orders found.")
    raise SystemExit

db = mysql.connector.connect(**DB_CONFIG)
cur = db.cursor()

cur.execute("DELETE FROM tbl_pushmycartusa_orderstatus")
db.commit()

insert_sql = """
INSERT INTO tbl_pushmycartusa_orderstatus(
orderdate,ordernumber,lineitemkey,orderstatus,sku,quantity,
quantity_refunded,payment_gateway,financial_status,
fulfillment_date,trackingnumber,carrier,trackingstatus
)
VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

for order in orders:

    order_number = order["order_number"]
    fulfillment_status = order.get("fulfillment_status")
    financial_status = order.get("financial_status")
    orderdate = datetime.strptime(
        order["created_at"][:10], "%Y-%m-%d"
    ).strftime("%Y-%m-%d")

    payment_gateway = ", ".join(order.get("payment_gateway_names", []))

    fulfillment_date = None
    trackingnumber = ""
    carrier = ""
    trackingstatus = ""

    if order.get("fulfillments"):
        f = order["fulfillments"][0]

        if f.get("created_at"):
            fulfillment_date = f["created_at"][:10]

        trackingnumber = ", ".join(f.get("tracking_numbers", []))
        carrier = f.get("tracking_company") or f.get("name") or ""

        # Shopify shipment status
        trackingstatus = f.get("shipment_status") or ""

    refunded = {}
    for refund in order.get("refunds", []):
        for r in refund.get("refund_line_items", []):
            li = r.get("line_item", {})
            sku = li.get("sku")
            refunded[sku] = refunded.get(sku, 0) + r.get("quantity", 0)

    for item in order.get("line_items", []):

        sku = item.get("sku")
        qty = item.get("quantity", 0)
        qty_ref = refunded.get(sku, 0)

        if qty_ref >= qty:
            status = "Refunded"
        elif qty_ref > 0:
            status = "Partially Refunded"
        else:
            status = fulfillment_status or "Unfulfilled"

        cur.execute(insert_sql, (
            orderdate,
            order_number,
            str(item["id"]),
            status,
            sku,
            qty,
            qty_ref,
            payment_gateway,
            financial_status,
            fulfillment_date,
            trackingnumber,
            carrier,
            trackingstatus
        ))

db.commit()

update_sql = """
UPDATE tbl_pushmycartusa_sales ps
JOIN tbl_pushmycartusa_orderstatus pso
ON ps.ordernumber=pso.ordernumber
AND ps.lineitemkey=pso.lineitemkey
SET
ps.orderstatus=pso.orderstatus,
ps.quantity_refunded=pso.quantity_refunded,
ps.financial_status=pso.financial_status,
ps.fulfillment_date=pso.fulfillment_date,
ps.trackingnumber=pso.trackingnumber,
ps.carrier=pso.carrier,
ps.trackingstatus=pso.trackingstatus
WHERE
NOT(ps.orderstatus <=> pso.orderstatus)
OR NOT(ps.quantity_refunded <=> pso.quantity_refunded)
OR NOT(ps.financial_status <=> pso.financial_status)
OR NOT(ps.fulfillment_date <=> pso.fulfillment_date)
OR NOT(ps.trackingnumber <=> pso.trackingnumber)
OR NOT(ps.carrier <=> pso.carrier) 
OR NOT(ps.trackingstatus <=> pso.trackingstatus);
"""

cur.execute(update_sql)
db.commit()

print(f"Processed {len(orders)} orders.")
print(f"Rows updated: {cur.rowcount}")

cur.close()
db.close()
