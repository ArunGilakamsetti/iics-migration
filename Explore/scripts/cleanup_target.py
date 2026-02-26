#!/usr/bin/env python3
"""
Pre-import cleanup for IICS target environment.
Deletes all objects of specified types that are NOT present in the package.
Now reads exportMetadata.v2.json to get the list of exported objects.
"""

import os
import sys
import json
import argparse
import zipfile
import tempfile
import requests
from typing import Set, Tuple, List, Dict

# ----------------------------------------------------------------------
# CONFIGURATION – map IICS object types to API endpoint paths
# Add/remove types as needed. Be careful with shared objects like Connections.
# ----------------------------------------------------------------------
OBJECT_TYPES = {
    "MTT": "mttask",          # Mapping Task
    "TASKFLOW": "taskflow",    # Taskflow
    "MAPPING": "mapping",      # Individual mapping (if type is "MAPPING")
    "DTEMPLATE": "mapping",    # Some mappings are exported as DTEMPLATE – adjust endpoint if needed
    # "Connection": "connection",  # Uncomment if you want to clean up connections (use with caution)
    # "AgentGroup": "agentgroup",  # Uncomment if you want to clean up agent groups (use with caution)
    # Add other types as needed
}
# ----------------------------------------------------------------------

def login(login_url: str, username: str, password: str) -> str:
    """Login and return session ID."""
    payload = {"username": username, "password": password}
    resp = requests.post(login_url, json=payload)
    resp.raise_for_status()
    return resp.json()["userInfo"]["sessionId"]


def list_all_objects(api_base: str, session_id: str, obj_type: str) -> List[Dict]:
    """
    List all objects of given type in the target environment,
    handling pagination automatically.
    """
    url = f"{api_base}/{OBJECT_TYPES[obj_type]}"
    headers = {"icSessionId": session_id, "Accept": "application/json"}
    params = {"pageSize": 100}
    all_objects = []
    page_token = None

    while True:
        if page_token:
            params["pageToken"] = page_token
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"Error listing {obj_type}: {e}")
            break

        if resp.status_code != 200:
            print(f"Warning: Failed to list {obj_type}: {resp.status_code} - {resp.text[:200]}")
            break

        data = resp.json()
        items = data.get("items", [])
        all_objects.extend(items)

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
        page_token = next_page_token

    return all_objects


def delete_object(api_base: str, session_id: str, obj_type: str, obj_id: str) -> bool:
    """Delete an object by ID. Returns True if successful."""
    url = f"{api_base}/{OBJECT_TYPES[obj_type]}/{obj_id}"
    headers = {"icSessionId": session_id}
    try:
        resp = requests.delete(url, headers=headers, timeout=30)
        return resp.status_code in (200, 204)
    except requests.exceptions.RequestException as e:
        print(f"Error deleting {obj_type} {obj_id}: {e}")
        return False


def get_package_objects(package_zip: str) -> Set[Tuple[str, str]]:
    """
    Extract the package and read exportMetadata.v2.json to collect (type, name) pairs.
    """
    objects_in_package = set()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Unzip package
        with zipfile.ZipFile(package_zip, 'r') as z:
            z.extractall(tmpdir)

        # Look for exportMetadata.v2.json
        manifest_path = os.path.join(tmpdir, "exportMetadata.v2.json")
        if not os.path.exists(manifest_path):
            print("Warning: exportMetadata.v2.json not found in package. No objects will be cleaned.")
            return objects_in_package

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except Exception as e:
            print(f"Error reading manifest: {e}")
            return objects_in_package

        exported_objects = manifest.get("exportedObjects", [])
        for item in exported_objects:
            obj_type = item.get("objectType")
            obj_name = item.get("objectName")
            if obj_type and obj_name:
                # Map the type to our internal type key (if needed)
                # For example, if the manifest uses "MTT", we keep it as is.
                objects_in_package.add((obj_type, obj_name))
            else:
                print(f"Skipping item without type/name: {item}")

    print(f"Found {len(objects_in_package)} objects in package: {objects_in_package}")
    return objects_in_package


def main():
    parser = argparse.ArgumentParser(description="Clean up target IICS environment before import.")
    parser.add_argument("--username", required=True, help="IICS username for target environment")
    parser.add_argument("--password", required=True, help="IICS password for target environment")
    parser.add_argument("--package", required=True, help="Path to the package zip file")
    parser.add_argument("--host", required=True, help="Pod hostname (e.g., apse1.dm-ap.informaticacloud.com)")
    parser.add_argument("--login-host", default="dm-ap.informaticacloud.com",
                        help="Login host (default: dm-ap.informaticacloud.com)")
    args = parser.parse_args()

    login_url = f"https://{args.login_host}/saas/public/core/v3/login"
    api_base = f"https://{args.host}/api/v2"

    print(f"Logging into {login_url}...")
    try:
        session_id = login(login_url, args.username, args.password)
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

    print("Extracting package contents...")
    package_objects = get_package_objects(args.package)
    print(f"Found {len(package_objects)} objects in package.")

    total_deleted = 0
    for obj_type, api_type in OBJECT_TYPES.items():
        print(f"Checking existing {obj_type}s in target...")
        existing = list_all_objects(api_base, session_id, obj_type)
        for obj in existing:
            obj_name = obj.get("name")
            obj_id = obj.get("id")
            if not obj_name or not obj_id:
                continue
            # Check if this object (type, name) exists in the package
            if (obj_type, obj_name) not in package_objects:
                print(f"Deleting {obj_type} '{obj_name}' (ID: {obj_id})...")
                if delete_object(api_base, session_id, obj_type, obj_id):
                    total_deleted += 1
                    print("  Deleted.")
                else:
                    print(f"  Failed to delete {obj_name}.")
            else:
                print(f"Keeping {obj_type} '{obj_name}' (present in package).")

    print(f"Cleanup completed. Total objects deleted: {total_deleted}")


if __name__ == "__main__":
    main()