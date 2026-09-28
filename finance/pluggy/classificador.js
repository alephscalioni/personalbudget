/* ---------- taxonomia: categoria pt-BR + grupo ----------
   A Pluggy devolve 56 categorias em ingles, com granularidade irregular
   ("Shopping" e "Online shopping" separadas, "Healthcare" e "Dentist" tambem).
   Aqui cada uma vira um par [categoria em portugues, grupo], e o grupo e o
   nivel que a tabela de fluxo usa. Categoria que a Pluggy inventar depois cai
   em Outros com o nome cru — aparece feio de proposito, pra ser notada. */
const CATS = {
  "Rent":                  ["Aluguel",              "Moradia"],
  "Housing":               ["Moradia",              "Moradia"],
  "Houseware":             ["Casa e utilidades",    "Moradia"],
  "Internet":              ["Internet",             "Moradia"],
  "Telecommunications":    ["Telefonia",            "Moradia"],
  "Insurance":             ["Seguros",              "Moradia"],
  "Electricity":           ["Energia",              "Moradia"],
  "Water and sewage":      ["Água e esgoto",        "Moradia"],
  "Utilities":             ["Contas de casa",       "Moradia"],
  "Real estate financing": ["Financiamento imobiliário", "Moradia"],

  "Groceries":             ["Mercado",              "Alimentação"],
  "Eating out":            ["Restaurante",          "Alimentação"],
  "Food delivery":         ["Delivery",             "Alimentação"],
  "Food and drinks":       ["Bar e bebidas",        "Alimentação"],

  "Gas stations":          ["Combustível",          "Transporte"],
  "Taxi and ride-hailing": ["App de transporte",    "Transporte"],
  "Public transportation": ["Transporte público",   "Transporte"],
  "Parking":               ["Estacionamento",       "Transporte"],
  "Tolls and in vehicle payment": ["Pedágio",       "Transporte"],
  "Automotive":            ["Automotivo",           "Transporte"],
  "Vehicle maintenance":   ["Manutenção do carro",  "Transporte"],
  "Vehicle ownership taxes and fees": ["IPVA e licenciamento", "Transporte"],
  "Transportation":        ["Transporte",           "Transporte"],

  "Healthcare":            ["Consulta e exame",     "Saúde"],
  "Pharmacy":              ["Farmácia",             "Saúde"],
  "Dentist":               ["Dentista",             "Saúde"],
  "Optometry":             ["Ótica",                "Saúde"],
  "Wellness and fitness":  ["Bem-estar",            "Saúde"],
  "Gyms and fitness centers": ["Academia",          "Saúde"],

  "Digital services":      ["Serviço digital",      "Assinaturas"],
  "Video streaming":       ["Streaming",            "Assinaturas"],

  "Online Courses":        ["Curso online",         "Educação"],
  "Education":             ["Escola e faculdade",   "Educação"],
  "Books":                 ["Livros",               "Educação"],

  "Shopping":              ["Loja",                 "Compras"],
  "Online shopping":       ["Compra online",        "Compras"],
  "Electronics":           ["Eletrônicos",          "Compras"],
  "Clothing":              ["Roupas",               "Compras"],
  "Kids and toys":         ["Infantil",             "Compras"],
  "Sports goods":          ["Artigos esportivos",   "Compras"],
  "Bookstore":             ["Livraria",             "Compras"],
  "Office supplies":       ["Papelaria",            "Compras"],
  "Pet supplies and vet":  ["Pet",                  "Pets"],

  "Travel":                ["Viagem",               "Viagem"],
  "Accomodation":          ["Hotel",                "Viagem"],
  "Airport and airlines":  ["Passagem aérea",       "Viagem"],
  "Mileage programs":      ["Milhas",               "Viagem"],

  "Leisure":               ["Lazer",                "Lazer"],
  "Cinema, theater and concerts": ["Cinema e teatro", "Lazer"],
  "Gaming":                ["Jogos",                "Lazer"],
  "Stadiums and arenas":   ["Estádio",              "Lazer"],
  "Tickets":               ["Ingressos",            "Lazer"],
  "Gambling":              ["Apostas",              "Lazer"],

  "Services":              ["Serviços",             "Serviços e taxas"],
  "Bank fees":             ["Tarifa bancária",      "Serviços e taxas"],
  "Interests charged":     ["Juros",                "Serviços e taxas"],
  "Tax on financial operations": ["IOF",            "Serviços e taxas"],
  "Late payment and overdraft costs": ["Multa e atraso", "Serviços e taxas"],
  "Loans and financing":   ["Empréstimo",           "Serviços e taxas"],
  "Financing":             ["Financiamento",        "Serviços e taxas"],
  "Taxes":                 ["Impostos",             "Serviços e taxas"],

  "Donations":             ["Doações",              "Doações"],

  /* PIX/TED/boleto pra terceiro que a Pluggy nao consegue dizer o que e.
     Grupo proprio porque "Outros" ja e o balaio do que sobrou de compra —
     misturar transferencia ali esconde as duas coisas. */
  "Transfers":             ["Transferência",        "Transferências"],
  "Transfer - PIX":        ["PIX enviado",          "Transferências"],
  "Transfer - TED":        ["TED",                  "Transferências"],
  "Transfer - Bank Slip":  ["Boleto",               "Transferências"],
  "Third party transfers": ["Transferência a terceiro", "Transferências"],

  "Cashback":              ["Cashback",             "Outros"],
  "Non-recurring income":  ["Receita eventual",     "Outros"],
  "Income":                ["Receita",              "Outros"],
  "Salary":                ["Salário",              "Outros"],
};

