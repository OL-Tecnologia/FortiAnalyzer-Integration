# Feature — Multi-tenant (clientes FAZ + branding + automação)

**Status:** 🚧 Em implementação (Fases 1–2 parciais no código)  
**Data:** 2026-08  
**Decisão de produto:** o sistema **já nasce multi-tenant** — não há modo “single-tenant legado” nem caminho separado presente/futuro.  
**Deploys iniciais:** (1) instância local com **1 tenant** cadastrado; (2) instância OL atualizada para o mesmo multi-tenant (Cliente + demais clientes com VPN).  
**Super Admin (.env):** `PORTAL_ADMIN_PASSWORD` — UI em `/admin.html`  
**Relacionado:** [v2-multi-cliente-api-frontend.md](v2-multi-cliente-api-frontend.md), [login-faz-sessao.md](login-faz-sessao.md), [agendamento-email-mensal.md](agendamento-email-mensal.md), [layout-pdf-branding.md](layout-pdf-branding.md)

Este documento **é a spec canônica** de multi-cliente. Substitui o rascunho V2 nos pontos de auth admin, automação e deploy.

---

## 1. Problema de negócio

A OL Tecnologia atende clientes em que **cada um tem FortiGate + FortiAnalyzer próprios** (nada compartilhado).

| Realidade | Consequência |
|-----------|--------------|
| Cada cliente = FAZ + ADOM + branding + e-mails próprios | Configuração **por tenant**, nunca um `.env` único de negócio |
| Maioria tem **VPN site-to-site** com a OL | Instância na OL cadastra **N tenants** alcançáveis |
| **instância local** (órgão público) **sem VPN** externa | Instância **na rede da instância local** com o **mesmo** multi-tenant; cadastram **somente 1 tenant** (o FAZ deles) |
| V1 = um `.env` global (Cliente) | Precisa migrar para catálogo de clients |

**Objetivo único:** um produto multi-tenant. A quantidade de tenants na instância é **dado de operação** (1 na instância local, N na OL), não um fork de código.

---

## 2. Princípios (não negociáveis)

1. **Sempre multi-tenant** — motor, API, scheduler e UI pensados para N clients; N=1 é só o caso instância local.  
2. **Código genérico; dados por cliente** — nada de Cliente/instância local hardcoded no motor.  
3. **Login do operador = FortiAnalyzer** do tenant escolhido (não usuário local do “PDF Analyzer”).  
4. **Super Admin configura tenants** — FAZ, ADOM, branding, agenda, e-mails, conta de automação.  
5. **Automação ≠ sessão do operador** — e-mail mensal usa **conta de serviço por tenant**.  
6. **Isolamento total** — cache, PDF, estado do scheduler e assets por `client_slug`.  
7. **Não editar `.env` pela tela de login pública.**  
8. **Mesma build em todo lugar** — a instância local e a OL diferem só pelos YAML/secrets e pela rede.  
9. **LGPD** — e-mails pessoais, senhas e dados de contato **não** vão para Git (código, YAML de exemplo, docs). Só `.env` local / secrets / UI Admin.

---

## 3. Como fica em cada lugar

```text
┌─────────────────────────────────────┐     ┌─────────────────────────────────────┐
│ Instância local (rede interna)        │     │ Instância OL (multi-FAZ / VPN)      │
│ Mesmo código multi-tenant           │     │ Mesmo código multi-tenant           │
│                                     │     │                                     │
│ tenants cadastrados:                │     │ tenants cadastrados:                │
│   • cliente  (único)                    │     │   • cliente                       │
│                                     │     │   • cliente_b                       │
│ Scheduler: 1 job (tenant cliente)       │     │   • …                               │
│ Operador: login no FAZ local          │     │ Scheduler: 1 job por tenant enabled │
└─────────────────────────────────────┘     │ Operador: escolhe cliente → FAZ     │
                                            └─────────────────────────────────────┘
```

| Instância | Tenants | Rede | O que o Super Admin faz |
|-----------|---------|------|-------------------------|
| **instância local** | Exatamente **1** (`cliente`) | Só alcança o FAZ local | Cadastra/edita esse único tenant (FAZ, branding, e-mail, automação) |
| **OL** | **N** (Cliente + outros com VPN) | VPN site-to-site até cada FAZ | Cadastra cada cliente alcançável; não cadastra instância local (FAZ inacessível) |

