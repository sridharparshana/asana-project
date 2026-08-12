import requests
import mysql.connector
from datetime import datetime, timedelta, timezone
import time


# ==== DATABASE CONFIG ====
DB_CONFIG = {
    'host': '3xxx',
    'user': 'dbxxxx',
    'password': 'Nxxxxxxax',
    'database': 'stockxxxxxxx'
}

# ==== SHOPIFY CONFIG ====
SHOP_NAME = "xxxxxx"
ACCESS_TOKEN = "shpat_7d55d0b95xxxxxx"
API_VERSION = "2024-07"

SHOPIFY_URL = (
    f"https://{SHOP_NAME}.myshopify.com/"
    f"admin/api/{API_VERSION}/orders.json"
)

HEADERS = {
    "X-Shopify-Access-Token": ACCESS_TOKEN,
    "Content-Type": "application/json"
}

# SETTINGS
DAYS_TO_FETCH = 90
# Number of records sent to MySQL at one time
BATCH_SIZE = 500
# DATE RANGE
end_date = datetime.now(timezone.utc)

start_date = (
    end_date -
    timedelta(days=DAYS_TO_FETCH)
)
# HELPER FUNCTIONS
def safe_string(value, max_length=None):
    """
    Convert None/problematic values to empty string.
    Optionally limit the length.
    """

    if value is None:
        return ""

    try:
        value = str(value)
    except Exception:
        return ""

    if max_length is not None:
        return value[:max_length]

    return value


def safe_float(value):
    try:
        if value is None or value == "":
            return 0.0

        return float(value)

    except (ValueError, TypeError):
        return 0.0


def safe_int(value):
    try:
        if value is None or value == "":
            return 0

        return int(value)

    except (ValueError, TypeError):
        return 0


def safe_date(value):
    """
    Convert Shopify datetime to YYYY-MM-DD.
    """

    if not value:
        return None

    try:
        return value[:10]

    except Exception:
        return None
# FETCH SHOPIFY ORDERS
# ============================================================
def fetch_shopify_orders():

    orders = []

    url = SHOPIFY_URL

    params = {
        "status": "any",
        "created_at_min": start_date.strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "created_at_max": end_date.strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "limit": 250
    }

    page = 0

    while url:

        page += 1

        print(
            f"📥 Fetching Shopify page {page}..."
        )

        response = None

        # API RETRY
        for attempt in range(1, 6):

            try:

                response = requests.get(
                    url,
                    headers=HEADERS,
                    params=params,
                    timeout=60
                )

                # Success
                if response.status_code == 200:
                    break

                # Rate limit
                if response.status_code == 429:

                    wait_time = int(
                        response.headers.get(
                            "Retry-After",
                            5
                        )
                    )

                    print(
                        f"⚠️ Shopify rate limit. "
                        f"Waiting {wait_time}s..."
                    )

                    time.sleep(wait_time)

                    continue

                # Temporary Shopify error
                if response.status_code in (
                    500,
                    502,
                    503,
                    504
                ):

                    wait_time = attempt * 3

                    print(
                        f"⚠️ Shopify server error "
                        f"{response.status_code}. "
                        f"Retrying in {wait_time}s..."
                    )

                    time.sleep(wait_time)

                    continue

                # Other error
                print(
                    f"❌ Shopify API Error: "
                    f"{response.status_code}"
                )

                print(
                    response.text[:500]
                )

                response = None

                break

            except requests.exceptions.RequestException as err:

                print(
                    f"⚠️ Shopify request error: "
                    f"{err}"
                )

                time.sleep(attempt * 3)


        if (
            response is None
            or response.status_code != 200
        ):

            print(
                "❌ Unable to fetch Shopify page."
            )

            break

        # JSON
        try:

            data = response.json()

        except Exception as err:

            print(
                f"❌ Invalid Shopify response: "
                f"{err}"
            )

            break


        page_orders = data.get(
            "orders",
            []
        )

        orders.extend(page_orders)

        print(
            f"   Page {page}: "
            f"{len(page_orders)} orders | "
            f"Total: {len(orders)}"
        )

        # PAGINATION

        next_url = None

        link_header = response.headers.get(
            "Link"
        )

        if link_header:

            for part in link_header.split(","):

                if 'rel="next"' in part:

                    next_url = (
                        part
                        .split(";")[0]
                        .strip()
                        .strip("<>")
                    )

                    break

        url = next_url

        # Parameters only required for first request
        params = {}


    return orders

# PREPARE DATABASE ROWS

