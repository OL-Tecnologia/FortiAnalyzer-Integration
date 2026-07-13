# Relatório para tomada de decisão — Conteúdo FAZ no PDF Cruz Azul

**Data:** 2026-06-08  
**Escopo:** PDF MENSAL unificado · exports JSON/PDF FortiAnalyzer  
**Status:** Etapas 2 e 3 **implementadas** nesta entrega

---

## 1. Contexto

O FortiAnalyzer exporta relatórios **MENSAL- RELATÓRIO GERAL** em JSON (prioritário), XML ou PDF. O PDF Cruz Azul reutiliza dados tabulares e gráficos Plotly, mas **descartava**:

| # | Lacuna | Impacto |
|---|--------|---------|
| 1 | Textos estruturais (capa, sumário FAZ, parágrafos) | Sem perda operacional — recriamos layout próprio |
| **2** | **Títulos de seção inteiros ignorados** | Gestor não via escopo completo do layout FAZ |
| **3** | **Texto em gráficos/widgets não capturado** | KPIs e charts sem tabela equivalente sumiam |
| 4 | Texto tabular parcial (regex PDF) | Dados incompletos no fallback PDF |
| 5 | Campos parseados não exibidos | Ex.: `device_names`, `sites (ref.)` |

Este documento registra **decisões** e o que foi **aplicado**.

---

## 2. Decisões tomadas

### 2.1 Etapa 2 — Títulos de seção FAZ ✅ **Implementada**

**Decisão:** incluir seção **«Referência — Conteúdo FortiAnalyzer (FAZ)»** por dispositivo, com tabela de **todos os títulos** detectados no export.

| Fonte | Método |
|-------|--------|
| JSON | Títulos decodificados de cada `chart.name` / macro (`faz_inventory.decode_chart_title`) |
| PDF | `extract_pdf_section_headings()` sobre `extract_text()` (`wan_pdf.py`) |

**Não replicamos** o sumário paginado do FAZ — apenas **inventário textual** para auditoria e decisão.

### 2.2 Etapa 3 — Texto de gráficos e widgets ✅ **Implementada**

**Decisão:** para cada chart/macro do export:

1. **Widgets/macros** → tabela `Widget | Valor` (inclui `mensal.macros` + macros do inventário).
2. **Gráficos** → **prévia tabular** (até 5 linhas) com células `coluna: valor` do JSON, ou linhas extraídas do PDF.
3. Marcar cada bloco: `renderizado` vs `não renderizado` + campo interno (`mapped_field`).

**Limite:** até 18 charts por dispositivo no PDF (prioridade: não renderizados primeiro).

### 2.3 Etapas adiadas (próxima iteração)

| Etapa | Decisão | Motivo |
|-------|---------|--------|
| 1 — Textos narrativos FAZ | **Adiar** | Substituídos por textos Cruz Azul; baixo ROI |
| 4 — Parser PDF completo | **Adiar** | JSON é fonte principal; ampliar regex sob demanda |
| 5 — Campos órfãos | **Parcial** | Apêndice de dispositivos pode ir para tabela global futura |

---

## 3. Implementação técnica

| Componente | Arquivo |
|------------|---------|
| Modelo `FazChartRecord`, campos `faz_*` | `data/mensal_models.py` |
| Inventário JSON/PDF | `data/parsers/faz_inventory.py` |
| Populate no parse JSON | `data/parsers/mensal_json.py` |
| Populate no parse PDF | `data/parsers/wan_pdf.py` → `mensal_pdf.py` |
| Seção PDF | `pdf/sections/faz_conteudo.py` |
| Integração | `pdf/unified_mensal_builder.py` (após Resumo Executivo) |
| Testes | `tests/test_faz_inventory.py` |

### Ordem no PDF (por dispositivo)

1. Cabeçalho (unidade, dispositivo, período)  
2. **Resumo Executivo**  
3. **Referência — Conteúdo FAZ** ← **novo**  
4. Análise Abrangente + demais seções  

---

## 4. Matriz de cobertura (pós-implementação)

| Conteúdo FAZ | Antes | Depois |
|--------------|-------|--------|
| Títulos de seção (JSON/PDF) | Ignorados | Tabela no PDF |
| Macros / widgets numéricos | Parcial (alguns KPIs) | Tabela completa |
| Texto tabular de charts | Só se mapeado | Prévia + status renderização |
| Gráficos visuais FAZ | Substituídos Plotly ou omitidos | Prévia textual se sem gráfico |
| Parágrafos introdutórios FAZ | Omitidos | Omitidos (decisão §2.3) |

---

## 5. Critérios de aceite

- [x] Dispositivo com JSON: seção FAZ lista títulos de charts e macros.  
- [x] Chart não mapeado aparece como «não renderizado» com prévia.  
- [x] Fallback PDF: títulos via `extract_text` + prévias das seções parseadas.  
- [x] Testes automatizados (`test_faz_inventory.py`).

---

## 6. Próximos passos sugeridos

1. Calibrar `faz_xml.py` com XML real (dados tabulares adicionais).  
2. Promover charts «não renderizados» frequentes a seções Plotly dedicadas.  
3. Script `scripts/audit_faz_pdf_text.py` para diff linha-a-linha PDF FAZ vs inventário.  
4. Apêndice global com `device_names` do PDF consolidado.

---

## 7. Referências

- README → «Próximos passos»  
- `scripts/compare_mensal_coverage.py` — gaps históricos  
- `doc/features/mensal-unificado.md`
