# Security Rules

- Check dependencies for known vulnerabilities (`pip-audit`).  
- Ensure authentication/authorization is correctly implemented.  
- Never expose sensitive data in logs or errors.  
- Apply the principle of least privilege (DB, API keys, services).  
- Validate input/output strictly (schemas, Pydantic).  
