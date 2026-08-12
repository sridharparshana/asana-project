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

ORDERNUMBER_FIELD_ID = "1211962087393887"
ORDERSTATUS_FIELD_ID = "1211977779079495"
FIRST_MILE_FIELD_ID = "1211908268997914"
LAST_MILE_FIELD_ID = "1211932673075094"
TRACKING_UPDATED_FIELD_ID = "1212924453496694"

FULFILLED_ENUM_ID = "1211977781879000"
TRACKING_YES_ENUM_ID = "1212924453496695"

db_config = {
    "host": "xxxxxxxx",
    "user": "xxxxx",
    "password": "xxxxxx",
    "database": "xxxxxxxxx"
}

headers = {
    "Authorization": f"Bearer {ASANA_TOKEN}"
}

session = requests.Session()
session.headers.update(headers)

conn = mysql.connector.connect(**db_config)
cursor = conn.cursor(buffered=True)


# ============================================
# GET TASKS
# ============================================

def get_tasks_from_section(section_id):

    url = (
        f"https://app.asana.com/api/1.0/sections/{section_id}/tasks"
        "?opt_fields=name,created_at,custom_fields.gid,custom_fields.text_value"
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
# FETCH TRACKINGS
# ============================================

def get_tracking_data(order_numbers):

    if not order_numbers:
        return {}

    placeholders = ",".join(["%s"] * len(order_numbers))

    query = f"""
        SELECT ordernumber, trackingnumber
        FROM vw_pushmycartusa_usps_trackings
        WHERE ordernumber IN ({placeholders})
    """

    cursor.execute(query, tuple(order_numbers))

    rows = cursor.fetchall()

    return {
        str(order): tracking
        for order, tracking in rows
    }


# ============================================
# UPDATE ASANA
# ============================================

def update_task(task_id, payload):

    url = f"https://app.asana.com/api/1.0/tasks/{task_id}"

    r = session.put(url, json={"data": payload})

    r.raise_for_status()


# ============================================
# PROCESS TASK
# ============================================

def process_task(task):

    task_id, raw_order, order_number, created_at = task

    created_at = created_at.replace("T", " ").replace(".000Z", "")

    if order_number not in tracking_data:
        return f"{raw_order} -> Not Found", False

    payload = {
        "custom_fields": {
            ORDERSTATUS_FIELD_ID: FULFILLED_ENUM_ID,
            LAST_MILE_FIELD_ID: tracking_data[order_number],
            FIRST_MILE_FIELD_ID: "FIRST MILE TRACKING UPDATE",
            TRACKING_UPDATED_FIELD_ID: TRACKING_YES_ENUM_ID
        }
    }

    try:
        update_task(task_id, payload)
        return f"{raw_order} -> Updated", True
    except Exception as e:
        return f"{raw_order} -> API Error ({e})", False


# ============================================
# MAIN
# ============================================

def main():

    global tracking_data

    total_tasks = 0
    total_updated = 0

    print("\n========== START ==========\n")

    for section_id, section_name in SECTION_IDS.items():

        print(f"\nProcessing : {section_name}\n")

        tasks = get_tasks_from_section(section_id)

        total_tasks += len(tasks)

        task_list = []
        order_numbers = []

        for task in tasks:

            order = None

            for field in task["custom_fields"]:

                if field["gid"] == ORDERNUMBER_FIELD_ID:
                    order = field.get("text_value")

            if order:

                clean = order.lstrip("#").strip()

                task_list.append(
                    (
                        task["gid"],
                        order,
                        clean,
                        task["created_at"]
                    )
                )

                order_numbers.append(clean)

        tracking_data = get_tracking_data(order_numbers)

        updated = 0

        with ThreadPoolExecutor(max_workers=10) as executor:

            futures = [
                executor.submit(process_task, t)
                for t in task_list
            ]

            for future in as_completed(futures):

                msg, ok = future.result()

                print(msg)

                if ok:
                    updated += 1
                    total_updated += 1

        print(f"\nUpdated : {updated}\n")

    print("\n========== SUMMARY ==========")
    print("Total Tasks   :", total_tasks)
    print("Total Updated :", total_updated)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