/* A categoria da Pluggy sai do nome do lojista e erra em coisa de trabalho:
   Railway (US$ 20/mes de hospedagem) cai em "Public transportation", Expo vira
   eletronico, clube de combustivel vira transferencia. Estas regras corrigem
   pelo nome. Ordem importa: a primeira que casar vence.

   O terceiro campo diz quando a regra vale. `true` = so quando a categoria da
   Pluggy for generica (Shopping/Services/Transfers/vazia). Sem isso, comprar
   uma panela no Mercado Livre viraria "Compra online" e perderia o "Casa e
   utilidades" que a Pluggy tinha acertado — o que a pessoa comprou informa
   mais que onde ela comprou. */
const GENERICAS = new Set(["Shopping", "Services", "Transfers"]);
const POR_NOME = [
  /* Merchant auditado por busca pública: Papa Grillos é oficina/acessórios
     automotivos em São Paulo, não casa/utilidades. */
  [/papa\s*grillos/i,           ["Manutenção do carro",  "Transporte"],  false],
  [/kome\s*-?\s*moema/i,       ["Restaurante",          "Alimentação"], false],
  [/victoria\s*bet/i,           ["Apostas",              "Lazer"],       false],
  [/super\s*tigre/i,            ["Combustível",          "Transporte"],  false],
  [/shopee\s*\*?brenaliltda/i, ["Compra online",        "Compras"],     false],
  [/wellhub/i,                  ["Academia",             "Saúde"],       false],
  [/railway|hostinger|cloudflare|vercel|netlify|digital\s?ocean|linode|heroku|supabase|\brender\.com/i,
                                    ["Hospedagem web",       "Infra"],       false],
  [/registro\s?br|namecheap|godaddy/i,
                                    ["Domínio",              "Infra"],       false],
  [/github|gitlab|650 industries|jetbrains|cursor|figma|postman|\btrae\b/i,
                                    ["Ferramenta de dev",    "Infra"],       false],
  [/abastece\s?a[ií]|e-?a[ií] clube/i,
                                    ["Combustível",          "Transporte"],  false],
  [/uber|99app|99 ?tecnologia|cabify/i,
                                    ["App de transporte",    "Transporte"],  true],
  [/ifood|rappi|z[eé] ?delivery/i,
                                    ["Delivery",             "Alimentação"], true],
  [/mercadolivre|mercado ?livre|shopee|amazon|aliexpress|shein|temu|magalu|americanas|kabum|pichau/i,
                                    ["Compra online",        "Compras"],     true],
  [/trip\.?com|booking|airbnb|decolar|latam|gol linhas|azul linhas|esim/i,
                                    ["Viagem",               "Viagem"],      true],
  [/art ?box ?3d|filamento|creality|bambu ?lab|elegoo|anycubic|3d ?fila/i,
                                    ["Insumos 3D",           "Negócio 3D"],  true],
  [/epic ?games?|steam ?games|nintendo|playstation|xbox|gvgmall/i,
                                    ["Jogos",                "Lazer"],       true],

  /* --- conta corrente: PIX e boleto, onde a Pluggy erra mais feio ---
     Financiamento imobiliario alterna entre "Real estate financing" e
     "Shopping" no mesmo contrato; condominio veio como "Stadiums and arenas"
     e o dizimo da igreja como "Income". Todas com soGenerica=false. */
  [/financ\w* imobili|cr[ée]dito imobili/i,
                                    ["Financiamento imobiliário", "Moradia"], false],
  [/harmonia morumbi|\blello\b|condom[íi]nio/i,
                                    ["Condomínio",           "Moradia"],     false],
  [/\benel\b|eletropaulo|\bcpfl\b|cemig|coelba|energisa/i,
                                    ["Energia",              "Moradia"],     false],
  [/sabesp|comgas|c[oó]pasa|sanepar/i,
                                    ["Água e gás",           "Moradia"],     false],
  [/igreja|par[óo]quia|d[íi]zimo|obra social/i,
                                    ["Igreja",               "Doações"],     false],
  [/fundacao (para )?pesq|fipecafi|universidade|faculdade|col[ée]gio/i,
                                    ["Escola e faculdade",   "Educação"],    false],
  [/auto ?art|kavak|cara[ií]ga|semi ?novos/i,
                                    ["Compra de veículo",    "Transporte"],  false],
  [/detran|\bipva\b|licenciamento/i,
                                    ["IPVA e licenciamento", "Transporte"],  false],
  [/electro imports|terabyte|\bpichau\b/i,
                                    ["Eletrônicos",          "Compras"],     false],
  [/portoseg|creditas|banco pan|crefisa/i,
                                    ["Empréstimo",           "Serviços e taxas"], true],
];

