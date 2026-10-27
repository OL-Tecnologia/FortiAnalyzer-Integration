# Feature — Segredos por cliente e e-mail de envio

**Status:** planejado. Este documento só registra a correção. Não altera o código.  
**Data:** 2026-10-27  
**Relacionado:** [multi-tenant-clientes-faz.md](multi-tenant-clientes-faz.md), [agendamento-email-mensal.md](agendamento-email-mensal.md), [ciclo-diario-semanal-mensal.md](ciclo-diario-semanal-mensal.md)

## Problema

A instalação que fica na máquina do cliente guarda, em texto puro, a senha da conta que entra no FortiAnalyzer. Quem abre a pasta, copia o zip ou pega um backup lê essa senha e entra na API com o mesmo usuário que o programa usa às 6h. Se a conta for Super_User, o invasor administra o FortiAnalyzer.

O Git não é o problema. Para o Git vai o sistema limpo. O problema é o disco da instalação.

Hoje existem dois arquivos legíveis no Bloco de Notas, ao lado do executável:

| Segredo | Onde está | Como é gravado |
|---------|-----------|----------------|
| Senha do Super Admin do portal | `.env` → `PORTAL_ADMIN_PASSWORD` | Texto puro. A primeira entrada em `/admin.html` cria a senha e grava no `.env`. Não há senha padrão |
| Senha do FortiAnalyzer do cliente | `configs\clients\.secrets\<slug>.yaml` → `faz_password` | Texto puro. `save_secret_password` em `src/forti_report/clients/store.py` |
| Usuário e senha da caixa que envia | `.env` → `SMTP_USER`, `SMTP_PASSWORD` | Texto puro. Uma conta para a instalação inteira. As telas não têm esses campos |

A pasta `.secrets` só impede o commit. No Windows ela aparece como qualquer outra pasta. Não há criptografia nem permissão restringindo a leitura.

O cadastro público `configs\clients\<slug>.yaml` não contém a senha do FortiAnalyzer. A API só responde se a senha está preenchida. A proteção acaba nesse ponto.

## O que não muda

- Um executável atende vários cadastros.
- Cada cadastro continua com o próprio FortiAnalyzer, ADOM, horário e destinatários.
- Diário, semanal e mensal continuam no horário já configurado por relatório.
- A colheita, os PDFs e o sumário não entram nesta correção.
- Servidor SMTP da instalação continua `smtp.office365.com`, porta 587, TLS. Isso fica no `.env` porque é da instalação, não do cliente.

## Como fica

| | Hoje | Depois |
|---|---|---|
| Senha do FortiAnalyzer | `configs\clients\.secrets\<slug>.yaml`, texto puro | Mesma pasta, criptografada com a conta do Windows que executa o programa. A pasta só é lida por essa conta |
| Quem só abre a pasta | Lê a senha | Vê arquivo ilegível |
| Quem já executa programa como o usuário que abre o executável | Lê a senha | Ainda recupera, porque o programa precisa da senha às 6h |
| Conta no FortiAnalyzer | A que foi digitada. Super_User abre o FortiAnalyzer todo | Uma conta por ADOM, só leitura de relatório. No FortiAnalyzer, o login só é aceito do IP da máquina que roda o programa |
| Várias filiais no mesmo FortiAnalyzer | Um cadastro por ADOM, cada um com o próprio destinatário. Uma senha de administrador único abre todas as filiais | Uma senha por ADOM. A senha da filial A não entra na filial B |
| Servidor da OL | A senha fica no disco desse servidor, em texto puro | A senha fica só nesse servidor. O PC do cliente não tem senha; recebe o PDF |
| Super Admin do portal | Texto no `.env`, criado na primeira entrada. A tela não mostra senha | Definida na primeira entrada, armazenada como hash ou cifra da conta do Windows, sem senha escrita na tela |
| Caixa que envia | Uma no `.env`, editada à mão | Gravada pelo cadastro. Por cliente, ou uma só no servidor da OL |

Criptografar o arquivo fecha a leitura por outro usuário do Windows, por zip e por backup. Não fecha o caso de quem já controla a conta que executa o programa. Para um ataque no PC do cliente não abrir o FortiAnalyzer, a senha não pode estar nesse PC: a colheita roda no servidor da OL ou numa VM só do coletor.

## Onde cada instalação guarda a senha

| Instalação | Onde o programa roda | Onde a senha fica | O que o cliente recebe |
|------------|----------------------|-------------------|------------------------|
| Direto no cliente | PC ou servidor do cliente | Nesse disco, criptografada | PDF por e-mail. A senha está na máquina dele |
| Mesmo FortiAnalyzer, duas ou mais filiais | A mesma instalação | Uma senha de FortiAnalyzer e uma caixa de envio por ADOM | Cada TI recebe só o PDF da sua filial |
| Servidor da OL | Servidor que a OL controla | Só nesse servidor | O PDF. O PC do cliente não guarda senha |
| VM do coletor | VM na rede do cliente, administrada pela OL | Só nessa VM | O PDF. O PC dos funcionários não vê a pasta |

