# Features — V1 (implementadas)

Catálogo das capacidades atuais do **fortiAnalyzer**. Detalhes em documentos filhos quando aplicável.

## Legenda de status

| Status | Significado |
|--------|-------------|
| ✅ V1 | Disponível via CLI |
| 📋 V2 | Planejado — ver [v2-multi-cliente-api-frontend.md](v2-multi-cliente-api-frontend.md) |

---

## Integração FortiAnalyzer

| Feature | Status | Documento / código |
|---------|--------|-------------------|
| Login JSON-RPC | ✅ V1 | `faz/client.py` |
| Listar dispositivos do ADOM | ✅ V1 | `faz/devices.py`, CLI `list-units` |
| Listar relatórios gerados | ✅ V1 | `faz/reports.py`, CLI `list-reports` |
| Download relatório (JSON/XML/PDF) | ✅ V1 | `faz/reports.py` |
| Filtro por schedule MENSAL | ✅ V1 | `FAZ_REPORT_SCHEDULE` |
| ADOM configurável por `.env` | ✅ V1 | `FAZ_ADOM` |
| Frontend web MENSAL (CRUZ_AZUL) | ✅ V1 | [frontend-mensal-cruz-azul.md](frontend-mensal-cruz-azul.md) |
| Login FAZ (tela + sessão, sem `.env`) | 📋 Planejado | [login-faz-sessao.md](login-faz-sessao.md) |
| Multi-ADOM / portal N clientes | 📋 V2 | [v2-multi-cliente-api-frontend.md](v2-multi-cliente-api-frontend.md) |

---

## Dados e hierarquia

| Feature | Status | Documento / código |
|---------|--------|-------------------|
| Padrão de hostname Cruz Azul (`fw-{reg}-cruz-azul-{site}`) | ✅ V1 | `data/hierarchy.py` |
| 6 unidades regionais, 11 antenas | ✅ V1 | `REGION_LABELS`, README raiz |
| Parser JSON MENSAL GERAL (layout FAZ) | ✅ V1 | `data/parsers/mensal_json.py` |
| Parser PDF MENSAL (fallback) | ✅ V1 | `data/parsers/mensal_pdf.py` |
| Parser XML (legado / parcial) | ✅ V1 | `data/parsers/faz_xml.py` |
| Hierarquia configurável por cliente | 📋 V2 | v2 doc |

---

## Cache e fechamento mensal

| Feature | Status | Documento / código |
|---------|--------|-------------------|
| Cache JSON por antena (nome fixo) | ✅ V1 | [cache-e-fechamento-mensal.md](cache-e-fechamento-mensal.md) |
| Metadados `.meta.json` (TID + período) | ✅ V1 | `services/mensal_cache.py` |
| Validação cache vs relatório atual FAZ | ✅ V1 | `json_cache_is_fresh` |
| Cache gráficos por TID (sem misturar mês anterior) | ✅ V1 | `charts/plotly_charts.py` + prune |
| PDF nome fixo sobrescrito | ✅ V1 | `MENSAL_UNIFICADO_{ADOM}.pdf` |
| `--force-download`, `--metadata-only`, `--no-charts` | ✅ V1 | `cli.py` |

---

## PDF MENSAL unificado (principal)

| Feature | Status | Documento / código |
|---------|--------|-------------------|
| PDF único 6 unidades + 11 antenas | ✅ V1 | [mensal-unificado.md](mensal-unificado.md) |
| Capa com cabeçalho/rodapé PNG + texto + logo cliente | ✅ V1 | `pdf/cover_page.py` |
| Sumário estilo FAZ com números de página | ✅ V1 | `pdf/mensal_toc.py`, `multiBuild` |
| Cabeçalho interno + logo SVG transparente | ✅ V1 | [layout-pdf-branding.md](layout-pdf-branding.md) |
| Rodapé linha vermelha + “Página X de Y” | ✅ V1 | `pdf/internal_page.py` |
| Margens 2,50 cm | ✅ V1 | `pdf/page_layout.py` |
| Tabelas unificadas (header 9pt, centralizado) | ✅ V1 | `pdf/table_utils.py` |
| KeepTogether título + tabela + gráfico | ✅ V1 | `unified_mensal_builder.py` |
| Gráficos Plotly (timeline, rosca, barras) | ✅ V1 | `charts/plotly_charts.py` |
| Seções SD-WAN, políticas, risco, sites | ✅ V1 | `unified_mensal_builder.py` |

---

## Outros relatórios PDF

| Feature | Status | Documento / código |
|---------|--------|-------------------|
| PDF por unidade regional (legado) | ✅ V1 | `pdf/regional_builder.py` |
| PDF WAN semanal (6 unidades) | ✅ V1 | [relatorios-wan.md](relatorios-wan.md) |
| PDF por antena individual (legado) | ✅ V1 | `pdf/builder.py`, CLI `generate` |
| PDF demo fictício | ✅ V1 | CLI `demo` |

---

## Performance e operação

| Feature | Status | Documento / código |
|---------|--------|-------------------|
| Otimização logo rasterizado + cache disco | ✅ V1 | [performance-geracao-pdf.md](performance-geracao-pdf.md) |
| Hierarquia só de cache (sem FAZ) se metas válidas | ✅ V1 | `mensal_pipeline._fetch_hierarchy_from_cache` |
| Script de profiling | ✅ V1 | `scripts/profile_pdf.py` |

---

## V2 — não implementado

Tudo relacionado a **vários clientes**, **frontend** e **API REST** está especificado apenas em:

**[v2-multi-cliente-api-frontend.md](v2-multi-cliente-api-frontend.md)**
