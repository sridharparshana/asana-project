import requests
import mysql.connector

# =====================================================
# CONFIGURATION
# =====================================================

ASANA_TOKEN = "token"
PROJECT_ID = "1212835434239570"

SECTION_IDS = {
    "1212808697694741": "New Orders",
    "1212808697694742": "In Processing"
}

LABEL_CREATED_SECTION_ID = "1213610555237617"
FULFILLED_SECTION_ID = "1212808697694743"

# =====================================================
# CUSTOM FIELD IDS
# =====================================================

LAST_MILE_FIELD_ID = "1211932673075094"
FIRST_MILE_FIELD_ID = "1211908268997914"

TRACKING_UPDATED_FIELD_ID = "1212924453496694"
TRACKING_YES_ENUM_ID = "1212924453496695"

ORDER_STATUS_FIELD_ID = "1212836496066940"
FULFILLED_ENUM_ID = "1212808697694754"

SHIPPED_FROM_FIELD_ID = "1213449649079983"
SHIPPED_DATE_FIELD_ID = "1211978742850054"

# =====================================================
# DATABASE CONFIG
# =====================================================

db_config = {
    "host": "host",
    "user": "user",
    "password": "password",
    "database": "databasename"
}

# =====================================================
# CONNECTIONS
# =====================================================

headers = {
    "Authorization": f"Bearer {ASANA_TOKEN}",
    "Content-Type": "application/json"
}

conn = mysql.connector.connect(**db_config)
cursor = conn.cursor(buffered=True)

# =====================================================
# ASANA HELPERS
# =====================================================

def get_tasks_from_section(section_id):
    """Fetch all tasks from a section"""
    url = f"https://app.asana.com/api/1.0/sections/{section_id}/tasks?opt_fields=custom_fields.name,custom_fields.text_value"
    tasks = []

    while url:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        tasks.extend(data["data"])
        url = data.get("next_page", {}).get("uri")

    return tasks


def move_task_to_section(task_id, section_id):
    """Move task to another section"""
    url = f"https://app.asana.com/api/1.0/sections/{section_id}/addTask"
    payload = {"data": {"task": task_id, "project": PROJECT_ID}}

    res = requests.post(url, headers=headers, json=payload)
    print("Move Task Status:", res.status_code)

# =====================================================
# DATABASE FUNCTIONS
# =====================================================

def get_order_header_data(order_numbers):
    """Fetch last mile, warehouse, shipdate"""
    if not order_numbers:
        return {}

    query = f"""
    SELECT ordernumber, trackingnumber, warehouseid, shipdate
    FROM shipped_orders_header
    WHERE ordernumber IN ({','.join(['%s'] * len(order_numbers))})
    """

    cursor.execute(query, tuple(order_numbers))
    rows = cursor.fetchall()

    result = {}
    for row in rows:
        result[str(row[0])] = {
            "tracking": row[1],
            "warehouse_id": row[2],
            "shipdate": row[3]
        }

    return result


def get_first_mile_data(order_numbers):
    """Fetch first mile tracking"""
    if not order_numbers:
        return {}

    query = f"""
    SELECT orderitemid, trackingnumber FROM tbl_stocktransfer
    WHERE orderitemid IN ({','.join(['%s'] * len(order_numbers))})
    UNION ALL
    SELECT orderitemid, trackingnumber FROM tbl_stock_intransit
    WHERE orderitemid IN ({','.join(['%s'] * len(order_numbers))})
    """

    cursor.execute(query, tuple(order_numbers) * 2)

    return {str(r[0]): r[1] for r in cursor.fetchall() if r[1]}


def get_warehouse_location(warehouse_id):
    """Get warehouse location name"""
    if not warehouse_id:
        return None

    query = "SELECT Location FROM StoreId WHERE Id = %s"
    cursor.execute(query, (warehouse_id,))
    row = cursor.fetchone()

    return row[0] if row else None

# =====================================================
# MAIN UPDATE FUNCTION
# =====================================================

