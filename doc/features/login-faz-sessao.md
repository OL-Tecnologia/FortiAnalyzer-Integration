# Feature — Login FortiAnalyzer (tela + sessão)

**Status:** ✅ Implementado (portal web V1.1)  
**Cliente inicial:** CRUZ_AZUL  
**Relacionado:** [frontend-mensal-cruz-azul.md](frontend-mensal-cruz-azul.md), [v2-multi-cliente-api-frontend.md](v2-multi-cliente-api-frontend.md)

---

## 1. Problema

Hoje as credenciais FAZ (`FAZ_USER`, `FAZ_PASSWORD`) ficam no `.env` e o `FortiAnalyzerClient.login()` lê strings fixas do servidor. Isso é adequado para CLI/automação interna, mas **não** para um portal onde **cada operador informa suas próprias credenciais** e o sistema libera o acesso ao ADOM apenas após autenticação válida no FortiAnalyzer.

**Requisito de negócio:** o usuário do sistema digita login/senha FAZ na tela; o backend chama um **módulo encapsulado** de autenticação; só então é permitido gerar o relatório MENSAL no ADOM configurado (`CRUZ_AZUL`).

---

## 2. Objetivos

| # | Objetivo |
|---|----------|
| 1 | Tela de login antes da geração de PDF |
| 2 | Credenciais **nunca** gravadas no `.env` nem persistidas em disco pelo fluxo web |
| 3 | Um único ponto de código responsável pelo login FAZ (`faz_auth` / credential provider) |
| 4 | Sessão com TTL; logout explícito |
| 5 | Endpoints de relatório **protegidos** — sem sessão válida, retorno 401 |
| 6 | ADOM fixo no servidor (`FAZ_ADOM`); usuário não escolhe outro ADOM na UI |

---

## 3. O que **não** fazer

| Prática | Motivo |
|---------|--------|
| Editar `.env` pela tela de login | Senha em arquivo, risco de corrupção e vazamento |
| Guardar senha em `localStorage` / `sessionStorage` | Exposta no navegador |
| Repassar senha em query string ou logs | Vazamento em histórico/proxy |
| Usuário escolher ADOM livremente | Acesso indevido a outros clientes |
| Espalhar `user`/`passwd` fora do módulo de auth | Dificulta auditoria e manutenção |

---

## 4. Arquitetura proposta

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend                                                    │
│  ┌──────────────┐      ┌─────────────────────────────────┐  │
│  │ Tela login   │ ───► │ Tela gerar PDF (já existente V1) │  │
│  │ user + senha │      │ só habilitada se autenticado    │  │
│  └──────────────┘      └─────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────┘
                                │ HTTPS
                                ▼
┌─────────────────────────────────────────────────────────────┐
│  API FastAPI                                                 │
│  POST /api/auth/faz/login  ──►  faz_auth.authenticate()     │
│  POST /api/auth/logout     ──►  invalida sessão               │
│  GET  /api/auth/me         ──►  status da sessão            │
│                                                              │
│  POST /api/reports/mensal/generate  ──► exige sessão FAZ    │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│  forti_report/faz/auth.py  (módulo encapsulado)              │
│  • resolve credenciais da sessão do usuário                  │
│  • chama FortiAnalyzerClient.login()                         │
│  • opcional: logout FAZ ao encerrar sessão portal            │
└───────────────────────────────┬─────────────────────────────┘
                                │ JSON-RPC
                                ▼
                    FortiAnalyzer (ADOM CRUZ_AZUL)
```

### Fluxo resumido

1. Usuário abre o portal → redireciona para login se não houver sessão.
2. `POST /api/auth/faz/login` com `{ "user", "password" }`.
3. Backend chama `authenticate(user, password)` → login FAZ → obtém `session` JSON-RPC.
4. Servidor armazena **session id FAZ** (e metadados) em store de sessão com **TTL** (ex.: 60 min).
5. Resposta define **cookie httpOnly** `session_id` (ou token opaco equivalente).
6. “Gerar relatório” envia cookie; pipeline usa `Settings` + credenciais/sessão da store — **sem** reler `.env` para senha.
7. Logout ou TTL expirado → 401; usuário faz login de novo.

---

## 5. Módulo encapsulado (contrato)

Arquivo sugerido: `src/forti_report/faz/auth.py`

```python
# Contrato ilustrativo — não implementado

def authenticate_faz(user: str, password: str, settings: Settings) -> FazSession:
    """Valida credenciais no FAZ; levanta FortiAnalyzerError se falhar."""

def get_credentials_for_session(session_id: str) -> FazCredentials | None:
    """Retorna user/password ou session FAZ ativa; None se expirada."""

def invalidate_session(session_id: str) -> None:
    """Logout portal + logout FAZ quando aplicável."""
