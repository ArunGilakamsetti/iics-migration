#!/usr/bin/env python3
"""
Builds an IICS import ZIP from the Explore folder.
Scans the workspace, generates exportMetadata.v2.json, and creates a package.
"""

import os
import json
import zipfile
import sys
from pathlib import Path

# Mapping of file extensions to IICS object types
# (Add more as needed based on your assets)
EXTENSION_TO_TYPE = {
    '.Project.json': 'Project',
    '.Folder.json': 'Folder',
    '.MTT.zip': 'MTT',
    '.DTEMPLATE.zip': 'DTEMPLATE',
    # Add other types: .TASKFLOW.xml, .Connection.json, etc.
}

def collect_objects(workspace_root):
    """
    Walk the workspace/Explore folder and collect all asset files.
    Returns a list of dicts with keys: objectName, objectType, path.
    """
    objects = []
    explore_path = os.path.join(workspace_root, 'Explore')
    if not os.path.isdir(explore_path):
        print(f"❌ Explore folder not found at {explore_path}")
        sys.exit(1)

    for root, dirs, files in os.walk(explore_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, workspace_root).replace('\\', '/')

            # Determine object type based on file extension
            obj_type = None
            for ext, typ in EXTENSION_TO_TYPE.items():
                if file.endswith(ext):
                    obj_type = typ
                    # For .zip files, the base name includes the type (e.g., mt_read_file.MTT)
                    if ext.endswith('.zip'):
                        # Remove the .zip extension, then split the last part to get name
                        base = file[:-4]  # remove .zip
                        # base might be like "mt_read_file.MTT" – we want the part before the last dot as name, and type from the last part
                        parts = base.split('.')
                        if len(parts) >= 2:
                            name = '.'.join(parts[:-1])  # everything except last part
                            # type already set from EXTENSION_TO_TYPE
                        else:
                            name = base
                    else:
                        # For .json files, remove the extension (e.g., .Project.json)
                        name = file.replace(ext, '')
                    break

            if obj_type and name:
                objects.append({
                    "objectName": name,
                    "objectType": obj_type,
                    "path": rel_path
                })
            else:
                print(f"⚠️ Skipping unrecognized file: {file_path}")

    return objects

def generate_manifest(objects, source_org_name="GitRepo", export_name="Export_from_Git"):
    """
    Create the exportMetadata.v2.json structure.
    """
    manifest = {
        "name": export_name,
        "sourceOrgId": "git",
        "sourceOrgName": source_org_name,
        "exportedObjects": objects
    }
    return manifest

def create_package(workspace_root, output_zip):
    """
    Generate manifest and zip everything into a package.
    """
    objects = collect_objects(workspace_root)
    if not objects:
        print("❌ No objects found. Aborting.")
        sys.exit(1)

    manifest = generate_manifest(objects)
    manifest_path = os.path.join(workspace_root, "exportMetadata.v2.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Create zip file containing the manifest and the Explore folder
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add manifest at root
        zipf.write(manifest_path, arcname="exportMetadata.v2.json")
        # Add all files under Explore
        explore_path = os.path.join(workspace_root, 'Explore')
        for root, dirs, files in os.walk(explore_path):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, workspace_root)
                zipf.write(full_path, arcname)

    os.remove(manifest_path)  # clean up
    print(f"✅ Package created: {output_zip}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        output_zip = sys.argv[1]
    else:
        output_zip = "release.zip"
    create_package(".", output_zip)