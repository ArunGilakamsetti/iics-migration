import json
import os
import sys
import zipfile
import shutil
import tempfile

def process_content(content, conn_map, new_agent):
    # Aggressive string swap for connections
    for dev_conn, tgt_conn in conn_map.items():
        content = content.replace(dev_conn, tgt_conn)

    # Targeted swap for agents
    try:
        data = json.loads(content)
        def replace_keys(obj):
            if isinstance(obj, dict):
                for k, v in list(obj.items()):
                    if k in ["runtimeEnvironmentName", "agentGroupName", "agentGroup"]:
                        if isinstance(v, str): obj[k] = new_agent
                    else: replace_keys(v)
            elif isinstance(obj, list):
                for item in obj: replace_keys(item)
        if new_agent: replace_keys(data)
        return json.dumps(data, indent=4)
    except:
        return content

def apply_mappings(config_path, workspace_dir):
    with open(config_path, 'r') as f:
        config = json.load(f)

    conn_map = {item['sourceConnectionName']: item['targetConnectionName'] 
                for item in config.get('connectionOverrides', [])}
    new_agent = config.get('runtimeEnvironmentOverride')

    modified_count = 0

    for root, _, files in os.walk(workspace_dir):
        # Skip hidden sidecars
        files = [f for f in files if not f.startswith('.')]
        
        for file in files:
            file_path = os.path.join(root, file)
            has_changed = False

            # CASE 1: JSON Files (Including the Manifest)
            if file.endswith(".json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        old_c = f.read()
                    new_c = process_content(old_c, conn_map, new_agent)
                    if old_c != new_c:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_c)
                        has_changed = True
                except UnicodeDecodeError:
                    continue # Skip binary files mislabeled as json

            # CASE 2: Nested Zip Assets
            elif file.endswith(".zip"):
                temp_dir = tempfile.mkdtemp()
                try:
                    with zipfile.ZipFile(file_path, 'r') as z_ref:
                        z_ref.extractall(temp_dir)
                    
                    z_modified = False
                    for zroot, _, zfiles in os.walk(temp_dir):
                        for zfile in zfiles:
                            # ONLY process text/json files inside the zip
                            if zfile.endswith(".json") or zfile.endswith(".xml") or zfile.endswith(".txt"):
                                zpath = os.path.join(zroot, zfile)
                                try:
                                    with open(zpath, 'r', encoding='utf-8') as f:
                                        zold = f.read()
                                    znew = process_content(zold, conn_map, new_agent)
                                    if zold != znew:
                                        with open(zpath, 'w', encoding='utf-8') as f:
                                            f.write(znew)
                                        z_modified = True
                                except UnicodeDecodeError:
                                    continue
                    
                    if z_modified:
                        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as z_out:
                            for zroot, _, zfiles in os.walk(temp_dir):
                                for zfile in zfiles:
                                    fp = os.path.join(zroot, zfile)
                                    z_out.write(fp, os.path.relpath(fp, temp_dir))
                        has_changed = True
                finally:
                    shutil.rmtree(temp_dir)

            if has_changed:
                modified_count += 1
                print(f"  ✅ Updated: {file}")

    print(f"✨ Successfully updated {modified_count} assets.")

if __name__ == "__main__":
    apply_mappings(sys.argv[1], sys.argv[2])