/* Ordem de decisao: mascara.json (t.grupo) > nome do lojista > categoria. */
function classifica(t) {
  if (t.grupo) return [t.categoria || "Sem categoria", t.grupo];
  const generica = !t.categoria || GENERICAS.has(t.categoria);
  const n = POR_NOME.find(([rx, , soGenerica]) =>
    (!soGenerica || generica) && rx.test(t.desc || ""));
  if (n) return n[1];
  const c = CATS[t.categoria];
  return c ? c : [t.categoria || "Sem categoria", "Outros"];
}
/* classifica() roda ~50 regex por lancamento. Com o seletor de nivel a tabela
   de fluxo varre a lista inteira uma vez por categoria, entao o veredito fica
   em cache por objeto — sem isso a pagina trava alguns segundos no load. */
const _cls = new WeakMap();
const cls = t => { let v = _cls.get(t);
                   if (!v) { v = classifica(t);
                             _cls.set(t, v = contraparte(t, v) || v); }
                   return v; };
const catDe = t => cls(t)[0];
const grupoDe = t => cls(t)[1];

const ORDEM_GRUPOS = ["Moradia","Alimentação","Transporte","Saúde",
                      "Cuidados pessoais","Infra","Assinaturas","Educação",
                      "Compras","Pets","Negócio 3D","Viagem","Lazer","Doações","Serviços e taxas",
                      "Transferências","Pessoas","Outros"];
const CORES = ["#2E6DA4","#1C2B3A","#d4a017","#1f7a4d","#c96a8a","#85B7EB",
               "#b54232","#5d6b78","#7a5ea8","#C8D4DF","#0f6f7a","#a8763e",
               "#3f8f6f","#8a4f6d","#3d5a3f","#6b7f2e"];
/* O contrapartes.json aceita qualquer string em "grupo", mas quem desenha era
   ORDEM_GRUPOS.filter(...): grupo fora da lista SUMIA do grafico e da tabela
   sem erro, e a soma por grupo parava de bater com o total caladamente. Agora
   o desconhecido entra no fim da ordem e ganha cor pelo nome. */
const rankGrupo = g => { const i = ORDEM_GRUPOS.indexOf(g);
                         return i >= 0 ? i : ORDEM_GRUPOS.length; };
const corDe = g => { const i = ORDEM_GRUPOS.indexOf(g);
  return CORES[(i >= 0 ? i : ORDEM_GRUPOS.length +
    [...g].reduce((a, c) => a + c.charCodeAt(0), 0)) % CORES.length]; };
const ordenaGrupos = tot => [...ORDEM_GRUPOS.filter(g => tot[g]),
    ...Object.keys(tot).filter(g => tot[g] && !ORDEM_GRUPOS.includes(g))]
  .sort((a, b) => tot[b] - tot[a]);

const gastos = D.lancamentos.filter(t => t.conta_tipo === "CREDIT"
  && t.tipo === "DEBIT" && t.categoria !== "Credit card payment" && t.fatura);
/* estorno e cashback entram como CREDIT no cartao; pagamento de fatura nao e
   entrada, e a liquidacao do ciclo — fica de fora dos dois lados */
const estornos = D.lancamentos.filter(t => t.conta_tipo === "CREDIT"
  && t.tipo === "CREDIT" && t.categoria !== "Credit card payment" && t.fatura);

