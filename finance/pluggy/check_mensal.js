/* check_mensal.js — conferencia do gera_fluxo_mensal.py, fora do navegador.
 *
 * Roda o JS DA PAGINA, nao uma copia dele: o bloco `JS` do gerador e puxado do
 * proprio modulo python, com o payload de verdade injetado, e avaliado aqui com
 * um DOM de mentira. Uma reescrita da mesma logica no harness passaria a
 * concordar com ela mesma e a divergir da tela na primeira mudanca.
 *
 * O que esta pagina promete e o que estes blocos cobram:
 *   1 nenhum lancamento perdido, duplicado ou fora de mes
 *   2 a soma dos meses e o total do ano, coluna a coluna
 *   3 em toda a arvore, o que a linha mostra e o que os lancamentos dela somam,
 *     e os filhos somam o pai — nos dois lados (entrou e saiu), em todo mes
 *   4 a ponte de caixa fecha, mes a mes, com o SALDO medido no extrato
 *   5 os dois botoes movem exatamente o que dizem que movem
 *   6 o mapa grupo x mes soma o mesmo total da espinha
 *
 * Uso: node check_mensal.js [consolidado.json]
 */
const fs = require("fs"), path = require("path"), cp = require("child_process");
const dir = __dirname;
const raw = process.argv[2] || path.join(dir, "../../../reports",
  "consolidado-" + new Date().toISOString().slice(0, 10) + ".json");

/* ---------- DOM de mentira ----------
   O JS da pagina pinta cinco lugares e desenha um grafico. Aqui nada precisa
   aparecer, mas tudo precisa existir: um getElementById que devolvesse
   undefined quebraria no primeiro `.innerHTML =` e o harness nunca chegaria a
   conferir numero nenhum. O innerHTML fica guardado — o bloco 3 le de volta. */
const PINT = {};
const noh = id => ({
  id,
  set innerHTML(v) { PINT[id] = v; }, get innerHTML() { return PINT[id] || ""; },
  set textContent(v) { PINT[id] = v; }, get textContent() { return PINT[id] || ""; },
  addEventListener() {}, scrollIntoView() {}, dataset: {},
  getContext: () => ({}),
});
const cache = new Map();
globalThis.document = {
  documentElement: {},
  getElementById: id => cache.get(id) || (cache.set(id, noh(id)), cache.get(id)),
  querySelector: () => noh("_"), querySelectorAll: () => [],
};
globalThis.getComputedStyle = () => ({getPropertyValue: () => "#000000"});
globalThis.Chart = class { constructor() {} destroy() {} };
globalThis.Chart.defaults = {};

/* ---------- o JS de verdade, com o payload de verdade ---------- */
const js = cp.execSync(
  `python3 -c "
import json,sys
sys.path.insert(0,'${dir}')
import gera_fluxo_mensal as G
from payload_consolidado import build
from gera_dashboard_consolidado import (classificador, aplica_contrapartes,
                                        aplica_mascara, aplica_posicoes_manuais)
P=build(json.load(open('${raw}')))
aplica_contrapartes(P); aplica_mascara(P); aplica_posicoes_manuais(P)
sys.stdout.write(G.JS.replace('__CLASSIFICADOR__', classificador())
                     .replace('__PAYLOAD__', json.dumps(P, ensure_ascii=False)))"`,
  {maxBuffer: 512 * 1024 * 1024, encoding: "utf-8"});

/* `const`/`let` declarados dentro de eval NUNCA escapam: a spec cria um escopo
   lexico proprio pro eval, direto ou indireto. O epilogo devolve na mao o que o
   harness usa — e essa lista e a interface real entre a pagina e a conferencia.
   setU/setX moram no epilogo de proposito: so quem esta DENTRO do escopo pode
   escrever nos `let` semUnicos/extRenda. */
const EXPORTA = ["D", "LIN", "monta", "quebra", "NIV_SAI", "NIV_REN", "balde",
  "vAbs", "vSai", "S", "Sa", "Ss", "RENDA", "GASTOCC", "ENTRAEXT", "SAIEXT",
  "INTERNAS", "unicos", "ehUnico", "gastos", "estornos", "entradasCC",
  "saidasCC", "faturasCC", "aplicCC", "grupoDe", "catDe", "ordenaGrupos",
  "abertos", "pintaEspinha", "redesenha", "rotMes", "MES0", "FUNDE", "prox"];
const A = (0, eval)(js + "\n;({" + EXPORTA.join(",") +
  ",setU:v=>{semUnicos=v},setX:v=>{extRenda=v}});");

