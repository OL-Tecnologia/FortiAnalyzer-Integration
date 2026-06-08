# Feature — Relatórios WAN (semanal)

**Status:** ✅ V1

## Objetivo

PDFs baseados no schedule **SEMANAL- RELATÓRIO TRÁFEGO WAN** do FortiAnalyzer, por unidade regional ou todas.

## Configuração

- `FAZ_WAN_REPORT_SCHEDULE` no `.env`  
- PDF de referência opcional em `tests/` ou `--pdf` na CLI  

## Comandos

```bash
python -m forti_report.cli generate-wan-all --days 60
python -m forti_report.cli generate-wan-unit spo --days 60
```

## Código

- `src/forti_report/services/wan_pipeline.py`  
- `src/forti_report/pdf/wan_regional_builder.py`  
- `src/forti_report/data/parsers/wan_pdf.py`  

## Saída

`output/wan_unidades/WAN_{unidade}_{data}.pdf`

## Relação com MENSAL unificado

Pipeline **separado** do MENSAL GERAL. Na V2, schedule WAN também deve ser configurável por cliente.
