#!/usr/bin/env python3
"""
Post‑deployment cleanup: deletes objects in target environment not present in the package.
Uses IICS CLI for listing and API for deletion.
"""

import sys
import os
import json
import subprocess
import requests

def login(login_url: str, username: str, password: str) -> str:
    """Login via API and return session ID."""
    resp = requests.post(login_url, json={"username": username, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.text}")
    return resp.json()["userInfo"]["sessionId"]

def get_local_assets(workspace_path: str) -> set:
    """
    Scan the extracted workspace and return set of (type, name) from JSON files.
    """
    assets = set()
    for root, _, files in os.walk(workspace_path):
        for file in files:
            if not file.endswith(".json"):
                continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                obj_type = data.get("type")
                obj_name = data.get("name")
                if obj_type and obj_name:
                    assets.add((obj_type, obj_name))
            except:
                continue
    return assets

def get_remote_assets_via_cli(cli_path: str, region: str, pod_host: str,
                               username: str, password: str) -> list:
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
        "-o", "remote_assets.txt"
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    objects = []
    with open("remote_assets.txt", "r") as f:
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
    return objects

def delete_object(api_base: str, session_id: str, obj_type: str, obj_id: str) -> bool:
    """
    Delete an object using the appropriate API endpoint.
    Maps CLI type to API endpoint (adjust as needed).
    """
    type_to_endpoint = {
        "MTT": "mttask",
        "TASKFLOW": "taskflow",
        "MAPPING": "mapping",
        "DTEMPLATE": "mapping",   # fallback
        "Connection": "connection",
        "AgentGroup": "agentgroup",
        "Folder": "folder",
        "Project": "project"
    }
    endpoint = type_to_endpoint.get(obj_type)
    if not endpoint:
        print(f"⚠️ No delete endpoint for type {obj_type}, skipping.")
        return False
    url = f"{api_base}/api/v2/{endpoint}/{obj_id}"
    headers = {"INFA-SESSION-ID": session_id}
    resp = requests.delete(url, headers=headers)
    return resp.status_code in (200, 204)

def main():
    if len(sys.argv) < 6:
        print("Usage: auto_cleanup.py <username> <password> <cli_path> <region> <workspace_path>")
        sys.exit(1)

    username, password, cli_path, region, workspace_path = sys.argv[1:6]
    login_host = os.getenv("IICS_LOGIN_HOST", "dm-ap.informaticacloud.com")
    pod_host = os.getenv("IICS_POD_HOST", "apse1.dm-ap.informaticacloud.com")  # change as needed

    login_url = f"https://{login_host}/saas/public/core/v3/login"
    api_base = f"https://{pod_host}"

    print("Logging in...")
    try:
        session_id = login(login_url, username, password)
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

    print("Extracting local assets from workspace...")
    local_assets = get_local_assets(workspace_path)
    print(f"Found {len(local_assets)} local assets.")

    print("Listing remote assets via CLI...")
    remote_objects = get_remote_assets_via_cli(cli_path, region, pod_host, username, password)
    print(f"Found {len(remote_objects)} remote objects.")

    deleted = 0
    for obj in remote_objects:
        obj_type = obj["type"]
        obj_name = obj["name"]
        obj_id = obj["id"]
        if (obj_type, obj_name) not in local_assets:
            print(f"Deleting orphan {obj_type} '{obj_name}' (ID: {obj_id})...")
            if delete_object(api_base, session_id, obj_type, obj_id):
                deleted += 1
                print("  Deleted.")
            else:
                print(f"  Failed to delete {obj_name}.")
        else:
            print(f"Keeping {obj_type} '{obj_name}' (present in package).")

    print(f"Cleanup completed. Deleted {deleted} objects.")

if __name__ == "__main__":
    main()