# Skill Conventions

This project follows the Agent Skills open standard (https://agentskills.io) and prioritizes compatibility with multiple coding agents. Skills must avoid features specific to a single agent — what only works in one agent does not belong here. This file defines the conventions to follow. Whenever you create or edit a skill in this project, check that it respects these conventions before finalizing.

## Frontmatter

Use only the fields required by the open standard:

```yaml
---
name: skill-name
description: What it does and when to use it.
---
```

No additional fields. Fields such as `allowed-tools`, `disable-model-invocation`, `argument-hint` and `arguments` are agent-specific extensions and compromise multi-agent compatibility.

## Arguments

Use `$ARGUMENTS` in the skill body to capture what the user typed after the name. Describe the expected parameters in natural language within the body itself — no `argument-hint`, no `arguments` field, no named variables.

## Declarative skills

The skill body instructs the agent in natural language. Long Bash blocks, complex conditional logic and command sequences do not belong in `SKILL.md` — they belong in helpers under `scripts/`. The body should orchestrate, not implement.

## File organization

Each skill is a directory. The open standard defines the conventional subfolders:

```
my-skill/
├── SKILL.md          # required
├── scripts/          # executable helpers
├── assets/           # templates, static files, schemas
└── references/       # reference documentation read on demand
```

Templates (files the skill fills in or uses as a model) go in `assets/`.

## Self-containment

Helpers and assets that are **exclusive to one skill** must live inside the skill's own tree (`scripts/`, `assets/`, `references/`). An exclusive helper outside its tree signals an organization problem: either it should be moved inside, or the skill is overstepping its responsibilities and the helper should not exist.

Scripts **shared across multiple skills** belong to no individual skill and must not live inside any of them. Place them where the project already concentrates shared scripts; if no convention is established, check the existing structure before creating a new folder.

References to project files outside `scripts/` are acceptable when they are part of the skill's business rule — for example, reading `storyboard.md`, `manifest.json`, or project configuration files.

What must not happen:
- A helper exclusive to one skill residing outside its tree (it should be inside)
- A skill referencing another skill's internal files (inter-skill dependency)

## Helpers

### Language

Prefer Node.js. It is the language with the broadest presence in the sandboxes of the main coding agents. Python is the second option — when there are no external dependencies, the stdlib is enough and works in any environment.

### Single-command execution

Helpers must be runnable with a single command, without a separate setup, install and run sequence. For Node.js, implement dependency installation automatically inside the script itself, detecting whether `node_modules` already exists before installing.

For Python with external dependencies, use the PEP 723 inline script metadata pattern — dependencies are declared in the file's own header and installed automatically by `uv run`:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx", "rich"]
# ///

import httpx
# ...
```

Execution: `uv run script.py` — installs and runs in a single command, without polluting the global environment.

### Avoid committing dependencies

Add a `.gitignore` inside `scripts/` so that whatever gets downloaded at runtime is not versioned:

```
# scripts/.gitignore
node_modules/
__pycache__/
*.pyc
.venv/
.installed
```
