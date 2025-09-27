# Regras de Segurança

- Verifique as dependências em busca de vulnerabilidades conhecidas (`pip-audit`).
- Garanta que a autenticação/autorização seja implementada corretamente.
- Nunca exponha dados sensíveis em logs ou erros.
- Aplique o princípio do menor privilégio (banco de dados, chaves de API, serviços).
- Valide estritamente a entrada/saída de dados (schemas, Pydantic).
