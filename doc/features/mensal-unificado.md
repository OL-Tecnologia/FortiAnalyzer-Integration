# Feature — PDF MENSAL unificado

**Status:** ✅ V1  
**Comando:** `generate-mensal-unified`

## Objetivo

Um único PDF com **6 unidades regionais** e **11 dispositivos** do ADOM, consolidando o layout **MENSAL- RELATÓRIO GERAL** do FortiAnalyzer.

## Fluxo

1. `MensalReportPipeline.fetch_hierarchy` — importa/baixa JSON por dispositivo.  
2. `UnifiedMensalPdfBuilder.build` — monta story ReportLab e `multiBuild` (sumário + páginas).  

## Estrutura do PDF

| Parte | Template | Módulo |
|-------|----------|--------|
| Capa | `cover` (full bleed) | `pdf/cover_page.py` |
| Sumário | `toc` | `pdf/mensal_toc.py` |
| Conteúdo | `main` | `pdf/unified_mensal_builder.py` |
| Cabeçalho/rodapé internos | `onPage` | `pdf/internal_page.py` |

## Seções por dispositivo (exemplos)

- **Resumo Executivo** — cards KPI, donut permitidas/bloqueadas, gauge SD-WAN  
- **Segurança Ampliada** — cards KPI + barras de risco/bloqueio  
- Gráficos executivos (barras H, donuts) nas seções de usuários, categorias, sites, SD-WAN e políticas  

- Resumo de utilização web  
- Timeline consumo de banda  
- Top usuários (permitidos / bloqueados)  
- Categorias + Top 20 sites + gráfico rosca  
- Application visibility, risco, phishing  
- SD-WAN (apps, destinos, usuários)  
- Políticas por banda/sessão  

## Parâmetros CLI

| Flag | Efeito |
|------|--------|
| `--days 60` | Janela de busca de relatórios no FAZ |
| `--metadata-only` | Não baixa; usa cache se validado |
| `--no-charts` | Só tabelas (mais rápido) |
| `--force-download` | Ignora JSON em cache |

## Saída

`output/MENSAL_UNIFICADO_{FAZ_ADOM}.pdf` — nome fixo, sobrescrito a cada geração.

## Código principal

- `src/forti_report/pdf/unified_mensal_builder.py`  
- `src/forti_report/services/mensal_pipeline.py`  
