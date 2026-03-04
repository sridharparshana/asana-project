import requests
import mysql.connector

# ============================================
# CONFIG
# ============================================

ASANA_TOKEN = "2/xxxxxxx1"

SECTION_IDS = {
    "1212808697694742": "In Processing",
    "1212808697694741": "New orders"
}

FULFILLED_ENUM_ID = "1212808697694754"

TRACKING_UPDATED_FIELD_ID = "1212924453496694"
TRACKING_YES_ENUM_ID = "1212924453496695"
TRACKING_NO_ENUM_ID = "1212924453496696"

# 🔥 NEW FIELD (Replace with your actual GID)
SHIPPED_FROM_FIELD_ID = "1213449649079983"

USA_WAREHOUSES = {749617, 749619, 749620}
OTHER_WAREHOUSES = {749637, 749638, 749639, 749640, 749641, 749643}

db_config = {
    "host": "1xxxxx",
    "user": "xxxxxx",
    "password": "xxxxxxxx",
    "database": "sxxxxxx"
}


headers = {
    "Authorization": f"Bearer {ASANA_TOKEN}"
}

# ============================================
# DB CONNECTION
# ============================================

conn = mysql.connector.connect(**db_config)
cursor = conn.cursor(buffered=True)

# ============================================
# 🔥 PRELOAD WAREHOUSE LOCATIONS (FAST)
# ============================================

def preload_warehouse_locations():

    cursor.execute("SELECT id, Location FROM StoreId")
    rows = cursor.fetchall()

    # Keep everything as string
    return {str(id_): location for id_, location in rows}


# ============================================
# GET TASKS
# ============================================

def get_tasks_from_section(section_id):

    url = (
        f"https://app.asana.com/api/1.0/sections/{section_id}/tasks"
        f"?opt_fields=name,custom_fields.name,custom_fields.gid,custom_fields.text_value"
    )

    all_tasks = []

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        all_tasks.extend(data["data"])
        next_page = data.get("next_page")
        url = next_page["uri"] if next_page else None

    return all_tasks


# ============================================
# BULK HEADER FETCH
# ============================================

def get_header_data(order_numbers):

    if not order_numbers:
        return {}

    format_strings = ','.join(['%s'] * len(order_numbers))

    query = f"""
        SELECT ordernumber, trackingnumber, warehouseid
        FROM shipped_orders_header
        WHERE ordernumber IN ({format_strings})
    """

    cursor.execute(query, tuple(order_numbers))
    rows = cursor.fetchall()

    return {
        str(ordernumber): (trackingnumber, int(warehouseid))
        for ordernumber, trackingnumber, warehouseid in rows
    }


# ============================================
# BULK FIRST MILE FETCH
# ============================================

def get_first_mile_data(order_numbers):

    if not order_numbers:
        return {}

    format_strings = ','.join(['%s'] * len(order_numbers))

    query = f"""
        SELECT orderitemid, trackingnumber FROM tbl_stocktransfer
        WHERE orderitemid IN ({format_strings})
        UNION
        SELECT orderitemid, trackingnumber FROM tbl_stock_intransit
        WHERE orderitemid IN ({format_strings})
    """

    cursor.execute(query, tuple(order_numbers) * 2)
    rows = cursor.fetchall()

    firstmile_map = {}
    for orderitemid, trackingnumber in rows:
        firstmile_map.setdefault(str(orderitemid), trackingnumber)

    return firstmile_map


# ============================================
# UPDATE TASK
# ============================================

def update_task(task_id, payload):
    url = f"https://app.asana.com/api/1.0/tasks/{task_id}"
    response = requests.put(url, headers=headers, json={"data": payload})
    response.raise_for_status()


# ============================================
# MAIN
# ============================================

def main():

    overall_total = 0
    overall_updated = 0

    # 🔥 preload locations once
    warehouse_locations = preload_warehouse_locations()

    print("\n========== START FAST PROCESS ==========\n")

    for section_id, section_name in SECTION_IDS.items():

        print(f"\n--- Processing Section: {section_name} ---\n")

        tasks = get_tasks_from_section(section_id)
        overall_total += len(tasks)

        order_map = {}
        field_map = {}

        for task in tasks:

            task_id = task["gid"]
            task_name = task["name"]

            order_number = None
            lastmile_field = None
            firstmile_field = None
            orderstatus_field = None

            for field in task["custom_fields"]:
                name = field["name"].strip().lower()

                if name == "order number":
                    order_number = field.get("text_value")
                elif name == "last mile tracking":
                    lastmile_field = field["gid"]
                elif name == "first mile tracking":
                    firstmile_field = field["gid"]
                elif name == "order status":
                    orderstatus_field = field["gid"]

            if order_number:
                clean = order_number.lstrip("#").strip()
                order_map[task_id] = clean
                field_map[task_id] = (
                    task_name,
                    lastmile_field,
                    firstmile_field,
                    orderstatus_field
                )

        if not order_map:
            continue

        order_numbers = list(order_map.values())

        header_data = get_header_data(order_numbers)
        firstmile_data = get_first_mile_data(order_numbers)

        section_updated = 0

        for task_id, order_number in order_map.items():

            task_name, lastmile_field, firstmile_field, orderstatus_field = field_map[task_id]

            if order_number not in header_data:
                continue

            trackingnumber, warehouseid = header_data[order_number]
            warehouse_name = warehouse_locations.get(str(warehouseid), "Unknown")

            payload = {"custom_fields": {}}

            # Insert warehouse name in Shipped_from
            payload["custom_fields"][SHIPPED_FROM_FIELD_ID] = warehouse_name

            # USA warehouse
            if warehouseid in USA_WAREHOUSES:

                payload["custom_fields"][lastmile_field] = trackingnumber
                payload["custom_fields"][firstmile_field] = "went from usa"
                payload["custom_fields"][orderstatus_field] = FULFILLED_ENUM_ID
                payload["custom_fields"][TRACKING_UPDATED_FIELD_ID] = TRACKING_YES_ENUM_ID

            elif warehouseid in OTHER_WAREHOUSES:

                payload["custom_fields"][lastmile_field] = trackingnumber

                if order_number in firstmile_data:
                    payload["custom_fields"][firstmile_field] = firstmile_data[order_number]
                    payload["custom_fields"][TRACKING_UPDATED_FIELD_ID] = TRACKING_YES_ENUM_ID
                else:
                    payload["custom_fields"][TRACKING_UPDATED_FIELD_ID] = TRACKING_NO_ENUM_ID

                payload["custom_fields"][orderstatus_field] = FULFILLED_ENUM_ID

            else:
                continue

            update_task(task_id, payload)
            section_updated += 1
            overall_updated += 1

            print(f"{task_id} | {task_name} → Updated")

        print(f"\nSection Updated: {section_updated}")

    print("\n========== FINAL SUMMARY ==========")
    print(f"Total Tasks Checked : {overall_total}")
    print(f"Total Orders Updated: {overall_updated}")
    print("====================================\n")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
