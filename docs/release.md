# Guia de Release

> **Pendente de revisão.** Este documento foi adaptado de outro projeto e ainda não reflete o fluxo definitivo deste projeto.

Este documento define o fluxo canônico de release para gerar uma nova versão da aplicação e publicar a imagem Docker correspondente.

Use este guia quando o objetivo for fechar uma release oficial. Se quiser apenas subir a aplicação já publicada, siga `docs/deploy.md`.

## Pré-condições obrigatórias

- a release nasce da branch `main`
- a working tree deve estar limpa antes do bump
- os testes devem passar antes de gerar a tag
- `pyproject.toml` deve ter o campo `version` coincidente com a tag que será criada

## Checklist canônico

Execute os comandos exatamente nesta ordem:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
git diff --quiet && git diff --cached --quiet
uv run pytest
# bump da versão em pyproject.toml
git add pyproject.toml
git commit -m "chore: bump version para vX.Y.Z"
git tag vX.Y.Z
git push origin main --follow-tags
gh release create vX.Y.Z --generate-notes
```

## O que cada passo prova

### 1. Sincronizar a linha oficial

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

Garante que a release parte da linha oficial e evita fechar versão sobre branch divergente.

### 2. Confirmar working tree limpa

```bash
git diff --quiet && git diff --cached --quiet
```

Se falhar, pare. Não feche release com mudanças locais pendentes.

### 3. Rodar o gate local obrigatório

```bash
uv run pytest
```

Preflight mínimo antes de gerar o commit e a tag de release.

### 4. Bump de versão

Edite `pyproject.toml` com a nova versão, commite e crie a tag:

```bash
git tag vX.Y.Z
git push origin main --follow-tags
```

### 5. Criar a release no GitHub

```bash
gh release create vX.Y.Z --generate-notes
```

O workflow de CI é disparado pelo evento `release: published`.

## Conferência de rastreabilidade

Depois da release, confirme:

1. `pyproject.toml` mostra a nova versão `X.Y.Z`.
2. Existe uma tag Git `vX.Y.Z` no repositório remoto.
3. O GitHub Actions executou o workflow de release.
4. A imagem Docker foi publicada com a tag `vX.Y.Z` e `latest`.

## Relação com outros guias

- Para subir a aplicação em produção: `docs/deploy.md`.
- Para operações de desenvolvimento local: `docs/dev.md`.
