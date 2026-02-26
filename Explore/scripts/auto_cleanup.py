import json, subprocess, os, zipfile, sys

def load_dev_manifest(package_file):
    """Load DEV package manifest from exportMetadata.v2.json."""
    with zipfile.ZipFile(package_file, 'r') as z:
        files = z.namelist()
        print("Package contents:", files)

        # Look specifically for exportMetadata.v2.json
        if "exportMetadata.v2.json" not in files:
            raise FileNotFoundError("exportMetadata.v2.json not found in package zip")

        with z.open("exportMetadata.v2.json") as f:
            manifest = json.load(f)

    # Extract exportedObjects list
    if "exportedObjects" in manifest:
        return { (obj['objectName'], obj['objectType']) for obj in manifest['exportedObjects'] }
    else:
        raise KeyError("exportMetadata.v2.json does not contain 'exportedObjects'")

def load_target_objects(file):
    """Load target environment objects from REST API output."""
    with open(file) as f:
        data = json.load(f)
    return { (obj['name'], obj['type']) for obj in data.get('objects', []) }

def delete_object(name, obj_type):
    """Delete object from target environment using CLI."""
    print(f"Deleting {obj_type}: {name}...")
    subprocess.run([
        "./iics", "deleteObject",
        "-n", name,
        "-t", obj_type,
        "-r", os.environ["IICS_REGION"],
        "--podHostName", os.environ["IICS_POD_HOST"],
        "-u", os.environ[f"{os.environ['DEPLOY_ENV'].upper()}_IICS_USER"],
        "-p", os.environ[f"{os.environ['DEPLOY_ENV'].upper()}_IICS_PWD"]
    ], check=True)

if __name__ == "__main__":
    env = os.environ["DEPLOY_ENV"]
    dry_run = "--check-only" in sys.argv

    # Load DEV manifest from prepared package
    package_file = f"package_{env}_final.zip"
    dev_objects = load_dev_manifest(package_file)

    # Load target environment objects
    target_objects = load_target_objects("target_objects.json")

    # Find objects in target but not in DEV
    to_delete = target_objects - dev_objects

    for name, obj_type in to_delete:
        if name.startswith("Adhoc_Activities/"):
            print(f"Skipping adhoc object: {name}")
            continue

        if dry_run:
            print(f"[DRY-RUN] Would delete {obj_type}: {name}")
        else:
            delete_object(name, obj_type)