def prepare_rows(orders):

    rows = []

    for order in orders:
        # ORDER INFORMATION

        order_number = safe_string(
            order.get("order_number"),
            100
        )

        fulfillment_status = safe_string(
            order.get("fulfillment_status"),
            100
        )

        financial_status = safe_string(
            order.get("financial_status"),
            100
        )

        orderdate = safe_date(
            order.get("created_at")
        )

        payment_gateway = safe_string(
            ", ".join(
                order.get(
                    "payment_gateway_names",
                    []
                )
            ),
            250
        )

        total_payment_usd = safe_float(
            order.get("total_price")
        )

        shipping_paid = safe_float(
            order
            .get(
                "total_shipping_price_set",
                {}
            )
            .get(
                "shop_money",
                {}
            )
            .get(
                "amount",
                0
            )
        )

        tax_amount = safe_float(
            order.get("total_tax")
        )

        # CUSTOMER
        customer = (
            order.get("customer")
            or {}
        )

        customerid = safe_string(
            customer.get("id"),
            100
        )

        customername = safe_string(
            (
                safe_string(
                    customer.get("first_name")
                )
                + " "
                + safe_string(
                    customer.get("last_name")
                )
            ).strip(),
            255
        )

        customeremail = safe_string(
            customer.get("email"),
            255
        )

        customerphone = safe_string(
            customer.get("phone"),
            100
        )
        # SHIPPING ADDRESS

        shipping_address = (
            order.get("shipping_address")
            or {}
        )

        shippingaddress1 = safe_string(
            shipping_address.get("address1"),
            500
        )

        address2 = safe_string(
            shipping_address.get("address2"),
            250
        )

        city = safe_string(
            shipping_address.get("city"),
            255
        )

        country = safe_string(
            shipping_address.get("country"),
            100
        )

        # FULFILLMENT

        fulfillment_date = None

        tracking_numbers = []

        for fulfillment in (
            order.get("fulfillments")
            or []
        ):

            if not fulfillment_date:

                fulfillment_date = safe_date(
                    fulfillment.get(
                        "created_at"
                    )
                )

            tracking_numbers.extend(
                fulfillment.get(
                    "tracking_numbers",
                    []
                )
                or []
            )

        trackingnumber = safe_string(
            ", ".join(tracking_numbers),
            1000
        )

        # REFUNDED ITEMS

        refunded_items = {}

        for refund in (
            order.get("refunds")
            or []
        ):

            for refund_line in (
                refund.get(
                    "refund_line_items",
                    []
                )
                or []
            ):

                line_item = (
                    refund_line.get(
                        "line_item"
                    )
                    or {}
                )

                refund_sku = safe_string(
                    line_item.get("sku")
                )

                refund_qty = safe_int(
                    refund_line.get(
                        "quantity"
                    )
                )

                refunded_items[
                    refund_sku
                ] = (
                    refunded_items.get(
                        refund_sku,
                        0
                    )
                    + refund_qty
                )

        # LINE ITEMS

        for item in (
            order.get("line_items")
            or []
        ):

            sku = safe_string(
                item.get("sku"),
                255
            )

            quantity = safe_int(
                item.get("quantity")
            )

            quantity_refunded = safe_int(
                refunded_items.get(
                    sku,
                    0
                )
            )

            # ITEM STATUS
            if (
                quantity_refunded >= quantity
                and quantity > 0
            ):

                item_status = "Refunded"

            elif (
                quantity_refunded > 0
                and quantity_refunded < quantity
            ):

                item_status = (
                    "Partially Refunded"
                )

            else:

                item_status = (
                    fulfillment_status
                    or "Unfulfilled"
                )


            # ITEM INFORMATION

            item_name = safe_string(
                item.get("name"),
                500
            )

            unit_price_usd = safe_float(
                item.get("price")
            )

            discount_amount = 0.0

            for discount in (
                item.get(
                    "discount_allocations",
                    []
                )
                or []
            ):

                discount_amount += safe_float(
                    discount.get("amount")
                )

            lineitemkey = safe_string(
                item.get("id"),
                100
            )

            # FINAL ROW

            rows.append(
                (
                    orderdate,
                    order_number,
                    lineitemkey,
                    item_status,
                    sku,
                    item_name,
                    quantity,
                    quantity_refunded,
                    unit_price_usd,
                    discount_amount,
                    tax_amount,
                    shipping_paid,
                    total_payment_usd,
                    payment_gateway,
                    financial_status,
                    fulfillment_date,
                    trackingnumber,
                    customerid,
                    customername,
                    customeremail,
                    customerphone,
                    shippingaddress1,
                    address2,
                    city,
                    country
                )
            )

    return rows


INSERT_SQL = """
INSERT IGNORE INTO tbl_pushmycartusa_sales (
    orderdate,
    ordernumber,
    lineitemkey,
    orderstatus,
    sku,
    item_name,
    quantity,
    quantity_refunded,
    unit_price_usd,
    discountamount,
    taxamount,
    shippingpaid,
    total_payment_usd,
    payment_gateway,
    financial_status,
    fulfillment_date,
    trackingnumber,
    customerid,
    customername,
    customeremail,
    customerphone,
    shippingaddress1,
    address2,
    city,
    country
)
VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s
)
"""

# FALLBACK FOR A BAD BATCH

