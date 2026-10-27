# V2 — Multi-cliente, API e frontend

**Status:** planejado — **não implementar na V1**  
**Data do documento:** 2026-06  
**Atualização:** 2026-08 — a spec canônica de multi-tenant (Super Admin, automação por tenant, deploy local de um tenant vs painel com vários tenants) está em **[multi-tenant-clientes-faz.md](multi-tenant-clientes-faz.md)**. Este doc permanece como rascunho de API/tenant.  
**Contexto:** A OL Tecnologia atende diversos clientes além do Cliente. O backend atual (CLI + `.env` único) atende um ADOM por vez. O frontend exigirá seleção de cliente, relatório e geração sob demanda.

---

## 1. Problema de negócio

- Todo fim de mês é gerado um **RELATÓRIO MENSAL GERAL (PDF)** para entrega ao cliente.
- Os **nomes de arquivo** podem permanecer fixos (`fw-….json`, `MENSAL_UNIFICADO_{ADOM}.pdf`), mas o **conteúdo deve ser sempre do período/relatório atual** — nunca dados do mês anterior (já tratado na V1 via TID; na V2 isso deve valer **por tenant**).
- Hoje trocar cliente = alterar `.env` (`FAZ_ADOM`, `FAZ_REPORT_SCHEDULE`) e reiniciar processo — **inadequado para portal com N clientes**.

---

## 2. Objetivos da V2

| # | Objetivo |
|---|----------|
| 1 | Suportar **N clientes** (ADOMs / tenants) sem misturar cache nem PDF |
| 2 | Permitir **configurar por cliente**: ADOM, schedule do relatório, assets, hierarquia de dispositivos |
| 3 | Expor **API HTTP** consumível pelo frontend (gerar, status, download PDF) |
| 4 | Manter regras V1 de **validação de cache** (TID/período) **isoladas por cliente** |
| 5 | Generalizar o que hoje é **específico Cliente** (regex hostname, unidades regionais, logos) |

---

## 3. Estado atual (V1) — o que já existe

### Cliente e relatório hoje

| Parâmetro | Onde | Exemplo Cliente |
|-----------|------|-------------------|
| Cliente (ADOM) | `FAZ_ADOM` | `ADOM_EXEMPLO` |
| Relatório MENSAL | `FAZ_REPORT_SCHEDULE` | `MENSAL- RELATÓRIO GERAL` |
| Relatório WAN | `FAZ_WAN_REPORT_SCHEDULE` | `SEMANAL- RELATÓRIO TRÁFEGO WAN` |
| Busca no FAZ | `find_latest_report_for_device` + filtro schedule | `faz/reports.py` |

### Acoplamento Cliente (deve virar config na V2)

- Regex de dispositivo: `fw-{reg}-exemplo-{site}` em `data/hierarchy.py`
- Rótulos de unidades: `REGION_LABELS` (CAS, SPO, …)
- Logo capa: `logo_exemplo.png`
- Parser assume layout **MENSAL- RELATÓRIO GERAL** (JSON layout-id 12)

### Cache V1 (reutilizar conceito, separar por tenant)

- `output/faz_mensal/{device}.json` + `{device}.meta.json`
- `output/chart_cache/` com subpastas por `tid:{faz_tid}`
- PDF: `output/MENSAL_UNIFICADO_{ADOM}.pdf`

**Gap V2:** tudo em `output/` único — dois clientes no mesmo servidor **colidiriam**.

---

## 4. Proposta de arquitetura V2

```text
┌─────────────┐     HTTPS      ┌──────────────────┐
│  Frontend   │ ─────────────► │  API (FastAPI)   │
│  (portal)   │ ◄───────────── │  /clients/...    │
└─────────────┘                └────────┬─────────┘
                                        │
                    Settings por request (tenant_id)
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            MensalReportPipeline   configs/          output/{tenant}/
            UnifiedMensalPdfBuilder clients/*.yaml   faz_mensal/
                                                   chart_cache/
                                                   *.pdf
```

### 4.1 Modelo de configuração por cliente (tenant)

Arquivo ou registro por cliente, exemplo:

