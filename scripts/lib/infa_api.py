import requests
import json

class IICSApiClient:
    def __init__(self, base_url, pod_url, username, password):
        self.base_url = base_url
        self.pod_url = pod_url
        self.username = username
        self.password = password
        self.session_id = None
        self.headers = {}

    def login(self):
        url = f"{self.base_url}/saas/public/core/v3/login"
        payload = {"username": self.username, "password": self.password}
        resp = requests.post(url, json=payload)
        if resp.status_code != 200:
            raise Exception(f"Login failed: {resp.text}")
        data = resp.json()
        self.session_id = data["userInfo"]["sessionId"]
        self.headers = {"INFA-SESSION-ID": self.session_id}
        return self.session_id

    def logout(self):
        if self.session_id:
            url = f"{self.base_url}/saas/public/core/v3/logout"
            requests.post(url, headers=self.headers)

    def export_package(self, project_name, include_dependencies=True):
        url = f"{self.pod_url}/api/v2/package/export"
        payload = {
            "objects": [{"type": "PROJECT", "name": project_name}],
            "includeDependencies": include_dependencies
        }
        resp = requests.post(url, headers=self.headers, json=payload)
        if resp.status_code != 200:
            raise Exception(f"Export failed: {resp.text}")
        return resp.content

    def import_package(self, package_content, overrides=None):
        url = f"{self.pod_url}/api/v2/package/import"
        files = {"packageFile": ("package.zip", package_content, "application/zip")}
        if overrides:
            files["overrides"] = ("overrides.json", json.dumps(overrides), "application/json")
        resp = requests.post(url, headers={"INFA-SESSION-ID": self.session_id}, files=files)
        if resp.status_code != 200:
            raise Exception(f"Import failed: {resp.text}")
        return resp.json()