A instância local **não** usa um “modo simplificado” diferente — usa multi-tenant com um registro. Se um dia a instância local tiver outro ADOM/FAZ na mesma rede, basta cadastrar o 2º tenant na **mesma** instância.

Na login, se `GET /api/clients` retornar **um** client: UI pode pré-selecionar / ocultar o dropdown — comportamento de UX, não arquitetura aparte.

---

## 4. Papéis e autenticação

### 4.1 Super Admin (portal)

| Item | Regra |
|------|-------|
| Finalidade | CRUD de tenants, testar conectividade, branding, agenda, e-mails, conta de automação |
| Credencial | Senha/admin **do portal** (não é login FAZ) |
| Armazenamento | Hash no servidor (`PORTAL_ADMIN_PASSWORD_HASH`); nunca no frontend |
| Sessão | Cookie/sessão **admin** separada da sessão FAZ |
| Endpoints | `/api/admin/*` e mutações de clients exigem sessão admin |

### 4.2 Operador (FAZ)

| Item | Regra |
|------|-------|
| Finalidade | Gerar PDF sob demanda, download, status |
| Fluxo | Escolhe tenant (ou único pré-selecionado) → user/senha do **Analyzer daquele tenant** |
| Backend | `authenticate_faz(client_config, user, password)` |
| Sessão | Cookie com `client_slug` + credenciais FAZ em memória (TTL) |
| Não pode | Alterar host, ADOM, logos, conta de automação |

### 4.3 Conta de serviço (automação)

| Item | Regra |
|------|-------|
| Finalidade | Scheduler: login FAZ → PDF → e-mail, sem humano |
| Onde vive | Por tenant, no config/secrets do servidor |
| UI | Super Admin cadastra; API **nunca** devolve senha em claro |
| Permissão FAZ | Mínima (ler/exportar relatórios do ADOM) |

```text
Operador (tela)     →  user/senha pessoais do FAZ do tenant
Scheduler (máquina) →  user/senha de serviço do FAZ do tenant
Super Admin         →  senha do portal (só config)
```

---

## 5. Modelo `ClientConfig` (tenant)

```yaml
# configs/clients/cliente.yaml  (ilustrativo)
slug: cliente
display_name: Cliente
enabled: true

faz:
  host: 10.x.x.x
  port: 8090
  use_ssl: true
  verify_ssl: false
  adom: ADOM
  report_schedule_mensal: "MENSAL- RELATÓRIO GERAL"   # nome real no FAZ local
  report_schedule_wan: ""
  time_period: last-30-days

automation:
  faz_user: usuario_servico
  faz_password_env: FAZ_PASSWORD

hierarchy:
  device_pattern: "^(?:(hafw\\d+)|fw)-(?P<region>[a-z0-9]+)-(?P<site>.+)$"
  region_labels: {}

pdf:
  cover_logo: assets/clients/cliente/logo.png   # capa: só logo (+ textos dinâmicos)
  internal_header: assets/img/cabecalho-interno.png  # corpo do PDF
  header_logo: assets/img/logo-horizontal-gray.svg
  cover_title: RELATÓRIO MENSAL GERAL
  email_subject_prefix: ""

output:
  subdir: cliente

schedule:
  enabled: true
  day: 5
  hour: 6
  minute: 0
  timezone: America/Sao_Paulo
  force_download: true
  retry_enabled: true
  max_retries: 3
  retry_hours: 2

email:
  # Não versionar e-mails reais (LGPD) — preencher na UI Admin / .env
  smtp_from: ""
  smtp_to: ""
  smtp_cc: ""
  smtp_alert_to: ""
```

Na OL: `cliente.yaml` + outros YAMLs no mesmo schema. Migração: o que hoje está no `.env` de negócio (FAZ_*, PDF logos, SMTP_TO, agenda) vai para o YAML do tenant.

### Estrutura de pastas (igual em a instância local e a OL)

```text
configs/clients/
  cliente.yaml              # só este na instância local
  cliente.yaml        # na instância OL
  ...
assets/clients/{slug}/
output/{slug}/
  faz_mensal/
  chart_cache/
  scheduler/scheduler_state.json
  MENSAL_UNIFICADO_{ADOM}.pdf
```

### O que fica global (`.env` da instância)

- `PORTAL_ADMIN_*`  
- SMTP técnico padrão (host/user/senha OL), se compartilhado  
- TTL de sessão, bind HTTP  
- Defaults do motor  

