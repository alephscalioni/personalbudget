# Pluggy — Open Finance BR

Cliente pra puxar contas, extrato e investimentos via [Pluggy](https://pluggy.ai).

## Setup (1x)

O `.env` já está criado (chmod 600, gitignorado) em:

```
~/brain-panel/workspaces/kaleu/scripts/finance/pluggy/.env
```

1. Consegue o par `CLIENT_ID` / `CLIENT_SECRET` (ver **Onde pegar a credencial** abaixo)
2. Preenche as duas linhas do `.env` (`nano .env`), ou roda `./set-credentials.sh`
   (input do secret oculto, sem passar por histórico de shell)
3. Testa: `./pluggy_client.py auth`

### Onde pegar a credencial

Duas rotas, **mesma API** — o cliente funciona igual nas duas.

**Meu Pluggy — grátis pra uso pessoal** (recomendada pro caso do Aleph):

1. `https://meu.pluggy.ai` → cria conta
2. Conecta os bancos lá dentro (é aqui que mora o vínculo com a instituição)
3. `https://dashboard.pluggy.ai` → cria conta. Já vem uma **aplicação demo**; pode usar ela
   ou criar uma Application nova
4. **Dentro da aplicação, no Dashboard**, adiciona uma conexão escolhendo o conector
   **Meu Pluggy** → login da conta Meu Pluggy → autoriza.
   ⚠️ O vínculo é feito do lado do Dashboard, não do Meu Pluggy. Cada banco novo
   conectado no Meu Pluggy precisa repetir essa autorização.
5. Copia `Client ID` + `Client Secret` da aplicação

Como o vínculo do banco é feito no Meu Pluggy, o `connect-page` daqui vira opcional —
os `itemId` saem do `./pluggy_client.py items` ou da própria UI.

O Dashboard abre com trial de ~15 dias, mas isso vale pros recursos **comerciais**:
uso pessoal via Meu Pluggy segue funcionando depois, sem custo e sem cartão.
Fonte: `https://meu.pluggy.ai/api-guide`.

**Dashboard puro** (sem Meu Pluggy) — trial de ~15 dias nos recursos comerciais, depois plano pago:

1. `https://dashboard.pluggy.ai` → **Applications** → nova Application
2. A tela mostra `Client ID` (UUID) e `Client Secret`
3. Vínculo de banco pelo widget: `./pluggy_client.py connect-page`

Ordem de precedência: env vars > `.env` da pasta > `--config CAMINHO`.

**Não mande a credencial por Telegram/Discord.** O texto fica no servidor da
plataforma e no transcript da sessão em `~/.claude/projects/…/*.jsonl`.
Se acontecer, rotacione o secret no dashboard.

### Estrutura

```
scripts/finance/pluggy/
├── .env                 ← credenciais (600, fora do git)
├── .env.example         ← modelo comentado
├── pluggy_client.py     ← biblioteca + CLI
├── set-credentials.sh   ← preenche o .env com input oculto
└── README.md
```

## Vincular um banco

A Pluggy não deixa o servidor mandar credencial de banco — o vínculo é feito
pelo **widget Connect**, no browser do Aleph.

```bash
./pluggy_client.py connect-page          # gera reports/pluggy-connect-YYYY-MM-DD.html
```

Abre o HTML, conecta o banco, e a tela mostra o **itemId**. Cola ele em
`PLUGGY_ITEM_IDS` no `config/pluggy.env` (csv pra vários bancos).

> O `connect_token` embutido no HTML vale ~30 min. Depois disso, regenerar.
> As credenciais do banco vão direto pro domínio da Pluggy — não passam
> por este arquivo nem pelo servidor.

## Comandos

| comando | o que faz |
|---|---|
| `auth` | força novo apiKey (cache em `~/.cache/kaleu/pluggy-apikey.json`, TTL 100min) |
| `connectors --busca nubank` | lista instituições suportadas |
| `connect-token [--item-id]` | JWT pro widget (com `--item-id` = modo update/reconexão) |
| `connect-page [--sandbox]` | gera o HTML do widget |
| `items` | lista vínculos (⚠️ `GET /v2/items` exige opt-in no time da Pluggy → pode dar 403) |
| `accounts [--item-id] [--tipo BANK\|CREDIT]` | contas + saldo |
| `transactions --account-id X [--dias 30]` | extrato com totais |
| `investments [--item-id] [--tipo ...]` | posição de investimentos |
| `summary` | consolidado: contas + investimentos + patrimônio líquido |

Flags globais: `--json` (saída crua), `--config CAMINHO`, `--no-cache`.

## Endpoints usados

| produto | endpoint | paginação |
|---|---|---|
| auth | `POST /auth` → `{apiKey}` | — |
| connect token | `POST /connect_token` → `{accessToken}` | — |
| items | `GET /v2/items` | cursor (`next`) |
| accounts | `GET /accounts?itemId=` | page/totalPages |
| transactions | `GET /v2/transactions?accountId=&dateFrom=&dateTo=` | cursor (`next`) |
| investments | `GET /investments?itemId=` | page/totalPages |

Header em tudo: `X-API-KEY: <apiKey>`. O cliente reautentica sozinho em 401/403.

## Gotchas

- **apiKey expira em 2h.** Cache com TTL de 100min + retry automático.
- **`GET /v2/items` é opt-in.** Se der 403, use `PLUGGY_ITEM_IDS` no config.
- **Cartão de crédito** vem com `type=CREDIT` e saldo positivo = dívida. O
  `accounts`/`summary` já inverte o sinal no líquido.
- Sandbox: `connect-page --sandbox` mostra os conectores fake pra testar sem banco real.
- **Compra internacional: `amount` NÃO está em BRL.** Quando `currencyCode != "BRL"`,
  o campo `amount` vem na moeda estrangeira e o valor convertido fica em
  `amountInAccountCurrency`. Somar `amount` cru mistura USD com BRL e subestima o
  gasto em ~5,3x. Use o helper `tx_amount(t)` do `pluggy_client.py` (ou o mesmo
  fallback) em qualquer agregação. No `--json` os dois campos vêm crus — a conversão
  é responsabilidade de quem consome.
- **Categorias da Pluggy erram feio em SaaS/infra.** Vistos na prática: `Railway` →
  *Public transportation*, `Anthropic* Claude Sub` → *Electronics*, `Jim.Com* Victoria Bet`
  → *Healthcare*. Pra bloco de infra/assinaturas, classifique por `description`, não por
  `category`.
- **O UUID da URL do dashboard é o `applicationId`, não o `itemId`.** `GET /items/<appId>`
  devolve 404 ITEM_NOT_FOUND. O `itemId` sai do widget de connect ou do `items`.
- **`--json` é flag GLOBAL**: `./pluggy_client.py --json transactions ...`. Depois do
  subcomando dá exit 2.
- **Cartão: agregue por ciclo de fatura, não por mês calendário.** Cada lançamento traz
  `creditCardMetadata.billForecastDate` (`"2026-09"`). Somar por `date[:7]` produz um
  número que não existe em lugar nenhum e não bate com o app do banco. Validação: a
  fatura set/26 fecha em R$ 15.752,53 com FX aplicado — exatamente o valor do
  "Pagamento recebido". Sem FX daria R$ 14.952,02.
- **IOF confirma a conversão.** O IOF cobrado é 3,50% do `amountInAccountCurrency`
  (Anthropic R$ 487,87 → IOF R$ 17,08). No Ultravioleta ele volta integral ("IOF de volta
  de X"), líquido zero — a compra internacional custa só o valor convertido.

## Consolidado multi-instituição

Três scripts, um por etapa — dá pra parar em qualquer uma:

```bash
./coleta_consolidada.py --dias 90        # API -> reports/consolidado-AAAA-MM-DD.json
./payload_consolidado.py <json>          # JSON bruto -> payload agregado (stdout)
./gera_dashboard_consolidado.py          # -> reports/patrimonio-consolidado-AAAA-MM-DD.html
```

O dashboard sai dark/light automático (segue o tema do sistema), com fatura por ciclo,
posição de investimentos com Δ contra o aplicado, gastos por categoria, parcelamentos
filtráveis por instituição e a lista de compras internacionais com o câmbio de cada uma.
Entrega por Telegram (`send-dashboard-telegram.sh`) — o gateway do Auren corrompe `.html`
no email.

Detalhes que não são óbvios no código:

- **`achados()` cruza a debênture com a ANBIMA.** Quando uma posição de debênture aparece
  bem abaixo do aplicado, o script lê o `db*.txt` mais recente de `financial-data/` e olha
  a coluna `% PU Par / % VNE`. Se estiver bem abaixo de 100, é amortização de principal,
  não prejuízo. Foi assim que o RESA27 (48,93% do VNE) deixou de parecer −39%.
- **Mesmo título em corretoras diferentes não é duplicidade** — o script confere datas de
  compra e quantidades antes de afirmar isso.
- **Chart.js precisa de `resize()` depois do primeiro paint.** O grid só define a largura
  final da coluna depois do layout; sem o resize o canvas congela a medida provisória e
  vaza pra fora do card. `animation:false` também é proposital: sem isso um screenshot
  headless pega o gráfico no meio da animação.
- Posições com saldo zero (liquidadas) são filtradas; o contador fica em `zeradas`.

## Dump completo em .json

`dump_pluggy.py` baixa tudo e guarda em disco:

```
financial-data/pluggy/
├── snapshots/AAAA-MM-DD/          retrato completo de cada execução
│   ├── items.json  accounts.json  investments.json  identity.json
│   └── transactions/<contaId>.json
├── ledger/
│   ├── transacoes.json            TODAS as transações já vistas, indexadas por id
│   └── posicoes.jsonl             1 linha por (data, papel) — série histórica
└── latest.json                    ponteiro pro snapshot mais recente
```

**Por que o ledger existe:** a API só devolve uma janela móvel. O que sai da janela
some da API, mas fica no ledger. Reexecutar é idempotente — transação já vista é
atualizada no lugar, nunca duplicada. Hoje o ledger cobre 12 meses / ~3.300 lançamentos.

A `posicoes.jsonl` é append-only e vira série temporal de carteira sem esforço:
uma linha por papel por dia, com saldo, PU, quantidade e valor aplicado.

Depois do dump, `coleta_consolidada.py --fonte dump` (default) monta o payload **sem
tocar na rede**, lendo o snapshot mais recente + o ledger. `--fonte api` força a leitura
ao vivo.

## Automação

`atualiza-consolidado.sh` encadeia dump → coleta → dashboard, com log em
`memory/pluggy-consolidado.log`. **Cron diário às 08:00.** Poda snapshots e HTMLs
com mais de 60 dias; o ledger nunca é podado.

## Monitor horário de compras

`monitor_compras.py` atualiza os últimos 30 dias na Pluggy e pergunta no Telegram sobre novas compras online ou lançamentos de categoria de compras. O estado idempotente fica em `financial-data/pluggy/monitor-compras-state.json`; cada transação é perguntada uma única vez. O `brain-panel/healthcheck.sh`, já chamado pelo cron a cada 2 minutos, dispara o monitor no máximo uma vez por hora.

## Painel

O dashboard mais recente é servido em `painel.alophus.com.br/financas`, restrito ao
**admin** (`_user_role(user) == "admin"`) — o role `r1_only` recebe 403, não redirect.

| rota | o que faz |
|---|---|
| `/financas` | dashboard mais recente |
| `/financas/d/AAAA-MM-DD` | dashboard de um dia específico |
| `/financas/dados` | índice JSON de tudo que o dump gerou |
| `/financas/dados/<caminho>` | baixa um `.json`/`.jsonl` do dump |

**Chart.js vai embutido no HTML** (`vendor/chart.umd.min.js`, baixado uma vez) porque a
CSP do painel só libera `script-src 'self' 'unsafe-inline' https://unpkg.com` — um
`<script src>` pro jsdelivr seria bloqueado silenciosamente. De quebra o arquivo passou a
funcionar offline, o que também serve pra entrega por Telegram.

## Layout e seções do dashboard

Desde 31/08/2026 o dashboard usa o **design system do painel** (navy `#0A0D12`/`#2E6DA4`
sobre `#F0F4F8`, Inter Tight + Instrument Serif + JetBrains Mono, cartão de canto reto) e
carrega `/static/nav.css` + `/static/nav.js`. Servido em `/financas` ele ganha a nav do
painel; como arquivo solto (Telegram) o `/static` não resolve e a página se vira sozinha.
Não tem dark mode — o painel é light-only.

Gasto de cartão é sempre agregado por **ciclo de fatura** (`billForecastDate`), nunca por
mês calendário.

### Taxonomia (tudo em pt-BR)

Dois níveis, definidos no JS do gerador:

- **`CATS`** — as ~55 categorias em inglês da Pluggy viram `[categoria em português, grupo]`.
  Ex.: `"Eating out" → ["Restaurante", "Alimentação"]`. Categoria nova que a Pluggy inventar
  cai em `Outros` com o nome cru em inglês — aparece feio de propósito, pra ser notada.
- **`POR_NOME`** — corrige pelo nome do lojista quando a categoria da Pluggy não serve. Cada
  regra é `[regex, [categoria, grupo], só_genérica]`. As últimas regras são da conta corrente,
  onde a Pluggy erra pior que no cartão: condomínio veio como *Stadiums and arenas*, o dízimo
  da igreja como *Income*, o salário da Auren como *Pet supplies and vet*, e o mesmo
  financiamento imobiliário alterna entre *Real estate financing* e *Shopping* de um mês pro
  outro.

O terceiro campo é o que evita estragar dado bom:

- `false` — a regra **sempre** vence a categoria. Use quando a Pluggy erra de fato: **Railway**
  (US$ 20/mês de hospedagem) cai em `Public transportation`, o Expo (`650 INDUSTRIES`) vira
  eletrônico, clube de combustível vira `Transfers`.
- `true` — a regra só vale quando a categoria é **genérica** (`Shopping`, `Services`,
  `Transfers` ou vazia). Sem isso, uma panela comprada no Mercado Livre viraria "Compra online"
  e perderia o "Casa e utilidades" que a Pluggy tinha acertado: **o que se comprou informa mais
  que onde se comprou**.

Ordem de decisão: `mascara.json` (grupo forçado) → `POR_NOME` → `CATS` → `Outros`.

Grupos: Moradia, Alimentação, Transporte, Saúde, **Infra**, Assinaturas, **Educação**,
Compras, Viagem, Lazer, **Doações**, Serviços e taxas, **Transferências**, Outros.

- `Infra` (hospedagem, domínio, ferramenta de dev, IA) sai inteira do `POR_NOME` — é a linha
  de custo de trabalho, separada das assinaturas pessoais.
- `Educação`, `Doações` e `Transferências` nasceram com a conta corrente: faculdade e igreja
  são despesa recorrente e mensurável (R$ 644/mês e R$ 782/mês), e PIX pra pessoa física sem
  finalidade identificável precisa de um balaio próprio — jogar em `Outros` esconderia as
  duas coisas, já que `Outros` é o resto das *compras*.

**Pra ajustar a classificação não precisa mexer em mais nada**: uma linha em `POR_NOME` fixa
um lojista recorrente que a Pluggy insiste em errar.

### Contraparte — quem está do outro lado do PIX

Um quarto da saída da conta (**R$ 70 mil em 12 meses**) parava em `Transferências` ou
`Serviços`: baldes que não respondem nada. O nome do outro lado sempre esteve na descrição —
faltava virar linha. `contraparte()` roda **depois** do `mascara.json`, do `POR_NOME` e das
`CATS`, e só quando o resultado ficou num balde vago (grupo `Transferências`/`Outros` ou
categoria `Serviços`): preenche buraco, nunca sobrescreve classificação boa.

O que dá pra decidir sozinho é a **forma** da contraparte, nunca a finalidade:

| forma | vira | por quê |
|---|---|---|
| pessoa física recorrente (3x+) **ou** ≥ R$ 1.000 na janela | `Pessoas / NOME (Nx)` | quem paga 25 PIX pra mesma pessoa sabe na hora o que é; a máquina não sabe e não finge |
| demais pessoas físicas | `Pessoas / PIX eventual a pessoas` | 40 linhas de R$ 50 não informam nada |
| adquirente (PagSeguro, PushinPay, Antpay…) | `Compras / Compra via gateway (lojista oculto)` | é compra; o lojista é que está atrás do gateway e não vem na API |

Resultado: a sobra sem rótulo útil caiu de **R$ 70.761,96 (183 lançamentos)** para
**R$ 40.577,05 (47)** — e R$ 37.493 disso é o PIX dele pra ele mesmo, que já tem rótulo
próprio (`Transferência para conta externa`). O grupo **`Pessoas`** soma R$ 27.556,60.

**Gotcha que custou caro:** `\b` em JS é ASCII. `/\bcia\b/` casa dentro de **"Alícia"** —
a letra acentuada conta como fronteira de palavra — e a irmã dele virava pessoa jurídica.
Por isso `ehEmpresa()` tokeniza sem acento e compara token inteiro contra um `Set`, em vez
de usar regex com `\b`.

### contrapartes.json — dar finalidade a um nome

Arquivo opcional e **gitignorado**, irmão do `mascara.json`. Cada regra dá categoria e grupo
a um lançamento da conta corrente, e **vence toda a classificação automática** porque chega
no JS como `t.grupo` (primeiro teste do `classifica()`):

```json
{"regras": [
  {"padrao": "fabiana lopes da silva", "categoria": "Faxina (Fabiana)", "grupo": "Moradia"},
  {"padrao": "karine cristina romancini", "categoria": "Psicóloga (irmã da Bia)", "grupo": "Saúde"}
]}
```

Diferente do `mascara.json`, **o nome não é trocado** — a intenção aqui é explicar o
lançamento, não escondê-lo. Pra esconder, use o `mascara.json` (que roda depois e é a última
palavra sobre o nome).

**Case o nome inteiro, nunca só o primeiro.** Duas armadilhas reais neste extrato: existem
dois Leonardos (o churrasqueiro do aniversário e um PIX avulso de R$ 23 pra outra pessoa) e
duas Karines — e a segunda Karine é uma **entrada** de R$ 155. O `aplica_contrapartes()` não
olha `natureza`: uma regra por primeiro nome carimbaria "Psicóloga" num recebimento e o valor
apareceria como gasto. Nome completo é a diferença entre explicar e inventar.

O campo `_pendente` (livre, ignorado pelo loader) serve pra guardar o rastro de quem ainda não
tem finalidade — quem é, quanto, quantas vezes, desde quando — pra pergunta não se perder
entre sessões. Sem regra, a pessoa continua caindo em `Pessoas` com nome e contagem, que é
justamente o rótulo que provoca a pergunta.

### Natureza do lançamento — só a conta corrente

O extrato da conta mistura coisas que não são gasto. O `coleta_consolidada.py` carimba cada
lançamento bancário com uma `natureza` (cartão fica com `null`, a lógica de ciclo de fatura
segue intacta):

| natureza | o que é | entra no gasto? |
|---|---|---|
| `consumo` | PIX, boleto, TED, débito automático de verdade | ✅ |
| `entrada` | salário, PIX de terceiro, reembolso | ✅ (como entrada) |
| `fatura` | pagamento de fatura de cartão | ❌ no consumo, ✅ no caixa |
| `investimento` | aplicação, resgate, caixinha | ❌ (troca de bolso) |
| `interna` | **as duas pontas** de uma transferência entre contas conectadas | ❌ (some do dashboard) |

Dois textos que a Pluggy não entrega classificados e o regex precisa pegar: a caixinha do
Nubank (`"Valor transferido para Investimentos"` / `"...recebido de..."`) é `investimento`, não
consumo; e `"Pagamento Cartão de crédito"` do Mercado Pago é `fatura` — numa conta corrente,
pagar cartão é liquidar fatura, e nem a categoria `Credit card payment` nem a palavra "fatura"
aparecem ali.

#### `interna` só existe em par — e essa é a regra inteira

A classificação tem duas fases porque uma sozinha erra. `natureza()` marca o candidato como
`propria?` quando o lançamento **tem cara** de transferência do titular: categoria
`Same person transfer`, CPF do pagador igual ao do recebedor no `paymentData`, o nome do
titular (vindo do `identity.json` do snapshot, não hardcoded) na descrição, a conta irmã
citada pelo nome (`"Transferência enviada para a conta investimento"`, XP) ou **o número de
outra conta conectada dentro da descrição** — `"TED BCO 260 AGE 1 CTA 4162153"` é a XP
mandando pro Nubank, e sem `num_conta()` normalizando `00416215-3 → 4162153` isso passava
como aplicação.

Depois, `casa_internas()` olha todas as contas juntas e procura a outra ponta: um DEBIT na
conta A e um CREDIT na conta B (contas diferentes, mesmo valor absoluto, até 3 dias de
distância). Achou par → as duas viram `interna` e **somem de todas as telas**: saiu do Itaú,
entrou no Nubank, nada mudou de patrimônio, contar como gasto de um lado e receita do outro
é ficção dos dois jeitos.

**Não achou a outra ponta, não é transferência interna.** É dinheiro atravessando a fronteira
do que o Open Finance enxerga — PIX pra corretora, pra banco não conectado. DEBIT vira saída
de caixa de verdade, CREDIT vira entrada, os dois no grupo `Transferências` com rótulo próprio
(`Transferência para/de conta externa`) pra dar pra achar na tela. Esconder isso como "entre
contas" é o que fazia o fluxo não fechar.

Nos dados de ago/26: **158 pares casados (R$ 553.108,79) anulados**, contra **27 saídas soltas
(R$ 37.493,00,** quase tudo PIX do Mercado Pago**)** e **16 entradas soltas (R$ 172.474,67,** o
TED mensal no Itaú e o PIX de R$ 75.302 em fev/26**)** que passaram a contar como movimento
real. As idas e voltas XP conta digital ↔ conta investimento também saíram daí — antes
inflavam aplicado/resgatado em ~R$ 64 mil / R$ 27 mil.

**Por que isso importa em número:** dos R$ 1,4 milhão que passam pelas contas em 12 meses, só
**R$ 280 mil** é gasto. Somar o extrato cru multiplicaria o gasto por seis.

#### O fluxo fecha na moeda

Como todo lançamento cai em exatamente uma natureza e `interna` soma **zero por construção**
(as duas pontas têm o mesmo valor), vale a identidade:

```
entradas − consumo − fatura − aplicado + resgatado = variação do saldo das contas
471.592,85 − 280.227,05 − 183.718,43 − 222.704,55 + 208.015,42 = −7.041,76
```

O coletor emite `caixa_inicial` (saldo de hoje **menos** os lançamentos da janela, deduzido de
trás pra frente), `caixa_final` e o bloco `internas`. O dashboard empilha a variação mês a mês
a partir do `caixa_inicial` e a última coluna tem que dar o saldo que os bancos reportam hoje —
**R$ 7.325,06 → R$ 283,30, resíduo zero**. Isso vive na tabela de fluxo como bloco
*"Conferência com o saldo das contas"*, não numa nota de rodapé: se o resíduo deixar de ser
zero, tem lançamento em bucket errado ou lançamento sumido, e **não existe linha de ajuste pra
esconder isso** (a antiga *"Entrou de conta própria (líquido)"* era exatamente isso e foi
removida).

O que essa linha prova é que **nada foi descartado na classificação** — não que o banco esteja
certo, já que o saldo inicial sai do saldo final. A evidência independente de que o razão está
completo é outra: Nubank e XP nasceram dentro da janela e o saldo inicial delas deu exatamente
`0,00`.

**Ponte entre os dois regimes** (o card *"Como as duas telas conversam"*): elas não se somam,
se ligam pela dívida do cartão — `dívida inicial + compras do período − faturas pagas = dívida
hoje`. Com R$ 162.834,59 de compra líquida, R$ 183.718,43 de fatura paga e R$ 24.064,77 em
aberto hoje, a dívida no começo da janela era R$ 44.948,61. A diferença entre o que se gastou e
o que se pagou no mesmo mês é calendário, não erro de conta.

`metodo` traduz `paymentData.paymentMethod` (e o `operationType` quando ele vem `OTHER`)
pra PIX / Boleto / TED / Cartão de débito / Débito automático. Distribuição real: **73% do
gasto da conta sai em PIX**, 14% em débito automático, 7% em boleto. Cartão de débito é
irrelevante (R$ 18 em 12 meses).

Duas seções vivem disso:

- **Gastos por ciclo** — barra empilhada por grupo com filtro; selecionando um grupo entra
  a linha da média dos ciclos fechados. Abaixo, seletor de ciclo com categorias do ciclo
  (Δ vs ciclo anterior, % do ciclo) e os 15 lojistas do ciclo.
- **Conta corrente — PIX, boleto e débito** — o espelho da seção do cartão, mas por **mês
  calendário** (não existe ciclo de fatura na conta): chips de meio de pagamento, barra
  empilhada por grupo com filtro, seletor de mês com categorias e destinos.
  - **Média e mediana lado a lado.** A compra do carro (R$ 91 mil em maio/26) leva a média
    pra R$ 20.915/mês enquanto a mediana fica em R$ 10.081. Quando as duas divergem assim,
    é um mês atípico, não padrão de gasto.
  - Botão **"sem extraordinários"** tira lançamento individual acima de R$ 20 mil
    (`CORTE_EXTRA`). Não some em silêncio: o resumo diz quantos saíram, quanto somavam e
    quais foram. Sem o corte, o eixo do gráfico mede um evento único e o resto vira rodapé.

- **Fluxo de caixa mensal** — dois regimes num seletor, e eles **não somam**:
  - **conta · PIX, boleto, financiamento** (caixa) — **é o default**: o dinheiro que de fato
    saiu, mais o **pagamento da fatura** (é nesse dia que ele sai). Por isso o cartão não
    entra compra a compra aqui — somar os dois dobraria a fatura.
  - **cartão · compras por ciclo** (competência) — o que foi consumido no cartão, no ciclo em
    que a compra caiu. Pagamento de fatura fica fora dos dois lados. Entrada é só
    estorno/cashback.

  **Por que a conta é o default:** abrindo no cartão, a tabela chamada "fluxo de caixa" não
  tinha conta de luz, PIX nem financiamento — nada disso passa no cartão — e ficava atrás de
  um botão rotulado "conta · por mês", que não anuncia o que tem dentro. Os rótulos agora
  dizem o conteúdo, não o regime.

  **Seletor de nível** (segunda linha de botões): `por grupo` · `por categoria` · `por meio de
  pagamento` (este só na conta — no cartão tudo é cartão). São os mesmos lançamentos
  quebrados de outro jeito, e **a soma de qualquer nível dá o mesmo "Total de saídas"** —
  é o teste que vale a pena rodar quando mexer aqui. O grupo sozinho esconde justamente o que
  se procura: "Moradia" não diz *Financiamento imobiliário* (R$ 34.559,85 em 13 parcelas),
  *Condomínio*, *Energia*, *Contas de casa*; e PIX (R$ 214.938,18, 73% da saída) não é grupo
  nenhum, é meio. Na linha da categoria o grupo vai como prefixo apagado
  (`Moradia · Condomínio`) e a ordem é grupo (ORDEM_GRUPOS) → maior primeiro.

  `classifica()` roda ~50 regex por lançamento e o nível de categoria varre a lista uma vez
  por categoria; sem o cache em `WeakMap` (`cls()`) a página trava alguns segundos no load.

  Em ambos: Δ vs período anterior, Total e Média sempre da janela inteira (não das colunas à
  vista), e a **média ignora a coluna aberta e a parcial** — incluí-las puxa o número pra
  baixo sem significar economia. O Δ também não usa a coluna parcial como base: comparar com
  um mês cortado pela janela dá +4962% que só mede o corte. O bloco *"Fora do consumo — troca
  de bolso"* traz aplicado, resgatado e poupança líquida; o bloco *"Conferência com o saldo
  das contas"* fecha a conta com a variação de caixa do mês e o saldo no fim do mês (linha de
  estoque: Total e Média saem em `—`, somar doze saldos não significa nada).

## As três páginas, e por que são três

O mesmo consolidado alimenta três HTMLs. Não é redundância: cada um responde uma
pergunta que os outros não conseguem responder sem mentir um pouco.

| script | pergunta | regime |
|---|---|---|
| `gera_dashboard_consolidado.py` | quanto eu tenho, onde gastei | foto + ciclo de fatura |
| `gera_fluxo_real.py` | queimando ou gerando, no ano | competência, um número |
| `gera_fluxo_mensal.py` | **em que mês**, e por causa de quê | competência, mês a mês |

Os três leem o `classificador.js`. Uma cópia da taxonomia dentro de qualquer um
deles divergiria na primeira regra nova e as telas passariam a dar números
diferentes pro mesmo gasto — sem ninguém perceber.

### `gera_fluxo_mensal.py` — o mês a mês

`reports/fluxo-mensal-AAAA-MM-DD.html`. Uma linha por mês; clicar abre
`grupo → categoria → quem recebeu → lançamento`, dos dois lados (entrou e saiu).

**Competência nas seções 1–3, caixa na 4.** O gasto do cartão conta no mês da
**compra**, não no da fatura: é a única forma de "vivi acima do que ganhei neste
mês?" ter resposta. A fatura não aparece nessas seções — ela é a liquidação de um
gasto já contado, e somar as duas contaria o mesmo dinheiro duas vezes. A seção 4
refaz o ano em regime de caixa (fatura paga, aplicação, resgate, conta externa) e
**fecha, mês a mês, com a variação do saldo medido no extrato**. As duas seções
divergem de propósito; o texto na página diz isso.

**Dois botões, duas premissas:**
- *sem eventos únicos* — corte mecânico de R$ 15 mil, **simétrico** (entrada e
  saída pelo mesmo critério). Tirar a compra do carro sem tirar a venda faria
  maio parecer um desastre que não foi. Mesmo corte do `gera_fluxo_real.py`: se
  as duas páginas cortassem em lugares diferentes, o mesmo mês apareceria com
  dois resultados.
- *conta externa = renda* — inverte a premissa das transferências que têm o nome
  do Aleph dos dois lados (a TED mensal de ~R$ 13,7 mil inclusa). Vale ~R$ 135 mil
  no ano e muda a resposta de lado, então é botão, não chute.

**Os dois botões se cruzam, e é o cruzamento que quebrou.** O corte de eventos
únicos ignorava a conta externa por construção (`!ehExt` dentro do `ehUnico`).
Enquanto ela é financiamento isso é certo — não está no resultado, não há o que
cortar. Mas com o botão 2 ligado ela ENTRA no resultado, e aí um lançamento dela
passa do corte: o Pix de R$ 75.302 de 27/02. Ele sobrevivia ao "sem eventos
únicos", fevereiro fechava +R$ 61.795 e o ano dava +R$ 68.645 — a mesma página
dizia *queimando* com um botão e *sobrando* com dois. Hoje `ehUnico` lê a
premissa (`extRenda || !ehExt(t)`), a lista de únicos virou função (muda com o
botão) e o ano fecha negativo em toda combinação. Com o botão 2 desligado a
regra segue **idêntica** à do `gera_fluxo_real.py`, que é o que a invariante
"mesma premissa, mesmo corte" realmente exige.

O harness tinha uma conferência pra isso e ela **passava sempre**: cobrava que
nenhum lançamento externo fosse evento único, o que era verdade por construção.
Asserção que repete a implementação não testa nada — e nenhum caso ligava os
dois botões ao mesmo tempo. Os quatro casos novos do bloco 5 cobram o estado
combinado, inclusive que o sinal do ano não dependa de qual botão foi apertado
por último.

**Gotchas que só apareceram fazendo:**
- **o mês-toco.** A janela abre em 31/08, então agosto tem um dia e R$ 686. Ao
  lado de meses inteiros isso mente na comparação. Regra mecânica: se a janela
  não começa no dia 1, o primeiro mês entra no seguinte e o rótulo diz
  (`ago–set/25`). O bloco 1 do harness cobra que nada sobrou no mês-toco.
- **contraste do mapa de calor não sai do alfa.** O mesmo alfa sobre o navy da
  Moradia e sobre o cinza-claro da Viagem dá fundos opostos — a linha Viagem
  saía branco-no-branco. `textoSobre()` mistura a cor com o branco do fundo e
  mede a luminância do resultado.
- **`.tbl-wrap` do CSS compartilhado corta em 460px.** Sem barra de rolagem à
  vista, jul e ago sumiam da ponte de caixa e metade dos grupos sumia do mapa —
  parecia que o mês não existia. Esta página zera o `max-height`.
- **recuo é padding da célula, não espaçador inline.** Com espaçador, a segunda
  linha de uma descrição longa voltava pra coluna zero e vazava por baixo.
- **grupo com um lançamento só continua sendo linha de grupo.** No resto da
  árvore um filho único vira folha direto (o financiamento imobiliário não vai
  cobrar três cliques pra mostrar 13 parcelas iguais), mas no primeiro nível um
  PIX solto entre "Moradia" e "Transporte" tira do leitor a única coisa que
  aquela coluna existe pra dar.

### `check_mensal.js` — a conferência

`node check_mensal.js [consolidado.json]`. Roda **o JS da página**, não uma cópia:
puxa o bloco `JS` do próprio módulo python, injeta o payload de verdade e avalia
com um DOM de mentira. Uma reescrita da mesma lógica no harness passaria a
concordar com ela mesma e a divergir da tela na primeira mudança.

`const`/`let` dentro de `eval` **nunca** escapam — a spec cria escopo léxico
próprio pro eval, direto ou indireto. O epílogo devolve na mão o que o harness
usa, e essa lista é a interface real entre a página e a conferência. `setU`/`setX`
moram no epílogo justamente porque só quem está dentro do escopo escreve nos
`let` dos botões.

Os seis blocos: cobertura (nada perdido, duplicado ou fora de mês) · a soma dos
meses é o total do ano · a árvore inteira, nos dois lados e em todo mês (o valor
da linha é o que os lançamentos dela somam, os filhos somam o pai, o conjunto é o
mesmo) · a ponte de caixa fecha mês a mês com o saldo do extrato · os botões
movem exatamente o que dizem · o mapa soma o mesmo que a espinha.

## mascara.json — esconder nome de lojista

Arquivo opcional e **gitignorado** ao lado do script. Cada regra troca o nome do lojista
por um rótulo neutro no dashboard inteiro (lojistas, parcelamentos, internacionais e o
payload embutido no HTML):

```json
{"regras": [
  {"padrao": "claude|anthropic|openai", "rotulo": "Assinatura de IA"},
  {"padrao": "kiwify|hotmart", "rotulo": "Assinatura de conteúdo", "grupo": "Outros"}
]}
```

- `padrao` é regex, sem diferenciar maiúscula, casado contra a descrição
- `rotulo` é o que aparece no lugar; várias compras com o mesmo rótulo somam numa linha só
- `grupo` é opcional — força a compra pra outro grupo (use `Outros` pra sumir do grupo real)
  e nesse caso a **categoria** também vira o rótulo, senão a tabela do ciclo mostraria a
  categoria verdadeira enquanto o fluxo conta a compra em Outros

**Só o nome sai; o valor continua somando** em categoria, grupo, fatura e total — nenhum
número do dashboard muda. Sem o arquivo, nada é mascarado.

O `.json` servido em `/financas/dados/` **também passa pela máscara**, aplicada na saída pelo
painel (`_financas_regras` / `_mascara_valor` no `main.py`): a regra troca a string inteira em
qualquer campo e qualquer profundidade, porque a descrição de um lançamento aparece em
`description`, `descriptionRaw` e `merchant.name` — um replace parcial deixaria o resto do
texto entregando o mesmo. O **dump em disco fica intacto**: é a fonte da verdade do ledger, e
mascarar ali seria irreversível. Consequência boa: editar o `mascara.json` muda na hora o que
sai do endpoint, sem reprocessar nada. O painel relê o arquivo quando o mtime muda.
