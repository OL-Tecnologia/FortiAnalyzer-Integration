# Feature — Performance na geração de PDF

**Status:** ✅ V1 (otimizações aplicadas)

## Gargalos identificados

| Etapa | Causa | Mitigação V1 |
|-------|--------|----------------|
| Logo SVG no cabeçalho | PNG gigante (milhares de px) | Raster ~240×50 px + cache disco |
| Logo em cada página | Novo `ImageReader` por página | Reuso do mesmo reader + prewarm |
| Gráficos Plotly | Kaleido (1ª vez sem cache) | `chart_cache/` por TID |
| `multiBuild` | Duas passagens (sumário) | Necessário para “Página X de Y” |
| Import FAZ | Login + listagem | Cache hierarquia se metas válidas |

## Tempos de referência (ambiente de dev)

| Cenário | Ordem de grandeza |
|---------|-------------------|
| 1ª geração (download + Kaleido frio) | ~3–4 min |
| Geração com cache quente | ~6–9 s |
| Sem gráficos (`--no-charts`) | ~6 s |
| `fetch` só cache validado | ~0,1 s |

## Comandos

```powershell
# Desenvolvimento rápido
.\.venv\Scripts\python.exe -m forti_report.cli generate-mensal-unified --days 60 --metadata-only --no-charts

# Medição
.\.venv\Scripts\python.exe scripts\profile_pdf.py
```

## Código

- `pdf/internal_page.py` — logo otimizado  
- `charts/plotly_charts.py` — `cache_scope`  
- `scripts/profile_pdf.py`  

## V2

Cache e profiling **por cliente**; fila de jobs assíncronos para geração longa no portal.