**Não** usar `FAZ_HOST` / `FAZ_ADOM` globais como fonte da verdade — isso vive no tenant.

---

## 6. Fluxos de UX

### 6.1 Super Admin — cadastrar tenant

```text
1. Administração → login Super Admin
2. Clientes → Novo / Editar
3. FAZ (host, porta, SSL, ADOM), schedules, branding, e-mails, conta automação
4. [Testar conectividade] → ok=true
5. Salva ClientConfig (+ assets)
```

**Instância local:** repetem o fluxo **uma vez** (tenant `cliente`).  
**OL:** repetem para Cliente e cada cliente com VPN.

### 6.2 Operador

```text
1. Lista de clients (GET /api/clients)
2. Se N=1 → pré-seleciona; se N>1 → dropdown
3. User/senha do Analyzer do tenant
4. POST /api/auth/faz/login { client_slug, user, password }
5. Gera/baixa PDF com paths e branding daquele slug
```

### 6.3 Scheduler (sempre multi-tenant)

```text
a cada tick:
  para cada client com schedule.enabled:     # na instância local: 1 item; na OL: N
    se janela devida e estado ≠ success:
      login FAZ com automation.*
      pipeline → output/{slug}/...
      e-mail com To/Cc/assunto do tenant
      estado em output/{slug}/scheduler/
```

Falha de um tenant **não** cancela os demais (relevante na OL; inócuo na instância local com N=1).

---

## 7. API

### Público / operador

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/api/clients` | — | Lista enabled (slug, display_name, adom) |
| POST | `/api/auth/faz/login` | — | `{ client_slug, user, password }` |
| POST | `/api/auth/logout` | sessão FAZ | |
| GET | `/api/auth/me` | sessão FAZ | inclui `client_slug` |
| POST | `/api/clients/{slug}/reports/mensal/generate` | sessão FAZ do **mesmo** slug | |
| GET | `/api/clients/{slug}/reports/mensal/latest` | sessão FAZ | |
| GET | `/api/clients/{slug}/reports/mensal/latest/download` | sessão FAZ | |

### Super Admin

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/api/admin/login` | — | `{ password }` |
| POST | `/api/admin/logout` | admin | |
| GET | `/api/admin/me` | admin | |
| GET | `/api/admin/clients` | admin | lista completa (sem senhas) |
| POST | `/api/admin/clients` | admin | cria tenant |
| PUT | `/api/admin/clients/{slug}` | admin | atualiza |
| POST | `/api/admin/clients/{slug}/test-connection` | admin | `{ ok, detail }` |
| POST | `/api/admin/clients/{slug}/assets` | admin | upload logos |

### Segurança

- Mutação de tenant → só admin.  
- Generate/download → `session.client_slug == path.slug`.  
- Rate limit nos dois logins.  
- Test-connection não vaza senhas.

---

## 8. Refactors no código V1

| Área atual | Mudança |
|------------|---------|
| `Settings` / `.env` de negócio | `ClientConfig` + `settings_from_client`; `.env` só globals |
| `hierarchy.py` Cliente | pattern/labels do tenant |
| `pdf/*` | branding do tenant |
| cache / `output/` | `output/{slug}/` |
| `faz/auth.py` | host/ADOM do client; sessão com `client_slug` |
| `mensal_scheduler` | loop em **todos** os clients enabled; estado por slug; `automation.*` |
| `email_delivery` | To/Cc/assunto por tenant |
| Frontend | seletor (N≥1), admin UI, sem hardcode Cliente |
| `automation_settings` | campos de agenda/e-mail **por tenant** |

CLI: `--client {slug}` obrigatório quando houver mais de um; com um único enabled, pode defaultar para ele.

---

## 9. Fases de implementação (tudo já é multi-tenant)

Não há fase “depois viramos multi-tenant”. As fases são fatias do **mesmo** desenho.

### Fase 0 — Spec ✅ (este doc)

### Fase 1 — Motor + isolamento + Cliente como tenant

- [ ] Schema `ClientConfig` + loader YAML  
- [ ] Migrar Cliente → `configs/clients/cliente.yaml`  
- [ ] `output/{slug}/` + hierarchy/PDF parametrizados  
- [ ] `settings_from_client` + CLI `--client`  
- [ ] Login FAZ com `client_slug`  
- [ ] Scheduler itera tenants (funciona com 1 ou N)  
- [ ] Example `configs/clients/cliente.yaml.example`  

