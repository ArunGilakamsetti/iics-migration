import json, subprocess, os, zipfile

def load_dev_manifest(package_file):
    """Load DEV package manifest and return set of (name, type)."""
    with zipfile.ZipFile(package_file, 'r') as z:
        manifest = json.loads(z.read('manifest.json'))
    return { (obj['name'], obj['type']) for obj in manifest['objects'] }

def load_target_objects(file):
    """Load target environment objects from listObjects output."""
    with open(file) as f:
        data = json.load(f)
    return { (obj['name'], obj['type']) for obj in data['objects'] }

def delete_object(name, obj_type):
    """Delete object from target environment using CLI."""
    print(f"Deleting {obj_type}: {name}...")
    subprocess.run([
        "./iics", "deleteObject",
        "-n", name,
        "-t", obj_type,
        "-r", os.environ["IICS_REGION"],
        "--podHostName", os.environ["IICS_POD_HOST"],
        "-u", os.environ["UAT_IICS_USER"],
        "-p", os.environ["UAT_IICS_PWD"]
    ], check=True)

if __name__ == "__main__":
    # Load DEV manifest
    dev_objects = load_dev_manifest(f"package_{os.environ['GITHUB_SHA']}.zip")

    # Load target environment objects
    target_objects = load_target_objects("target_objects.json")

    # Find objects in target but not in DEV
    to_delete = target_objects - dev_objects

    for name, obj_type in to_delete:
        # Skip anything inside Adhoc_Activities folder
        if name.startswith("Adhoc_Activities/"):
            print(f"Skipping adhoc object: {name}")
            continue
        delete_object(name, obj_type)
