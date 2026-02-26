import json
import os
import sys
import zipfile
import shutil
import tempfile

def process_content(content, conn_map, new_agent):
    # 1. Aggressive String Replacement for Connections
    original_content = content
    for dev_conn, uat_conn in conn_map.items():
        content = content.replace(dev_conn, uat_conn)

    # 2. Precise JSON replacement for Agent
    try:
        data = json.loads(content)
        def replace_agent(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "runtimeEnvironmentName":
                        obj[k] = new_agent
                    else:
                        replace_agent(v)
            elif isinstance(obj, list):
                for item in obj:
                    replace_agent(item)
        
        if new_agent:
            replace_agent(data)
        return json.dumps(data, indent=4)
    except:
        return content # Return string-replaced version if not valid JSON

def apply_mappings(config_path, workspace_dir):
    if not os.path.exists(config_path):
        print(f"❌ Config not found: {config_path}"); sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    conn_map = {item['sourceConnectionName']: item['targetConnectionName'] 
                for item in config.get('connectionOverrides', [])}
    new_agent = config.get('runtimeEnvironmentOverride')

    modified_count = 0

    for root, _, files in os.walk(workspace_dir):
        for file in files:
            file_path = os.path.join(root, file)
            
            # CASE 1: Standard JSON files
            if file.endswith(".json"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
                new_content = process_content(old_content, conn_map, new_agent)
                if old_content != new_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    modified_count += 1

            # CASE 2: Nested IICS Zip Assets (The missing link!)
            elif file.endswith(".zip"):
                has_changed = False
                temp_dir = tempfile.mkdtemp()
                
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                for zroot, _, zfiles in os.walk(temp_dir):
                    for zfile in zfiles:
                        if zfile.endswith(".json"):
                            zpath = os.path.join(zroot, zfile)
                            with open(zpath, 'r', encoding='utf-8') as f:
                                zold = f.read()
                            znew = process_content(zold, conn_map, new_agent)
                            if zold != znew:
                                with open(zpath, 'w', encoding='utf-8') as f:
                                    f.write(znew)
                                has_changed = True
                
                if has_changed:
                    # Re-zip the modified contents
                    with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                        for zroot, _, zfiles in os.walk(temp_dir):
                            for zfile in zfiles:
                                full_p = os.path.join(zroot, zfile)
                                rel_p = os.path.relpath(full_p, temp_dir)
                                zip_out.write(full_p, rel_p)
                    modified_count += 1
                
                shutil.rmtree(temp_dir)

    print(f"✨ Successfully updated {modified_count} assets (including nested zips).")

if __name__ == "__main__":
    apply_mappings(sys.argv[1], sys.argv[2])