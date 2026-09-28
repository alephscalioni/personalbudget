/* check_fluxo.js — conferencia do gera_fluxo_real.py, fora do navegador.
 *
 * A pagina responde "queimando ou gerando" com uma ponte de 8 linhas. Se
 * qualquer fatia (renda, gasto, externa, fatura, aplicacao) for contada duas
 * vezes ou esquecida, a ponte deixa de bater com a variacao de caixa medida
 * pelos SALDOS das contas — que e um numero independente, vindo do extrato.
 *
 * Uso: node check_fluxo.js [consolidado.json]
 */
const fs = require("fs"), path = require("path"), cp = require("child_process");
const dir = __dirname;
const raw = process.argv[2] || path.join(dir, "../../../reports",
  "consolidado-" + new Date().toISOString().slice(0,10) + ".json");

/* o payload passa pelo build() + contrapartes + mascara, igual a pagina */
globalThis.D = JSON.parse(cp.execSync(
  `python3 -c "
import json,sys
sys.path.insert(0,'${dir}')
from payload_consolidado import build
from gera_dashboard_consolidado import aplica_contrapartes, aplica_mascara
import hashlib
from gera_dashboard_consolidado import aplica_posicoes_manuais
P=build(json.load(open('${raw}')))
aplica_contrapartes(P); aplica_mascara(P)
h=lambda: hashlib.sha256(json.dumps(P['lancamentos'],sort_keys=True).encode()).hexdigest()
antes=h(); inv_antes=P['resumo']['investimentos']
manual=aplica_posicoes_manuais(P)
P['_manual']={'intacto':antes==h(),'valor':manual,
              'delta_inv':round(P['resumo']['investimentos']-inv_antes,2)}
print(json.dumps(P,ensure_ascii=False))"`,
  {maxBuffer: 512*1024*1024, encoding:"utf-8"}));

/* `const` declarado dentro de eval NUNCA escapa: a spec cria um escopo lexico
   proprio pro eval, valha ele direto ou indireto. Entao o classificador roda
   com um epilogo que devolve na mao o que a pagina usa dele — a lista abaixo e
   a interface real entre classificador.js e quem o consome. */
const EXPORTA = ["entradasCC","saidasCC","faturasCC","aplicCC","gastos","estornos",
                 "vAbs","limpaDesc","catDe","grupoDe","corDe","ordenaGrupos"];
const CLS = (0, eval)(
  fs.readFileSync(path.join(dir, "classificador.js"), "utf-8")
  + "\n;({" + EXPORTA.join(",") + "});");
const {entradasCC, saidasCC, faturasCC, aplicCC, gastos, estornos,
       vAbs, limpaDesc, catDe, grupoDe, corDe, ordenaGrupos} = CLS;
const D = globalThis.D;

const ehExt = t => !!t.externa;
const renda    = entradasCC.filter(t => !ehExt(t));
const entraExt = entradasCC.filter(ehExt);
const gastoCC  = saidasCC.filter(t => !ehExt(t));
const saiExt   = saidasCC.filter(ehExt);
const S  = (a,f) => a.reduce((s,t) => s + (f?f(t):t.valor), 0);
const Sa = a => S(a, vAbs);
const R = v => Math.round(v*100)/100;

const T = {renda:Sa(renda), gastoCC:Sa(gastoCC), gastoCard:Sa(gastos)-Sa(estornos),
           entraExt:Sa(entraExt), saiExt:Sa(saiExt), fatura:Sa(faturasCC),
           aplic:-S(aplicCC)};
T.resultado = T.renda - T.gastoCC - T.gastoCard;
T.extLiq    = T.entraExt - T.saiExt;
T.amortCard = T.fatura - T.gastoCard;

let erros = 0;
const ok = (nome, cond, detalhe) => {
  console.log((cond ? "  ok   " : "  FALHA") + "  " + nome + (detalhe ? "  — " + detalhe : ""));
  if (!cond) erros++;
};

