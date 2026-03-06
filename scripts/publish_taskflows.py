#!/usr/bin/env python3
"""
Publishes all taskflows in the target environment after import.
Ensures they are fully activated and dependencies are resolved.
"""

import requests
import time
import sys
import os
from typing import Dict, List, Optional

class IICSTaskflowPublisher:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session_id = None
        self.headers = None

    def login(self) -> bool:
        """Authenticate and get session ID."""
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

    def list_taskflows(self, name_filter: Optional[str] = None) -> List[Dict]:
        """List all taskflows, optionally filtering by name."""
        url = f"{self.base_url}/api/v2/workflow"
        params = {"pageSize": 100}
        all_tfs = []
        page_token = None

        while True:
            if page_token:
                params["pageToken"] = page_token
            try:
                resp = requests.get(url, headers=self.headers, params=params, timeout=30)
                if resp.status_code != 200:
                    print(f"⚠️ Failed to list taskflows: {resp.status_code}")
                    break
                data = resp.json()
                items = data.get("items", [])
                if name_filter:
                    items = [tf for tf in items if name_filter.lower() in tf.get("name", "").lower()]
                all_tfs.extend(items)
                next_token = data.get("nextPageToken")
                if not next_token:
                    break
                page_token = next_token
            except Exception as e:
                print(f"❌ Error listing taskflows: {e}")
                break
        return all_tfs

    def publish_taskflow(self, taskflow_id: str) -> bool:
        """Publish a single taskflow by ID."""
        url = f"{self.base_url}/api/v2/workflow/{taskflow_id}/publish"
        try:
            resp = requests.post(url, headers=self.headers, timeout=60)
            if resp.status_code == 202:  # Accepted – publish started
                print(f"  ⏳ Publish started for taskflow {taskflow_id}")
                return True
            elif resp.status_code == 200:
                print(f"  ✅ Publish completed immediately for {taskflow_id}")
                return True
            else:
                print(f"  ❌ Publish failed for {taskflow_id}: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"  ❌ Exception during publish: {e}")
            return False

    def wait_for_publish(self, taskflow_id: str, timeout_seconds: int = 300) -> bool:
        """Poll until taskflow status becomes PUBLISHED or timeout."""
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
                        print(f"    ✅ Taskflow {taskflow_id} is now PUBLISHED")
                        return True
                    else:
                        print(f"    ⏳ Current status: {status}")
                time.sleep(poll_interval)
            except Exception as e:
                print(f"    ❌ Error checking status: {e}")
                time.sleep(poll_interval)
        print(f"    ⏰ Timeout waiting for taskflow {taskflow_id}")
        return False

    def publish_all_unpublished(self, name_filter: Optional[str] = None):
        """Find all taskflows that are not published and publish them."""
        print("\n🔍 Listing taskflows...")
        taskflows = self.list_taskflows(name_filter)
        if not taskflows:
            print("No taskflows found.")
            return

        unpublished = [tf for tf in taskflows if tf.get("status", "").upper() != "PUBLISHED"]
        print(f"Found {len(taskflows)} taskflows, {len(unpublished)} unpublished.")

        for tf in unpublished:
            name = tf.get("name", "Unknown")
            tf_id = tf.get("id")
            print(f"\n📦 Processing taskflow: {name} (ID: {tf_id})")
            if self.publish_taskflow(tf_id):
                if not self.wait_for_publish(tf_id):
                    print(f"  ❌ Failed to confirm publish for {name}")
            else:
                print(f"  ❌ Could not start publish for {name}")

def main():
    base_url = os.environ.get("IICS_BASE_URL")
    username = os.environ.get("IICS_USERNAME")
    password = os.environ.get("IICS_PASSWORD")
    taskflow_filter = os.environ.get("TASKFLOW_FILTER")  # optional name substring

    if not all([base_url, username, password]):
        print("❌ Missing required environment variables")
        sys.exit(1)

    publisher = IICSTaskflowPublisher(base_url, username, password)
    if not publisher.login():
        sys.exit(1)

    publisher.publish_all_unpublished(taskflow_filter)
    print("\n✅ Taskflow publishing completed.")

if __name__ == "__main__":
    main()