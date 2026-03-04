#!/usr/bin/env python3
"""
Publishes one or more taskflows in the target IICS environment.
Usage: python publish_taskflows.py <username> <password> <pod_host> <region> [taskflow_names...]
"""

import sys
import requests
import time

def login(username, password, pod_host):
    url = f"https://{pod_host}/saas/public/core/v3/login"
    payload = {"username": username, "password": password}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data["userInfo"]["sessionId"]

def get_taskflow_id(session_id, pod_host, taskflow_name):
    # Adjust the endpoint to your IICS version
    url = f"https://{pod_host}/api/v2/taskflow"
    headers = {"INFA-SESSION-ID": session_id}
    params = {"name": taskflow_name}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        print(f"⚠️ Failed to find taskflow '{taskflow_name}': {resp.status_code}")
        return None
    items = resp.json().get("items", [])
    if not items:
        print(f"⚠️ Taskflow '{taskflow_name}' not found.")
        return None
    # Assume first match
    return items[0]["id"]

def publish_taskflow(session_id, pod_host, taskflow_id, taskflow_name):
    # This endpoint may vary; consult your IICS API docs
    url = f"https://{pod_host}/api/v2/taskflow/{taskflow_id}/publish"
    headers = {"INFA-SESSION-ID": session_id}
    resp = requests.post(url, headers=headers)
    if resp.status_code in (200, 204):
        print(f"✅ Published taskflow: {taskflow_name}")
        return True
    else:
        print(f"❌ Failed to publish {taskflow_name}: {resp.status_code} {resp.text}")
        return False

def main():
    if len(sys.argv) < 5:
        print("Usage: python publish_taskflows.py <username> <password> <pod_host> <region> [taskflow_names...]")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    pod_host = sys.argv[3]
    region = sys.argv[4]  # not used directly in this example, but kept for consistency
    taskflow_names = sys.argv[5:]

    if not taskflow_names:
        print("No taskflow names provided. Exiting.")
        return

    session_id = login(username, password, pod_host)

    for name in taskflow_names:
        taskflow_id = get_taskflow_id(session_id, pod_host, name)
        if taskflow_id:
            publish_taskflow(session_id, pod_host, taskflow_id, name)

if __name__ == "__main__":
    main()