console.log("\n== 1. a ponte fecha com a variacao de caixa medida pelos saldos ==");
const ponte = T.resultado + T.extLiq - T.amortCard - T.aplic;
const delta = D.caixa_final - D.caixa_inicial;
ok("ponte == delta caixa", Math.abs(ponte - delta) < 0.01,
   `ponte ${R(ponte)} vs delta ${R(delta)} (residuo ${(ponte-delta).toExponential(2)})`);

console.log("\n== 2. as 5 naturezas cobrem todo lancamento de conta corrente ==");
const cc = D.lancamentos.filter(t => t.conta_tipo !== "CREDIT");
const nats = {}; cc.forEach(t => nats[t.natureza] = (nats[t.natureza]||0) + 1);
ok("nenhuma natureza fora das 5", Object.keys(nats).every(n =>
   ["consumo","entrada","fatura","interna","investimento"].includes(n)),
   JSON.stringify(nats));
ok("soma dos lancamentos == delta caixa",
   Math.abs(S(cc) - delta) < 0.01, `${R(S(cc))} vs ${R(delta)}`);

console.log("\n== 3. externa nao vaza pra renda nem pro gasto ==");
ok("renda sem externa", renda.every(t => !t.externa), `${renda.length} lancamentos`);
ok("gasto CC sem externa", gastoCC.every(t => !t.externa), `${gastoCC.length} lancamentos`);
ok("entrada = renda + externa",
   Math.abs(Sa(entradasCC) - (T.renda + T.entraExt)) < 0.01);
ok("consumo = gasto + externa",
   Math.abs(Sa(saidasCC) - (T.gastoCC + T.saiExt)) < 0.01);

console.log("\n== 4. cartao: a pizza nao conta a fatura por cima da compra ==");
ok("fatura fora do gasto", !gastos.some(t => t.categoria === "Credit card payment"));
ok("fatura fora da conta corrente", !gastoCC.some(t => t.natureza === "fatura"));
ok("todo gasto de cartao tem ciclo", gastos.every(t => !!t.fatura));

console.log("\n== 5. pizza: soma dos grupos == gasto total ==");
const g = {};
gastoCC.forEach(t => g[grupoDe(t)] = (g[grupoDe(t)]||0) + vAbs(t));
gastos .forEach(t => g[grupoDe(t)] = (g[grupoDe(t)]||0) + vAbs(t));
estornos.forEach(t => g[grupoDe(t)] = (g[grupoDe(t)]||0) - vAbs(t));
const somaG = Object.values(g).reduce((a,b)=>a+b,0);
ok("soma dos grupos == gastoCC + cartao",
   Math.abs(somaG - (T.gastoCC + T.gastoCard)) < 0.01,
   `${R(somaG)} vs ${R(T.gastoCC + T.gastoCard)}`);
ok("todo grupo desenha (ordenaGrupos nao perde nenhum)",
   ordenaGrupos(g).length === Object.keys(g).filter(k => g[k]).length,
   `${ordenaGrupos(g).length} grupos`);

console.log("\n== 6. eventos unicos: a regra e simetrica ==");
const CORTE = 15000;
const ehUnico = t => !ehExt(t) && Math.abs(t.valor) >= CORTE && t.metodo !== "Salário"
                  && (t.natureza === "entrada" || t.natureza === "consumo");
const u = cc.filter(ehUnico);
ok("pega os dois lados", u.some(t=>t.valor>0) && u.some(t=>t.valor<0),
   `${u.filter(t=>t.valor>0).length} entradas, ${u.filter(t=>t.valor<0).length} saidas`);
ok("nao pega salario", !u.some(t => t.metodo === "Salário"));
ok("nao pega externa", !u.some(t => t.externa));

