"""Check that what the DSL declares is what actually exists in `src/`.

Run through `bin/validate_generation`, right after `bin/generate_code`. It is a
consistency check over the generated tree, not a test suite: the behaviour of the
generated code is covered by `tests/test_generator.py`.

For every entity in `dsl/entities/`:
  - `models.py` holds the table class
  - `schemas.py` holds the `Read` DTO (unless the entity is a link model)
  - `router.py` holds the CRUD router, or must NOT exist for the domain when
    every entity of that domain declared `generate_router: false`
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).parent.parent
ENTITIES_DIR = ROOT_DIR / "dsl" / "entities"
SRC_DIR = ROOT_DIR / "src" / "caramello_api"
MIGRATIONS_DIR = SRC_DIR / "migrations" / "versions"


def check_file_content(file_path: Path, search_string: str) -> bool:
    """Report whether `search_string` occurs in `file_path`."""
    try:
        content = file_path.read_text()
    except FileNotFoundError:
        print(f"[FAIL] file not found: {file_path}")
        return False
    if search_string in content:
        print(f"[ OK ] found {search_string!r} in {file_path}")
        return True
    print(f"[FAIL] {search_string!r} NOT found in {file_path}")
    return False


def load_yaml(file_path: Path) -> Any:
    """Load a YAML file, returning None instead of raising on failure."""
    try:
        return yaml.safe_load(file_path.read_text())
    except FileNotFoundError:
        print(f"[FAIL] file not found: {file_path}")
        return None


def main() -> None:
    print("Starting validation flow...")

    if not ENTITIES_DIR.exists():
        print(f"[FAIL] DSL directory not found: {ENTITIES_DIR}")
        sys.exit(1)

    entity_files = sorted(ENTITIES_DIR.glob("*.yaml"))
    all_passed = True
    # Per domain: does at least one entity still want the CRUD router?
    router_expected: dict[str, bool] = {}

    print(f"Checking {len(entity_files)} entities from {ENTITIES_DIR}...")

    for entity_path in entity_files:
        entity_data = load_yaml(entity_path)
        if not entity_data:
            all_passed = False
            continue

        entity_name = entity_data["name"]
        domain = entity_data["domain"]
        is_link_model = bool(entity_data.get("is_link_model"))
        wants_router = not is_link_model and entity_data.get("generate_router", True)
        router_expected[domain] = router_expected.get(domain, False) or bool(wants_router)

        # The table class and the Read DTO live in two separate files per domain.
        if not check_file_content(SRC_DIR / domain / "models.py", f"class {entity_name}(Base):"):
            all_passed = False

        if not is_link_model:
            schemas_file = SRC_DIR / domain / "schemas.py"
            if not check_file_content(schemas_file, f"class {entity_name}Read(BaseModel):"):
                all_passed = False

        if wants_router:
            router_file = SRC_DIR / domain / "router.py"
            if not check_file_content(router_file, f'tags=["{entity_name}"]'):
                all_passed = False

    # A domain where every entity opted out must have no router module at all —
    # otherwise the tree is carrying dead code the generator no longer maintains.
    for domain, expected in sorted(router_expected.items()):
        router_file = SRC_DIR / domain / "router.py"
        if expected:
            continue
        if router_file.exists():
            print(f"[FAIL] {router_file} exists although every {domain} entity opts out")
            all_passed = False
        else:
            print(f"[ OK ] no router module for {domain} (every entity opts out)")

    if not all_passed:
        print("[FAIL] entity validation failed.")
        sys.exit(1)

    migrations = sorted(MIGRATIONS_DIR.glob("*.py"))
    if not migrations:
        print(f"[WARN] no migration found in {MIGRATIONS_DIR}")
    else:
        print(f"[ OK ] found {len(migrations)} migration(s)")

    print("Validation successful.")


if __name__ == "__main__":
    main()