def clean_row(row):

    """
    If a row causes a database error,
    keep the important order/item information
    and empty optional text fields.
    """

    row = list(row)

    # Keep:
    # orderdate
    # ordernumber
    # lineitemkey
    # orderstatus
    # sku
    # quantity
    # price
    # etc.

    # Empty optional fields

    row[5] = ""       # item_name
    row[13] = ""      # payment_gateway
    row[16] = ""      # trackingnumber
    row[18] = ""      # customername
    row[19] = ""      # customeremail
    row[20] = ""      # customerphone
    row[21] = ""      # shippingaddress1
    row[22] = ""      # address2
    row[23] = ""      # city
    row[24] = ""      # country

    return tuple(row)


# ============================================================
# MAIN
# ============================================================

print("\n")
print("==============================================")
print("       SHOPIFY FAST ORDER SYNC")
print("==============================================")

start_time = time.time()

# STEP 1 - FETCH

orders = fetch_shopify_orders()

print(
    f"\n📦 Total Orders Fetched: "
    f"{len(orders)}"
)


if not orders:

    print(
        "⚠️ No orders found."
    )

    raise SystemExit


# STEP 2 - PREPARE

print(
    "\n🔧 Preparing line items..."
)

rows = prepare_rows(
    orders
)

total_rows = len(rows)

print(
    f"📦 Total Line Items: "
    f"{total_rows}"
)

# STEP 3 - DATABASE CONNECTION
try:

    mydb = mysql.connector.connect(
        **DB_CONFIG
    )

    mycursor = mydb.cursor()

    print(
        "✅ Database connected."
    )

except mysql.connector.Error as err:

    print(
        f"❌ Database connection failed: "
        f"{err}"
    )

    raise SystemExit

# STEP 4 - BULK INSERT

inserted_count = 0
skipped_count = 0
failed_count = 0

try:

    print(
        "\n🚀 Starting bulk insertion..."
    )

    for start in range(
        0,
        total_rows,
        BATCH_SIZE
    ):

        end = min(
            start + BATCH_SIZE,
            total_rows
        )

        batch = rows[start:end]

        # NORMAL BULK INSERT

        try:

            mycursor.executemany(
                INSERT_SQL,
                batch
            )

            affected = mycursor.rowcount

            inserted_count += affected

            skipped_count += (
                len(batch) - affected
            )

            print(
                f"   🟢 Batch "
                f"{start + 1}-{end} | "
                f"Inserted: {affected} | "
                f"Skipped: "
                f"{len(batch) - affected}"
            )


        except mysql.connector.Error as batch_error:

            print(
                f"\n⚠️ Batch "
                f"{start + 1}-{end} "
                f"encountered an error."
            )

            print(
                f"   Error: {batch_error}"
            )

            print(
                "   🔧 Processing this batch "
                "individually..."
            )

            mydb.rollback()

            for row in batch:

                try:

                    mycursor.execute(
                        INSERT_SQL,
                        row
                    )

                    affected = mycursor.rowcount

                    if affected == 1:

                        inserted_count += 1

                    else:

                        skipped_count += 1


                except mysql.connector.Error:

                    try:

                        cleaned_row = clean_row(
                            row
                        )

                        mycursor.execute(
                            INSERT_SQL,
                            cleaned_row
                        )

                        affected = (
                            mycursor.rowcount
                        )

                        if affected == 1:

                            inserted_count += 1

                            print(
                                f"      🟡 Inserted "
                                f"after cleaning: "
                                f"Order {row[1]} | "
                                f"Line {row[2]}"
                            )

                        else:

                            skipped_count += 1


                    except mysql.connector.Error as final_error:

                        failed_count += 1

                        print(
                            f"      🔴 Failed: "
                            f"Order {row[1]} | "
                            f"Line {row[2]} | "
                            f"{final_error}"
                        )

        processed = end

        percent = (
            processed / total_rows
        ) * 100

        print(
            f"      Progress: "
            f"{processed}/{total_rows} "
            f"({percent:.1f}%)"
        )

    print(
        "\n💾 Committing all records..."
    )

    mydb.commit()

    print(
        "✅ All records committed successfully."
    )


except Exception as err:

    print(
        f"\n❌ Fatal database error: "
        f"{err}"
    )

    print(
        "⚠️ Rolling back entire transaction..."
    )

    mydb.rollback()

    raise


finally:

    try:
        mycursor.close()
    except Exception:
        pass

    try:
        mydb.close()
    except Exception:
        pass

elapsed_seconds = (
    time.time() - start_time
)

elapsed_minutes = (
    elapsed_seconds / 60
)


print("\n")
print("==============================================")
print("             SYNC COMPLETED")
print("==============================================")

print(
    f"📦 Orders fetched   : "
    f"{len(orders)}"
)

print(
    f"📦 Line items       : "
    f"{total_rows}"
)

print(
    f"🟢 Inserted         : "
    f"{inserted_count}"
)

print(
    f"⏭️ Already existed   : "
    f"{skipped_count}"
)

print(
    f"🔴 Failed            : "
    f"{failed_count}"
)

print(
    f"⏱️ Total time        : "
    f"{elapsed_minutes:.2f} minutes"
)

print("==============================================")