```yaml
# configs/clients/cliente.yaml  (ilustrativo)
slug: cliente
display_name: Cliente
faz:
  adom: ADOM
  report_schedule_mensal: "MENSAL- RELATÓRIO GERAL"
  report_schedule_wan: "SEMANAL- RELATÓRIO TRÁFEGO WAN"
  time_period: last-30-days
hierarchy:
  device_pattern: "^(?:(hafw\\d+)|fw)-(?P<region>[a-z0-9]+)-(?P<site>.+)$"
  region_labels:
    norte: "Norte"
    sul: "Sul"
pdf:
  cover_logo: assets/clients/cliente/logo.png
  cover_header: assets/img/cabecalho_capa.png
  internal_header: assets/img/cabecalho-interno.png
  header_logo: assets/img/logo-horizontal-gray.svg
output:
  subdir: cliente   # output/cliente/...
```

Credenciais FAZ podem ser **globais** (um usuário automação) ou **por cliente** — decisão de segurança na implementação.

### 4.2 API REST (escopo sugerido)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/clients` | Lista clientes configurados |
| GET | `/api/v1/clients/{slug}` | Detalhe + status último PDF |
| GET | `/api/v1/clients/{slug}/hierarchy` | Unidades regionais/dispositivos + relatório vinculado |
| POST | `/api/v1/clients/{slug}/reports/mensal/generate` | Body: `{ days, download, charts, force_download }` |
| GET | `/api/v1/clients/{slug}/reports/mensal/latest` | Metadados (período, tid, data geração) |
| GET | `/api/v1/clients/{slug}/reports/mensal/latest/download` | Stream PDF |
| GET | `/api/v1/faz/reports?adom=&days=` | Listar schedules (admin / debug) |

Autenticação do portal: **fora do escopo deste doc** (JWT, SSO, etc.) — definir na V2.

### 4.3 Alterar “nome do cliente” e “relatório” (requisito do usuário)

| Ação do usuário (frontend) | Backend V2 |
|----------------------------|------------|
| Selecionar cliente | Carrega `ClientConfig` → `faz_adom`, assets, `output_subdir`, regex |
| Escolher tipo de relatório | Campo `report_schedule_mensal` (ou lista vinda do FAZ) |
| Gerar PDF | `Settings.model_copy(update=...)` + paths `output/{slug}/` |
| Novo mês | Mesmo slug; cache invalida por TID; pastas chart antigas removidas |

**Não depender de um único `.env`** para o portal: `.env` só defaults globais (host FAZ, credenciais).

### 4.4 Isolamento de dados entre clientes

Obrigatório na V2:

```text
output/{client_slug}/faz_mensal/
output/{client_slug}/chart_cache/
output/{client_slug}/MENSAL_UNIFICADO_{ADOM}.pdf
```

Funções em `mensal_cache.py` e `config.py` devem receber `base_dir` ou `client_slug` — refatoração planejada.

---

## 5. Escopo fora da V2 (ou V2.1)

- Editor visual de templates PDF no frontend  
- Agendamento automático (cron) sem CLI  
- Suporte a layout FAZ diferente do MENSAL GERAL (novo parser por `layout_id`)  
- Multi-idioma PDF  
- Histórico de PDFs por mês no storage (S3) com retenção  

---

## 6. Migração V1 → V2

1. Extrair `Settings` para aceitar `output_dir` e `faz_mensal_cache_dir` **por cliente**.  
2. Introduzir `ClientConfig` + loader YAML/DB.  
3. Parametrizar `hierarchy.py` (pattern + labels).  
4. Criar camada API fina sobre `MensalReportPipeline`.  
5. Frontend consome API; CLI permanece para ops/debug (`--client cliente`).  

---

## 7. Critérios de aceite (V2)

- [ ] Dois ADOMs configurados geram PDFs em pastas separadas sem cruzar JSON/gráficos.  
- [ ] Alterar `report_schedule` no config altera qual relatório o FAZ baixa.  
- [ ] Frontend gera PDF para cliente A sem reiniciar serviço nem editar `.env`.  
- [ ] Fechamento mensal: novo TID no FAZ força download e gráficos novos para aquele cliente.  
- [ ] Documentação de API (OpenAPI) publicada junto ao serviço.  

---

## 7. Referências V1

- Cache mensal: [cache-e-fechamento-mensal.md](cache-e-fechamento-mensal.md)  
- PDF MENSAL: [mensal-unificado.md](mensal-unificado.md)  
- Artefatos: [../referencias-projeto.md](../referencias-projeto.md)  