```

**Regra:** todo acesso ao FAZ a partir da API web passa por este módulo. `FortiAnalyzerClient` pode aceitar `session` já obtida ou `Settings.model_copy(update={faz_user, faz_password})` resolvido via `get_credentials_for_session`.

---

## 6. Configuração (`.env` após a feature)

| Variável | Papel |
|----------|--------|
| `FAZ_HOST`, `FAZ_PORT`, `FAZ_USE_SSL`, `FAZ_VERIFY_SSL` | Infraestrutura FAZ |
| `FAZ_ADOM` | ADOM fixo (`CRUZ_AZUL`) |
| `FAZ_REPORT_SCHEDULE` | Schedule MENSAL |
| `FAZ_SESSION_TTL_MINUTES` | TTL da sessão portal (novo, sugerido: 60) |
| `FAZ_USER`, `FAZ_PASSWORD` | **Opcional** — só fallback CLI/dev; **vazio em produção web** |

---

## 7. API planejada

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/api/auth/faz/login` | — | Body: `{ user, password }` → cookie sessão |
| POST | `/api/auth/logout` | cookie | Encerra sessão |
| GET | `/api/auth/me` | cookie | `{ authenticated, adom, user, expires_at }` |
| POST | `/api/reports/mensal/generate` | cookie | **Alteração:** 401 sem sessão |
| GET | `/api/reports/mensal/jobs/{id}/stream` | cookie | SSE progresso |
| GET | `/api/reports/mensal/jobs/{id}/download` | cookie | PDF |

Respostas de erro de login: mensagem genérica (“Credenciais inválidas”) — sem detalhar se foi user ou senha.

---

## 8. Frontend planejado

| Tela / elemento | Comportamento |
|-----------------|---------------|
| `/login.html` ou rota `/login` | Formulário user + senha FAZ |
| Redirect | Sem cookie → login; com cookie → dashboard/gerar |
| Botão “Gerar relatório” | Desabilitado até `GET /api/auth/me` OK |
| Logout | Limpa cookie; volta ao login |
| Senha | Campo `type=password`; não persistir no browser |

Integração com [frontend-mensal-cruz-azul.md](frontend-mensal-cruz-azul.md): mesma identidade visual; login como **porta de entrada**.

---

## 9. Segurança (checklist)

- [ ] HTTPS obrigatório em produção  
- [ ] Cookie `HttpOnly`, `Secure`, `SameSite=Lax` (ou `Strict`)  
- [ ] TTL de sessão + renovação opcional  
- [ ] Rate limit em `/api/auth/faz/login` (anti brute-force)  
- [ ] Não logar `password` nem corpo completo do login  
- [ ] ADOM fixo no backend  
- [ ] Jobs usam sessão do usuário que iniciou (não sessão global compartilhada entre usuários)  
- [ ] Logout invalida sessão no store  

---

## 10. Impacto no código existente

| Componente | Mudança |
|------------|---------|
| `forti_report/faz/client.py` | Opcional: aceitar session pré-existente ou credenciais injetadas |
| `forti_report/faz/auth.py` | **Novo** — login encapsulado |
| `forti_report/api/app.py` | Rotas auth + dependency `require_faz_session` |
| `forti_report/services/mensal_job.py` | Receber `session_id` / `Settings` da sessão |
| `forti_report/services/mensal_pipeline.py` | Propagar `Settings` com credenciais da sessão |
| `frontend/` | Tela login + guard nas chamadas API (`credentials: 'include'`) |
| `forti_report/cli.py` | **Sem mudança** — continua usando `.env` para ops |

---

## 11. Critérios de aceite

- [ ] Usuário gera PDF **sem** `FAZ_PASSWORD` no `.env` (credenciais só na tela).  
- [ ] Tentativa de gerar sem login retorna **401**.  
- [ ] Após logout ou TTL, gerar exige login novamente.  
- [ ] Senha não aparece em arquivos, logs nem resposta JSON.  
- [ ] CLI `generate-mensal-unified` segue funcionando com `.env` (modo dev/ops).  
- [ ] Documentação operacional atualizada.  

---

## 12. Fora de escopo (nesta feature)

- Login SSO / LDAP da OL (portal corporativo) — pode ser camada futura **acima** do login FAZ.  
- Multi-ADOM selecionável — V2.  
- Armazenamento persistente de sessões (Redis) — só se houver múltiplas instâncias API; V1 pode usar memória com ressalva de restart.  

---

## 13. Ordem de implementação sugerida

1. `faz/auth.py` + store de sessão em memória  
2. Endpoints `/api/auth/*` + dependency de proteção  
3. Tela de login no `frontend/`  
4. Ajustar `mensal_job` / pipeline para credenciais da sessão  
5. Testes: login OK, login falho, 401 em generate, expiração TTL  
6. Atualizar [frontend-mensal-cruz-azul.md](frontend-mensal-cruz-azul.md) com seção “Autenticação”  

---

## 14. Referências

- Login FAZ atual: `src/forti_report/faz/client.py` (`login()` → `/sys/login/user`)  
- Config: `src/forti_report/config.py`  
- Frontend V1: `frontend/`, `doc/features/frontend-mensal-cruz-azul.md`  
- Multi-cliente / multi-tenant: `doc/features/multi-tenant-clientes-faz.md`  
- Rascunho V2 (API): `doc/features/v2-multi-cliente-api-frontend.md`  
