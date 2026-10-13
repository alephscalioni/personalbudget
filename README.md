# Personal Budget

App pessoal de finanças com dados locais do Open Finance, FastAPI, SQLite e frontend modular em JavaScript. Não depende de CDN nem de serviços externos para abrir o painel.

## Executar

Requer Python 3.10 ou superior. Na pasta do projeto:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
./start.sh
```

Abra **http://127.0.0.1:8787** (ou `http://localhost:8787`). Para reproduzir as versões validadas, use `backend/requirements.lock.txt` na instalação.

O app lê o último `data/reports/consolidado-AAAA-MM-DD.json`. A primeira gravação cria `data/budget.sqlite3`. O servidor escuta apenas em `127.0.0.1` por padrão.

## Recursos

- Visão geral com patrimônio, receitas, despesas, resultado mensal e gráficos.
- Extrato pesquisável por texto, mês, tipo, categoria e instituição, com paginação e CSV dos resultados filtrados.
- Registro manual de receitas e despesas, com exclusão confirmada.
- Planejamento recorrente com limites por categoria, renda, meta de poupança e estimativa de VA/VR editáveis.
- Contas, cartões e investimentos, distinguindo posições declaradas.
- Metas com valor reservado, objetivo, prazo e atualização de progresso.
- Ocultação de valores, interface responsiva e exportação do planejamento em JSON.
- Relatório original preservado em `/app/dashboard.html`.

## Estrutura

```text
backend/
  app.py             Rotas HTTP, proteção de origem e arquivos públicos
  config.py          Caminhos e configuração de ambiente
  models.py          Validação das gravações
  service.py         Adaptador do pipeline financeiro existente
  store.py           Persistência SQLite, separada dos extratos
  tests/             Testes da API e persistência
frontend/
  index.html         Estrutura e navegação
  shell.css          Design responsivo e acessibilidade
  js/app.js          Telas, estado e formulários
  js/finance.js      Cálculos puros em centavos
  js/ui.js           Formatação, componentes e cliente HTTP
finance/pluggy/       Integração, regras compartilhadas e geradores originais
data/reports/        Snapshots bancários originais
data/budget.sqlite3  Planejamento e registros manuais
tests/               Testes das regras financeiras compartilhadas
```

O módulo `/app/js/classifier.js` é servido pelo backend a partir do `finance/pluggy/classificador.js` original. A mesma taxonomia identifica gastos, estornos, pagamentos de fatura e movimentações próprias. Não há uma segunda cópia das regras de classificação.

## Critérios de cálculo

O app separa data bancária e competência. Por padrão, salários identificados a partir do dia 25 entram no planejamento do mês seguinte (regra editável em Orçamento). Cada lançamento bancário pode receber uma competência e classificação explícitas em Transações → Ajustar, preservando data e valor originais. Transferências próprias não são convertidas automaticamente em salários; uma portabilidade deve ser confirmada no ajuste. Compras no cartão contam como despesa; estornos abatem despesas; pagamentos de fatura não são novos gastos ou receitas. Transferências próprias, aplicações e eventos patrimoniais identificados ficam fora do resultado mensal. O extrato permite consultá-los em “Outras movimentações”.

Os valores `valor` do consolidado já são convertidos à moeda da conta pelo coletor. Os agregados de gasto bruto do payload antigo não são usados como despesa líquida no novo app.

O patrimônio é sempre a posição do **último consolidado**, independente do mês selecionado. Metas e lançamentos manuais não alteram saldos bancários. Registros manuais participam dos indicadores mensais; se forem importados posteriormente, remova a cópia manual para evitar duplicação.

O orçamento usa consumo identificado mais VA/VR **estimado**. Seus limites são recorrentes, não históricos. O relatório detalhado mantém as premissas originais de `premissas-fluxo.json`; não incorpora as edições e os registros feitos no novo app.

## Atualização e cópias de segurança

**Atualizar dados** solicita uma coleta Pluggy quando `PERSONALBUDGET_SYNC_ENABLED=1` e as credenciais estão configuradas. A coleta automática ocorre de hora em hora e regenera o relatório detalhado após atualizar os dados. Se a geração do relatório falhar, os dados bancários atualizados continuam disponíveis e a interface sinaliza o relatório pendente. Sem sincronização configurada, importe os consolidados em `data/reports/`: a API reconhece gerações mais recentes, inclusive depois de iniciada, preservando o snapshot salvo se um novo arquivo estiver inválido.

Novas coletas preservam o identificador do provedor para manter classificações e competências após correções bancárias. Ajustes antigos são migrados quando o lançamento ainda corresponde aos campos originais; snapshots sem identificador do provedor continuam usando a identificação legada.

A exportação JSON guarda planejamento, metas e lançamentos manuais; não há importação de JSON pela interface nesta versão. Para uma cópia recuperável completa, pare o servidor e copie `data/` e os arquivos de configuração de `finance/pluggy/`. Para restaurar, com o servidor parado, recoloque esses arquivos nos mesmos caminhos.

## Configuração

