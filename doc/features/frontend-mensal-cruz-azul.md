# Feature — Frontend web MENSAL (CRUZ_AZUL)

**Status:** ✅ V1  
**Cliente:** CRUZ_AZUL (único; multi-cliente na V2)

## Objetivo

Interface web para operadores gerarem o PDF MENSAL unificado sem usar a CLI, com feedback visual de cada etapa e download do arquivo final.

## Como executar

```powershell
cd c:\scr\fortiAnalyzer
.\.venv\Scripts\pip install -e ".[dev]" fastapi uvicorn
.\.venv\Scripts\python.exe -m forti_report.api.app
```

Abrir no navegador: **http://localhost:8000**

Alternativa:

```powershell
.\.venv\Scripts\forti-web.exe
```

## Funcionalidades da UI

| Elemento | Descrição |
|----------|-----------|
| Badge ADOM | Lê `/api/client` (CRUZ_AZUL + schedule) |
| Gerar relatório | Inicia job assíncrono |
| Barra de progresso | Percentual + mensagem da etapa atual |
| Log de etapas | Histórico (FAZ, cada antena, PDF, cache) |
| Opções | Incluir gráficos; forçar download FAZ |
| Baixar PDF | Habilitado ao concluir (`/api/.../download`) |

## API

| Método | Rota | Uso |
|--------|------|-----|
| GET | `/api/client` | Metadados do cliente |
| POST | `/api/reports/mensal/generate` | Cria job |
| GET | `/api/reports/mensal/jobs/{id}/stream` | SSE progresso |
| GET | `/api/reports/mensal/jobs/{id}/download` | PDF |
| GET | `/api/health` | Health check |

## Etapas de progresso (backend)

1. Início / conexão FAZ  
2. Cache (se `--metadata-only` equivalente)  
3. Metadados no FAZ  
4. Por antena: `Antena X/N: {nome}`  
5. Hierarquia  
6. Geração PDF  
7. Cache de gráficos  
8. Concluído + URL de download  

## Código

- `frontend/` — HTML, CSS, JS  
- `src/forti_report/api/app.py` — FastAPI  
- `src/forti_report/services/mensal_job.py` — job em thread  
- `src/forti_report/services/mensal_pipeline.py` — callback `on_progress`  

## Limitações V1

- Um cliente por instância (`.env` / `FAZ_ADOM`)  
- Credenciais FAZ ainda via `.env` — login na tela planejado em [login-faz-sessao.md](login-faz-sessao.md)  
- Jobs só em memória (reiniciar servidor perde histórico)  
- Geração longa (~minutos na 1ª vez) — manter aba aberta ou usar fallback polling  
