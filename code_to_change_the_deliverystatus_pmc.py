import requests
import mysql.connector

# ============================================
# CONFIG
# ============================================

ASANA_TOKEN = "2/xxxxxx"

SECTION_ID = "1211976004727406"

db_config = {
    "host": "xxxxx",
    "user": "xxxxx",
    "password": "xxxxxxx",
    "database": "xxxxxxx"
}

# ============================================
# UPDATE THESE ENUM IDS
# ============================================

# Order Status -> Delivered_review_pending
DELIVERED_REVIEW_PENDING_ID = "1213614797634316"

# Delivery Status -> Delivered
DELIVERED_ENUM_ID = "1211976264687534"

headers = {
    "Authorization": f"Bearer {ASANA_TOKEN}"
}

# ============================================
# GET ALL TASKS
# ============================================

def get_tasks():

    tasks = []
    url = f"https://app.asana.com/api/1.0/sections/{SECTION_ID}/tasks?limit=100"

    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()

        tasks.extend(data["data"])

        next_page = data.get("next_page")
        url = next_page["uri"] if next_page else None

    return tasks


# ============================================
# GET TASK DETAILS
# ============================================

def get_task_details(task_id):

    url = f"https://app.asana.com/api/1.0/tasks/{task_id}"

    params = {
        "opt_fields": "custom_fields.name,custom_fields.gid,custom_fields.text_value,custom_fields.enum_value,custom_fields.enum_options"
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json()["data"]


# ============================================
# UPDATE TASK
# ============================================

def update_task(task_id, payload):

    url = f"https://app.asana.com/api/1.0/tasks/{task_id}"

    response = requests.put(
        url,
        headers=headers,
        json={"data": payload}
    )

    response.raise_for_status()


# ============================================
# PROCESS TASK
# ============================================

def process_task(task_id, cursor):

    task = get_task_details(task_id)

    ordernumber = None
    order_status_field = None
    delivery_status_field = None

    # Read required custom fields
    for field in task["custom_fields"]:

        field_name = field["name"].strip().lower()

        if field_name in ["order number", "ordernumber"]:

            ordernumber = field.get("text_value")

            if ordernumber:
                ordernumber = ordernumber.replace("#", "").strip()

        elif field_name == "order_status":

            order_status_field = field["gid"]

        elif field_name == "delivery status":

            delivery_status_field = field["gid"]

    if not ordernumber:
        return f"{task_id} - No Order Number"

    # ============================================
    # CHECK VIEW
    # ============================================

    cursor.execute("""
        SELECT 1
        FROM vw_pmc_tracking_status
        WHERE ordernumber=%s
        LIMIT 1
    """, (ordernumber,))

    exists = cursor.fetchone()

    if not exists:
        return f"{ordernumber} - Not Found"

    payload = {
        "custom_fields": {
            order_status_field: DELIVERED_REVIEW_PENDING_ID,
            delivery_status_field: DELIVERED_ENUM_ID
        }
    }

    update_task(task_id, payload)

    return f"{ordernumber} - Updated"


# ============================================
# MAIN
# ============================================

def main():

    print("\nFetching Tasks...\n")

    tasks = get_tasks()

    print(f"Total Tasks : {len(tasks)}\n")

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    updated = 0
    checked = 0

    print("Checking Orders...\n")

    for task in tasks:

        task_id = task["gid"]

        try:

            result = process_task(task_id, cursor)

            print(result)

            checked += 1

            if "Updated" in result:
                updated += 1

        except Exception as e:

            print(f"{task_id} - Error : {e}")

    cursor.close()
    conn.close()

    print("\n===================================")
    print(f"Total Checked : {checked}")
    print(f"Total Updated : {updated}")
    print("===================================\n")


if __name__ == "__main__":
    main()
