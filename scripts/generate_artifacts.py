#!/usr/bin/env python3
"""
Scans the Explore folder and generates an artifacts file for IICS export.
Includes all common leaf asset types, excluding projects and folders.
Add or remove extensions as needed.
"""

import os
import sys
import argparse

# ----------------------------------------------------------------------
# Mapping from file extensions to IICS asset types
# Extend this list based on the asset types in your IICS environment.
# ----------------------------------------------------------------------
EXTENSION_TO_TYPE = {
    # Mapping Tasks
    '.MTT.zip': 'MTT',
    # Taskflows
    '.TASKFLOW.xml': 'TASKFLOW',
    # Mapping Templates
    '.DTEMPLATE.zip': 'DTEMPLATE',
    # Individual Mappings (if exported separately)
    '.MAPPING.zip': 'MAPPING',
    # Connections
    '.Connection.json': 'Connection',
    # Agent Groups (usually not exported, but included for completeness)
    '.AgentGroup.json': 'AgentGroup',
    # Profiles
    '.PROFILE.json': 'PROFILE',
    # Schedules
    '.SCHEDULE.json': 'SCHEDULE',
    # Parameter Sets
    '.PARAMSET.json': 'PARAMSET',
    # Decisions
    '.DECISION.json': 'DECISION',
    # Add any other leaf asset types you need
}

def main():
    parser = argparse.ArgumentParser(description='Generate artifacts.txt from Explore folder (leaf assets only).')
    parser.add_argument('--explore-path', default='Explore', help='Path to Explore folder (default: Explore)')
    parser.add_argument('--output', default='artifacts.txt', help='Output file name (default: artifacts.txt)')
    parser.add_argument('--include-folders', action='store_true', help='Include folder assets (not recommended)')
    parser.add_argument('--include-projects', action='store_true', help='Include project assets (not recommended)')
    args = parser.parse_args()

    if not os.path.isdir(args.explore_path):
        print(f"❌ Explore folder not found: {args.explore_path}")
        sys.exit(1)

    artifacts = []

    for root, dirs, files in os.walk(args.explore_path):
        for file in files:
            file_path = os.path.join(root, file)
            matched = False
            # Check for leaf assets first
            for ext, asset_type in EXTENSION_TO_TYPE.items():
                if file.endswith(ext):
                    # Build the asset path relative to the workspace root
                    rel_path = os.path.relpath(file_path, start=args.explore_path)
                    # Remove the extension to match CLI format
                    base_path = rel_path.replace(ext, '')
                    # Replace backslashes with forward slashes
                    base_path = base_path.replace('\\', '/')
                    # Prepend 'Explore/' and append .<type>
                    asset_line = f"Explore/{base_path}.{asset_type}"
                    artifacts.append(asset_line)
                    print(f"  Found leaf asset: {asset_line}")
                    matched = True
                    break

            if not matched:
                # Optionally include folders/projects if flags are set
                if args.include_folders and file.endswith('.Folder.json'):
                    rel_path = os.path.relpath(file_path, start=args.explore_path)
                    base_path = rel_path.replace('.Folder.json', '')
                    base_path = base_path.replace('\\', '/')
                    asset_line = f"Explore/{base_path}.Folder"
                    artifacts.append(asset_line)
                    print(f"  Including folder asset: {asset_line}")
                elif args.include_projects and file.endswith('.Project.json'):
                    rel_path = os.path.relpath(file_path, start=args.explore_path)
                    base_path = rel_path.replace('.Project.json', '')
                    base_path = base_path.replace('\\', '/')
                    asset_line = f"Explore/{base_path}.Project"
                    artifacts.append(asset_line)
                    print(f"  Including project asset: {asset_line}")
                else:
                    print(f"  Skipping (unrecognized or excluded): {file}")

    if not artifacts:
        print("❌ No leaf assets found. Aborting.")
        sys.exit(1)

    with open(args.output, 'w') as f:
        for line in artifacts:
            f.write(line + '\n')

    print(f"✅ Generated {args.output} with {len(artifacts)} leaf assets.")

if __name__ == "__main__":
    main()