- `PERSONALBUDGET_PORT`: porta HTTP; padrão `8787`.
- `PERSONALBUDGET_HOST`: endereço de escuta; padrão `127.0.0.1`.
- `PERSONALBUDGET_ALLOWED_HOSTS`: hosts adicionais permitidos, separados por vírgula.
- `PERSONALBUDGET_REPORTS`: pasta dos consolidados.
- `PERSONALBUDGET_DATABASE`: caminho do SQLite, útil para testes isolados.
- `PERSONALBUDGET_GENERATOR`: gerador do relatório detalhado.

Localmente, o acesso é direto por padrão. A versão online exige login e HTTPS. As contas `biancascalioni` e `alephscalioni` têm senha provisória e troca obrigatória no primeiro login; até a troca, nenhum extrato é liberado. Os dados financeiros são compartilhados entre as duas contas. Novas publicações não redefinem as senhas pessoais. Credenciais e extratos não são servidos como arquivos estáticos. As respostas financeiras usam `Cache-Control: no-store` e gravações de outras origens são rejeitadas.

Para reconstruir somente o relatório:

```bash
.venv/bin/python -m backend.sync
```

## Validação

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/python -m unittest discover -s backend/tests -v
node --test tests/finance.test.mjs
```

Os testes usam SQLite temporário e verificam persistência, validação, origem, classificação, estornos, exclusão de pagamentos/transferências e arredondamento. Node é necessário apenas para esses testes; a execução do app usa Python e o navegador.


## Acesso online e recuperação

O frontend é publicado na Vercel com uma lista explícita de arquivos públicos; a API e o relatório detalhado passam por autenticação no Railway. O volume `/data` armazena relatórios, configurações, contas e SQLite. Consulte `deployment/README.md`.

A senha provisória fica apenas em `.runtime/cloud-access.json`. Cada usuário escolhe uma senha pessoal de pelo menos 12 caracteres. Alterar ou redefinir a senha invalida as sessões anteriores da conta.

A recuperação usa Google SMTP (`smtp.gmail.com`, TLS, porta 587), com uma senha de app. Configure `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `PERSONALBUDGET_APP_URL`, `PERSONALBUDGET_ALEPH_EMAIL` e `PERSONALBUDGET_BIANCA_EMAIL` no backend. `scripts/configure-smtp.py` lê o arquivo privado `.runtime/smtp.env` e envia as variáveis pelo stdin, sem registrar credenciais nos logs. O link de recuperação expira em 20 minutos, é de uso único e só seu hash é armazenado. A interface informa quando o SMTP ainda não está configurado.

O backup JSON do planejamento não inclui contas, hashes de senha ou tokens de recuperação. Para preservar também os acessos, faça backup do volume persistente, protegido e fora do Git.

Referência SMTP: https://support.google.com/a/answer/176600

### Ciclo do salário, caixa e competência

A visão padrão é o ciclo do salário: recebimento no fim do mês financia o próximo mês; recebimento no dia 01 financia esse mesmo mês. O cartão usa o mês da fatura, quando disponível. Caixa considera movimentações bancárias pela data, incluindo liquidação de fatura, investimentos e transferências. A visão de competência usa o mês informado; sem ajuste, usa a data do lançamento e atribui salário do dia 01 ao mês anterior. São aproximações explícitas e editáveis; não representam conciliação automática de todas as obrigações.

Filtros de instituição, categoria, origem e tipo afetam totais, gráfico e exportação. A pizza abre os lançamentos de cada categoria. Saldos declarados são editáveis e persistidos separadamente; podem ser excluídos da visualização patrimonial. VA/VR continua como estimativa de planejamento, identificada na tela.

### Kaleu no navegador e Telegram

O Kaleu existente em `codex-bots` usa `scripts/kaleu-client.py` para ler e alterar o mesmo planejamento pela API autenticada. A credencial financeira não concede acesso às senhas dos usuários, relatórios privados por sessão, ou mensagens de outros usuários. Alterações de orçamento, metas, lançamentos, classificações e saldos declarados registram antes/depois e autor em `/api/audit`.

O navegador usa uma fila persistente; `scripts/kaleu-worker.py` consulta a fila de saída no servidor do usuário e executa Codex com a autenticação já existente, em um workspace financeiro separado. Histórico de chat é separado por usuário. Telegram e navegador compartilham dados financeiros, não o histórico privado de conversas. Pedidos interrompidos não são reexecutados automaticamente, pois podem já ter feito alterações. O worker depende do servidor pessoal ligado e conectado. Nenhum desses endpoints executa pagamentos bancários.

Configuração privada: `~/.config/personalbudget/kaleu.json`; variável cloud `PERSONALBUDGET_KALEU_TOKEN`. `scripts/configure-kaleu.py` provisiona os caminhos deste ambiente e o serviço `kaleu-personalbudget.service`. O protocolo e os campos disponíveis estão em `deployment/kaleu/AGENTS.md`.

### Categorização no backend

`GET /api/data` retorna `transactions` já categorizadas. O painel consome esse resultado; `finance` continua contendo a origem bancária. Cada lançamento inclui `classification` com origem (`manual`, `rule`, `bank`, `ai`, `pending`), motivo, confiança quando fornecida pela IA e `needs_review`.

