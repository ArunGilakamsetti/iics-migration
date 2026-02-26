import json
import os
import sys
import zipfile
import shutil
import tempfile

def process_content(content, conn_map, new_agent):
    # 1. Aggressive String Replacement for Connections
    # This handles connection names regardless of where they are in the JSON
    for dev_conn, uat_conn in conn_map.items():
        if dev_conn in content:
            content = content.replace(dev_conn, uat_conn)

    # 2. Precise replacement for Agent/Runtime Environment
    try:
        data = json.loads(content)
        def replace_agent_keys(obj):
            if isinstance(obj, dict):
                for k, v in list(obj.items()):
                    # Target all known IICS agent key variations
                    if k in ["runtimeEnvironmentName", "agentGroupName", "agentGroup"]:
                        if isinstance(v, str) and v != new_agent:
                            obj[k] = new_agent
                    else:
                        replace_agent_keys(v)
            elif isinstance(obj, list):
                for item in obj:
                    replace_agent_keys(item)
        
        if new_agent:
            replace_agent_keys(data)
        return json.dumps(data, indent=4)
    except:
        return content 

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
        # Skip the hidden metadata files (starting with dot) to avoid checksum conflicts
        files = [f for f in files if not f.startswith('.')]
        
        for file in files:
            file_path = os.path.join(root, file)
            
            # Process JSON and ZIP (Nested MTTs)
            if file.endswith(".json") or file.endswith(".zip"):
                is_zip = file.endswith(".zip")
                has_changed = False
                
                if not is_zip:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        old_c = f.read()
                    new_c = process_content(old_c, conn_map, new_agent)
                    if old_c != new_c:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_c)
                        has_changed = True
                else:
                    # Handle nested Zip assets
                    temp_dir = tempfile.mkdtemp()
                    with zipfile.ZipFile(file_path, 'r') as z_ref:
                        z_ref.extractall(temp_dir)
                    
                    for zroot, _, zfiles in os.walk(temp_dir):
                        for zfile in zfiles:
                            zpath = os.path.join(zroot, zfile)
                            with open(zpath, 'r', encoding='utf-8') as f:
                                zold = f.read()
                            znew = process_content(zold, conn_map, new_agent)
                            if zold != znew:
                                with open(zpath, 'w', encoding='utf-8') as f:
                                    f.write(znew)
                                has_changed = True
                    
                    if has_changed:
                        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as z_out:
                            for zroot, _, zfiles in os.walk(temp_dir):
                                for zfile in zfiles:
                                    fp = os.path.join(zroot, zfile)
                                    z_out.write(fp, os.path.relpath(fp, temp_dir))
                    shutil.rmtree(temp_dir)

                if has_changed:
                    modified_count += 1
                    print(f"  ✅ Modified: {file}")

    print(f"✨ Successfully updated {modified_count} assets.")

if __name__ == "__main__":
    apply_mappings(sys.argv[1], sys.argv[2])