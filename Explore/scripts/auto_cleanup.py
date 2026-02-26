import requests
import os
import sys
from datetime import datetime

# Common IICS extensions to strip from filenames to get the internal object name
IICS_EXTENSIONS = [
    ".MTT.json", ".DTEMPLATE.json", ".Connection.json", 
    ".WORKFLOW.json", ".DSS.json", ".DMASK.json", ".AI_SERVICE_CONNECTOR.json",
    ".TASKFLOW.json", ".BUSINESS_SERVICE.json"
]

def auto_cleanup(user, pwd, project_name, workspace_dir):
    log_entries = [f"--- IICS Cleanup Audit: {datetime.now()} ---"]
    log_entries.append(f"Target Project: {project_name}")
    
    # 1. Login via v2 to discover the Pod-specific URL
    login_url = "https://dm-ap.informaticacloud.com/ma/api/v2/user/login"
    
    try:
        login_res = requests.post(login_url, json={"username": user, "password": pwd})
        if login_res.status_code != 200:
            print(f"❌ Login failed: {login_res.text}")
            sys.exit(1)

        auth_data = login_res.json()
        session_id = auth_data["icSessionId"]
        # Construct the v3 Base URL from the discovered Pod URL
        v3_base_url = f"{auth_data['serverUrl']}/public/core/v3"
        
        headers = {
            "INFA-SESSION-ID": session_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        print("✅ Login Successful. Pod URL Discovered.")
        
    except Exception as e:
        print(f"❌ Connection Error during login: {str(e)}")
        sys.exit(1)

    # 2. Build Local Asset List (Source of Truth)
    assets_to_keep = set()
    if not os.path.exists(workspace_dir):
        print(f"❌ Error: Workspace directory '{workspace_dir}' not found.")
        sys.exit(1)

    for root, _, files in os.walk(workspace_dir):
        for f in files:
            if f.endswith(".json") and not f.startswith("."):
                clean_name = f
                for ext in IICS_EXTENSIONS:
                    if f.endswith(ext):
                        clean_name = f.replace(ext, "")
                        break
                assets_to_keep.add(clean_name)

    # 3. Fetch Remote Assets from IICS
    print(f"🔍 Querying IICS for objects in: {project_name}")
    lookup_url = f"{v3_base_url}/objects?q=location=='{project_name}'"
    remote_res = requests.get(lookup_url, headers=headers)
    
    if remote_res.status_code != 200:
        print(f"❌ Failed to fetch objects: {remote_res.text}")
        sys.exit(1)
        
    remote_objects = remote_res.json().get("objects", [])

    # 4. Sync and Comparison Logic
    # Filter out invalid entries and folders to get a clean count
    valid_remote_objects = [obj for obj in remote_objects if "name" in obj and obj.get("type") != "Folder"]
    
    print(f"📊 Summary: Found {len(valid_remote_objects)} assets in IICS target folder.")
    print(f"📦 Summary: Found {len(assets_to_keep)} assets in local workspace.")
    log_entries.append(f"Remote Assets: {len(valid_remote_objects)} | Local Assets: {len(assets_to_keep)}")

    if len(valid_remote_objects) == 0:
        print("⚠️ Warning: No remote assets found. Check if PROJECT_NAME matches your IICS folder exactly.")
    
    deleted_count = 0
    failed_count = 0

    for obj in valid_remote_objects:
        obj_name = obj["name"]
        obj_type = obj.get("type", "Unknown")

        if obj_name not in assets_to_keep:
            print(f"🗑️ Found Orphan: {obj_name} ({obj_type})")
            del_url = f"{v3_base_url}/objects/{obj['id']}"
            del_res = requests.delete(del_url, headers=headers)
            
            if del_res.status_code == 204:
                print(f"  ✅ Deleted {obj_name}")
                log_entries.append(f"SUCCESS: Deleted {obj_name} ({obj_type})")
                deleted_count += 1
            else:
                print(f"  ❌ Failed to delete {obj_name}. Status: {del_res.status_code}")
                log_entries.append(f"FAILED: {obj_name} (Status {del_res.status_code})")
                failed_count += 1

    # 5. Finalize Audit Log
    log_entries.append(f"Total Deleted: {deleted_count} | Total Failed: {failed_count}")
    with open("cleanup_audit.log", "w") as f:
        f.write("\n".join(log_entries))
    
    print(f"✨ Cleanup finished. Deleted: {deleted_count}, Failed: {failed_count}.")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 auto_cleanup.py <USER> <PWD> <PROJECT_NAME> <WORKSPACE_DIR>")
        sys.exit(1)
    auto_cleanup(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])