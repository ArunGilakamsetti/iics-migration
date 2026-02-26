import requests
import os
import sys
from datetime import datetime

IICS_EXTENSIONS = [
    ".MTT.json", ".DTEMPLATE.json", ".Connection.json", 
    ".WORKFLOW.json", ".DSS.json", ".DMASK.json", ".AI_SERVICE_CONNECTOR.json"
]

def auto_cleanup(user, pwd, project_name, workspace_dir):
    log_entries = [f"--- IICS Cleanup Audit: {datetime.now()} ---"]
    
    # 1. Login via v2 to get the correct Pod URL (Base URL)
    # The 'ma' (Multi-tenant Administrator) URL is the global entry point
    login_url = "https://dm-ap.informaticacloud.com/ma/api/v2/user/login"
    
    try:
        login_res = requests.post(login_url, json={"username": user, "password": pwd})
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.text}")
            sys.exit(1)

        auth_data = login_res.json()
        session_id = auth_data["icSessionId"]
        # Convert the serverUrl to the v3 Base API URL
        # Example: https://na1.dm-us.informaticacloud.com/saas -> https://na1.dm-us.informaticacloud.com/saas/public/core/v3
        v3_base_url = f"{auth_data['serverUrl']}/public/core/v3"
        
        headers = {
            "INFA-SESSION-ID": session_id,
            "Accept": "application/json"
        }
        print("✅ Login Successful. Discovered Pod URL.")
        
    except Exception as e:
        print(f"Connection Error: {str(e)}")
        sys.exit(1)

    # 2. Build local asset list
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
    # We use double quotes around project names in case they have spaces
    lookup_url = f"{v3_base_url}/objects?q=location=='{project_name}'"
    remote_res = requests.get(lookup_url, headers=headers)
    
    if remote_res.status_code != 200:
        print(f"Failed to fetch objects: {remote_res.text}")
        sys.exit(1)
        
    remote_objects = remote_res.json().get("objects", [])

    # 4. Sync Logic
    for obj in remote_objects:
        if obj["type"] == "Folder":
            continue
            
        if obj["name"] not in assets_to_keep:
            print(f"🗑️ Found Orphan: {obj['name']} ({obj['type']})")
            del_url = f"{v3_base_url}/objects/{obj['id']}"
            del_res = requests.delete(del_url, headers=headers)
            
            if del_res.status_code == 204:
                log_entries.append(f"SUCCESS: Deleted {obj['name']}")
            else:
                log_entries.append(f"FAILED: {obj['name']} - Status {del_res.status_code}")

    with open("cleanup_audit.log", "w") as f:
        f.write("\n".join(log_entries))
    print("Cleanup step completed.")

if __name__ == "__main__":
    auto_cleanup(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])