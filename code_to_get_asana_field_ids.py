import requests

ASANA_TOKEN = "2/xxxxxxxx"
PROJECT_ID = "1211908062105522"

headers = {
    "Authorization": f"Bearer {ASANA_TOKEN}"
}

url = f"https://app.asana.com/api/1.0/projects/{PROJECT_ID}?opt_fields=custom_field_settings.custom_field"

response = requests.get(url, headers=headers)
response.raise_for_status()

project_data = response.json()["data"]

print("\nCustom Fields:\n")

for field_setting in project_data["custom_field_settings"]:
    field = field_setting["custom_field"]

    print(f"Field Name: {field['name']}")
    print(f"Field ID: {field['gid']}")

    if field["resource_subtype"] == "enum":
        print("Dropdown Options:")
        for option in field["enum_options"]:
            print(f"  Option Name: {option['name']}")
            print(f"  Option ID: {option['gid']}")
        print("-" * 50)
