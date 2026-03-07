#!/usr/bin/env python3
"""
Publishes specific taskflows by full asset path in the target environment.
Expects a file with one asset path per line (e.g., Explore/Project/Folder/Taskflow.TASKFLOW).
"""

import requests
import time
import sys
import os
import re
from typing import Set, Dict, Optional, Tuple

class IICSTaskflowPublisher:
    def __init__(self, login_host: str, api_host: str, username: str, password: str):
        self.login_host = login_host
        self.api_host = api_host
        self.username = username
        self.password = password
        self.session_id = None
        self.headers = None

    def login(self) -> bool:
        login_url = f"https://{self.login_host}/saas/public/core/v3/login"
        payload = {"username": self.username, "password": self.password}
        try:
            resp = requests.post(login_url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            self.session_id = data["userInfo"]["sessionId"]
            self.headers = {
                "INFA-SESSION-ID": self.session_id,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            print("✅ Login successful")
            return True
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

    def find_taskflow_by_path(self, asset_path: str) -> Optional[Dict]:
        """
        Find a taskflow by its full asset path (e.g., Explore/Project/Folder/Name.TASKFLOW).
        Returns the taskflow object if found.
        """
        # Remove the leading 'Explore/' and the trailing '.TASKFLOW'
        # Example: "Explore/Project/Folder/MyTask.TASKFLOW" -> path = "Project/Folder", name = "MyTask"
        match = re.match(r"Explore/(.+)\.TASKFLOW$", asset_path)
        if not match:
            print(f"  ⚠️ Invalid taskflow path format: {asset_path}")
            return None
        full_path = match.group(1)  # e.g., "Project/Folder/MyTask"
        # Split into folder path and name
        parts = full_path.split('/')
        name = parts[-1]
        folder_path = '/'.join(parts[:-1]) if len(parts) > 1 else ""

        # Use the search API to find objects by name and location
        url = f"https://{self.api_host}/api/v2/mdata/search"
        params = {
            "q": f"name:'{name}' AND type:'TASKFLOW'"
        }
        if folder_path:
            params["q"] += f" AND location:'{folder_path}'"

        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"  ❌ Search failed: {resp.status_code}")
                return None
            items = resp.json()
            # If multiple, we might need to refine; assume first match is correct
            if items:
                return items[0]
            else:
                print(f"  ❌ Taskflow '{name}' not found in folder '{folder_path}'")
                return None
        except Exception as e:
            print(f"  ❌ Error during search: {e}")
            return None

    def publish_taskflow(self, taskflow_id: str) -> bool:
        url = f"https://{self.api_host}/api/v2/workflow/{taskflow_id}/publish"
        try:
            resp = requests.post(url, headers=self.headers, timeout=60)
            if resp.status_code in (200, 202):
                return True
            else:
                print(f"  ❌ Publish failed: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"  ❌ Exception during publish: {e}")
            return False

    def wait_for_publish(self, taskflow_id: str, timeout_seconds: int = 300) -> bool:
        url = f"https://{self.api_host}/api/v2/workflow/{taskflow_id}"
        start = time.time()
        poll_interval = 10
        while time.time() - start < timeout_seconds:
            try:
                resp = requests.get(url, headers=self.headers, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "").upper()
                    if status == "PUBLISHED":
                        return True
                    else:
                        print(f"    ⏳ Current status: {status}")
                time.sleep(poll_interval)
            except Exception as e:
                print(f"    ❌ Error checking status: {e}")
                time.sleep(poll_interval)
        return False

    def publish_taskflows_from_file(self, file_path: str):
        with open(file_path, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        for path in lines:
            print(f"\n📦 Processing taskflow: {path}")
            tf = self.find_taskflow_by_path(path)
            if not tf:
                print(f"  ❌ Taskflow not found.")
                continue
            tf_id = tf.get("id")
            current_status = tf.get("status", "").upper()
            if current_status == "PUBLISHED":
                print(f"  ✅ Already published")
                continue
            if self.publish_taskflow(tf_id):
                if self.wait_for_publish(tf_id):
                    print(f"  ✅ Published successfully")
                else:
                    print(f"  ⚠️ Publish started but did not complete within timeout.")
            else:
                print(f"  ❌ Failed to start publish.")

def main():
    login_host = os.environ.get("IICS_LOGIN_HOST")
    api_host = os.environ.get("IICS_API_HOST")
    username = os.environ.get("IICS_USERNAME")
    password = os.environ.get("IICS_PASSWORD")
    taskflow_file = os.environ.get("TASKFLOW_FILE", "taskflows_full.txt")

    if not all([login_host, api_host, username, password]):
        print("❌ Missing required environment variables")
        sys.exit(1)

    if not os.path.exists(taskflow_file):
        print(f"⚠️ No taskflow file found at {taskflow_file}. Nothing to publish.")
        return

    publisher = IICSTaskflowPublisher(login_host, api_host, username, password)
    if not publisher.login():
        sys.exit(1)

    publisher.publish_taskflows_from_file(taskflow_file)
    print("\n✅ Taskflow publishing completed.")

if __name__ == "__main__":
    main()