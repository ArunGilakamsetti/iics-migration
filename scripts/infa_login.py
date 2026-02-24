#!/usr/bin/env python3
import os, sys, json
from lib.infa_api import IICSApiClient
from lib.my_logger import MyLogger

def main():
    logger = MyLogger(__name__).get_logger()
    try:
        base_url = os.environ["IICS_LOGIN_URL"]
        pod_url = os.environ["IICS_POD_URL"]
        username = os.environ["IICS_USERNAME"]
        password = os.environ["IICS_PASSWORD"]

        client = IICSApiClient(base_url, pod_url, username, password)
        session_id = client.login()
        logger.info("Login successful")

        # Save session for subsequent steps
        with open("session_info.json", "w") as f:
            json.dump({"session_id": session_id, "base_url": base_url, "pod_url": pod_url}, f)

        # For GitHub Actions
        env_file = os.getenv("GITHUB_ENV")
        if env_file:
            with open(env_file, "a") as f:
                f.write(f"sessionId={session_id}\n")
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()