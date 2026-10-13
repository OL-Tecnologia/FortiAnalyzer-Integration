# FortiAnalyzer → PDF (Cruz Azul)

Importação de relatórios do FortiAnalyzer (ADOM **CRUZ_AZUL**), gráficos com **Plotly** e PDF customizado (capa, sumário com links, seções, cabeçalho/rodapé).

**Documentação completa:** pasta [doc/](doc/) (features V1, referências do projeto, planejamento V2 multi-cliente + frontend).

## Estrutura do projeto

```text
fortiAnalyzer/
├── api.json                 # Swagger módulo Report (referência)
├── doc/                     # Documentação: features, V2, referências
├── assets/                  # Imagens: cover.png, header.png, footer.png
├── output/                  # PDFs gerados
├── src/forti_report/
│   ├── config.py            # Variáveis de ambiente (.env)
│   ├── cli.py               # Linha de comando
│   ├── faz/                 # Cliente JSON-RPC + relatórios
│   ├── data/                # Modelos + parsers XML do FAZ
│   ├── charts/              # Plotly → PNG (Kaleido)
│   ├── pdf/                 # ReportLab: capa, TOC, seções
│   │   └── sections/        # Uma classe por seção do PDF
│   └── services/            # Pipeline import → PDF
├── scripts/generate_report.py
└── tests/
```

## Fluxo

1. **FAZ** — login, listar/baixar relatório por dispositivo (`XML` para parse).
2. **data** — normalizar em `UnitReport` / `SectionData`.
3. **charts** — Plotly gera PNG embutido no PDF.
4. **pdf** — capa (imagem), sumário com links `#seção`, seções, header/footer.

## Setup

### Distribuição (.exe completo)

1. Compile: `powershell -ExecutionPolicy Bypass -File install\build_app.ps1`
2. Envie a pasta **`dist\FortiAnalyzer-Reports\`** ao time.
3. No destino: duplo clique em **`FortiAnalyzer-Reports.exe`** → portal em http://localhost:8000/login.html

### Instalação por código-fonte (dev)

Duplo clique em **`install.bat`** (wizard em http://127.0.0.1:8765). Uso diário: **`FortiAnalyzer Reports.bat`**.

Guia: [install/INSTALACAO.md](install/INSTALACAO.md)

### Manual

```bash
cd c:\scr\fortiAnalyzer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Editar .env com FAZ_USER e FAZ_PASSWORD
```

Coloque as imagens em `assets/`:

- `cover.png` — capa
- `header.png` — cabeçalho
- `footer.png` — rodapé

## Hierarquia e terminologia

| Termo | Exemplo | Descrição |
|-------|---------|-----------|
| **Unidade regional** | CAS - Campinas, SPO | Agrupamento por região (`fw-{região}-cruz-azul-{site}`) |
| **Unidade** | Ambulatório, Colégio | Nome do site/local (coluna **Unidade** no PDF) |
| **Dispositivo** | `fw-cas-cruz-azul-ambulatorio` | Hostname FortiGate no FAZ |

Dispositivos seguem o padrão `fw-{região}-cruz-azul-{site}`:

| Unidade regional | Unidades (sites) |
|------------------|------------------|
| **CAS - Campinas** | Ambulatório, Colégio |
| **GRS** | Guarulhos |
| **OCO** | Osasco |
| **SNE** | Santo André |
| **SPO** | Centro, Itaquera, Matriz (HA), Penha, Stamaro |
| **SVE** | São Vicente |

```bash
# Ver unidades regionais e dispositivos
python scripts/generate_report.py list-hierarchy

# Importar tudo agrupado → output/hierarchy.json
python scripts/generate_report.py pull-hierarchy --metadata-only --days 60

# PDF consolidado de uma unidade regional (sumário + seção por dispositivo)
python scripts/generate_report.py generate-unit spo --metadata-only

# PDF de todas as unidades regionais → output/unidades/
python scripts/generate_report.py generate-all-units --metadata-only
```

## Frontend web (CRUZ_AZUL)

```powershell
.\.venv\Scripts\python.exe -m forti_report.api.app
# http://localhost:8000
```

Ver [doc/features/frontend-mensal-cruz-azul.md](doc/features/frontend-mensal-cruz-azul.md).

## Comandos (dispositivos individuais)

```bash
# Listar todas as unidades (11 dispositivos no CRUZ_AZUL)
python scripts/generate_report.py list-units

# Importar metadados de todas (tid, período, relatório vinculado)
python scripts/generate_report.py pull-all --metadata-only

# Importar tentando download do conteúdo (requer permissão no FAZ)
python scripts/generate_report.py pull-all --days 60

# Gerar PDF de todas as unidades regionais → output/unidades/
python scripts/generate_report.py generate-all-units --metadata-only

# PDF WAN (6 unidades) — layout SEMANAL Tráfego WAN + tráfego/sites
python scripts/generate_report.py generate-wan-all --days 60

