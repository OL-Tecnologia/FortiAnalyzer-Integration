# Documentação — FortiAnalyzer → PDF

Índice da pasta `doc/` do projeto **fortiAnalyzer** (OL Tecnologia).

| Documento | Conteúdo |
|-----------|----------|
| [referencias-projeto.md](referencias-projeto.md) | Arquivos, pastas, APIs e materiais usados no projeto |
| [features/README.md](features/README.md) | Catálogo de features **V1** (implementadas) |
| [features/login-faz-sessao.md](features/login-faz-sessao.md) | Login FAZ via tela (planejado) |
| [features/frontend-mensal-cruz-azul.md](features/frontend-mensal-cruz-azul.md) | Frontend web V1 — CRUZ_AZUL |
| [features/v2-multi-cliente-api-frontend.md](features/v2-multi-cliente-api-frontend.md) | Feature planejada **V2** — multi-cliente + frontend |

## Versões

- **V1 (atual):** CLI, ADOM único via `.env`, PDF MENSAL unificado Cruz Azul, cache validado por TID, pipelines WAN/regional legados.
- **V2 (planejada):** API HTTP, vários clientes/ADOMs, configuração por tenant, frontend; ver documento dedicado.

## Leitura rápida

- Operar o sistema hoje → [README.md](../README.md) na raiz + [features/README.md](features/README.md).
- Fechamento mensal / cache → [features/cache-e-fechamento-mensal.md](features/cache-e-fechamento-mensal.md).
- Evolução multi-cliente → [features/v2-multi-cliente-api-frontend.md](features/v2-multi-cliente-api-frontend.md).