const ciclos = [...new Set(gastos.map(t => t.fatura))].sort();
const cicloAberto = ciclos[ciclos.length - 1];   /* ainda acumulando */
const cicloParcial = ciclos[0];                  /* janela do extrato corta ele */
const fechados = ciclos.filter(c => c !== cicloAberto && c !== cicloParcial);
const rotuloCiclo = c => c + (c === cicloAberto ? " (aberto)"
                        : c === cicloParcial ? " (parcial)" : "");

const soma = (arr, f) => arr.reduce((s, t) => s + f(t), 0);
const porCiclo = (arr, filtro) => {
  const m = {}; ciclos.forEach(c => m[c] = 0);
  arr.forEach(t => { if (!filtro || filtro(t)) m[t.fatura] += t.valor; });
  return m;
};

/* ---------- conta corrente: PIX, boleto e debito ----------
   No cartao um DEBIT vem positivo (aumenta a divida); na conta corrente vem
   negativo (sai do saldo). Como a `natureza` ja diz a direcao, aqui a gente
   trabalha sempre com o modulo e nao precisa lembrar do sinal de cada banco.

   A natureza vem do coletor e separa o que o extrato mistura:
     consumo      gasto de verdade (PIX, boleto, TED, debito)
     entrada      salario, PIX de terceiro, reembolso
     fatura       pagamento de fatura — o gasto ja foi contado no cartao
     investimento aplicacao/resgate/caixinha — troca de bolso
     interna      as DUAS pontas de uma transferencia entre contas conectadas

   "interna" nao aparece em lugar nenhum do dashboard, de proposito: sai R$ 5.000
   do Itau e entram R$ 5.000 no Nubank, os dois lados se anulam e o patrimonio
   nao mudou. O coletor so marca assim quando acha a outra ponta. PIX que saiu e
   nao entrou em conta nenhuma daqui atravessou a fronteira do que o Open Finance
   ve: e saida de caixa de verdade e vem como consumo, no grupo Transferencias. */
const vAbs = t => Math.abs(t.valor);
/* Eventos de troca de patrimônio não são renda nem consumo recorrente. Eles
   continuam no extrato bruto e na reconciliação de caixa, mas ficam fora da
   análise normalizada. A venda do carro antigo entrou pela Kavak; a compra do
   novo saiu em duas transferências para a Auto Art. */
const RX_EVENTO_PATRIMONIAL = /\bkavak\b|\bauto\s*art\b/i;
const ehEventoPatrimonial = t => t.conta_tipo !== "CREDIT"
  && RX_EVENTO_PATRIMONIAL.test(t.desc || "");
/* As duas pontas conectadas vêm como `interna`; conta própria fora do perímetro
   vem com `externa`. Nenhuma das duas mede renda ou gasto. */
const ehMovimentacaoPropria = t => t.conta_tipo !== "CREDIT"
  && (t.natureza === "interna" || !!t.externa);
/* O banco prefixa o extrato com o meio de pagamento ("Transferência
   enviada|FULANO", "Pagamento de Pix QR Code LOJA"). Na tabela de destino isso
   e ruido: o meio ja tem coluna propria. Rotulo mascarado nao casa com nenhum
   prefixo, entao passa intacto. */
const limpaDesc = d => (d || "?")
  .replace(/^(transfer[êe]ncia (pix )?(enviada|recebida)|pix (enviado|recebido)|pagamento de (pix qr code|conta|boleto)|ted (enviada|recebida))\s*\|?\s*/i, "")
  .trim() || (d || "?");
const daConta = n => D.lancamentos.filter(t => t.conta_tipo !== "CREDIT"
                                          && t.natureza === n);
const saidasCC   = daConta("consumo");
const entradasCC = daConta("entrada");
const faturasCC  = daConta("fatura");
const aplicCC    = D.lancamentos.filter(t => t.conta_tipo !== "CREDIT"
                                        && t.natureza === "investimento");

/* ---------- contraparte: quem esta do outro lado do PIX ----------
   Um quarto da saida da conta (R$ 70 mil em 12 meses) parava em
   "Transferencias" ou "Servicos" — baldes que nao dizem nada. O nome do outro
   lado SEMPRE esteve na descricao; o que faltava era virar linha.

   O que da pra decidir sozinho e a FORMA da contraparte, nunca a finalidade:

     pessoa fisica recorrente — ganha categoria propria com o nome e a contagem.
       Quem paga 25 PIX pra mesma pessoa em 12 meses sabe na hora o que e; a
       maquina nao sabe, e nao vai fingir que sabe.
     pessoa fisica eventual   — um balde so. Senao virariam 40 linhas de R$ 50
       cada, e a tabela deixaria de ser legivel pra ganhar nada.
     gateway de pagamento     — isso e COMPRA. O lojista e que esta escondido
       atras do adquirente (PagSeguro, PushinPay, Antpay...) e nao vem na API:
       o rotulo diz isso em vez de inventar uma loja.

   Nomear a finalidade e do Aleph: `contrapartes.json` (ao lado do mascara.json)
   mapeia regex -> rotulo/grupo, e vence tudo isso porque chega em `t.grupo`. */
