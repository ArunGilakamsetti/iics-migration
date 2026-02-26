import requests
import os
import sys
from datetime import datetime

IICS_EXTENSIONS = [
    ".MTT.json", ".DTEMPLATE.json", ".Connection.json", 
    ".WORKFLOW.json", ".DSS.json", ".DMASK.json", ".AI_SERVICE_CONNECTOR.json",
    ".TASKFLOW.json", ".BUSINESS_SERVICE.json"
]

def auto_cleanup(user, pwd, project_name, workspace_dir):
    log_entries = [f"--- IICS Deep Cleanup Audit: {datetime.now()} ---"]
    
    # 1. Login
    login_url = "https://dm-ap.informaticacloud.com/ma/api/v2/user/login"
    try:
        res = requests.post(login_url, json={"username": user, "password": pwd})
        auth_data = res.json()
        v3_base_url = f"{auth_data['serverUrl']}/public/core/v3"
        headers = {"INFA-SESSION-ID": auth_data["icSessionId"], "Accept": "application/json"}
        print("✅ Login Successful.")
    except:
        print("❌ Login failed."); sys.exit(1)

    # 2. Map Local Assets (Workspace)
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

    # 3. Lookup the Project/Folder ID first
    # Many orgs require the folder ID to filter objects reliably
    print(f"🔍 Locating folder ID for: {project_name}")
    folder_query = f"{v3_base_url}/objects?q=name=='{project_name}' and type=='Folder'"
    folder_res = requests.get(folder_query, headers=headers).json()
    
    folder_id = None
    if folder_res.get("objects"):
        folder_id = folder_res["objects"][0]["id"]
        print(f"📍 Found Folder ID: {folder_id}")
    else:
        # If lookup by name fails, we try the direct location query as fallback
        print("⚠️ Could not find Folder ID. Falling back to location string query.")

    # 4. Fetch Remote Assets
    if folder_id:
        # Querying by locationId is the most accurate way in v3
        lookup_url = f"{v3_base_url}/objects?q=locationId=='{folder_id}'"
    else:
        lookup_url = f"{v3_base_url}/objects?q=location=='{project_name}'"

    remote_objects = requests.get(lookup_url, headers=headers).json().get("objects", [])
    valid_remote_objects = [obj for obj in remote_objects if "name" in obj and obj.get("type") != "Folder"]

    print(f"📊 Summary: Found {len(valid_remote_objects)} remote assets in IICS.")
    print(f"📦 Summary: Found {len(assets_to_keep)} assets in Git workspace.")

    # 5. Deletion Logic
    deleted = 0
    for obj in valid_remote_objects:
        if obj["name"] not in assets_to_keep:
            print(f"🗑️ Found Orphan: {obj['name']} ({obj['type']})")
            del_res = requests.delete(f"{v3_base_url}/objects/{obj['id']}", headers=headers)
            if del_res.status_code == 204:
                log_entries.append(f"DELETED: {obj['name']}")
                deleted += 1
            else:
                log_entries.append(f"FAILED: {obj['name']} (Status: {del_res.status_code})")

    with open("cleanup_audit.log", "w") as f:
        f.write("\n".join(log_entries))
    print(f"✨ Done. Deleted {deleted} orphans.")

if __name__ == "__main__":
    auto_cleanup(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])