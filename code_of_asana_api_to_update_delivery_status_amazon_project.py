import requests
import mysql.connector
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================
# CONFIG
# ============================================

ASANA_TOKEN = "2/xxxxxxxxxx"
SECTION_ID = "1212808697694743" #can get this ids from asana token

# ---------- ASANA FIELD IDS ----------

LAST_MILE_TRACKING = "1211932673075094" #unique number of this field

DELIVERY_STATUS_FIELD = "1211976264687531" #unique number of this field
DELIVERY_STATUS_DELIVERED = "1211976264687534" #unique number of this field

ORDER_STATUS_FIELD = "1212836496066940" #unique number of this field
ORDER_STATUS_DELIVERED = "1212808697694755" #unique number of this field

DELIVERED_DATE_FIELD = "1212924709673143" #unique number of this field

MAX_THREADS = 10

# ---------- DATABASE ----------

db_config = {
    "host": "HOST",
    "user": "USER",
    "password": "PASSWORD",
    "database": "DATABASE"
}

# ---------- SESSION ----------

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {ASANA_TOKEN}"
})

# ============================================
# GET TASKS (PAGINATION)
# ============================================

def get_tasks():

    tasks = []
    url = f"https://app.asana.com/api/1.0/sections/{SECTION_ID}/tasks?limit=100"

    while url:

        r = session.get(url)
        r.raise_for_status()

        data = r.json()

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
        "opt_fields": "name,custom_fields.gid,custom_fields.text_value"
    }

    r = session.get(url, params=params)
    r.raise_for_status()

    return r.json()["data"]


# ============================================
# UPDATE TASK
# ============================================

def update_task(task_id, payload):

    url = f"https://app.asana.com/api/1.0/tasks/{task_id}"

    r = session.put(url, json={"data": payload})
    r.raise_for_status()


# ============================================
# PROCESS TASK
# ============================================

def process_task(task):

    task_id = task["gid"]

    try:

        task_data = get_task_details(task_id)
        task_name = task_data["name"]

        tracking = None

        for field in task_data["custom_fields"]:

            if field["gid"] == LAST_MILE_TRACKING:
                tracking = field.get("text_value")

        if not tracking:
            return None

        # Thread-safe DB connection
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        query = """
            SELECT deliverystatus, delivered_date
            FROM shipped_orders_header
            WHERE trackingnumber = %s
        """

        cursor.execute(query, (tracking,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if not result:
            return None

        deliverystatus, delivered_date = result

        if deliverystatus and "delivered" in deliverystatus.lower():

            payload = {
                "custom_fields": {
                    DELIVERY_STATUS_FIELD: DELIVERY_STATUS_DELIVERED,
                    ORDER_STATUS_FIELD: ORDER_STATUS_DELIVERED
                }
            }

            if delivered_date:
                payload["custom_fields"][DELIVERED_DATE_FIELD] = {
                    "date": delivered_date.strftime("%Y-%m-%d")
                }

            update_task(task_id, payload)

            return task_name

    except Exception as e:
        print(f"{task_id} → {e}")

    return None


# ============================================
# MAIN
# ============================================

def main():

    print("\nFetching tasks from Asana...\n")

    tasks = get_tasks()

    delivered_tasks = []

    print(f"Processing {len(tasks)} tasks...\n")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures = [executor.submit(process_task, task) for task in tasks]

        for future in as_completed(futures):

            result = future.result()

            if result:
                delivered_tasks.append(result)
                print("Delivered →", result)

    print("\n---------------- SUMMARY ----------------")

    print(f"Total Tasks Checked : {len(tasks)}")
    print(f"Total Delivered     : {len(delivered_tasks)}")

    print("\nDelivered Tasks:")

    for t in delivered_tasks:
        print("•", t)

    print("-----------------------------------------\n")


if __name__ == "__main__":
    main()