# PDF WAN de uma unidade
python scripts/generate_report.py generate-wan-unit spo --days 60
```

## Adicionar uma nova seção ao PDF

1. Criar `src/forti_report/pdf/sections/minha_secao.py` herdando `PdfSection`.
2. Registrar em `pdf/sections/registry.py`.
3. Preencher dados em `data/parsers/` ou no pipeline.
4. O sumário inclui automaticamente seções com `key` presente em `unit.sections`.

## Plotly

- Gráficos em `charts/plotly_charts.py`.
- Exportação via **Kaleido** (`chart_to_png_bytes`).
- Cores/layout ajustáveis em `CHART_COLORS` e `fig.update_layout`.

## Próximos passos

Itens pendentes para evoluir o PDF MENSAL além do que o parser JSON (`mensal_json.py`) já cobre hoje.

### 1. Calibrar parser XML do FAZ

**Arquivo:** `src/forti_report/data/parsers/faz_xml.py`

Hoje o pipeline MENSAL prioriza o **JSON** exportado pelo schedule **MENSAL- RELATÓRIO GERAL**. O parser XML é um *placeholder* (só extrai ranking genérico de sites) e serve como fallback quando o download vier em XML.

**O que fazer:**

1. Baixar um XML real de um dispositivo Cruz Azul (ex.: `fw-cas-cruz-azul-ambulatorio`) via FAZ ou `pull-all --days 60`.
2. Mapear tags/XPath de cada chart do MENSAL (resumo web, usuários, categorias, SD-WAN, políticas).
3. Expandir `parse_report_xml_to_sections()` para popular `SectionData` com as mesmas `key`s usadas em `unified_mensal_builder.py`.
4. Adicionar teste em `tests/` com XML de amostra versionado (sem credenciais).

### 2. Novas seções no PDF

**Implementado (V1):**

| Seção | Escopo | Módulo |
|-------|--------|--------|
| Resumo Executivo — Visão Geral | Após tabela global | `pdf/sections/resumo_executivo.py` |
| Resumo Executivo | Por dispositivo | `pdf/sections/resumo_executivo.py` |
| Segurança Ampliada | Por dispositivo | `pdf/sections/seguranca.py` |
| Referência FAZ (inventário interno) | Fora do PDF do cliente | `pdf/sections/faz_conteudo.py` (não renderizado na entrega) |

**Ideias futuras:** comparativo mensal, SLA/conectividade, resumo por unidade regional, parágrafos narrativos FAZ originais.

**Como adicionar outra seção** (ver também [Adicionar uma nova seção ao PDF](#adicionar-uma-nova-seção-ao-pdf)):

1. Criar `src/forti_report/pdf/sections/<nome>.py` com `build_*_flowables(...)`.
2. Registrar a chamada em `unified_mensal_builder.py` → `_mensal_sections`.
3. Preencher dados no parser (`mensal_json.py` / `faz_xml.py`) se necessário.

### 3. Lote — todos os dispositivos Cruz Azul

Escopo: **11 dispositivos** no padrão `fw-*-cruz-azul-*` (e HA `hafw*-...`), agrupados em **6 unidades regionais**.

| Ação | Comando |
|------|---------|
| Listar hierarquia | `python scripts/generate_report.py list-hierarchy` |
| Importar metadados + cache JSON | `python scripts/generate_report.py pull-hierarchy --days 60` |
| PDF MENSAL unificado (portal ou CLI) | `python scripts/generate_report.py generate-mensal-unified --days 60` |
| Forçar novo download do FAZ | acrescentar `--force-download` |
| Só tabelas (rápido) | acrescentar `--no-charts` |

A hierarquia em `src/forti_report/data/hierarchy.py` já filtra automaticamente hostnames `fw-{região}-cruz-azul-{site}`; dispositivos fora desse padrão não entram no PDF unificado.

**Produção:** dia 5 às 06:00, e-mail do cliente e alerta interno — ver [doc/features/agendamento-email-mensal.md](doc/features/agendamento-email-mensal.md). Agende também o Task Scheduler como backup.

## Agendamento mensal + e-mail

Rotina automática no **dia 5 às 06:00** (dia/hora, e-mails e login FAZ são **configuráveis** no `.env`).

```powershell
# Ajustar campos (FAZ, dia/hora, To/alerta) — senhas mascaradas
configurar-agendamento.bat

# Task Scheduler / manual
powershell -ExecutionPolicy Bypass -File scripts\run-scheduled-mensal.ps1

# Status
python -m forti_report.cli scheduler-status
```

Segurança: senhas só no `.env` local (`.gitignore`). Templates `.env.example` / `install/config.env` não carregam senhas.

Detalhes: [doc/features/agendamento-email-mensal.md](doc/features/agendamento-email-mensal.md).

## Configuração (.env)

| Variável | Descrição |
|----------|-----------|
| `FAZ_HOST` / `FAZ_PORT` | Ex.: `172.16.8.39` / `8090` |
| `FAZ_ADOM` | `CRUZ_AZUL` |
| `FAZ_USER` / `FAZ_PASSWORD` | Conta de serviço da automação (configurável / segredo) |
| `MENSAL_SCHEDULE_DAY` / `_HOUR` / `_MINUTE` | Dia e hora do envio (configurável) |
| `SMTP_TO` / `SMTP_ALERT_TO` / `SMTP_FROM` | Destinatários (configurável) |
| `SMTP_PASSWORD` | Segredo SMTP — só no `.env` |
| `PDF_*_IMAGE` | Caminhos das imagens |
| `OUTPUT_DIR` | Pasta de saída |
