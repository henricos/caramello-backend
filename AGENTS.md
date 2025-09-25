# AI Workflow Guidelines

This project follows an **API First** strategy, adopting the **OpenAPI Specification** as the **single source of truth**.  
All modeling, database, and API decisions must always comply with OpenAPI.  

## Core Workflow

1. Create or update entities in YAML inside the `dsl/` folder.  
2. Generate an updated **OpenAPI** specification from DSL.  
3. From this point, the **OpenAPI becomes the only source of truth**.  
4. Generate/update the following based on OpenAPI:  
   - **SQLModel Models** → `src/caramello/models/`  
   - **Pydantic Schemas** → `src/caramello/schemas/`  
   - **FastAPI Routers** → `src/caramello/api/`  
   - **Alembic Migrations** → `alembic/`  
5. Run and maintain tests in `tests/` ensuring consistency with the contract.  

## DSL (YAML)
- The DSL is an **auxiliary shortcut** to describe business entities (name, fields, types, relations).  
- The DSL is simple, focused only on **CRUD entities**.  
- The DSL’s role is to **generate an OpenAPI file**.  
- The DSL is **never the source of truth**. After generation, **only the OpenAPI must be used**.  

## OpenAPI
- The **OpenAPI Specification** is the **only source of truth** for the project.  
- It must include:  
  - **CRUD endpoints** (derived from DSL).  
  - **Additional endpoints** (business, authentication, workflows, etc.) defined directly in OpenAPI.  
- OpenAPI must be **version controlled** and kept updated in the repository.  
- All other artifacts must be generated or validated against it.  

## Reference Documentation
Additional rules and guidelines are available under the [`docs/`](./docs) folder:  
- [Style Guide](./docs/style_guide.md)  
- [Project Structure](./docs/project_structure.md)  
- [Commit Rules](./docs/commit_rules.md)  
- [Pull Request Rules](./docs/pr_rules.md)  
- [Security Rules](./docs/security_rules.md)  
- [Quality Rules](./docs/quality_rules.md)  

> **Important:**  
> - The DSL is only auxiliary.  
> - OpenAPI is the **only official reference**.  
> - All code must reflect the contract defined in OpenAPI.  
