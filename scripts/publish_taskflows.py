#!/usr/bin/env python3
"""
Publishes specific taskflows by name in the target environment.
Expects a file with one taskflow name per line.
"""

import requests
import time
import sys
import os
from typing import Set, Dict, Optional

class IICSTaskflowPublisher:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session_id = None
        self.headers = None

    def login(self) -> bool:
        login_url = f"{self.base_url}/saas/public/core/v3/login"
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

    def find_taskflow_by_name(self, name: str) -> Optional[Dict]:
        """Find a taskflow by exact name."""
        url = f"{self.base_url}/api/v2/workflow"
        params = {"name": name, "exactMatch": "true"}  # some APIs support exact match; fallback to filtering
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                # If API doesn't support exact match, filter client-side
                if not items:
                    # fallback: list all and filter
                    all_items = []
                    page_token = None
                    while True:
                        page_params = {"pageSize": 100}
                        if page_token:
                            page_params["pageToken"] = page_token
                        r = requests.get(url, headers=self.headers, params=page_params, timeout=30)
                        if r.status_code != 200:
                            break
                        page_data = r.json()
                        all_items.extend(page_data.get("items", []))
                        next_token = page_data.get("nextPageToken")
                        if not next_token:
                            break
                        page_token = next_token
                    items = [tf for tf in all_items if tf.get("name") == name]
                if items:
                    return items[0]
            return None
        except Exception as e:
            print(f"❌ Error finding taskflow {name}: {e}")
            return None

    def publish_taskflow(self, taskflow_id: str) -> bool:
        url = f"{self.base_url}/api/v2/workflow/{taskflow_id}/publish"
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
        url = f"{self.base_url}/api/v2/workflow/{taskflow_id}"
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

    def publish_named_taskflows(self, names: Set[str]):
        for name in names:
            print(f"\n📦 Processing taskflow: {name}")
            tf = self.find_taskflow_by_name(name)
            if not tf:
                print(f"  ❌ Taskflow '{name}' not found in target environment.")
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
    base_url = os.environ.get("IICS_BASE_URL")
    username = os.environ.get("IICS_USERNAME")
    password = os.environ.get("IICS_PASSWORD")
    taskflow_file = os.environ.get("TASKFLOW_FILE", "taskflows.txt")

    if not all([base_url, username, password]):
        print("❌ Missing required environment variables")
        sys.exit(1)

    if not os.path.exists(taskflow_file):
        print(f"⚠️ No taskflow file found at {taskflow_file}. Nothing to publish.")
        return

    with open(taskflow_file, 'r') as f:
        names = {line.strip() for line in f if line.strip()}

    if not names:
        print("ℹ️ Taskflow list is empty. Nothing to publish.")
        return

    publisher = IICSTaskflowPublisher(base_url, username, password)
    if not publisher.login():
        sys.exit(1)

    publisher.publish_named_taskflows(names)
    print("\n✅ Taskflow publishing completed.")

if __name__ == "__main__":
    main()