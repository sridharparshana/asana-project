import requests
import mysql.connector
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================
# CONFIG
# ============================================

ASANA_TOKEN = "2/1xxxxxxxxx"

SECTION_IDS = {
    "1211908062105523": "Pending orders",
    "1212933698863437": "New orders"
}

# ===== FIELD IDS =====
ORDERNUMBER_FIELD_ID = "1211962087393887"
ORDERSTATUS_FIELD_ID = "1211977779079495"
FIRST_MILE_FIELD_ID = "1211908268997914"
LAST_MILE_FIELD_ID = "1211932673075094"
SHIPPED_FROM_FIELD_ID = "1213449649079983"
TRACKING_UPDATED_FIELD_ID = "1212924453496694"

# ===== ENUM IDS =====
FULFILLED_ENUM_ID = "1211977781879000"
TRACKING_YES_ENUM_ID = "1212924453496695"
TRACKING_NO_ENUM_ID = "1212924453496696"

USA_WAREHOUSES = {749617, 749619, 749620}
OTHER_WAREHOUSES = {749637, 749638, 749639, 749640, 749641, 749643}

db_config = {
    "host": "18xxx",
    "user": "xxxx",
    "password": "xxxx",
    "database": "stxxxx"
}

headers = {
    "Authorization": f"Bearer {ASANA_TOKEN}"
}

# ============================================
# SESSION (FASTER HTTP)
# ============================================

session = requests.Session()
session.headers.update(headers)

# ============================================
# DB CONNECTION
# ============================================

conn = mysql.connector.connect(**db_config)
cursor = conn.cursor(buffered=True)

# ============================================
# PRELOAD WAREHOUSE LOCATIONS
# ============================================

def preload_warehouse_locations():
    cursor.execute("SELECT id, Location FROM StoreId")
    rows = cursor.fetchall()
    return {str(i): loc for i, loc in rows}

# ============================================
# GET TASKS
# ============================================

def get_tasks_from_section(section_id):

    url = (
        f"https://app.asana.com/api/1.0/sections/{section_id}/tasks"
        f"?opt_fields=name,created_at,custom_fields.gid,custom_fields.text_value"
    )

    tasks = []

    while url:
        r = session.get(url)
        r.raise_for_status()

        data = r.json()

        tasks.extend(data["data"])

        next_page = data.get("next_page")
        url = next_page["uri"] if next_page else None

    return tasks

# ============================================
# BULK DB FETCH
# ============================================

def get_header_data(order_numbers):

    if not order_numbers:
        return {}

    format_strings = ",".join(["%s"] * len(order_numbers))

    query = f"""
    SELECT ordernumber, trackingnumber, warehouseid
    FROM shipped_orders_header
    WHERE ordernumber IN ({format_strings})
    """

    cursor.execute(query, tuple(order_numbers))

    rows = cursor.fetchall()

    return {
        str(o): (t, int(w))
        for o, t, w in rows
    }


def get_first_mile_data(order_numbers):

    if not order_numbers:
        return {}

    format_strings = ",".join(["%s"] * len(order_numbers))

    query = f"""
    SELECT orderitemid, trackingnumber FROM tbl_stocktransfer
    WHERE orderitemid IN ({format_strings})
    UNION
    SELECT orderitemid, trackingnumber FROM tbl_stock_intransit
    WHERE orderitemid IN ({format_strings})
    """

    cursor.execute(query, tuple(order_numbers) * 2)

    rows = cursor.fetchall()

    fm = {}

    for oid, track in rows:
        fm.setdefault(str(oid), track)

    return fm

# ============================================
# UPDATE TASK
# ============================================

def update_task(task_id, payload):

    url = f"https://app.asana.com/api/1.0/tasks/{task_id}"

    r = session.put(url, json={"data": payload})

    r.raise_for_status()

# ============================================
# PROCESS ONE TASK (THREAD SAFE)
# ============================================

def process_task(task_data):

    task_id, raw_order, order_number, created_at = task_data

    created_at = created_at.replace("T", " ").replace(".000Z", " +0530")

    if order_number not in header_data:
        return f"{task_id} | {raw_order} | date: {created_at} → Not found in header", False

    trackingnumber, warehouseid = header_data[order_number]

    warehouse_name = warehouse_locations.get(str(warehouseid), "Unknown")

    payload = {"custom_fields": {}}

    payload["custom_fields"][SHIPPED_FROM_FIELD_ID] = warehouse_name
    payload["custom_fields"][LAST_MILE_FIELD_ID] = trackingnumber
    payload["custom_fields"][ORDERSTATUS_FIELD_ID] = FULFILLED_ENUM_ID

    if warehouseid in USA_WAREHOUSES:

        payload["custom_fields"][FIRST_MILE_FIELD_ID] = "went from usa"
        payload["custom_fields"][TRACKING_UPDATED_FIELD_ID] = TRACKING_YES_ENUM_ID

    elif warehouseid in OTHER_WAREHOUSES:

        if order_number in firstmile_data:

            payload["custom_fields"][FIRST_MILE_FIELD_ID] = firstmile_data[order_number]
            payload["custom_fields"][TRACKING_UPDATED_FIELD_ID] = TRACKING_YES_ENUM_ID

        else:

            payload["custom_fields"][TRACKING_UPDATED_FIELD_ID] = TRACKING_NO_ENUM_ID
            return f"{task_id} | {raw_order} | date: {created_at} → No first mile tracking", False

    else:

        return f"{task_id} | {raw_order} | date: {created_at} → Unknown warehouse", False

    try:

        update_task(task_id, payload)

        return f"{task_id} | {raw_order} | date: {created_at} → Updated", True

    except Exception:

        return f"{task_id} | {raw_order} | date: {created_at} → API Error", False

# ============================================
# MAIN
# ============================================

def main():

    global warehouse_locations
    global header_data
    global firstmile_data

    warehouse_locations = preload_warehouse_locations()

    total_tasks = 0
    total_updated = 0

    print("\n========== START PMC PROCESS ==========\n")

    for section_id, section_name in SECTION_IDS.items():

        print(f"--- Processing Section: {section_name} ---\n")

        tasks = get_tasks_from_section(section_id)

        total_tasks += len(tasks)

        task_list = []
        order_numbers = []

        for task in tasks:

            task_id = task["gid"]
            created_at = task["created_at"]

            order_number = None

            for f in task["custom_fields"]:
                if f["gid"] == ORDERNUMBER_FIELD_ID:
                    order_number = f.get("text_value")

            if order_number:

                raw = order_number
                clean = order_number.lstrip("#").strip()

                task_list.append((task_id, raw, clean, created_at))

                order_numbers.append(clean)

        header_data = get_header_data(order_numbers)
        firstmile_data = get_first_mile_data(order_numbers)

        section_updated = 0

        # THREAD POOL (FAST)
        with ThreadPoolExecutor(max_workers=10) as executor:

            futures = [executor.submit(process_task, t) for t in task_list]

            for future in as_completed(futures):

                msg, updated = future.result()

                print(msg)

                if updated:
                    section_updated += 1
                    total_updated += 1

        print(f"\nSection Updated: {section_updated}\n")

    print("========== FINAL SUMMARY ==========")
    print(f"Total Tasks Checked : {total_tasks}")
    print(f"Total Orders Updated: {total_updated}")
    print("====================================")

    cursor.close()
    conn.close()

# ============================================

if __name__ == "__main__":
    main()
