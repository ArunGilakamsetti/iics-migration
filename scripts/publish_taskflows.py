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

    def find_taskflow_by_name(self, name: str) -> Optional[Dict]:
        """Find a taskflow by exact name."""
        url = f"https://{self.api_host}/api/v2/workflow"
        params = {"pageSize": 100}
        all_items = []
        page_token = None
        try:
            while True:
                if page_token:
                    params["pageToken"] = page_token
                resp = requests.get(url, headers=self.headers, params=params, timeout=30)
                if resp.status_code != 200:
                    break
                data = resp.json()
                all_items.extend(data.get("items", []))
                next_token = data.get("nextPageToken")
                if not next_token:
                    break
                page_token = next_token
            # Find exact match
            for tf in all_items:
                if tf.get("name") == name:
                    return tf
            return None
        except Exception as e:
            print(f"❌ Error finding taskflow {name}: {e}")
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
    login_host = os.environ.get("IICS_LOGIN_HOST")
    api_host = os.environ.get("IICS_API_HOST")
    username = os.environ.get("IICS_USERNAME")
    password = os.environ.get("IICS_PASSWORD")
    taskflow_file = os.environ.get("TASKFLOW_FILE", "taskflows.txt")

    if not all([login_host, api_host, username, password]):
        print("❌ Missing required environment variables (IICS_LOGIN_HOST, IICS_API_HOST, IICS_USERNAME, IICS_PASSWORD)")
        sys.exit(1)

    if not os.path.exists(taskflow_file):
        print(f"⚠️ No taskflow file found at {taskflow_file}. Nothing to publish.")
        return

    with open(taskflow_file, 'r') as f:
        names = {line.strip() for line in f if line.strip() and not line.startswith('#')}

    if not names:
        print("ℹ️ Taskflow list is empty. Nothing to publish.")
        return

    publisher = IICSTaskflowPublisher(login_host, api_host, username, password)
    if not publisher.login():
        sys.exit(1)

    publisher.publish_named_taskflows(names)
    print("\n✅ Taskflow publishing completed.")

if __name__ == "__main__":
    main()