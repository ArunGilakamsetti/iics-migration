#!/usr/bin/env python3
"""
Pre-import cleanup for IICS target environment.
Deletes all objects of specified types that are NOT present in the package.
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
# CONFIGURATION – adjust these to match your IICS pod/region
# ----------------------------------------------------------------------
LOGIN_URL = "https://dm-ap.informaticacloud.com/saas/public/core/v3/login"
API_BASE = "https://dm-ap.informaticacloud.com/api/v2"

# Object types to clean up: maps internal type to API endpoint path
# Add or remove types as needed
OBJECT_TYPES = {
    "MTT": "mttask",          # Mapping Task
    "TASKFLOW": "taskflow",    # Taskflow
    "MAPPING": "mapping",      # Individual mapping (if exported separately)
    # "CONNECTION": "connection", # Usually not cleaned up – rely on overrides
}
# ----------------------------------------------------------------------


def login(username: str, password: str) -> str:
    """Login and return session ID."""
    payload = {"username": username, "password": password}
    resp = requests.post(LOGIN_URL, json=payload)
    resp.raise_for_status()
    return resp.json()["userInfo"]["sessionId"]


def list_all_objects(session_id: str, obj_type: str) -> List[Dict]:
    """
    List all objects of given type in the target environment,
    handling pagination automatically.
    """
    url = f"{API_BASE}/{OBJECT_TYPES[obj_type]}"
    headers = {"icSessionId": session_id, "Accept": "application/json"}
    params = {"pageSize": 100}  # adjust if needed
    all_objects = []
    page_token = None

    while True:
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            print(f"Warning: Failed to list {obj_type}: {resp.status_code}")
            break

        data = resp.json()
        items = data.get("items", [])
        all_objects.extend(items)

        # Check for next page token (depends on API)
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
        page_token = next_page_token

    return all_objects


def delete_object(session_id: str, obj_type: str, obj_id: str) -> bool:
    """Delete an object by ID. Returns True if successful."""
    url = f"{API_BASE}/{OBJECT_TYPES[obj_type]}/{obj_id}"
    headers = {"icSessionId": session_id}
    resp = requests.delete(url, headers=headers)
    return resp.status_code in (200, 204)


def get_package_objects(package_zip: str) -> Set[Tuple[str, str]]:
    """
    Extract the package and parse all object JSON files to collect
    (type, name) pairs.
    """
    objects_in_package = set()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Unzip package
        with zipfile.ZipFile(package_zip, 'r') as z:
            z.extractall(tmpdir)

        # Walk through extracted workspace and find JSON files
        for root, dirs, files in os.walk(tmpdir):
            for file in files:
                if file.endswith(".json"):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        # Each object JSON typically has "type" and "name" fields
                        obj_type = data.get("type")
                        obj_name = data.get("name")
                        if obj_type and obj_name:
                            objects_in_package.add((obj_type, obj_name))
                    except Exception as e:
                        # Not a valid object JSON – ignore
                        continue
    return objects_in_package


def main():
    parser = argparse.ArgumentParser(description="Clean up target IICS environment before import.")
    parser.add_argument("--username", required=True, help="IICS username for target environment")
    parser.add_argument("--password", required=True, help="IICS password for target environment")
    parser.add_argument("--package", required=True, help="Path to the package zip file")
    args = parser.parse_args()

    print("Logging into target IICS...")
    session_id = login(args.username, args.password)

    print("Extracting package contents...")
    package_objects = get_package_objects(args.package)
    print(f"Found {len(package_objects)} objects in package.")

    total_deleted = 0
    for obj_type, api_type in OBJECT_TYPES.items():
        print(f"Checking existing {obj_type}s in target...")
        existing = list_all_objects(session_id, obj_type)
        for obj in existing:
            obj_name = obj.get("name")
            obj_id = obj.get("id")
            if not obj_name or not obj_id:
                continue
            if (obj_type, obj_name) not in package_objects:
                print(f"Deleting {obj_type} '{obj_name}' (ID: {obj_id})...")
                if delete_object(session_id, obj_type, obj_id):
                    total_deleted += 1
                    print("  Deleted.")
                else:
                    print(f"  Failed to delete {obj_name}.")
            else:
                print(f"Keeping {obj_type} '{obj_name}' (present in package).")

    print(f"Cleanup completed. Total objects deleted: {total_deleted}")


if __name__ == "__main__":
    main()