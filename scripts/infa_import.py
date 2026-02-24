#!/usr/bin/env python3
import os, sys, json, argparse
from lib.infa_api import IICSApiClient
from lib.my_logger import MyLogger

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--env", required=True)
    args = parser.parse_args()

    logger = MyLogger(__name__).get_logger()
    try:
        with open("session_info.json") as f:
            session_info = json.load(f)
        with open(args.config) as f:
            env_config = json.load(f)

        client = IICSApiClient(session_info["base_url"], session_info["pod_url"], "", "")
        client.session_id = session_info["session_id"]
        client.headers = {"INFA-SESSION-ID": client.session_id}

        with open(args.package, "rb") as f:
            package_content = f.read()

        overrides = {
            "connectionOverrides": env_config.get("connections", {}),
            "runtimeEnvironment": env_config.get("runtime_environment")
        }

        logger.info(f"Importing to {args.env}")
        result = client.import_package(package_content, overrides)
        logger.info(f"Import completed: {result}")

        with open(f"import_result_{args.env}.json", "w") as f:
            json.dump(result, f)
    except Exception as e:
        logger.error(f"Import failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()