console.log("\n== 7. o botao 'sem eventos unicos' ==");
/* O screenshot nao clica no botao, entao a conferencia do toggle mora aqui:
   tirar os unicos tem que bater exatamente com o KPI de resultado recorrente,
   e a pizza tem que encolher exatamente o gasto unico — nem mais, nem menos. */
const uRenda = Sa(u.filter(t => t.natureza === "entrada"));
const uGasto = Sa(u.filter(t => t.natureza === "consumo"));
const recorrente = (T.renda - uRenda) - (T.gastoCC + T.gastoCard - uGasto);
ok("recorrente == resultado sem o liquido dos unicos",
   Math.abs(recorrente - (T.resultado - uRenda + uGasto)) < 0.01,
   `${R(recorrente)}`);
const gSem = {};
gastoCC.filter(t => !ehUnico(t)).forEach(t => gSem[grupoDe(t)] = (gSem[grupoDe(t)]||0) + vAbs(t));
gastos.forEach(t => gSem[grupoDe(t)] = (gSem[grupoDe(t)]||0) + vAbs(t));
estornos.forEach(t => gSem[grupoDe(t)] = (gSem[grupoDe(t)]||0) - vAbs(t));
ok("pizza encolhe exatamente o gasto unico",
   Math.abs(Object.values(gSem).reduce((a,b)=>a+b,0) - (somaG - uGasto)) < 0.01,
   `${R(Object.values(gSem).reduce((a,b)=>a+b,0))} vs ${R(somaG - uGasto)}`);
/* Grupo negativo (estorno > gasto) e legitimo no total, mas nao pode ir pro
   doughnut, que desenha Math.abs e estragaria todo percentual. O contrato e:
   sai do desenho, fica no total. */
const negS = Object.entries(gSem).filter(([,v]) => v < 0).map(([k])=>k);
const negT = Object.entries(g).filter(([,v]) => v < 0).map(([k])=>k);
ok("grupo negativo fica fora do desenho mas dentro do total",
   Math.abs(Object.values(gSem).reduce((a,b)=>a+b,0)
            - Object.entries(gSem).filter(([,v])=>v>0).reduce((a,[,v])=>a+v,0)
            - Object.entries(gSem).filter(([,v])=>v<=0).reduce((a,[,v])=>a+v,0)) < 0.01,
   `negativos: ${(negT.length?negT:["nenhum"]).join(",")}`);
ok("cartao nao entra na regra de unico (natureza nula)",
   !gastos.some(ehUnico) && !estornos.some(ehUnico));

console.log("\n== 8. posicao declarada a mao nao contamina o fluxo ==");
/* Aplicacao e resgate ja chegam pelo extrato com natureza "investimento". Se o
   aplica_posicoes_manuais encostasse em lancamento, a mesma grana entraria
   duas vezes e a ponte pararia de fechar — sem erro nenhum na tela. */
const MAN = D._manual || {};
ok("nao encostou em nenhum lancamento", MAN.intacto === true,
   `declarado ${R(MAN.valor||0)}`);
ok("entrou inteiro no patrimonio", Math.abs((MAN.delta_inv||0) - (MAN.valor||0)) < 0.01,
   `delta investimentos ${R(MAN.delta_inv||0)}`);
ok("ponte segue fechando depois de aplicar", Math.abs(ponte - delta) < 0.01);
ok("toda posicao declarada se identifica",
   D.investimentos.filter(v => v.manual).every(v => v.referencia && v.origem),
   `${D.investimentos.filter(v => v.manual).length} declaradas`);

console.log("\n== numeros ==");
Object.entries(T).forEach(([k,v]) => console.log(`  ${k.padEnd(11)} ${R(v).toLocaleString("pt-BR")}`));
console.log(`  ${"ponte".padEnd(11)} ${R(ponte)}   delta caixa ${R(delta)}`);
console.log(erros ? `\n${erros} FALHA(S)\n` : "\nTudo confere.\n");
process.exit(erros ? 1 : 0);
