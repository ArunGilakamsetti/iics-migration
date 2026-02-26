import sys
import os
import json
import requests

def get_iics_session(user, pwd, pod_host):
    login_url = f"https://{pod_host}/saas/public/core/v3/login"
    res = requests.post(login_url, json={"username": user, "password": pwd})
    if res.status_code != 200:
        print("❌ Login Failed"); sys.exit(1)
    print("✅ Login Successful.")
    data = res.json()
    return data['userInfo']['sessionId'], data['userInfo']['baseUrl']

def get_remote_assets(session_id, base_url, project_name):
    # We use a broad search filter to find anything in the target project path
    search_url = f"{base_url}/api/v2/mdata/search"
    headers = {"icSessionId": session_id, "Accept": "application/json"}
    
    # IICS locations often look like "Project_Alpha" or "Project_Alpha/Folder"
    params = {"q": f"location:'{project_name}' OR location:'{project_name}/*'"}
    res = requests.get(search_url, headers=headers, params=params)
    
    if res.status_code != 200:
        print(f"⚠️ Search failed with status {res.status_code}")
        return {}

    remote_assets = {}
    for asset in res.json():
        # Map asset name + type to the object ID
        key = f"{asset['name']}.{asset['type']}"
        remote_assets[key] = asset['id']
    
    return remote_assets

def get_local_assets(workspace_path):
    local_assets = set()
    for root, _, files in os.walk(workspace_path):
        for file in files:
            # Skip hidden metadata sidecars and folder/project definitions
            if file.startswith(".") or file.endswith((".Folder.json", ".Project.json")):
                continue
            
            # Extract Name.Type from filename (e.g., MyMapping.DTEMPLATE.zip -> MyMapping.DTEMPLATE)
            parts = file.split('.')
            if len(parts) >= 2:
                local_assets.add(f"{parts[0]}.{parts[1]}")
    return local_assets

def delete_asset(session_id, base_url, asset_id, asset_key):
    delete_url = f"{base_url}/api/v2/mdata/delete/{asset_id}"
    headers = {"icSessionId": session_id, "Accept": "application/json"}
    res = requests.post(delete_url, headers=headers)
    if res.status_code == 200:
        print(f"🗑️ Deleted orphan: {asset_key}")
    else:
        print(f"❌ Failed to delete {asset_key}: {res.text}")

def main():
    user, pwd, project_name, workspace_path = sys.argv[1:5]
    pod_host = os.getenv("IICS_POD_HOST", "dm-ap.informaticacloud.com")
    
    session_id, base_url = get_iics_session(user, pwd, pod_host)
    
    print(f"🔍 Fetching remote assets for location: {project_name}")
    remote_assets = get_remote_assets(session_id, base_url, project_name)
    local_assets = get_local_assets(workspace_path)
    
    print(f"📊 Summary: Found {len(remote_assets)} remote assets in IICS.")
    print(f"📦 Summary: Found {len(local_assets)} assets in Git workspace.")
    
    orphans_found = 0
    for asset_key, asset_id in remote_assets.items():
        if asset_key not in local_assets:
            # Double check: we don't want to delete the project or folders themselves
            if ".Folder" in asset_key or ".Project" in asset_key:
                continue
            delete_asset(session_id, base_url, asset_id, asset_key)
            orphans_found += 1
            
    print(f"✨ Done. Deleted {orphans_found} orphans.")

if __name__ == "__main__":
    main()