import sys
import os
import json
import requests

def get_iics_session(user, pwd, pod_host):
    login_url = f"https://{pod_host}/saas/public/core/v3/login"
    res = requests.post(login_url, json={"username": user, "password": pwd})
    if res.status_code != 200:
        print(f"❌ Login Failed: {res.text}"); sys.exit(1)
    
    data = res.json()
    # v3 uses baseApiUrl; we fall back to sessionId for the headers
    session_id = data['userInfo']['sessionId']
    
    # Standardizing the base URL for v2/v3 cross-calls
    base_url = data['userInfo'].get('baseApiUrl')
    if not base_url:
        # Fallback for older POD responses
        base_url = f"https://{pod_host}/saas"
        
    print(f"✅ Login Successful. POD: {base_url}")
    return session_id, base_url

def get_remote_assets(session_id, base_url, project_name):
    # Search uses the v2 mdata API
    search_url = f"{base_url}/api/v2/mdata/search"
    headers = {"icSessionId": session_id, "Accept": "application/json"}
    
    # Query for assets exactly in this project or subfolders
    params = {"q": f"location:'{project_name}' OR location:'{project_name}/*'"}
    res = requests.get(search_url, headers=headers, params=params)
    
    if res.status_code != 200:
        print(f"⚠️ Search failed: {res.text}")
        return {}

    remote_assets = {}
    for asset in res.json():
        # Map asset name + type to ID (e.g., "m_orders.MTT")
        asset_type = asset.get('type', 'UNKNOWN')
        asset_name = asset.get('name', 'UNKNOWN')
        key = f"{asset_name}.{asset_type}"
        remote_assets[key] = asset['id']
    
    return remote_assets

def get_local_assets(workspace_path):
    local_assets = set()
    if not os.path.exists(workspace_path):
        print(f"⚠️ Workspace path not found: {workspace_path}")
        return local_assets

    for root, _, files in os.walk(workspace_path):
        for file in files:
            # Ignore hidden files, Folders, and Projects
            if file.startswith(".") or ".Folder.json" in file or ".Project.json" in file:
                continue
            
            # Extract name and type: "Mapping_Name.DTEMPLATE.zip" -> "Mapping_Name.DTEMPLATE"
            parts = file.split('.')
            if len(parts) >= 2:
                # We normalize by taking the first two parts
                local_assets.add(f"{parts[0]}.{parts[1]}")
    return local_assets

def delete_asset(session_id, base_url, asset_id, asset_key):
    # Delete uses v2 mdata API
    delete_url = f"{base_url}/api/v2/mdata/delete/{asset_id}"
    headers = {"icSessionId": session_id, "Accept": "application/json"}
    res = requests.post(delete_url, headers=headers)
    if res.status_code == 200:
        print(f"🗑️ Deleted orphan: {asset_key}")
    else:
        print(f"❌ Failed to delete {asset_key}: {res.text}")

def main():
    if len(sys.argv) < 5:
        print("Usage: python3 auto_cleanup.py <user> <pwd> <project> <path>")
        sys.exit(1)

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
        # Only delete if it exists in IICS but NOT in Git
        if asset_key not in local_assets:
            # Safety check: Don't delete the project or connection objects unless desired
            if ".Folder" in asset_key or ".Project" in asset_key or ".Connection" in asset_key:
                continue
            delete_asset(session_id, base_url, asset_id, asset_key)
            orphans_found += 1
            
    print(f"✨ Done. Total orphans deleted: {orphans_found}")

if __name__ == "__main__":
    main()