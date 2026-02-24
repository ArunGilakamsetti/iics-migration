#!/usr/bin/env python3
import os, sys, json, argparse
from datetime import datetime
from scripts.lib.infa_api import IICSApiClient
from scripts.lib.my_logger import MyLogger

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    logger = MyLogger(__name__).get_logger()
    try:
        with open("session_info.json") as f:
            session_info = json.load(f)

        client = IICSApiClient(session_info["base_url"], session_info["pod_url"], "", "")
        client.session_id = session_info["session_id"]
        client.headers = {"INFA-SESSION-ID": client.session_id}

        logger.info(f"Exporting project: {args.project}")
        package = client.export_package(args.project)
        with open(args.output, "wb") as f:
            f.write(package)
        logger.info(f"Exported to {args.output}")

        # Save manifest for reference
        manifest = {
            "project": args.project,
            "export_timestamp": datetime.now().isoformat(),
            "package_file": args.output
        }
        with open("export_manifest.json", "w") as f:
            json.dump(manifest, f)
    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()