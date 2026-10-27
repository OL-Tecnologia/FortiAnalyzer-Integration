# Feature — Agendamento mensal + e-mail

**Status:** ✅ V1  
**Comando:** `run-scheduled-mensal`

## Objetivo

No **dia 5 de cada mês, às 06:00** (configurável), gerar automaticamente o PDF MENSAL unificado e enviá-lo por e-mail ao cliente, com alerta interno em caso de falha.

## Arquitetura híbrida

| Gatilho | Uso |
|---------|-----|
| **Scheduler interno** | Inicia com o portal FastAPI quando `MENSAL_SCHEDULE_ENABLED=true` |
| **Task Scheduler Windows** | Chama `scripts/run-scheduled-mensal.ps1` como backup |

Ambos usam a mesma rotina (`run_scheduled_mensal`). A **idempotência** (`output/scheduler/scheduler_state.json`) evita envio duplicado no mesmo mês.

## Fluxo

1. Verifica se já enviou com sucesso no período `YYYY-MM`.
2. Verifica janela agendada (dia/hora + fuso).
3. Gera PDF via `MensalReportPipeline` com `--force-download` (cache desligado).
4. Envia e-mail com anexo PDF.
5. Em falha: alerta para `SMTP_ALERT_TO` e retry conforme configuração.

## E-mail

| Campo | Onde configurar |
|-------|-----------------|
| De / Para / Alerta | `.env` local ou UI Admin do tenant — **não versionar e-mails reais (LGPD)** |
| Assunto | Prefixo por tenant + mês/ano |

Corpo fixo em `services/email_delivery.py`.

### SMTP — configuração correta

| Cenário | Host | Porta | Auth |
|---------|------|-------|------|
| **Office 365 (recomendado)** | `smtp.office365.com` | 587 + STARTTLS | Sim (mailbox de serviço + senha) |
| **Relay interno** | host do relay da rede | 25 | Não (só na rede interna/VPN) |
| **Errado** | `*.mail.protection.outlook.com` | — | MX de **entrada**, não envia como mailbox |

**Importante:** envio via SMTP relay **não aparece** em "Itens enviados" do Outlook da mailbox de serviço. Só mensagens enviadas pelo Outlook/Webmail aparecem lá.

## Configuração (.env) — produção + campos editáveis

Tudo que muda por cliente ou política de segurança fica no **`.env`** (nunca no código).

| Grupo | Variáveis | Configurável? |
|-------|-----------|---------------|
| Login FAZ (automação) | `FAZ_USER`, `FAZ_PASSWORD` | Sim — conta de serviço |
| Dia / hora | `MENSAL_SCHEDULE_DAY`, `_HOUR`, `_MINUTE`, `_TIMEZONE` | Sim |
| Destinatários | `SMTP_FROM`, `SMTP_TO`, `SMTP_CC`, `SMTP_ALERT_TO` | Sim |
| SMTP | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Sim |

**Segurança / LGPD**
- `.env` está no `.gitignore` — senhas e e-mails reais **não** entram no Git
- Templates (`.env.example`, `install/config.env`, YAMLs de exemplo) vêm **sem** dados pessoais
- Assistente mascará senhas no resumo (`configurar-agendamento.bat`)
- Portal web continua com login na tela; a rotina agendada usa só `FAZ_*` / e-mails do `.env` ou do tenant (Admin)

```env
FAZ_USER=                    # conta de serviço (configurável)
FAZ_PASSWORD=                # segredo — só no .env local

MENSAL_SCHEDULE_ENABLED=true
MENSAL_SCHEDULE_DAY=5        # configurável
MENSAL_SCHEDULE_HOUR=6       # configurável
MENSAL_SCHEDULE_MINUTE=0
MENSAL_SCHEDULE_TIMEZONE=America/Sao_Paulo

SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_AUTH=true
SMTP_USER=                   # mailbox de serviço — só no .env local
SMTP_PASSWORD=               # segredo — só no .env local
SMTP_FROM=                   # só no .env local / Admin
SMTP_TO=                     # destinatário cliente — só no .env local / Admin
SMTP_ALERT_TO=               # alerta interno — só no .env local / Admin
```

Assistente: `configurar-agendamento.bat` ou `scripts\configure_scheduler.py`

**Painel web** (após login): seção **Configuração da automação** em `/` — mesmos campos (FAZ, dia/hora, e-mails), com senhas mascaradas (não retornadas pela API).
API: `GET/PUT /api/settings/automation` (requer sessão).


## Comandos

```powershell
# Configuração interativa (.env)
configurar-agendamento.bat
# ou
powershell -ExecutionPolicy Bypass -File scripts\configure-scheduler.ps1

# Ver configuração atual (senhas mascaradas)
.\.venv\Scripts\python.exe scripts\configure_scheduler.py --show

# Rotina agendada (Task Scheduler)
powershell -ExecutionPolicy Bypass -File scripts\run-scheduled-mensal.ps1

# Teste manual (ignora horário e idempotência)
.\.venv\Scripts\python.exe -m forti_report.cli run-scheduled-mensal --force

# Status
.\.venv\Scripts\python.exe -m forti_report.cli scheduler-status
curl http://localhost:8000/api/scheduler/status

# Testar SMTP (sem enviar)
.\.venv\Scripts\python.exe -m forti_report.cli test-smtp --probe-only

# Testar envio de e-mail simples
.\.venv\Scripts\python.exe -m forti_report.cli test-smtp

# Reenviar PDF já gerado (sem regerar)
.\.venv\Scripts\python.exe -m forti_report.cli send-mensal-email
```

## Task Scheduler Windows

1. Gatilho: mensal, dia **5**, **06:00**
2. Ação: `powershell.exe -ExecutionPolicy Bypass -File "C:\...\fortiAnalyzer\scripts\run-scheduled-mensal.ps1"`
3. Conta com acesso ao FAZ e permissão de escrita em `output/`

## Logs e estado

| Arquivo | Função |
|---------|--------|
| `output/scheduler/scheduler_state.json` | Último período, status, tentativas |
| `output/logs/scheduler-YYYY-MM-DD.log` | Log diário da rotina |
| `output/logs/email-YYYY-MM-DD.log` | Log de envios SMTP |

## Código

- `src/forti_report/services/mensal_scheduler.py`
- `src/forti_report/services/email_delivery.py`
- `src/forti_report/config.py` (variáveis `MENSAL_SCHEDULE_*`, `SMTP_*`)

## Retry

Se falhar, tenta novamente até `MENSAL_SCHEDULE_MAX_RETRIES` (padrão 3), com intervalo de `MENSAL_SCHEDULE_RETRY_HOURS` (padrão 2h).
