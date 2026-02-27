#!/usr/bin/env python3
"""
Pre‑import cleanup: deletes projects in target environment that are present in the package.
Uses baseApiUrl from login if available, otherwise constructs from pod host.
"""

import sys
import os
import json
import requests
import tempfile
import zipfile
from typing import Set, Dict, List

def login(login_url: str, username: str, password: str) -> tuple:
    """Login and return (session_id, base_api_url)."""
    resp = requests.post(login_url, json={"username": username, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.text}")
    data = resp.json()
    session_id = data["userInfo"]["sessionId"]
    base_api_url = data["userInfo"].get("baseApiUrl")  # may be None
    return session_id, base_api_url

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

def list_projects(base_urls: List[str], session_id: str) -> List[Dict]:
    """Try multiple base URLs to list projects."""
    headers = {"INFA-SESSION-ID": session_id, "Accept": "application/json"}
    for base in base_urls:
        url = f"{base.rstrip('/')}/project"
        print(f"🔍 Trying: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            print(f"   → Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                projects = data if isinstance(data, list) else data.get("items", [])
                return projects
            else:
                print(f"   Response: {resp.text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    return []

def delete_project(base_urls: List[str], session_id: str, project_id: str) -> bool:
    """Try multiple base URLs to delete a project."""
    headers = {"INFA-SESSION-ID": session_id}
    for base in base_urls:
        url = f"{base.rstrip('/')}/project/{project_id}"
        print(f"🗑️ Trying delete: {url}")
        try:
            resp = requests.delete(url, headers=headers, timeout=30)
            print(f"   → Status: {resp.status_code}")
            if resp.status_code in (200, 204):
                return True
            else:
                print(f"   Response: {resp.text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    return False

def main():
    if len(sys.argv) < 3:
        print("Usage: auto_cleanup.py <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1:3]
    login_host = os.getenv("IICS_LOGIN_HOST", "dm-ap.informaticacloud.com")
    pod_host = os.getenv("IICS_POD_HOST")
    zip_path = os.getenv("PACKAGE_ZIP", "ready_to_deploy.zip")

    if not pod_host:
        print("❌ IICS_POD_HOST environment variable not set.")
        sys.exit(1)

    login_url = f"https://{login_host}/saas/public/core/v3/login"

    print("🔐 Logging in...")
    try:
        session_id, api_base_from_login = login(login_url, username, password)
        print(f"✅ Login successful. API base from login: {api_base_from_login}")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        sys.exit(1)

    # Prepare list of base URLs to try
    base_urls = []
    if api_base_from_login:
        base_urls.append(api_base_from_login)
    # Always try constructed from pod host with common paths
    base_urls.append(f"https://{pod_host}/saas/api/v2")
    base_urls.append(f"https://{pod_host}/api/v2")
    # Remove duplicates while preserving order
    seen = set()
    unique_base_urls = []
    for url in base_urls:
        if url not in seen:
            seen.add(url)
            unique_base_urls.append(url)

    print("📦 Reading project names from manifest...")
    projects_to_delete = get_manifest_projects(zip_path)
    if not projects_to_delete:
        print("No projects found in manifest. Nothing to delete.")
        return
    print(f"Projects to delete: {projects_to_delete}")

    print("🔍 Listing existing projects in target...")
    all_projects = list_projects(unique_base_urls, session_id)
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
            if delete_project(unique_base_urls, session_id, project_map[proj_name]):
                deleted += 1
                print("   ✅ Deleted.")
            else:
                print(f"   ❌ Failed to delete {proj_name}.")
        else:
            print(f"ℹ️ Project '{proj_name}' not found in target. Skipping.")

    print(f"✨ Cleanup completed. Total projects deleted: {deleted}")

if __name__ == "__main__":
    main()