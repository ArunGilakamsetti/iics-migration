import requests
import os
import sys

# List of common IICS extensions to strip from filenames
IICS_EXTENSIONS = [
    ".MTT.json", ".DTEMPLATE.json", ".Connection.json", 
    ".WORKFLOW.json", ".DSS.json", ".DMASK.json", ".AI_SERVICE_CONNECTOR.json"
]

def auto_cleanup(user, pwd, project_name, workspace_dir):
    # 1. Login Logic
    login_url = "https://dm-ap.informaticacloud.com/saas/api/core/v3/login"
    login_res = requests.post(login_url, json={"username": user, "password": pwd})
    if login_res.status_code != 200:
        print("Login failed.")
        sys.exit(1)

    auth_data = login_res.json()
    base_url = auth_data["userInfo"]["baseApiUrl"]
    headers = {"INFA-SESSION-ID": auth_data["userInfo"]["sessionId"]}

    # 2. Build local asset list with better parsing
    assets_to_keep = set()
    for root, _, files in os.walk(workspace_dir):
        for f in files:
            if f.endswith(".json") and not f.startswith("."):
                clean_name = f
                for ext in IICS_EXTENSIONS:
                    if f.endswith(ext):
                        clean_name = f.replace(ext, "")
                        break
                assets_to_keep.add(clean_name)

    # 3. Fetch Remote Assets
    query = f"location=='{project_name}'"
    lookup_url = f"{base_url}/public/core/v3/objects?q={query}"
    remote_res = requests.get(lookup_url, headers=headers)
    remote_objects = remote_res.json().get("objects", [])

    # 4. Filtered Delete
    print(f"Checking for orphans in {project_name}...")
    for obj in remote_objects:
        # SAFETY: Never delete Folders or Connections automatically unless sure
        if obj["type"] == "Folder":
            continue
            
        # Optional: Skip deleting connections to be safe
        # if obj["type"] == "Connection": continue

        if obj["name"] not in assets_to_keep:
            print(f"🗑️ Deleting {obj['type']}: {obj['name']}...")
            del_res = requests.delete(f"{base_url}/public/core/v3/objects/{obj['id']}", headers=headers)
            if del_res.status_code == 204:
                print(f"✅ Success.")
            else:
                print(f"❌ Failed (Status {del_res.status_code}). Check for active dependencies.")

if __name__ == "__main__":
    auto_cleanup(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])