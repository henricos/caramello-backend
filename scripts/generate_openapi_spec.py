import yaml
import os
from pathlib import Path

# Define base paths
ROOT_DIR = Path(__file__).parent.parent
DSL_DIR = ROOT_DIR / "dsl"
ENTITIES_DIR = DSL_DIR / "entities"
OPENAPI_OUTPUT_DIR = ROOT_DIR / "openapi" / "v1"
OPENAPI_OUTPUT_FILE = OPENAPI_OUTPUT_DIR / "spec.yaml"

def load_yaml(file_path):
    """Loads a YAML file safely."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML in {file_path}: {e}")
        return None

def convert_dsl_type_to_openapi(dsl_type):
    """Maps DSL types to OpenAPI types."""
    type_map = {
        "uuid": {"type": "string", "format": "uuid"},
        "string": {"type": "string"},
        "text": {"type": "string"},
        "integer": {"type": "integer"},
        "float": {"type": "number", "format": "float"},
        "boolean": {"type": "boolean"},
        "datetime": {"type": "string", "format": "date-time"},
        # Add other mappings as needed
    }
    return type_map.get(dsl_type, {"type": "string"}) # Default to string if not mapped

def convert_dsl_to_openapi_schema(entity_data):
    """Converts a DSL entity definition to an OpenAPI schema."""
    schema_name = entity_data['name']
    properties = {}
    required_fields = []

    for field in entity_data.get('fields', []):
        field_name = field['name']
        field_type = field['type']
        
        openapi_type_info = convert_dsl_type_to_openapi(field_type)
        
        property_schema = {
            "type": openapi_type_info["type"],
            **({"format": openapi_type_info["format"]} if "format" in openapi_type_info else {}),
            "description": field.get('description', f"Field {field_name} of entity {schema_name}"),
        }

        if field.get('primary_key') or field.get('required'):
            required_fields.append(field_name)
        
        if field.get('default'):
            # For default values, OpenAPI uses 'default'
            # The exact logic may vary, here's a simple example
            if field['default'] == 'uuid4':
                property_schema['default'] = 'uuid.uuid4' # Example, may need adjustment for the generator
            elif field['default'] == 'now':
                property_schema['default'] = 'datetime.now' # Example
            else:
                property_schema['default'] = field['default']

        properties[field_name] = property_schema
    
    return {
        schema_name: {
            "type": "object",
            "properties": properties,
            "required": required_fields,
            "description": entity_data.get('description', f"Schema for entity {schema_name}"),
        }
    }

def main():
    """Main function to generate the OpenAPI specification."""
    print("Starting OpenAPI specification generation...")

    # 1. Load the main manifest
    manifest_path = DSL_DIR / "manifest.yaml"
    openapi_spec = load_yaml(manifest_path)
    if not openapi_spec:
        return

    print(f"Manifest '{manifest_path.name}' loaded successfully.")

    # Initialize important sections if they don't exist
    if 'paths' not in openapi_spec:
        openapi_spec['paths'] = {}
    if 'components' not in openapi_spec:
        openapi_spec['components'] = {}
    if 'schemas' not in openapi_spec['components']:
        openapi_spec['components']['schemas'] = {}

    # 2. Iterate over entities defined in the manifest
    entity_files = openapi_spec.get('x-caramello-entities', [])
    if not entity_files:
        print("Warning: No entities found in 'x-caramello-entities' in the manifest.")
    
    for entity_file in entity_files:
        entity_path = ENTITIES_DIR / entity_file
        print(f"Processing entity: {entity_path}...")
        
        entity_data = load_yaml(entity_path)
        if not entity_data:
            continue # Skip to the next entity if there's an error

        entity_name = entity_data.get('name', 'UnknownName')
        print(f"-> Entity '{entity_name}' loaded.")

        # Convert DSL entity to OpenAPI schema and add to the specification
        openapi_schema = convert_dsl_to_openapi_schema(entity_data)
        openapi_spec['components']['schemas'].update(openapi_schema)


    # 3. Ensure the output directory exists
    OPENAPI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 4. Write the final specification to the output file
    try:
        with open(OPENAPI_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(openapi_spec, f, sort_keys=False, allow_unicode=True)
        print(f"\nOpenAPI specification generated successfully at: {OPENAPI_OUTPUT_FILE}")
    except IOError as e:
        print(f"Error writing output file: {e}")
    
if __name__ == "__main__":
    main()