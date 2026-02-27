#!/usr/bin/env python3
"""
Pre‑import cleanup: deletes projects in target environment that are present in the package.
Now tries multiple API base URLs and prints debug info.
"""

import sys
import os
import json
import requests
import tempfile
import zipfile
from typing import Set, Dict, List

def login(login_url: str, username: str, password: str) -> str:
    """Login and return session ID."""
    resp = requests.post(login_url, json={"username": username, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.text}")
    return resp.json()["userInfo"]["sessionId"]

def get_manifest_projects(zip_path: str) -> Set[str]:
    """
    Extract exportMetadata.v2.json from the zip and return set of project names.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as z:
            manifest_members = [m for m in z.namelist() if m.endswith("exportMetadata.v2.json")]
            if not manifest_members:
                return set()
            z.extract(manifest_members[0], tmpdir)
            manifest_path = os.path.join(tmpdir, manifest_members[0])
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            projects = set()
            for obj in manifest.get("exportedObjects", []):
                if obj.get("objectType") == "Project":
                    proj_name = obj.get("objectName")
                    if proj_name:
                        projects.add(proj_name)
            return projects

def list_projects(api_base: str, session_id: str) -> List[Dict]:
    """Try to list projects using common endpoint variations."""
    # Try multiple possible endpoints
    endpoints_to_try = [
        f"{api_base}/project",
        f"{api_base}/projects",
        f"{api_base}/api/v2/project",
        f"{api_base}/api/v2/projects",
        f"{api_base}/saas/api/v2/project",
        f"{api_base}/saas/api/v2/projects",
    ]
    headers = {"INFA-SESSION-ID": session_id, "Accept": "application/json"}
    for url in endpoints_to_try:
        print(f"🔍 Trying: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"   → Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                # Handle response format (list or dict with 'items')
                projects = data if isinstance(data, list) else data.get("items", [])
                if projects:
                    print(f"✅ Found projects via {url}")
                    return projects
                else:
                    print("   (empty list)")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    return []

def delete_project(api_base: str, session_id: str, project_id: str) -> bool:
    """Delete a project by ID. Try multiple endpoint variations."""
    endpoints_to_try = [
        f"{api_base}/project/{project_id}",
        f"{api_base}/api/v2/project/{project_id}",
        f"{api_base}/saas/api/v2/project/{project_id}",
    ]
    headers = {"INFA-SESSION-ID": session_id}
    for url in endpoints_to_try:
        print(f"🗑️ Trying delete: {url}")
        try:
            resp = requests.delete(url, headers=headers, timeout=10)
            if resp.status_code in (200, 204):
                print(f"   ✅ Deleted via {url}")
                return True
            else:
                print(f"   → Status: {resp.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    return False

def main():
    if len(sys.argv) < 3:
        print("Usage: auto_cleanup.py <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1:3]
    login_host = os.getenv("IICS_LOGIN_HOST", "dm-ap.informaticacloud.com")
    pod_host = os.getenv("IICS_POD_HOST", login_host)  # fallback to login host
    zip_path = os.getenv("PACKAGE_ZIP", "ready_to_deploy.zip")

    login_url = f"https://{login_host}/saas/public/core/v3/login"
    # Base URL for API calls – try with just host (no path prefix)
    api_base = f"https://{pod_host}"

    print("🔐 Logging in...")
    try:
        session_id = login(login_url, username, password)
        print("✅ Login successful.")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        sys.exit(1)

    print("📦 Reading project names from manifest...")
    projects_to_delete = get_manifest_projects(zip_path)
    if not projects_to_delete:
        print("No projects found in manifest. Nothing to delete.")
        return
    print(f"Projects to delete: {projects_to_delete}")

    print("🔍 Listing existing projects in target...")
    all_projects = list_projects(api_base, session_id)
    if not all_projects:
        print("No projects found in target. Nothing to delete.")
        return

    # Create name-to-id mapping
    project_map = {p["name"]: p["id"] for p in all_projects if "name" in p and "id" in p}
    print(f"Found projects in target: {list(project_map.keys())}")

    deleted = 0
    for proj_name in projects_to_delete:
        if proj_name in project_map:
            print(f"🗑️ Deleting project '{proj_name}' (ID: {project_map[proj_name]})...")
            if delete_project(api_base, session_id, project_map[proj_name]):
                deleted += 1
            else:
                print(f"   ❌ Failed to delete {proj_name}.")
        else:
            print(f"ℹ️ Project '{proj_name}' not found in target. Skipping.")

    print(f"✨ Cleanup completed. Total projects deleted: {deleted}")

if __name__ == "__main__":
    main()