const R2 = v => Math.round(v * 100) / 100;
const fmt = v => (v < 0 ? "-" : "") + "R$ " +
  Math.abs(v).toLocaleString("pt-BR", {minimumFractionDigits: 2, maximumFractionDigits: 2});
let falhas = 0;
const ok = (cond, msg, extra) => {
  console.log((cond ? "  ok   " : "  FALHA") + "  " + msg + (extra ? "  " + extra : ""));
  if (!cond) falhas++;
};
const perto = (a, b, tol) => Math.abs(a - b) < (tol === undefined ? 1e-6 : tol);
const bloco = t => console.log("\n" + t);

/* ============================================================ 1 */
bloco("1 · cobertura: todo lancamento em um mes, e um so");
{
  const universo = [...A.RENDA, ...A.GASTOCC, ...A.ENTRAEXT, ...A.SAIEXT,
                    ...A.gastos, ...A.estornos, ...A.faturasCC, ...A.aplicCC,
                    ...A.INTERNAS];
  const baldes = new Set(universo.map(A.balde));
  ok(![...baldes].some(b => b === A.MES0 && A.FUNDE),
     "nenhum lancamento sobrou no mes-toco " + A.MES0,
     A.FUNDE ? "(fundido em " + A.prox(A.MES0) + ")" : "(janela abre no dia 1)");
  const forma = /^\d{4}-\d{2}$/;
  ok([...baldes].every(b => forma.test(b)), "todo balde e YYYY-MM",
     baldes.size + " meses");
  ok(A.LIN.length === baldes.size, "a espinha tem uma linha por balde",
     A.LIN.length + " linhas");
  ok(A.LIN.every((r, i) => i === 0 || r.k > A.LIN[i-1].k), "meses em ordem");

  /* cada lancamento aparece exatamente uma vez nas listas de UM mes */
  const conta = new Map();
  A.LIN.forEach(r => [...r.renda, ...r.saiu].forEach(t =>
    conta.set(t, (conta.get(t) || 0) + 1)));
  const dups = [...conta.values()].filter(v => v > 1).length;
  const esperado = A.RENDA.length + A.GASTOCC.length + A.gastos.length + A.estornos.length;
  ok(dups === 0, "nenhum lancamento em dois meses", dups + " duplicados");
  ok(conta.size === esperado, "nenhum lancamento fora da espinha",
     conta.size + " de " + esperado);
}

/* ============================================================ 2 */
bloco("2 · a soma dos meses e o total do ano");
{
  const T = {
    e:  A.S(A.LIN, r => r.entrou),
    cc: A.S(A.LIN, r => r.saiuCC),
    cd: A.S(A.LIN, r => r.saiuCard),
  };
  ok(perto(T.e,  A.Sa(A.RENDA)),   "entrou", fmt(T.e));
  ok(perto(T.cc, A.Ss(A.GASTOCC)), "saiu da conta", fmt(T.cc));
  ok(perto(T.cd, A.Ss(A.gastos) + A.Ss(A.estornos)), "saiu no cartao (liq. estorno)",
     fmt(T.cd));
  const res = T.e - T.cc - T.cd;
  ok(perto(A.LIN[A.LIN.length - 1].acum, res), "o acumulado da ultima linha e o ano",
     fmt(res) + " em " + A.LIN.length + " meses = " + fmt(res / A.LIN.length) + "/mes");
}

