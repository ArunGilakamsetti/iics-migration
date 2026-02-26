import json
import os
import sys
import zipfile
import shutil
import tempfile

def process_content(content, conn_map, agent_map):
    """
    Applies overrides to text content. 
    Handles both simple string replacement and deep JSON key replacement.
    """
    # 1. Replace Connections (String-based for safety in all fields)
    for dev_conn, tgt_conn in conn_map.items():
        if dev_conn in content:
            content = content.replace(dev_conn, tgt_conn)

    # 2. Replace Agents (Targeted JSON replacement for specific IICS keys)
    try:
        data = json.loads(content)
        def replace_agents(obj):
            if isinstance(obj, dict):
                for k, v in list(obj.items()):
                    # Target known IICS agent key variations
                    if k in ["runtimeEnvironmentName", "agentGroupName", "agentGroup"]:
                        if isinstance(v, str):
                            # Match against our agent mapping list
                            for mapping in agent_map:
                                if v == mapping['sourceAgentName']:
                                    obj[k] = mapping['targetAgentName']
                                    break
                    else:
                        replace_agents(v)
            elif isinstance(obj, list):
                for item in obj:
                    replace_agents(item)
        
        replace_agents(data)
        return json.dumps(data, indent=4)
    except:
        # If content isn't valid JSON, fallback to string replacement for agents
        for mapping in agent_map:
            content = content.replace(mapping['sourceAgentName'], mapping['targetAgentName'])
        return content

def apply_mappings(config_path, workspace_dir):
    if not os.path.exists(config_path):
        print(f"Error: Config not found at {config_path}"); sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Extract mappings from config
    conn_map = {item['sourceConnectionName']: item['targetConnectionName'] 
                for item in config.get('connectionOverrides', [])}
    agent_map = config.get('agentOverrides', [])

    modified_count = 0

    for root, _, files in os.walk(workspace_dir):
        for file in files:
            file_path = os.path.join(root, file)
            has_changed = False

            # CASE 1: JSON files (Visible assets + Hidden metadata .json)
            if file.endswith(".json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        old_c = f.read()
                    new_c = process_content(old_c, conn_map, agent_map)
                    if old_c != new_c:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_c)
                        has_changed = True
                except UnicodeDecodeError:
                    continue # Skip binary files mislabeled as JSON

            # CASE 2: Nested Zip Assets (MTTs, Connections, etc.)
            elif file.endswith(".zip"):
                temp_dir = tempfile.mkdtemp()
                try:
                    with zipfile.ZipFile(file_path, 'r') as z_ref:
                        z_ref.extractall(temp_dir)
                    
                    z_modified = False
                    for zroot, _, zfiles in os.walk(temp_dir):
                        for zfile in zfiles:
                            # Only process text-based files inside the zip
                            if zfile.endswith((".json", ".xml", ".txt")):
                                zpath = os.path.join(zroot, zfile)
                                try:
                                    with open(zpath, 'r', encoding='utf-8') as f:
                                        zold = f.read()
                                    znew = process_content(zold, conn_map, agent_map)
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
                print(f"  Updated: {file}")

    print(f"Successfully updated {modified_count} assets and metadata files.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 apply_mappings.py <config_path> <workspace_dir>")
        sys.exit(1)
    apply_mappings(sys.argv[1], sys.argv[2])