**Aceite:** OL gera PDF Cliente via tenant YAML; scheduler usa conta `automation` do tenant.

### Fase 2 — Super Admin + UI

- [ ] Auth admin + CRUD + test-connection  
- [ ] UI administração completa  
- [ ] Login com seletor (pré-seleção se N=1)  
- [ ] Fim da edição de FAZ/ADOM via `.env` de negócio  

**Aceite:** na instância local, Super Admin cadastra o único tenant, testa FAZ, salva; operador loga no Analyzer e gera PDF; e-mail automático na agenda.

### Fase 3 — Rollout OL multi-cliente + instância local

- [ ] Deploy/atualização da instância OL com multi-tenant  
- [ ] Cadastro dos clientes com VPN além de Cliente  
- [ ] Deploy instância local (mesmo build) com 1 tenant  
- [ ] Docs operacionais: “só cadastrar tenant se o FAZ for alcançável desta instância”  
- [ ] Falha de um tenant não derruba os outros no scheduler  

**Aceite:** OL envia e-mail para ≥2 tenants sem misturar artefatos; instância local opera com 1 tenant e e-mail local.

### Fase 4 — Endurecimento (opcional)

- [ ] Secrets fora do YAML (env/vault)  
- [ ] Auditoria de alterações de tenant  
- [ ] Redis de sessão se houver réplicas  
- [ ] Parser por `layout_id` se FAZ divergir  

---

## 10. O que **não** fazer

| Prática | Motivo |
|---------|--------|
| Fork “versão de um tenant single-tenant” | Duplica manutenção; N=1 já cobre |
| Gravar FAZ/ADOM na login sem Super Admin | Risco de reaponta/phishing |
| Usar sessão do operador no scheduler | Job precisa de conta de serviço |
| `output/` único global | Mistura cache/PDF entre tenants |
| Operador digitar host/ADOM livre | Escape de tenant |
| Cadastrar o tenant no painel OL sem rota de rede | FAZ inacessível |
| Commitar senhas FAZ no git | Usar env/secret ref |

---

## 11. Critérios de aceite globais

- [ ] Uma única codebase multi-tenant em a instância local e a OL.  
- [ ] instância local: 1 tenant cadastrado → PDF + login FAZ + e-mail automático.  
- [ ] OL: N tenants → PDF/e-mail isolados por slug; Cliente migrado do `.env`.  
- [ ] Operador autentica sempre no FAZ do tenant.  
- [ ] Super Admin obrigatório para CRUD de tenant.  
- [ ] Teste de conectividade falhou → não aplica config inválida.  
- [ ] OpenAPI + testes (admin, FAZ, isolamento de path, scheduler multi).  

---

## 12. Relação com docs existentes

| Doc | Relação |
|-----|---------|
| [v2-multi-cliente-api-frontend.md](v2-multi-cliente-api-frontend.md) | Rascunho; **este doc manda** |
| [login-faz-sessao.md](login-faz-sessao.md) | Login FAZ + `client_slug` |
| [agendamento-email-mensal.md](agendamento-email-mensal.md) | 1 job global → loop por tenant |
| [layout-pdf-branding.md](layout-pdf-branding.md) | Branding por `ClientConfig` |
| [frontend-mensal.md](frontend-mensal.md) | UI generalizada ao client da sessão |

---

## 13. Decisões de produto (registro)

| Decisão | Escolha |
|---------|---------|
| Arquitetura | **Multi-tenant desde o primeiro PR** |
| Instância local | Mesmo produto; **1 tenant** cadastrado na instância local |
| OL | **Atualizar** a instância atual para multi-tenant; migrar Cliente; incluir clientes com VPN |
| Login operador | Sempre FortiAnalyzer do tenant |
| Config | Super Admin |
| E-mail automático | Conta de serviço **por tenant** |
| Formato | YAML em `configs/clients/` |

---

## 14. Ordem sugerida de PRs

1. `ClientConfig` + loader + `output/{slug}` + CLI `--client`  
2. Hierarchy/PDF parametrizados; migração Cliente YAML (OL)  
3. Auth FAZ com `client_slug` + testes  
4. Scheduler multi-tenant + secrets `automation`  
5. Admin auth + test-connection + CRUD  
6. Frontend admin + seletor na login (N=1 pré-seleciona)  
7. Rollout: atualizar servidor OL + pacote deploy local (1 tenant)  