Requisito operacional, configurado no FortiAnalyzer, não no código: a conta de automação enxerga um único ADOM, com leitura de relatório, e o trusted host é o IP da máquina que roda o programa. Uma conta com acesso a todos os ADOMs continua abrindo todas as filiais, mesmo com o arquivo criptografado.

A senha que já está em texto numa pasta instalada ou num zip enviado precisa ser trocada no FortiAnalyzer. A migração do arquivo não apaga a cópia que já vazou.

## Cadastro de e-mail

Hoje o Super Admin e a conta logada gravam, no YAML do cliente, remetente, destinatário, cópia e alerta. Usuário e senha da caixa que envia não têm campo. Com um cliente na sessão, salvar a automação não escreve `SMTP_USER` nem `SMTP_PASSWORD`. O texto da tela diz que o SMTP técnico permanece no `.env`.

Destinatário vazio herda o `SMTP_TO` do `.env`. Com esse campo preenchido por outro cliente, o PDF segue para a caixa errada.

Depois, as duas telas gravam por cliente:

- usuário e senha do FortiAnalyzer daquele ADOM;
- usuário e senha da caixa que envia aquele ADOM;
- remetente, destinatário, cópia e alerta.

A senha digitada não volta para a tela. O campo mostra só que já existe senha. Salvar de novo sem preencher a senha conserva a anterior. O YAML público continua sem segredo. O arquivo cifrado fica em `configs\clients\.secrets\<slug>.yaml`, no lugar do YAML em texto.

Há dois modos de envio, escolhidos na instalação:

| Modo | Quando usar | O que o cadastro do cliente guarda |
|------|-------------|-------------------------------------|
| Caixa por cliente | Instalação no cliente ou filial com caixa própria | Usuário e senha SMTP daquele ADOM, mais os destinatários |
| Caixa única da OL | Servidor da OL, uma mailbox de serviço para todos | Só destinatários. A senha de envio é uma, no servidor, também cifrada |

Servidor, porta, TLS e a exigência de autenticação continuam no `.env` da instalação.

A tela de Super Admin deixa de exibir `AltereEstaSenha`. Na instalação limpa, a primeira entrada define a senha do portal. Ela não fica em texto no `.env`.

## Envio

Hoje, na hora marcada, o agendador percorre cada cliente com **Habilitar envio automático** ligado, entra no FortiAnalyzer daquele cadastro e autentica no Office 365 com a conta única do `.env`. O remetente pode ser o do cadastro. O Office 365 só aceita esse remetente se for a conta autenticada, ou se ela tiver permissão de enviar em nome da outra. Sem `SMTP_USER` e `SMTP_PASSWORD`, o envio não autentica. A falha vira aviso em log, o PDF fica marcado como sucesso e o mesmo período não é reenviado.

Depois, o mesmo horário dispara o mesmo PDF e autentica com a caixa gravada naquele cadastro. O remetente é essa caixa. Duas filiais às 6h geram dois envios. Cada um usa a própria conta do FortiAnalyzer, a própria caixa e o próprio destinatário.

Destinatário vazio não herda endereço de outro cadastro nem o `SMTP_TO` global. O PDF pode ser gerado. O e-mail não sai, e o estado do período registra a falha de envio para a retentativa já existente. A falha deixa de ser só um aviso que marca sucesso.

## Recebimento

O destinatário, a cópia e o alerta já são por cadastro. Isso permanece. Cada filial recebe só o PDF do próprio ADOM, no endereço do TI responsável. Quem está no destinatário da filial A não recebe o relatório da filial B.

## Migração

Na primeira execução depois da correção, o programa lê a senha em texto que já existir no `.secrets` e no `.env`, grava a cifra e apaga o texto puro. Não escreve a senha em log. Um `.env` de exemplo e o pacote limpo continuam sem senha.

Pacote de cliente continua sem YAML de cliente, sem `.secrets`, sem PDF e sem `.env` preenchido. O `.env` entregue é o modelo de `install\config.env`.

## Critério de pronto

- Abrir `configs\clients\.secrets\<slug>.yaml` no Bloco de Notas não mostra a senha do FortiAnalyzer nem a senha da caixa de envio.
- Super Admin e a conta logada gravam essas duas senhas sem editar o `.env` à mão.
- A tela não devolve a senha já gravada.
- Dois ADOMs na mesma instalação enviam para destinatários diferentes, cada um com a própria conta do FortiAnalyzer.
- Destinatário vazio não usa o endereço de outro cliente.
- `/admin.html` não mostra senha padrão.
- O pacote limpo e o Git continuam sem segredo de cliente.
- Quem só abre a pasta não lê a senha. A spec não promete proteção contra quem já executa código como o usuário do programa.

## Fora desta correção

- Criar o perfil e o trusted host dentro do FortiAnalyzer.
- Mudar horário, colheita ou layout dos PDFs.
- Fazer o executável virar serviço do Windows. Enquanto a janela precisar ficar aberta, o disparo das 6h continua dependendo disso.
