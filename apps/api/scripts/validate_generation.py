import os
import sys
from pathlib import Path
import subprocess
import yaml

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ Command passed: {command}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {command}")
        print(e.stderr)
        return False

def check_file_content(file_path, search_string):
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            if search_string in content:
                print(f"✅ Found '{search_string}' in {file_path}")
                return True
            else:
                print(f"❌ '{search_string}' NOT found in {file_path}")
                return False
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False

def load_yaml(file_path):
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None

def main():
    print("🚀 Starting Validation Flow...")
    
    # 1. Check Generated Files based on DSL Directory
    dsl_dir = Path("dsl/entities")
    if not dsl_dir.exists():
        print(f"❌ DSL directory not found: {dsl_dir}")
        sys.exit(1)

    entity_files = list(dsl_dir.glob("*.yaml"))
    all_passed = True
    
    print(f"🔍 Checking {len(entity_files)} entities from {dsl_dir}...")
    
    for entity_path in entity_files:
        entity_data = load_yaml(entity_path)
        if not entity_data:
            all_passed = False
            continue
            
        entity_name = entity_data['name']
        table_name = entity_data.get('table_name', entity_name.lower())
        
        # Check Model File
        model_file = Path(f"src/caramello_api/models/{entity_name.lower()}.py")
        if not check_file_content(model_file, f'class {entity_name}Read(SQLModel):'):
             print(f"❌ Missing Read DTO in {model_file}")
             all_passed = False
             
        # Check Test File (if not link model)
        if not entity_data.get('is_link_model'):
            test_file = Path(f"tests/generated/test_{entity_name.lower()}.py")
            if not test_file.exists():
                print(f"❌ Missing generated test file: {test_file}")
                all_passed = False

    if not all_passed:
        print("❌ Entity validation failed.")
        sys.exit(1)

    # 2. Check Migrations exist
    versions_dir = Path("alembic/versions")
    migrations = list(versions_dir.glob("*.py"))
    if not migrations:
        print("⚠️ No migrations found in alembic/versions (Did you run 'alembic revision --autogenerate'?)")
        # Warn but maybe not fail if we just cleaned it
    else:
        print(f"✅ Found {len(migrations)} migration(s)")

    # 3. Run Tests
    print("Running generated tests...")
    if not run_command("uv run pytest tests/generated"):
        sys.exit(1)

    print("🎉 Validation Successful!")

if __name__ == "__main__":
    main()