/* Ganha linha propria quem aparece varias vezes OU quem levou dinheiro que
   importa. So a recorrencia deixava um PIX unico de R$ 1.500 pra um parente
   sumir no balde do "eventual" — valor alto e uma pergunta tao legitima quanto
   repeticao. O resto vira um balde so: 40 linhas de R$ 50 nao informam nada. */
const MIN_RECORRENTE = 3;
const MIN_NOMEADO = 1000;
/* balde final que nao informa nada — so nesses a contraparte entra */
const BALDE_VAGO = new Set(["Transferências", "Outros"]);
const RX_CNPJ = /^\d{2}\.\d{3}\.\d{3}\b/;
/* Empresa se reconhece por token inteiro, NAO por regex com \b: em JS o \b e
   ASCII, entao a letra acentuada conta como fronteira e /\bcia\b/ casa dentro
   de "Alicia" — a irma dele virava pessoa juridica. Tokenizar sem acento
   resolve de vez, e de quebra pega "S/A", "S.A." e "LTDA." na mesma peneira. */
const EMPRESA_TOKENS = new Set(["ltda","sa","eireli","epp","mei","me","cia",
  "inc","banco","bank","instituicao","pagamento","pagamentos","tecnologia",
  "servico","servicos","solucoes","comercio","industria","marketplace",
  "associacao","equipamentos","sistemas","brasil","pref","mun","detran",
  "restaurante","supermercado","farmacia","clinica","posto"]);
const semAcento = s => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "");
const ehEmpresa = nome => semAcento(nome).toLowerCase()
  .split(/[^a-z0-9]+/).filter(Boolean).some(w => EMPRESA_TOKENS.has(w));
/* adquirentes: cobram em nome de outro, entao o nome deles nao e o lojista */
const RX_GATEWAY = /pagseguro|pagbrasil|pushinpay|pay2all|antpay|paggo|unlimint|pagali|incentive pagamentos|mercado pago institui|pix marketplace|stafebank|moda mundial|amaralina|pagar\.?me|stripe|asaas|iugu|efi ?bank|juno|getnet|cielo|rede ?card/i;
/* nome de gente: so letras e conectivos, 2 a 6 palavras */
const RX_PESSOA = /^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.-]*(\s+[A-Za-zÀ-ÿ'.-]+){1,5}$/;

/* recorrencia so existe olhando a lista inteira, entao o mapa e montado na
   primeira pergunta — cls() ja roda antes de saidasCC estar pronto? nao: o
   primeiro uso e o totalGrupoCC, logo abaixo. */
let _recorr = null;
const recorrentes = () => {
  if (_recorr) return _recorr;
  _recorr = {};
  saidasCC.forEach(t => { const k = limpaDesc(t.desc);
                          const r = (_recorr[k] ||= {n: 0, v: 0});
                          r.n++; r.v += vAbs(t); });
  return _recorr;
};

/* Entra DEPOIS do mascara.json, do POR_NOME e das CATS: so preenche buraco,
   nunca sobrescreve classificacao boa. Devolve null pra deixar como estava. */
function contraparte(t, [cat, grupo]) {
  if (t.conta_tipo === "CREDIT" || t.externa) return null;
  /* mesma guarda do aplica_contrapartes no python: nome de pessoa so vira
     rotulo em saida de consumo. Um PIX recebido de alguem e entrada, nao
     gasto com essa pessoa, e transferencia interna nao e gasto com ninguem. */
  if (t.tipo !== "DEBIT" || t.natureza !== "consumo") return null;
  if (!(BALDE_VAGO.has(grupo) || cat === "Serviços")) return null;
  const nome = limpaDesc(t.desc);
  if (RX_GATEWAY.test(nome))
    return ["Compra via gateway (lojista oculto)", "Compras"];
  if (RX_CNPJ.test(nome) || ehEmpresa(nome) || !RX_PESSOA.test(nome))
    return null;
  const r = recorrentes()[nome] || {n: 0, v: 0};
  return (r.n >= MIN_RECORRENTE || r.v >= MIN_NOMEADO)
    ? [`${nome} (${r.n}x)`, "Pessoas"]
    : ["PIX eventual a pessoas", "Pessoas"];
}
