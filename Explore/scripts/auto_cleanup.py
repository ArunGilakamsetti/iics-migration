#!/usr/bin/env python3
"""
Pre‑import cleanup: deletes projects in target environment that are present in the package.
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
    """List all projects in target environment."""
    url = f"{api_base}/project"
    headers = {"INFA-SESSION-ID": session_id, "Accept": "application/json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"⚠️ Failed to list projects: {resp.status_code}")
        return []
    data = resp.json()
    return data if isinstance(data, list) else data.get("items", [])

def delete_project(api_base: str, session_id: str, project_id: str) -> bool:
    """Delete a project by ID."""
    url = f"{api_base}/project/{project_id}"
    headers = {"INFA-SESSION-ID": session_id}
    resp = requests.delete(url, headers=headers)
    return resp.status_code in (200, 204)

def main():
    if len(sys.argv) < 3:
        print("Usage: auto_cleanup.py <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1:3]
    login_host = os.getenv("IICS_LOGIN_HOST", "dm-ap.informaticacloud.com")
    pod_host = os.getenv("IICS_POD_HOST", "apse1.dm-ap.informaticacloud.com")
    zip_path = os.getenv("PACKAGE_ZIP", "ready_to_deploy.zip")  # set in workflow

    login_url = f"https://{login_host}/saas/public/core/v3/login"
    api_base = f"https://{pod_host}/api/v2"  # try without /saas

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

    deleted = 0
    for proj_name in projects_to_delete:
        if proj_name in project_map:
            print(f"🗑️ Deleting project '{proj_name}' (ID: {project_map[proj_name]})...")
            if delete_project(api_base, session_id, project_map[proj_name]):
                deleted += 1
                print("   ✅ Deleted.")
            else:
                print(f"   ❌ Failed to delete {proj_name}.")
        else:
            print(f"ℹ️ Project '{proj_name}' not found in target. Skipping.")

    print(f"✨ Cleanup completed. Total projects deleted: {deleted}")

if __name__ == "__main__":
    main()