def update_task_all_fields(task_id, last_mile=None, first_mile=None,
                           warehouse_id=None, shipped_date=None,
                           mark_fulfilled=False):

    payload = {"custom_fields": {}}

    # Last Mile
    if last_mile:
        payload["custom_fields"][LAST_MILE_FIELD_ID] = str(last_mile)

    # First Mile
    if first_mile:
        payload["custom_fields"][FIRST_MILE_FIELD_ID] = str(first_mile)

    # Shipped From
    if warehouse_id:
        location = get_warehouse_location(warehouse_id)
        print("Warehouse:", warehouse_id, "| Location:", location)

        if location:
            payload["custom_fields"][SHIPPED_FROM_FIELD_ID] = location

    # Shipped Date
    if shipped_date:
        payload["custom_fields"][SHIPPED_DATE_FIELD_ID] = {
            "date": shipped_date.strftime("%Y-%m-%d")
        }

    # Mark Fulfilled
    if mark_fulfilled:
        payload["custom_fields"][ORDER_STATUS_FIELD_ID] = FULFILLED_ENUM_ID
        payload["custom_fields"][TRACKING_UPDATED_FIELD_ID] = TRACKING_YES_ENUM_ID

    # API CALL
    url = f"https://app.asana.com/api/1.0/tasks/{task_id}"
    res = requests.put(url, headers=headers, json={"data": payload})

    print("\n=== UPDATE TASK ===")
    print("Payload:", payload)

    if res.status_code == 200:
        print("✅ Task updated successfully")
    else:
        print("❌ Update failed:", res.status_code, res.text)

# =====================================================
# STEP 1: NEW + IN PROCESSING
# =====================================================

def process_new_and_processing():

    print("\n=== STEP 1: NEW + IN PROCESSING ===")

    for section_id in SECTION_IDS:

        tasks = get_tasks_from_section(section_id)
        task_order_map = {}

        # Extract order numbers
        for task in tasks:
            order = None

            for field in task["custom_fields"]:
                if field["name"].lower() == "order number":
                    order = field.get("text_value")

            if order:
                task_order_map[task["gid"]] = order.strip("# ")

        # Fetch DB data
        header_data = get_order_header_data(list(task_order_map.values()))

        # Process each task
        for task_id, order in task_order_map.items():

            data = header_data.get(order)

            last_mile = data["tracking"] if data else None
            warehouse_id = data["warehouse_id"] if data else None
            shipdate = data["shipdate"] if data else None

            print(f"\nTask {task_id} | Order {order}")
            print("Last Mile:", last_mile)

            if last_mile:
                print("➡ Updating LAST MILE + SHIPPING + Moving")

                update_task_all_fields(
                    task_id,
                    last_mile=last_mile,
                    warehouse_id=warehouse_id,
                    shipped_date=shipdate
                )

                move_task_to_section(task_id, LABEL_CREATED_SECTION_ID)
            else:
                print("❌ No last mile yet")

# =====================================================
# STEP 2: LABEL CREATED
# =====================================================

def process_label_created():

    print("\n=== STEP 2: LABEL CREATED ===")

    tasks = get_tasks_from_section(LABEL_CREATED_SECTION_ID)
    task_order_map = {}

    for task in tasks:
        order = None

        for field in task["custom_fields"]:
            if field["name"].lower() == "order number":
                order = field.get("text_value")

        if order:
            task_order_map[task["gid"]] = order.strip("# ")

    first_mile_data = get_first_mile_data(list(task_order_map.values()))

    for task_id, order in task_order_map.items():

        first_mile = first_mile_data.get(order)

        print(f"\nTask {task_id} | Order {order}")
        print("First Mile:", first_mile)

        if first_mile:
            print("➡ Updating FIRST MILE + Marking Fulfilled")

            update_task_all_fields(
                task_id,
                first_mile=first_mile,
                mark_fulfilled=True
            )

            move_task_to_section(task_id, FULFILLED_SECTION_ID)
        else:
            print("⏳ Waiting for first mile")

# =====================================================
# MAIN
# =====================================================

def main():
    print("\n========= START =========")

    process_new_and_processing()
    process_label_created()

    print("\n========= DONE =========")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
