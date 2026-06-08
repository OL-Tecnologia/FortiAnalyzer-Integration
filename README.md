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

## Hierarquia: Unidade → Antenas

Dispositivos seguem o padrão `fw-{região}-cruz-azul-{site}`:

| Unidade | Antenas |
|---------|---------|
| **CAS - Campinas** | Ambulatório, Colégio |
| **GRS** | Guarulhos |
| **OCO** | Osasco |
| **SNE** | Santo André |
| **SPO** | Centro, Itaquera, Matriz (HA), Penha, Stamaro |
| **SVE** | São Vicente |

```bash
# Ver unidades e antenas
python scripts/generate_report.py list-hierarchy

# Importar tudo agrupado → output/hierarchy.json
python scripts/generate_report.py pull-hierarchy --metadata-only --days 60

# PDF consolidado de uma unidade (sumário + seção por antena)
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

## Comandos (antenas individuais)

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

- [ ] Calibrar `data/parsers/faz_xml.py` com XML real do **MENSAL- RELATÓRIO GERAL**
- [ ] Novas seções (resumo executivo, segurança, etc.)
- [ ] Batch: todas as antenas `fw-*-cruz-azul-*`

## Configuração (.env)

| Variável | Descrição |
|----------|-----------|
| `FAZ_HOST` / `FAZ_PORT` | Ex.: `172.16.8.39` / `8090` |
| `FAZ_ADOM` | `CRUZ_AZUL` |
| `FAZ_USER` / `FAZ_PASSWORD` | Credenciais API |
| `PDF_*_IMAGE` | Caminhos das imagens |
| `OUTPUT_DIR` | Pasta de saída |
