# Feature — Cache e fechamento mensal

**Status:** ✅ V1

## Regra de negócio

- **Nomes de arquivo fixos** (`fw-norte-matriz.json`, PDF `MENSAL_UNIFICADO_ADOM_EXEMPLO.pdf`).  
- **Conteúdo sempre do relatório atual** no FAZ — nunca reutilizar mês anterior por engano.

## Como funciona

### 1. Cache JSON (`output/faz_mensal/`)

| Arquivo | Função |
|---------|--------|
| `{device}.json` | Export JSON do FAZ (sobrescrito no download) |
| `{device}.meta.json` | `tid`, `period_start`, `period_end`, `cached_at` |

Antes de usar o JSON, o sistema compara **TID** (e período quando disponível) com o relatório MENSAL mais recente no FAZ (`json_cache_is_fresh` em `services/mensal_cache.py`).

- TID mudou (novo mês) → baixa de novo e sobrescreve.  
- Sem `.meta.json` → cache considerado inválido → baixa de novo.

### 2. Cache de gráficos (`output/chart_cache/`)

- PNG em subpastas identificadas por **escopo** `tid:{faz_tid}`.  
- Chave Plotly inclui escopo + tipo de gráfico + dimensões.  
- Ao final da geração, `prune_stale_chart_cache` remove pastas de TIDs antigos.

### 3. Preferência de cache

`FAZ_PREFER_CACHE=true` (padrão): usa JSON local **somente se** for o relatório atual no FAZ.

`--force-download`: ignora preferência e baixa tudo de novo.

## Comando recomendado (fim de mês)

```powershell
.\.venv\Scripts\python.exe -m forti_report.cli generate-mensal-unified --days 60
```

Rotina rápida (mesmo TID no FAZ, cache já válido):

```powershell
.\.venv\Scripts\python.exe -m forti_report.cli generate-mensal-unified --days 60 --metadata-only
```

## Código

- `src/forti_report/services/mensal_cache.py`  
- `src/forti_report/services/mensal_pipeline.py` (`_load_mensal_content`, `_fetch_hierarchy_from_cache`)  

## Limitação V1

Cache e saída são **globais** em `output/` — um único ADOM por ambiente. Multi-cliente isolado → **V2**.
