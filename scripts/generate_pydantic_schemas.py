import subprocess
from pathlib import Path

# Define base paths
ROOT_DIR = Path(__file__).parent.parent
OPENAPI_OUTPUT_FILE = ROOT_DIR / "openapi" / "v1" / "spec.yaml"
SCHEMAS_OUTPUT_DIR = ROOT_DIR / "src" / "caramello" / "schemas" / "generated"

def generate_pydantic_schemas():
    """Generates Pydantic schemas from the OpenAPI specification."""
    print(f"\nGenerating Pydantic schemas in: {SCHEMAS_OUTPUT_DIR}...")
    SCHEMAS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        "uv", "run", "datamodel-codegen",
        "--input", str(OPENAPI_OUTPUT_FILE),
        "--output", str(SCHEMAS_OUTPUT_DIR / "api_schemas.py"),
        "--input-file-type", "openapi",
        "--output-model-type", "pydantic_v2.BaseModel",
        "--disable-timestamp",
        "--enum-field-as-literal", "all",
    ]
    
    try:
        subprocess.run(command, check=True, cwd=ROOT_DIR)
        print("Pydantic schemas generated successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error generating Pydantic schemas: {e}")
    except FileNotFoundError:
        print("Error: 'datamodel-codegen' not found. Ensure it is installed.")

if __name__ == "__main__":
    generate_pydantic_schemas()