/* ============================================================ 3 */
bloco("3 · a arvore: filhos somam o pai, sem perder nem duplicar lancamento");
{
  let nos = 0, folhas = 0, erroVal = 0, erroSoma = 0, erroSet = 0;
  function anda(lancs, niv, d, val) {
    const filhos = A.quebra(lancs, niv, d, val);
    if (!filhos.length) return;
    let soma = 0, n = 0;
    const vistos = new Set();
    filhos.forEach(no => {
      nos++;
      /* (a) o numero que a linha mostra e o que os lancamentos dela somam */
      if (!perto(no.val, A.S(no.lancs, val))) erroVal++;
      soma += no.val; n += no.lancs.length;
      no.lancs.forEach(t => vistos.add(t));
      if (no.lancs.length === 1) { folhas++; return; }
      if (no.d + 1 < niv.length) anda(no.lancs, niv, no.d + 1, val);
      else folhas += no.lancs.length;
    });
    /* (b) os filhos somam o pai   (c) o conjunto de lancamentos e o mesmo */
    if (!perto(soma, A.S(lancs, val), 1e-6)) erroSoma++;
    if (n !== lancs.length || vistos.size !== lancs.length) erroSet++;
  }
  A.LIN.forEach(r => {
    anda(r.renda, A.NIV_REN, 0, A.vAbs);
    anda(r.saiu,  A.NIV_SAI, 0, A.vSai);
  });
  ok(erroVal === 0,  "o valor da linha e a soma dos lancamentos dela", nos + " nos");
  ok(erroSoma === 0, "os filhos somam o pai em todo nivel");
  ok(erroSet === 0,  "nenhum lancamento perdido ou duplicado na quebra",
     folhas + " folhas");

  /* a tela: abrir TODO mundo e contar as linhas que sairam do innerHTML */
  A.abertos.clear();
  A.LIN.forEach(r => A.abertos.add(r.k));
  A.pintaEspinha();
  const html = document.getElementById("tabMM").innerHTML;
  const cnt = re => (html.match(re) || []).length;
  ok(cnt(/class="m-mes/g) === A.LIN.length, "uma linha de mes por mes");
  ok(cnt(/class="m-resumo"/g) === A.LIN.length, "a faixa de resumo abre junto");
  ok(cnt(/class="m-bloco"/g) === A.LIN.length * 2, "dois blocos por mes (entrou/saiu)");
  ok(cnt(/class="m-no"/g) > 0 && cnt(/class="m-folha"/g) > 0, "a arvore pintou",
     cnt(/class="m-no"/g) + " nos, " + cnt(/class="m-folha"/g) + " folhas visiveis");
  ok(!/undefined|NaN/.test(html), "nenhum undefined/NaN na tabela");
  A.abertos.clear();
}

/* ============================================================ 4 */
bloco("4 · a ponte de caixa fecha com o saldo do extrato");
{
  const fatia = (arr, k, f) => A.S(arr.filter(t => A.balde(t) === k), f || A.vAbs);
  let pior = 0, piorMes = "";
  A.LIN.forEach(r => {
    const ent = fatia(A.RENDA, r.k) + fatia(A.ENTRAEXT, r.k);
    const sai = fatia(A.GASTOCC, r.k) + fatia(A.SAIEXT, r.k);
    const fat = fatia(A.faturasCC, r.k);
    const apl = -fatia(A.aplicCC, r.k, t => t.valor);
    const int = fatia(A.INTERNAS, r.k, t => t.valor);
    const d = Math.abs((ent - sai - fat - apl + int) - r.caixa);
    if (d > pior) { pior = d; piorMes = r.k; }
  });
  ok(pior < 1e-6, "a ponte reconstroi a variacao de caixa de cada mes",
     "pior: " + pior.toExponential(1) + (piorMes ? " em " + piorMes : ""));

  const soma = A.S(A.LIN, r => r.caixa);
  const medido = A.D.caixa_final - A.D.caixa_inicial;
  ok(perto(soma, medido), "a soma dos meses e a variacao medida pelos saldos",
     fmt(medido) + " (residuo " + (soma - medido).toExponential(1) + ")");
  ok(perto(A.LIN[A.LIN.length - 1].saldo, A.D.caixa_final),
     "o saldo da ultima linha e o caixa de hoje", fmt(A.D.caixa_final));

  /* as internas so podem sumir se as DUAS pontas cairem no mesmo mes */
  const porMes = {};
  A.INTERNAS.forEach(t => porMes[A.balde(t)] = (porMes[A.balde(t)] || 0) + t.valor);
  const vaza = Object.entries(porMes).filter(([, v]) => Math.abs(v) > 0.005);
  ok(vaza.length === 0, "transferencia entre contas suas se anula dentro do mes",
     A.INTERNAS.length + " lancamentos" + (vaza.length ? " — vaza em " + vaza.map(x => x[0]) : ""));
}

/* ============================================================ 5 */
bloco("5 · os botoes movem exatamente o que dizem");
{
  const tot = L => ({e: A.S(L, r => r.entrou), s: A.S(L, r => r.total)});
  const base = tot(A.LIN);

  A.setU(true);  const semU = tot(A.monta());
  const U0 = A.unicos();
  A.setU(false);
  const uniE = A.Sa(U0.filter(t => t.natureza === "entrada"));
  const uniS = A.Sa(U0.filter(t => t.natureza === "consumo"));
  ok(perto(base.e - semU.e, uniE), "«sem eventos unicos» tira as entradas unicas",
     fmt(uniE));
  ok(perto(base.s - semU.s, uniS), "…e as saidas unicas, pelo mesmo corte", fmt(uniS));
  ok(uniE > 0 && uniS > 0, "o corte e simetrico: pega os dois lados",
     U0.length + " eventos");

  A.setX(true);  const comX = tot(A.monta()); A.setX(false);
  ok(perto(comX.e - base.e, A.Sa(A.ENTRAEXT)), "«conta externa = renda» soma so a entrada externa",
     fmt(A.Sa(A.ENTRAEXT)));
  ok(perto(comX.s - base.s, A.Sa(A.SAIEXT)), "…e a saida externa do outro lado",
     fmt(A.Sa(A.SAIEXT)));

  /* Aqui morava a conferencia errada. Ela cobrava que nenhum lancamento externo
     fosse evento unico — o que era verdade POR CONSTRUCAO (`!ehExt` dentro do
     `ehUnico`) e passava sempre, sem nunca olhar os dois botoes LIGADOS AO MESMO
     TEMPO. Era exatamente ali que a pagina mentia: com a conta externa contada
     como renda, o Pix de R$ 75.302 de 27/02 entrava no resultado e o botao
     «sem eventos unicos» nao conseguia tira-lo. O estado combinado agora tem
     conferencia propria. */
  A.setU(false); A.setX(false);
  const soExt = A.ENTRAEXT.concat(A.SAIEXT);
  A.setX(true);
  const extUni = soExt.filter(A.ehUnico);
  ok(extUni.length > 0,
     "com o botao 2 ligado, o corte enxerga a conta externa",
     extUni.length + " acima de R$ 15 mil: " + extUni.map(t => t.data).join(", "));
  const ambos = tot(A.monta());
  A.setU(true);  const ambosSemU = tot(A.monta());
  const dE = A.Sa(A.unicos().filter(t => t.natureza === "entrada"));
  const dS = A.Sa(A.unicos().filter(t => t.natureza === "consumo"));
  A.setU(false); A.setX(false);
  ok(perto(ambos.e - ambosSemU.e, dE),
     "com os dois botoes, «sem unicos» tira TAMBEM a entrada unica externa", fmt(dE));
  ok(perto(ambos.s - ambosSemU.s, dS), "…e a saida, pelo mesmo corte", fmt(dS));
  ok(dE - uniE > 0, "e a diferenca e exatamente o que estava escapando",
     fmt(dE - uniE));

  /* o sinal do ano nao pode depender de qual botao voce apertou por ultimo:
     antes do conserto, os dois ligados davam +R$ 68.645 ("sobrando") contra
     -R$ 66.336 so com o botao 1 */
  ok(ambosSemU.e - ambosSemU.s < 0,
     "com os dois botoes o ano continua negativo, como em toda outra combinacao",
     fmt(ambosSemU.e - ambosSemU.s));

  const depois = tot(A.monta());
  ok(perto(depois.e, base.e) && perto(depois.s, base.s),
     "voltar os botoes devolve os mesmos numeros");
}

/* ============================================================ 6 */
bloco("6 · o mapa grupo x mes soma o mesmo que a espinha");
{
  const gs = new Map();
  A.LIN.forEach(r => r.saiu.forEach(t => {
    const g = A.grupoDe(t), row = gs.get(g) || gs.set(g, {}).get(g);
    row[r.k] = (row[r.k] || 0) + A.vSai(t);
  }));
  const tot = {}; gs.forEach((row, g) => tot[g] = Object.values(row).reduce((a, b) => a + b, 0));
  let ruim = 0;
  A.LIN.forEach(r => {
    const col = [...gs.values()].reduce((s, row) => s + (row[r.k] || 0), 0);
    if (!perto(col, r.total)) ruim++;
  });
  ok(ruim === 0, "a coluna de cada mes soma o «saiu» daquele mes");
  const geral = Object.values(tot).reduce((a, b) => a + b, 0);
  ok(perto(geral, A.S(A.LIN, r => r.total)), "o total do mapa e o saiu do ano",
     fmt(geral));
  const ord = A.ordenaGrupos(tot);
  ok(ord.length === Object.keys(tot).length, "ordenaGrupos nao perde grupo novo",
     ord.length + " grupos");
  const neg = Object.entries(tot).filter(([, v]) => v < 0);
  ok(true, "grupos que fecham negativo (estorno > gasto) seguem no mapa",
     neg.length ? neg.map(([g, v]) => g + " " + fmt(v)).join(", ") : "nenhum");
}

console.log("\n" + (falhas ? falhas + " FALHA(S)" : "tudo certo") +
            " · " + A.D.resumo.n_lancamentos + " lancamentos · janela " +
            A.D.janela.join(" a "));
process.exit(falhas ? 1 : 0);
