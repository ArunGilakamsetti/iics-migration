#!/usr/bin/env python3
"""
Post‑deployment cleanup: deletes objects in target environment not present in the package.
Uses IICS CLI for listing (with fallback to direct API) and API for deletion.
"""

import sys
import os
import json
import subprocess
import requests
from typing import List, Dict, Set, Tuple

# ----------------------------------------------------------------------
# Configuration – map CLI type names to API endpoint paths
# ----------------------------------------------------------------------
TYPE_TO_ENDPOINT = {
    "MTT": "mttask",
    "TASKFLOW": "taskflow",
    "MAPPING": "mapping",
    "DTEMPLATE": "mapping",      # fallback
    "Connection": "connection",
    "AgentGroup": "agentgroup",
    "Folder": "folder",
    "Project": "project"
}
# All types we care about for remote listing (used in API fallback)
ALL_TYPES = list(TYPE_TO_ENDPOINT.keys())

def login(login_url: str, username: str, password: str) -> str:
    """Login via API and return session ID."""
    resp = requests.post(login_url, json={"username": username, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.text}")
    return resp.json()["userInfo"]["sessionId"]

def get_local_assets(workspace_path: str) -> Set[Tuple[str, str]]:
    """
    Scan the extracted workspace and return set of (type, name) from JSON files.
    Also prints debug info.
    """
    assets = set()
    if not os.path.isdir(workspace_path):
        print(f"❌ Workspace path not found: {workspace_path}")
        return assets

    print(f"🔍 Scanning workspace: {workspace_path}")
    json_files_found = 0
    for root, dirs, files in os.walk(workspace_path):
        for file in files:
            if not file.endswith(".json"):
                continue
            json_files_found += 1
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                obj_type = data.get("type")
                obj_name = data.get("name")
                if obj_type and obj_name:
                    assets.add((obj_type, obj_name))
                    print(f"  📄 Found asset: {obj_type} '{obj_name}' in {file}")
                else:
                    print(f"  ⚠️ JSON missing type/name: {file}")
            except Exception as e:
                print(f"  ⚠️ Could not parse {file}: {e}")

    print(f"📊 JSON files found: {json_files_found}")
    if json_files_found == 0:
        # List all files in workspace to debug
        print("📁 Workspace directory listing:")
        for root, dirs, files in os.walk(workspace_path):
            for file in files:
                print(f"   {os.path.join(root, file)}")
    return assets

def get_remote_assets_via_cli(cli_path: str, region: str, pod_host: str,
                               username: str, password: str) -> List[Dict]:
    """
    Use IICS CLI to list all objects in the target environment.
    Returns list of dicts with keys: type, name, id.
    """
    cmd = [
        cli_path, "list",
        "-r", region,
        "--podHostName", pod_host,
        "-u", username,
        "-p", password,
        "-o", "all_objects.txt"
    ]
    print(f"🔧 Running CLI: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ CLI list failed (exit {result.returncode})")
        print(f"STDERR: {result.stderr}")
        print(f"STDOUT: {result.stdout}")
        return []   # fallback to API

    # Parse output
    objects = []
    # Try output file first
    if os.path.exists("all_objects.txt"):
        with open("all_objects.txt", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    objects.append({
                        "type": parts[0],
                        "name": parts[1],
                        "id": parts[2]
                    })
    else:
        # Fallback to stdout
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                objects.append({
                    "type": parts[0],
                    "name": parts[1],
                    "id": parts[2]
                })
    print(f"✅ CLI found {len(objects)} remote objects.")
    return objects

def get_remote_assets_via_api(api_base: str, session_id: str) -> List[Dict]:
    """
    Fallback method: query each object type via IICS API.
    Returns list of dicts with keys: type, name, id.
    """
    headers = {"INFA-SESSION-ID": session_id, "Accept": "application/json"}
    objects = []
    for obj_type in ALL_TYPES:
        endpoint = TYPE_TO_ENDPOINT.get(obj_type)
        if not endpoint:
            continue
        url = f"{api_base}/api/v2/{endpoint}"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                print(f"⚠️ API list for {obj_type} returned {resp.status_code}")
                continue
            data = resp.json()
            # The response may be a list or a dict with 'items'
            items = data if isinstance(data, list) else data.get("items", [])
            for item in items:
                obj_name = item.get("name")
                obj_id = item.get("id")
                if obj_name and obj_id:
                    objects.append({
                        "type": obj_type,
                        "name": obj_name,
                        "id": obj_id
                    })
        except Exception as e:
            print(f"⚠️ API list for {obj_type} failed: {e}")
    print(f"✅ API fallback found {len(objects)} remote objects.")
    return objects

def delete_object(api_base: str, session_id: str, obj_type: str, obj_id: str) -> bool:
    """Delete an object via API."""
    endpoint = TYPE_TO_ENDPOINT.get(obj_type)
    if not endpoint:
        print(f"⚠️ No delete endpoint for type {obj_type}, skipping.")
        return False
    url = f"{api_base}/api/v2/{endpoint}/{obj_id}"
    headers = {"INFA-SESSION-ID": session_id}
    try:
        resp = requests.delete(url, headers=headers, timeout=30)
        if resp.status_code in (200, 204):
            return True
        else:
            print(f"   ❌ Delete failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"   ❌ Delete exception: {e}")
        return False

def main():
    if len(sys.argv) < 6:
        print("Usage: auto_cleanup.py <username> <password> <cli_path> <region> <workspace_path>")
        sys.exit(1)

    username, password, cli_path, region, workspace_path = sys.argv[1:6]
    login_host = os.getenv("IICS_LOGIN_HOST", "dm-ap.informaticacloud.com")
    pod_host = os.getenv("IICS_POD_HOST", "apse1.dm-ap.informaticacloud.com")

    login_url = f"https://{login_host}/saas/public/core/v3/login"
    api_base = f"https://{pod_host}"

    print("🔐 Logging in...")
    try:
        session_id = login(login_url, username, password)
        print("✅ Login successful.")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        sys.exit(1)

    print("📂 Extracting local assets from workspace...")
    local_assets = get_local_assets(workspace_path)
    print(f"📊 Local assets found: {len(local_assets)}")

    print("🌐 Listing remote assets...")
    # Try CLI first
    remote_objects = get_remote_assets_via_cli(cli_path, region, pod_host, username, password)
    if len(remote_objects) == 0:
        print("⚠️ CLI returned zero objects, falling back to API...")
        remote_objects = get_remote_assets_via_api(api_base, session_id)

    if len(remote_objects) == 0:
        print("⚠️ No remote objects found. Nothing to delete.")
        return

    deleted = 0
    for obj in remote_objects:
        obj_type = obj["type"]
        obj_name = obj["name"]
        obj_id = obj["id"]
        if (obj_type, obj_name) not in local_assets:
            print(f"🗑️ Deleting orphan {obj_type} '{obj_name}' (ID: {obj_id})...")
            if delete_object(api_base, session_id, obj_type, obj_id):
                deleted += 1
                print("   ✅ Deleted.")
            else:
                print(f"   ❌ Failed to delete {obj_name}.")
        else:
            print(f"✅ Keeping {obj_type} '{obj_name}' (present in package).")

    print(f"✨ Cleanup completed. Total objects deleted: {deleted}")

if __name__ == "__main__":
    main()