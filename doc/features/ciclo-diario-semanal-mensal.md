# Feature — Ciclo diário, semanal e mensal

**Status:** 📋 Planejado  
**Entrega atual (V1):** só o PDF **MENSAL-RELATÓRIO DE ENDPOINT**, disparo padrão dia 5 às 06:00.

## Objetivo

Três PDFs por cliente, cada um com e-mail próprio. O FortiAnalyzer fecha o período no **domingo às 08:00**. O disparo padrão dos três é **segunda às 06:00**, já com o arquivo de domingo. Dia, hora e minuto são do cliente: o padrão só vale até alguém alterar no admin.

O programa não lê log bruto. Baixa o relatório já gerado no FAZ. O prefixo escolhe o layout. O hostname depois do prefixo só identifica o firewall e muda de cliente para cliente.

## Calendário

| Marco | Padrão | Quem configura |
|-------|--------|----------------|
| Fechamento no FAZ | Domingo 08:00 | Horário do layout no FortiAnalyzer |
| Semana de conteúdo | Segunda a domingo | Fixo na regra de negócio; o dia do *envio* é configurável |
| Disparo diário | Segunda 06:00 | Admin do cliente (dia, hora, minuto, fuso) |
| Disparo semanal | Segunda 06:00 | Admin do cliente |
| Disparo mensal | Segunda 06:00, na segunda seguinte ao fechamento do mês | Admin do cliente |

O diário das 08:00 não sai no mesmo minuto em que o FAZ grava o arquivo. O e-mail da segunda 06:00 usa os arquivos que já fecharam, o último deles no domingo às 08:00.

## O que cada PDF reúne

### Diário

Um PDF com os arquivos **RELATÓRIO DIÁRIO DE CONFIGURAÇÕES** de segunda a domingo.

| Campo | Valor |
|-------|--------|
| Prefixo | `RELATÓRIO DIÁRIO DE CONFIGURAÇÕES` |
| Janela no FAZ | Últimas 24 horas, geração diária às 08:00 |
| Disparo padrão | Segunda 06:00 |

### Semanal

Um PDF com os quatro layouts semanais e um resumo dos diários dessa semana (segunda a domingo).

| Prefixo | Janela no FAZ |
|---------|----------------|
| `SEMANAL-RELATÓRIO DE ENDPOINT` | 7 dias |
| `SEMANAL-RELATÓRIO CONSUMO DE BANDA` | 7 dias |
| `SEMANAL-RELATÓRIO SISTEMA` | 7 dias |
| `SEMANAL- RELATÓRIO TRÁFEGO WAN` | 7 dias (há um espaço depois do hífen) |

Disparo padrão: segunda 06:00. No FAZ esses layouts nascem na sexta; a segunda de manhã usa o arquivo da sexta anterior mais os diários até o domingo 08:00.

### Mensal

Um PDF com os layouts mensais. O de endpoint já existe no V1. Os outros quatro entram neste ciclo.

| Prefixo | Já no PDF V1 |
|---------|----------------|
| `MENSAL-RELATÓRIO DE ENDPOINT` | Sim |
| `MENSAL- RELATÓRIO TRÁFEGO WAN` | Não (espaço depois do hífen) |
| `MENSAL-RELATÓRIO CONSUMO DE BANDA` | Não |
| `MENSAL-RELATÓRIO MENSAL DE CONFIGURAÇÕES` | Não |
| `MENSAL-RELATÓRIO SISTEMA` | Não |

Disparo padrão: segunda 06:00, na segunda seguinte ao fechamento do mês. O V1 ainda dispara no dia 5 às 06:00; a troca desse padrão faz parte desta feature.

## Configuração por cliente

Nada de horário fixo no código. Cada tenant guarda o próprio disparo, no mesmo espírito de `schedule.day` / `hour` / `minute` do mensal.

| Campo | Diário | Semanal | Mensal |
|-------|--------|---------|--------|
| Ligado | sim/não | sim/não | sim/não |
| Dia da semana ou do mês | padrão: segunda | padrão: segunda | padrão: a segunda seguinte ao fechamento |
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

- [ ] Admin altera dia e hora do diário, do semanal e do mensal sem mudar código.
- [ ] Com o padrão, os três e-mails saem na segunda às 06:00 e incluem o fechamento de domingo 08:00.
- [ ] O semanal traz os quatro prefixos semanais e o resumo dos diários de segunda a domingo.
- [ ] O mensal traz os cinco prefixos mensais.
- [ ] Hostname fora de `fw-{região}-{site}` continua no PDF.
- [ ] Prefixo errado não pega o arquivo mais novo de outro layout.
