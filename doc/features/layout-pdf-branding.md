# Feature — Layout e branding PDF (MENSAL)

**Status:** ✅ V1 (Cliente + OL)

## Capa

- Faixa superior: `cabecalho_capa.png` — **padrão OL fixo** (não configurável por cliente)  
- Miolo: texto (`RELATÓRIO MENSAL GERAL`, ADOM, unidades/dispositivos FAZ, mês/ano) + **logo do cliente** (upload por tenant)  
- Faixa inferior: `rodape_capa.png` — **padrão OL fixo** (não configurável por cliente)  

**Módulo:** `pdf/cover_page.py` — prévia na admin em `/admin.html`

## Páginas internas (corpo)

- Faixa `cabecalho-interno.png` (altura proporcional à largura A4)  
- Logo OL: `logo-horizontal-gray.svg` rasterizado PNG transparente, ~4,25 cm largura  
- Rodapé tipográfico: linha `#9B1C1C`, texto `RELATORIO MENSAL GERAL — {ADOM}`, `Página X de Y`  

**Módulo:** `pdf/internal_page.py`

## Conteúdo

- Margens laterais **70 pt (2,50 cm)** — `page_layout.py`  
- Tabelas: cabeçalho 9 pt, centralizado, sem quebra em títulos — `table_utils.py`  
- `KeepTogether` para título + tabela + gráfico — `unified_mensal_builder._pack_section`  

## Sumário

- `TableOfContents` ReportLab, estilos compactos, pontilhado  
- Entradas: resumo global, unidades regionais, dispositivos (subseções detalhadas fora do TOC)  

**Módulo:** `pdf/mensal_toc.py`

## V2

Branding por cliente via config (logos/cores/textos), sem alterar código por ADOM.
