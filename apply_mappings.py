import json, os, sys, re

def apply_mappings(mapping_file, workspace_dir):
    if not os.path.exists(mapping_file):
        print(f"Error: Mapping file {mapping_file} not found.")
        sys.exit(1)

    with open(mapping_file, 'r') as f:
        config = json.load(f)
    
    conn_map = config.get("connectionOverrides", [])
    agent_map = config.get("runtimeEnvironmentOverride")

    print(f"Applying mappings to workspace: {workspace_dir}")

    for root, _, files in os.walk(workspace_dir):
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Replace Connections using your specific keys
                for m in conn_map:
                    src = m.get("sourceConnectionName")
                    tgt = m.get("targetConnectionName")
                    if src and tgt:
                        content = content.replace(f'"{src}"', f'"{tgt}"')
                
                # Replace Agent/Runtime Group
                if agent_map:
                    content = re.sub(r'"agentName":\s*".*?"', f'"agentName": "{agent_map}"', content)

                if content != original_content:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"  Modified: {file}")

if __name__ == "__main__":
    # Usage: python3 apply_mappings.py <config_path> <workspace_path>
    apply_mappings(sys.argv[1], sys.argv[2])