A prioridade é: ajuste manual → regras explícitas → regras de estabelecimento e categoria bancária → IA para casos pendentes. Salários usam as regras privadas de pagador/titular existentes. Transferências próprias, faturas e movimentações patrimoniais não viram receita por decisão da IA. PIX sem finalidade identificável fica em **Receitas a revisar**; a IA pode se abster. Receitas têm categorias próprias: salário, trabalho extra, reembolsos, rendimentos, cashback, aluguéis, vendas e outras receitas.

- `GET /api/classification`: catálogo, regras, pendências e estado da fila.
- `PUT /api/classification/rules/{id}`: cria/atualiza uma regra; `DELETE` remove. Maior `priority` vence; empate usa o ID. Os critérios presentes são combinados com AND.
- `PUT /api/transactions/{id}/classification`: confirma uma categoria individual (`income_category` para receita) sem alterar o extrato.

Exemplo de regra:

```json
{"name":"Vendas da loja","kind":"income","category":"Vendas","priority":200,"description_contains":"Cliente da loja","institution":"Banco"}
```

Os critérios disponíveis são `description_contains`, `description_exact`, `institution`, `payer_document_root` (8 dígitos do CNPJ) e `method`. É obrigatório informar descrição ou documento. Regras genéricas não atribuem salário. As regras ficam no banco e no backup, com histórico de alterações.

No deploy cloud, a IA fica habilitada por padrão quando o token do Kaleu está configurado. Para desabilitar, defina `PERSONALBUDGET_CLASSIFICATION_AI_ENABLED=0`. Na execução local, habilite com `PERSONALBUDGET_CLASSIFICATION_AI_ENABLED=1`. Mantenha o worker `scripts/kaleu-worker.py` atualizado, autenticado com `PERSONALBUDGET_KALEU_TOKEN`. O worker reutiliza a autenticação Codex já configurada, atende o chat primeiro e depois lotes de até 20 pendências. O backend apenas enfileira; carregar o painel não executa o modelo. Sem habilitação, as regras continuam funcionando e os casos ambíguos permanecem para revisão.

A saída segue um [JSON Schema do Codex](https://developers.openai.com/codex/noninteractive/#create-structured-outputs-with-a-schema) e é validada novamente pelo backend. A IA recebe descrição limitada, categoria bancária, método e categorias permitidas; não recebe saldo ou extrato completo. Ela só devolve categoria, confiança e motivo. Confiança abaixo de 0,9 gera sugestão para revisão; esse número é declarado pelo modelo, não uma garantia estatística. Respostas sem categoria também permanecem pendentes. O cache usa a evidência e as regras: resultados antigos não se aplicam a descrições alteradas. A fila possui leases de 6 minutos, execução de até 5 minutos e até 3 tentativas; erros não alteram valores nem ajustes manuais.


### Demonstrativo mensal e média móvel

A tela **Fluxo de caixa** mostra saldo inicial, entradas por tipo, saídas por tipo e saldo final. Financiamento, condomínio, contas residenciais e faturas têm linhas próprias. Cada linha histórica abre seus lançamentos. Transferências próprias, aplicações e resgates são separados das receitas e despesas operacionais, mas entram na reconciliação do caixa. Compras no cartão aparecem no quadro de consumo por categoria; o caixa registra somente o pagamento da fatura.

Os saldos históricos são reconstruídos a partir do saldo das contas bancárias na última coleta; não são saldos históricos fornecidos individualmente pelo banco. Dependem da cobertura do extrato disponível. Lançamentos manuais e saldos patrimoniais declarados não alteram este demonstrativo bancário.

A projeção usa uma média móvel simples de 3, 6 ou 12 meses completos, com meses de valor zero no denominador. Se houver menos meses completos, informa a amostra utilizada; sem nenhum mês completo, não produz previsão. O mês atual combina realizado com o restante positivo até atingir a média de entradas e saídas. O saldo final estimado financia os próximos seis meses; não há previsão de aplicações, resgates, transferências próprias, reajustes ou vencimentos futuros. Projeção é estimativa, não compromisso cadastrado.

`GET /api/statement?window=3&horizon=6` retorna histórico, linhas com evidência, médias por tipo e projeção com saldos encadeados. `GET /api/data` inclui o demonstrativo padrão. O planejamento anterior por ciclo salarial continua acessível pelo botão da tela.


O demonstrativo compara os últimos seis meses até o mês selecionado em colunas, com linhas por tipo de entrada e saída. Os valores com lançamentos são clicáveis para conferência. O bloco de conciliação mostra o mesmo período por conta bancária, com saldo inicial, entradas, saídas e saldo final. A soma das contas é comparada ao demonstrativo e ao saldo atual da coleta, em centavos. Também são sinalizados lançamentos sem conta, IDs duplicados, sinais inconsistentes e diferenças em relação ao saldo inicial do coletor. Esse saldo inicial do coletor é derivado do próprio extrato; a conciliação não substitui a conferência com um extrato histórico independente.
