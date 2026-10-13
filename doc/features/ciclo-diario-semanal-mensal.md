# Feature — Ciclo diário, semanal e mensal

**Status:** em implementação  
**Entrega:** PDF diário, semanal e mensal a partir da colheita dos 10 layouts.

## Objetivo

Três PDFs por cliente. O diário sai todo dia às 06:00 e usa o arquivo que o FortiAnalyzer gravou às 08:00 do dia anterior. O semanal sai na segunda às 06:00, junto com o diário. O mensal sai no dia 1 às 06:00, junto com o diário. Hora e minuto são do cliente; 06:00 é o padrão.

O programa não lê log bruto. Baixa o relatório já gerado no FAZ. O prefixo escolhe o layout. O hostname depois do prefixo só identifica o firewall e muda de cliente para cliente.

## Calendário

| Marco | Padrão | Quem configura |
|-------|--------|----------------|
| Fechamento do diário no FAZ | Todo dia 08:00 | Horário do layout no FortiAnalyzer |
| Semana de conteúdo | Segunda a domingo já encerrada | Fixo na regra de negócio |
| Disparo diário | Todo dia 06:00 | Admin do cliente (hora, minuto, fuso) |
| Disparo semanal | Segunda 06:00, junto com o diário | Admin do cliente (hora e minuto) |
| Disparo mensal | Dia 1 às 06:00, junto com o diário | Admin do cliente (hora e minuto) |

Se o dia 1 cair numa segunda, os três PDFs saem na mesma leva das 06:00. O diário das 06:00 usa o arquivo que o FAZ já gravou às 08:00 do dia anterior.

## O que cada PDF reúne

### Diário

Um PDF com o arquivo **RELATÓRIO DIÁRIO DE CONFIGURAÇÕES** já fechado.

| Campo | Valor |
|-------|--------|
| Prefixo | `RELATÓRIO DIÁRIO DE CONFIGURAÇÕES` |
| Janela no FAZ | Últimas 24 horas, geração diária às 08:00 |
| Disparo padrão | Todo dia 06:00 |

### Semanal

Um PDF com os quatro layouts semanais e um resumo dos diários dessa semana (segunda a domingo).

| Prefixo | Janela no FAZ |
|---------|----------------|
| `SEMANAL- RELATÓRIO TRÁFEGO WAN` | 7 dias (há um espaço depois do hífen) |
| `SEMANAL-RELATÓRIO CONSUMO DE BANDA` | 7 dias |
| `SEMANAL-RELATÓRIO DE ENDPOINT` | 7 dias |
| `SEMANAL-RELATÓRIO SISTEMA` | 7 dias |

Disparo padrão: segunda 06:00, no mesmo horário do diário.

### Mensal

Um PDF com os cinco layouts mensais. Layout sem arquivo gerado entra no PDF com a indicação de que o FortiAnalyzer ainda não o gerou.

| Prefixo |
|---------|
| `MENSAL- RELATÓRIO TRÁFEGO WAN` |
| `MENSAL-RELATÓRIO CONSUMO DE BANDA` |
| `MENSAL-RELATÓRIO DE ENDPOINT` |
| `MENSAL-RELATÓRIO MENSAL DE CONFIGURAÇÕES` |
| `MENSAL-RELATÓRIO SISTEMA` |

Disparo padrão: dia 1 às 06:00, junto com o primeiro diário do mês.

## Configuração por cliente

Nada de horário fixo no código. Cada tenant guarda o próprio disparo, no mesmo espírito de `schedule.day` / `hour` / `minute` do mensal.

| Campo | Diário | Semanal | Mensal |
|-------|--------|---------|--------|
| Ligado | sim/não | sim/não | sim/não |
| Quando | todo dia | segunda | dia 1 |
| Hora | 6 | 6 | 6 |
| Minuto | 0 | 0 | 0 |
| Fuso | `America/Sao_Paulo` | idem | idem |
| Prefixos FAZ | o diário acima | os quatro semanais | os cinco mensais |

E-mail (de, para, cópia, alerta, prefixo do assunto) continua por tenant. Assunto distingue diário, semanal e mensal.

## Busca no FortiAnalyzer

1. Listar relatórios `generated` do dispositivo.
2. Ficar só com nome ou título que contém o prefixo daquele PDF. Um diário não substitui um semanal, e um semanal não substitui um mensal.
3. O sufixo (`fw-cas-cruz-azul-colegio`, `MLGOMES_FG4H0E`, etc.) não filtra a hierarquia.
4. Baixar JSON, depois XML, depois PDF.
5. Parser de endpoint não serve para configurações, sistema, banda ou WAN. Cada prefixo novo só entra no PDF depois de um JSON real com os títulos dos gráficos.

## Fora deste ciclo

- Pipeline legado `SEMANAL- RELATÓRIO TRÁFEGO WAN` (`services/wan_pipeline.py`) lê PDF de referência e não é o semanal deste documento.
- Log bruto de tráfego, evento ou UTM não é fonte.

## Critérios de aceite

- [ ] Admin altera hora e minuto sem mudar código. O dia do diário, da segunda e do dia 1 segue a regra acima.
- [ ] Com o padrão, o diário sai todo dia às 06:00 com o arquivo das 08:00 do dia anterior.
- [ ] Na segunda às 06:00 saem o diário e o semanal. O semanal traz os quatro prefixos e o resumo dos diários de segunda a domingo.
- [ ] No dia 1 às 06:00 saem o diário e o mensal. O mensal traz os cinco prefixos.
- [ ] Se o dia 1 for segunda, os três saem juntos.
- [ ] Hostname fora de `fw-{região}-{site}` continua no PDF.
- [ ] Prefixo errado não pega o arquivo mais novo de outro layout.
