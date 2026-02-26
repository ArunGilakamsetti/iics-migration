import json
import os
import sys

def apply_mappings(config_path, workspace_dir):
    # 1. Load the structured config
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    conn_map = {item['sourceConnectionName']: item['targetConnectionName'] 
                for item in config.get('connectionOverrides', [])}
    new_agent = config.get('runtimeEnvironmentOverride')

    print(f"🔄 Applying mappings: {len(conn_map)} connections and 1 agent override.")

    modified_count = 0

    # 2. Walk through the workspace
    for root, _, files in os.walk(workspace_dir):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except Exception as e:
                        continue # Skip non-JSON or corrupt files

                # Convert to string for bulk connection replacement
                content = json.dumps(data)
                original_content = content

                # 3. Replace Connections
                for dev_conn, uat_conn in conn_map.items():
                    content = content.replace(f'"{dev_conn}"', f'"{uat_conn}"')

                # 4. Replace Runtime Environment (Agent)
                # We reload as dict to target the specific key safely
                updated_data = json.loads(content)
                
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
                    replace_agent(updated_data)

                # 5. Save if modified
                final_content = json.dumps(updated_data, indent=4)
                if final_content != json.dumps(data, indent=4):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(final_content)
                    modified_count += 1

    print(f"✨ Successfully updated {modified_count} files.")

if __name__ == "__main__":
    apply_mappings(sys.argv[1], sys.argv[2])