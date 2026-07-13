# Referências e artefatos do projeto

Lista do que o projeto utiliza hoje: código, configuração, assets, saídas e documentação externa.

## Repositório (estrutura principal)

```text
fortiAnalyzer/
├── api.json                    # Swagger / referência API FortiAnalyzer (módulo Report)
├── .env / .env.example         # Credenciais e parâmetros (não versionar .env com senha)
├── pyproject.toml              # Pacote Python forti_report
├── requirements.txt            # Dependências (se usado além do pyproject)
├── README.md                   # Guia operacional na raiz
├── doc/                        # Esta documentação
├── frontend/                   # UI web V1 (gerar + progresso + download)
│   ├── index.html
│   ├── styles.css
│   └── app.js
│   └── img/                    # Capa, cabeçalho interno, logos
├── output/                     # PDFs e artefatos gerados
│   ├── faz_mensal/             # Cache JSON (+ .meta.json) por dispositivo
│   ├── chart_cache/            # PNG de gráficos (por escopo TID)
│   └── hierarchy.json          # Snapshot hierarquia após pull-hierarchy
├── scripts/                    # Utilitários CLI auxiliares
├── src/forti_report/           # Código-fonte principal
└── tests/                      # Testes automatizados
```

## Configuração (`.env`)

| Variável | Função |
|----------|--------|
| `FAZ_HOST`, `FAZ_PORT`, `FAZ_USE_SSL`, `FAZ_VERIFY_SSL` | Conexão JSON-RPC FortiAnalyzer |
| `FAZ_USER`, `FAZ_PASSWORD` | Autenticação |
| `FAZ_ADOM` | Cliente no FAZ (ex.: `CRUZ_AZUL`) |
| `FAZ_REPORT_SCHEDULE` | Filtro do relatório MENSAL (ex.: `MENSAL- RELATÓRIO GERAL`) |
| `FAZ_WAN_REPORT_SCHEDULE` | Relatório WAN semanal |
| `FAZ_TIME_PERIOD` | Período padrão em execuções no FAZ |
| `FAZ_PREFER_CACHE` | Preferir JSON local se validado contra relatório atual |
| `OUTPUT_DIR` | Pasta de saída (default: `output`) |
| `PDF_*` | Caminhos de imagens (capa, cabeçalho, rodapé, logos) |

Definições em: `src/forti_report/config.py`.

## Documentação externa / referência técnica

| Artefato | Uso |
|----------|-----|
| `api.json` | Endpoints Report do FAZ (`/report/adom/{adom}/reports/...`); base para `faz/client.py` e `faz/reports.py` |
| FortiAnalyzer (ambiente) | ADOM, schedules, dispositivos `fw-*-cruz-azul-*`, export JSON/XML/PDF |
| Relatório de referência WAN (opcional) | PDF em `tests/` para layout SEMANAL Tráfego WAN |

## Assets visuais (`assets/`)

| Arquivo (configurável) | Uso |
|------------------------|-----|
| `assets/img/cabecalho_capa.png` | Faixa superior da capa MENSAL |
| `assets/img/rodape_capa.png` | Faixa inferior da capa |
| `assets/img/cabecalho-interno.png` | Cabeçalho páginas internas |
| `assets/img/logo-horizontal-gray.svg` | Logo OL no cabeçalho interno |
| `assets/img/logo_cruz-azul.png` | Logo cliente na capa |
| `assets/cover.png`, `header.png`, `footer.png` | Legado / fallback |

## Saídas geradas (`output/`)

| Artefato | Descrição |
|----------|-----------|
| `MENSAL_UNIFICADO_{ADOM}.pdf` | PDF mensal unificado entregável |
| `faz_mensal/{device}.json` | Export JSON FAZ por dispositivo (nome fixo, conteúdo sobrescrito) |
| `faz_mensal/{device}.meta.json` | TID e período para validar cache |
| `chart_cache/` | PNG Plotly; subpastas por escopo `tid:` |
| `unidades/`, `wan_unidades/` | PDFs regionais / WAN (pipelines legados) |
| `hierarchy.json` | Manifesto hierarquia após import |

## Scripts auxiliares

| Script | Função |
|--------|--------|
| `scripts/generate_report.py` | Wrapper para `forti_report.cli` |
| `scripts/profile_pdf.py` | Medição de tempo de geração PDF |
| `scripts/compare_mensal_coverage.py` | Comparação cobertura seções vs PDF referência |

## Módulos de código (mapa)

| Módulo | Responsabilidade |
|--------|------------------|
| `forti_report/cli.py` | Comandos CLI |
| `forti_report/config.py` | Settings (Pydantic) |
| `forti_report/faz/` | Cliente JSON-RPC, devices, reports |
| `forti_report/data/` | Modelos, hierarquia, parsers JSON/XML/PDF |
| `forti_report/charts/` | Plotly + Kaleido → PNG |
| `forti_report/pdf/` | ReportLab: capa, TOC, MENSAL unificado, WAN, regional |
| `forti_report/api/app.py` | API FastAPI + SSE progresso |
| `forti_report/services/mensal_job.py` | Job assíncrono para o frontend |

## Testes

| Arquivo | Área |
|---------|------|
| `tests/test_hierarchy.py` | Agrupamento unidade regional → dispositivo |
| `tests/test_mensal_json.py` | Parser JSON MENSAL |
| `tests/test_mensal_pipeline.py` | Pipeline MENSAL |
| `tests/test_mensal_utils.py` | Utilitários métricas |
| `tests/test_wan_pdf.py` | PDF WAN |
| `tests/test_units.py`, `test_models.py` | Modelos base |

## Dependências principais (runtime)

- **httpx** — HTTP/JSON-RPC FAZ  
- **pydantic-settings** — `.env`  
- **reportlab**, **svglib**, **Pillow** — PDF e logo SVG  
- **plotly**, **kaleido** — gráficos  
