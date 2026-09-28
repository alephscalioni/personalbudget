#!/usr/bin/env python3
"""Fluxo de caixa real: queimando ou gerando?

O dashboard de patrimonio responde "quanto eu tenho e onde gastei". Esta pagina
responde uma pergunta so: o dinheiro que entra paga o que sai, ou nao?

A diferenca esta em UMA distincao que o outro dashboard nao faz: `externa`.
O coletor marca assim a transferencia em que os dois lados sao o proprio Aleph
mas a outra ponta nao esta conectada no Open Finance (casa_internas nao achou o
par). Sao R$ 172.475 de "entrada" e R$ 37.493 de "saida" na janela.

Contar isso como renda e o que fazia a resposta virar de "queimando" pra
"gerando": nao e alguem pagando o Aleph, e dinheiro dele mesmo atravessando a
fronteira do que a API enxerga. Aqui ele aparece na PONTE (como foi bancado),
nunca na renda.

Reusa build() do payload_consolidado e classificador.js — a mesma taxonomia do
dashboard de patrimonio, pra um gasto nao cair em grupo diferente nas duas telas.
"""
import argparse, json
from datetime import date
from pathlib import Path

from payload_consolidado import build
from gera_dashboard_consolidado import (CSS, WORKSPACE, classificador, money,
                                        money0, periodo, aplica_contrapartes,
                                        aplica_mascara, aplica_posicoes_manuais)

JS = r"""
const D = __PAYLOAD__;
const fmt  = v => (v<0?"-":"") + "R$ " + Math.abs(v).toLocaleString("pt-BR",
                  {minimumFractionDigits:2, maximumFractionDigits:2});
const fmt0 = v => (v<0?"-":"") + "R$ " + Math.round(Math.abs(v)).toLocaleString("pt-BR");
const css  = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
/* Sem animacao de proposito: e uma pagina pra ler numero, nao pra assistir. De
   quebra, o screenshot de conferencia passa a mostrar o grafico pronto — com
   animacao ele congela no meio da transicao e nao prova nada. */
Chart.defaults.animation = false;

__CLASSIFICADOR__

/* ==================== as fatias ====================
   entradasCC / saidasCC / faturasCC / aplicCC vem do classificador.
   Aqui so entra a peneira que o outro dashboard nao tem: `externa`. */
const ehExt = t => !!t.externa;
const renda     = entradasCC.filter(t => !ehExt(t) && !ehEventoPatrimonial(t));
const entraExt  = entradasCC.filter(ehExt);            /* conta dele fora do Pluggy */
const gastoCC   = saidasCC.filter(t => !ehExt(t) && !ehEventoPatrimonial(t));
const saiExt    = saidasCC.filter(ehExt);              /* foi pra conta dele la fora */
const patrEntrada = entradasCC.filter(ehEventoPatrimonial);
const patrSaida   = saidasCC.filter(ehEventoPatrimonial);
/* no cartao o DEBIT vem positivo; estorno/cashback e CREDIT e abate */
const gastoCard = gastos, abateCard = estornos;

const S  = (arr, f) => arr.reduce((s,t) => s + (f?f(t):t.valor), 0);
const Sa = arr => S(arr, vAbs);

const TOT = {
  renda:    Sa(renda),
  gastoCC:  Sa(gastoCC),
  gastoCard:Sa(gastoCard) - Sa(abateCard),
  entraExt: Sa(entraExt),
  saiExt:   Sa(saiExt),
  patrEntrada: Sa(patrEntrada),
  patrSaida: Sa(patrSaida),
  fatura:   Sa(faturasCC),
  aplic:    -S(aplicCC),          /* >0 = aportou liquido; <0 = resgatou */
};
TOT.gasto     = TOT.gastoCC + TOT.gastoCard;
TOT.resultado = TOT.renda - TOT.gasto;
TOT.extLiq    = TOT.entraExt - TOT.saiExt;
TOT.patrLiq   = TOT.patrEntrada - TOT.patrSaida;
TOT.amortCard = TOT.fatura - TOT.gastoCard;   /* pagou mais fatura do que gastou */

/* ---------- eventos unicos ----------
   Regra mecanica, nao escolhida a dedo: >= CORTE, dos dois lados (entrada e
   saida), fora salario e fora `externa`. Simetrica de proposito — tirar a
   compra do carro sem tirar a venda dele faria o mes parecer um desastre que
   nao foi. A lista fica visivel na tela justamente porque a regra e grosseira. */
const CORTE = 15000;
const ehUnico = t => !ehExt(t) && Math.abs(t.valor) >= CORTE
                  && !ehEventoPatrimonial(t)
                  && t.metodo !== "Salário"
                  && (t.natureza === "entrada" || t.natureza === "consumo");
const unicos = D.lancamentos.filter(t => t.conta_tipo !== "CREDIT" && ehUnico(t))
                            .sort((a,b) => a.data.localeCompare(b.data));
const unicoRenda = Sa(unicos.filter(t => t.natureza === "entrada"));
const unicoGasto = Sa(unicos.filter(t => t.natureza === "consumo"));
TOT.recorrente = (TOT.renda - unicoRenda) - (TOT.gasto - unicoGasto);

/* ---------- meses ---------- */
const mes = t => t.data.slice(0,7);
const MESES = [...new Set(D.lancamentos.filter(t => t.conta_tipo !== "CREDIT")
                                       .map(mes))].sort();
const N_MES = MESES.filter(m => m >= MESES[1]).length;   /* 1o mes e so a borda */

let semUnicos = false;
const vis = arr => semUnicos ? arr.filter(t => !ehUnico(t)) : arr;
const serie = arr => MESES.map(m => Sa(vis(arr).filter(t => mes(t) === m)));

/* ==================== conferencia ====================
   A ponte tem que fechar no centavo com a variacao de caixa medida pelos
   saldos, senao alguma fatia esta sendo contada duas vezes ou nenhuma. */
const PONTE = TOT.resultado + TOT.patrLiq + TOT.extLiq
              - TOT.amortCard - TOT.aplic;
const DELTA = D.caixa_final - D.caixa_inicial;
const RESIDUO = Math.abs(PONTE - DELTA);
console.log("ponte", PONTE.toFixed(2), "delta caixa", DELTA.toFixed(2),
            "residuo", RESIDUO.toFixed(6));
if (RESIDUO > 0.01) console.error("PONTE NAO FECHA — residuo", RESIDUO);

/* ==================== cabecalho ==================== */
const queima = TOT.resultado < 0;
document.getElementById("veredito").innerHTML = queima
  ? 'Você está <em>queimando</em> caixa' : 'Você está <em>gerando</em> caixa';
document.getElementById("hero-v").textContent = fmt(TOT.resultado);
document.getElementById("hero-v").className = "price " + (queima ? "neg" : "pos");
document.getElementById("hero-mes").textContent = fmt0(TOT.resultado / N_MES) + " por mês";
document.getElementById("hero-rec").textContent = fmt0(TOT.recorrente / N_MES) + " por mês";

const kpi = (id, v, foot, cor) => {
  document.getElementById(id).textContent = fmt0(v);
  if (cor) document.getElementById(id).classList.add(cor);
  if (foot) document.getElementById(id+"-f").textContent = foot;
};
kpi("k-renda", TOT.renda, fmt0(TOT.renda/N_MES) + "/mês · " + renda.length + " entradas");
kpi("k-gasto", -TOT.gasto, fmt0(TOT.gasto/N_MES) + "/mês · conta + cartão", "neg");
kpi("k-res", TOT.resultado, "no período todo", queima ? "neg" : "pos");
kpi("k-rec", TOT.recorrente, "sem os " + unicos.length + " eventos únicos",
    TOT.recorrente < 0 ? "neg" : "pos");

/* ==================== 1. a ponte ==================== */
const linhasPonte = [
  ["Renda de terceiros",            TOT.renda,      "salário, PIX e TED de outras pessoas e empresas"],
  ["Gasto na conta corrente",      -TOT.gastoCC,    "PIX, boleto, débito, financiamento"],
  ["Gasto no cartão",              -TOT.gastoCard,  "compras do ciclo, já líquidas de estorno"],
  ["=RESULTADO",                    TOT.resultado,  "o que a renda cobriu do que você gastou"],
  ["Troca de veículo",              TOT.patrLiq,    fmt0(TOT.patrEntrada) + " da venda e " + fmt0(TOT.patrSaida) + " da compra; fora da análise normalizada"],
  ["Transferência da conta externa",TOT.extLiq,     entraExt.length + " entradas e " + saiExt.length + " saídas com o SEU nome dos dois lados"],
  ["Amortização da dívida do cartão",-TOT.amortCard,"pagou " + fmt0(TOT.fatura) + " de fatura para " + fmt0(TOT.gastoCard) + " de compra"],
  ["Aporte líquido em investimento",-TOT.aplic,     "aplicação menos resgate"],
  ["=VARIAÇÃO DE CAIXA",            DELTA,          fmt(D.caixa_inicial) + " no início, " + fmt(D.caixa_final) + " no fim"],
];
document.getElementById("ponte").innerHTML = linhasPonte.map(([n,v,nota]) => {
  const tot = n.startsWith("=");
  return `<tr class="${tot?'tot':''}"><td>${tot?n.slice(1):n}<i>${nota}</i></td>
          <td class="n ${v<0?'neg':'pos'}">${fmt(v)}</td></tr>`;
}).join("");
document.getElementById("residuo").textContent = RESIDUO < 0.01
  ? "confere no centavo (resíduo " + RESIDUO.toExponential(1) + ")"
  : "NÃO FECHA — resíduo " + fmt(RESIDUO);

/* ==================== 2. mes a mes ==================== */
const chMes = new Chart(document.getElementById("chMes"), {
  data: {labels: MESES, datasets: [
    {type:"bar",  label:"Renda",     backgroundColor:css("--pos"),  order:3},
    {type:"bar",  label:"Gasto",     backgroundColor:css("--neg"),  order:3},
    {type:"line", label:"Resultado", borderColor:css("--indigo"), borderWidth:2,
     pointRadius:3, pointBackgroundColor:css("--indigo"), fill:false, order:1},
  ]},
  options: {responsive:true, maintainAspectRatio:false,
    interaction:{mode:"index", intersect:false},
    scales:{y:{grid:{color:css("--grid")}, ticks:{callback:v=>fmt0(v)}},
            x:{grid:{display:false}}},
    plugins:{legend:{position:"bottom"},
             tooltip:{callbacks:{label:c=>c.dataset.label+": "+fmt(c.raw)}}}},
});
function renderMes() {
  const r = serie(renda), g = serie(gastoCC), c = serie(gastoCard), e = serie(abateCard);
  const gt = g.map((v,i) => v + c[i] - e[i]);
  chMes.data.datasets[0].data = r;
  chMes.data.datasets[1].data = gt.map(v => -v);
  chMes.data.datasets[2].data = r.map((v,i) => v - gt[i]);
  chMes.update();
  const azuis = r.filter((v,i) => v - gt[i] > 0).length;
  document.getElementById("mes-nota").textContent =
    azuis + " de " + MESES.length + " meses fecharam no azul.";
}

/* ==================== 3. onde foi (pizza) ==================== */
const porGrupo = () => {
  const t = {};
  vis(gastoCC).forEach(x => t[grupoDe(x)] = (t[grupoDe(x)]||0) + vAbs(x));
  vis(gastoCard).forEach(x => t[grupoDe(x)] = (t[grupoDe(x)]||0) + vAbs(x));
  vis(abateCard).forEach(x => t[grupoDe(x)] = (t[grupoDe(x)]||0) - vAbs(x));
  Object.keys(t).forEach(k => { if (Math.abs(t[k]) < 0.005) delete t[k]; });
  return t;
};
const chPizza = new Chart(document.getElementById("chPizza"), {
  type:"doughnut",
  options:{responsive:true, maintainAspectRatio:false, cutout:"58%",
    plugins:{legend:{position:"right", labels:{boxWidth:12, font:{size:11}}},
      tooltip:{callbacks:{label:c => c.label+": "+fmt(c.raw)+
        "  ("+(100*c.raw/c.dataset.data.reduce((a,b)=>a+b,0)).toFixed(1)+"%)"}}}},
});
function renderPizza() {
  const t = porGrupo(), gs = ordenaGrupos(t), tot = gs.reduce((s,g)=>s+t[g],0);
  /* Grupo pode fechar NEGATIVO quando o estorno do periodo passa o gasto — e o
     caso de "Outros", que leva um credito de R$ 2.099 da Samsung contra R$ 962
     de gasto. Doughnut do Chart.js desenha Math.abs(valor): a fatia apareceria
     como gasto positivo e TODO percentual sairia errado, porque o denominador
     e a soma dos desenhados. Entao o negativo sai do grafico e vira linha
     explicita embaixo — some do desenho, nao da conta: o total da legenda e da
     tabela continua sendo o liquido de verdade. */
  const desenha = gs.filter(g => t[g] > 0), fora = gs.filter(g => t[g] <= 0);
  chPizza.data = {labels:desenha, datasets:[{data:desenha.map(g=>t[g]),
                  backgroundColor:desenha.map(corDe), borderWidth:0}]};
  chPizza.update();
  document.getElementById("pizza-tot").textContent = fmt(tot);
  document.getElementById("pizza-neg").innerHTML = fora.length
    ? "Fora do gráfico por fechar negativo (estorno maior que o gasto): "
      + fora.map(g => `<b>${g}</b> ${fmt(t[g])}`).join(", ")
      + ". Continua contando no total e na tabela."
    : "";
  /* categorias dentro do grupo, pra pizza nao virar so nome bonito */
  const cats = {};
  const junta = (arr, sinal) => arr.forEach(x => {
    const k = grupoDe(x) + "||" + catDe(x);
    cats[k] = (cats[k]||0) + sinal*vAbs(x); });
  junta(vis(gastoCC),1); junta(vis(gastoCard),1); junta(vis(abateCard),-1);
  document.getElementById("tabCat").innerHTML = gs.map(g => {
    const linhas = Object.entries(cats).filter(([k]) => k.startsWith(g+"||"))
      .map(([k,v]) => [k.split("||")[1], v]).filter(([,v]) => Math.abs(v) >= 0.005)
      .sort((a,b) => b[1]-a[1]);
    return `<tr class="tot"><td><b style="color:${corDe(g)}">■</b> ${g}</td>
            <td class="n">${fmt(t[g])}</td><td class="n pc">${(100*t[g]/tot).toFixed(1)}%</td></tr>`
         + linhas.map(([c,v]) =>
            `<tr><td class="ind">${c}</td><td class="n">${fmt(v)}</td>
             <td class="n pc">${(100*v/tot).toFixed(1)}%</td></tr>`).join("");
  }).join("");
}

/* ==================== 4. resgates ==================== */
/* O que ele perguntou: "teve meses que resgatei pra pagar as coisas". Entao a
   tabela nao mostra so o resgate — mostra o resgate ao lado do buraco do mes e
   dos maiores gastos daquele mes, que e a resposta pra "pagar o que". */
const linhasRes = MESES.map(m => {
  const doMes = a => a.filter(t => mes(t) === m);
  const apl = doMes(aplicCC);
  const res = S(apl.filter(t => t.valor > 0)), apo = -S(apl.filter(t => t.valor < 0));
  const r = Sa(doMes(renda));
  const g = Sa(doMes(gastoCC)) + Sa(doMes(gastoCard)) - Sa(doMes(abateCard));
  const maiores = [...doMes(gastoCC), ...doMes(gastoCard)]
    .sort((a,b) => vAbs(b)-vAbs(a)).slice(0,3)
    .map(t => limpaDesc(t.desc) + " " + fmt0(vAbs(t))).join(" · ");
  return {m, res, apo, liq: res-apo, saldo: r-g, maiores};
}).filter(x => x.res || x.apo);
document.getElementById("tabRes").innerHTML = linhasRes.map(x =>
  `<tr><td>${x.m}</td>
   <td class="n">${x.apo?fmt0(-x.apo):"—"}</td>
   <td class="n">${x.res?fmt0(x.res):"—"}</td>
   <td class="n ${x.liq>0?'neg':'pos'}"><b>${fmt0(x.liq)}</b></td>
   <td class="n ${x.saldo<0?'neg':'pos'}">${fmt0(x.saldo)}</td>
   <td class="d">${x.maiores||"—"}</td></tr>`).join("");
const resTot = linhasRes.reduce((s,x)=>s+x.res,0), apoTot = linhasRes.reduce((s,x)=>s+x.apo,0);
document.getElementById("res-nota").textContent =
  "Resgatou " + fmt(resTot) + " e aplicou " + fmt(apoTot) + " na janela: "
  + (resTot > apoTot ? "saldo de " + fmt(resTot-apoTot) + " saiu do investimento pro caixa."
                     : "sobrou " + fmt(apoTot-resTot) + " indo pro investimento.");

/* ==================== 5. a conta externa ==================== */
document.getElementById("tabExt").innerHTML =
  [...entraExt, ...saiExt].sort((a,b) => a.data.localeCompare(b.data)).map(t =>
  `<tr><td>${t.data.split("-").reverse().join("/")}</td>
   <td class="d">${limpaDesc(t.desc)}</td><td>${t.instituicao}</td>
   <td class="n ${t.valor<0?'neg':'pos'}">${fmt(t.valor)}</td></tr>`).join("");
document.getElementById("ext-tot").textContent = fmt(TOT.extLiq);

/* ==================== 6. eventos unicos ==================== */
document.getElementById("tabUni").innerHTML = unicos.map(t =>
  `<tr><td>${t.data.split("-").reverse().join("/")}</td>
   <td class="d">${limpaDesc(t.desc)}</td><td>${t.instituicao}</td>
   <td class="n ${t.valor<0?'neg':'pos'}">${fmt(t.valor)}</td></tr>`).join("");

/* ==================== toggle ==================== */
document.getElementById("tg").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  semUnicos = b.dataset.v === "1";
  [...e.currentTarget.children].forEach(x => x.classList.toggle("on", x === b));
  desenha();
});
function desenha() { renderMes(); renderPizza(); }
desenha();
addEventListener("resize", () => [chMes, chPizza].forEach(c => c.resize()));
"""

CSS_EXTRA = """
.price.neg{color:#ff9d8a}.price.pos{color:#7fd6a8}
.kpi .v.neg{color:var(--neg)}.kpi .v.pos{color:var(--pos)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-family:var(--f-mono);font-size:10px;letter-spacing:1.5px;
text-transform:uppercase;color:var(--muted);font-weight:500;padding:0 8px 8px;
border-bottom:1px solid var(--line)}
td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.pc{color:var(--muted);width:64px}
td.d{color:var(--muted)}
td.ind{padding-left:26px;color:var(--muted)}
tr.tot td{font-weight:700;background:var(--off);border-bottom:1px solid var(--base)}
tr.tot td i{font-weight:400}
td i{display:block;font-style:normal;font-size:11px;color:var(--muted);margin-top:2px}
.n.neg{color:var(--neg)}.n.pos{color:var(--pos)}
.ch{height:320px;position:relative}
.ch-sm{height:300px;position:relative}
.tg{display:inline-flex;border:1px solid var(--line);background:var(--white);margin-bottom:14px}
.tg button{font:inherit;font-size:12px;padding:7px 14px;border:0;background:none;
cursor:pointer;color:var(--muted)}
.tg button.on{background:var(--base);color:var(--off)}
.nota{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.55}
.alerta{background:#fdf6e3;border:1px solid #e8d9a8;border-left:3px solid var(--amber);
padding:16px 20px;margin-bottom:18px;font-size:13px;line-height:1.6}
.alerta b{color:var(--base)}
.ok{font-family:var(--f-mono);font-size:11px;color:var(--pos)}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}
.cols2{grid-template-columns:1fr}.wrap{padding:32px 20px 48px}h1{font-size:38px}}
"""

HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Queimando ou gerando? — __DATA_BR__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>__CSS__</style><script>__CHARTJS__</script></head><body>
<div class="wrap">
  <div class="page-label">Fluxo de caixa normalizado · __JANELA__</div>
  <h1 id="veredito">—</h1>
  <p class="subtitle">Renda de terceiros contra gasto de verdade, nos
  __PERIODO__. Transferências entre contas próprias e a compra/venda dos carros
  ficam fora da renda e dos gastos; aparecem apenas na reconciliação do caixa.</p>

  <div class="total-card">
    <div class="lbl">Resultado no período</div>
    <div class="price" id="hero-v">—</div>
    <div class="sub"><span id="hero-mes">—</span>
      <span>sem eventos únicos: <b id="hero-rec">—</b></span>
      <span>caixa hoje __CAIXA__ · investido __INVEST__ __MANUAL__ · fatura aberta __DIVIDA__</span></div>
  </div>

  <div class="alerta"><b>Análise normalizada.</b> Movimentações entre suas contas
    não entram como renda nem gasto. A venda do carro antigo e os três pagamentos
    da compra do carro novo também foram retiradas do resultado operacional.
    Premissa atual de renda líquida familiar: <b>__RENDA_ATUAL__/mês</b>
    (__RENDA_ALEPH__ Aleph + __RENDA_BIA__ Bia). Contra gasto normalizado médio
    de <b>__GASTO_MEDIO__/mês</b>, a margem estimada é
    <b>__MARGEM_ATUAL__/mês</b>. Bônus de fevereiro/março e setembro ficam
    separados como renda extraordinária.</div>

  <div class="grid kpis" style="margin-bottom:44px">
    <div class="card kpi"><div class="label">Renda de terceiros</div>
      <div class="v" id="k-renda">—</div><div class="foot" id="k-renda-f">—</div></div>
    <div class="card kpi"><div class="label">Gasto total</div>
      <div class="v" id="k-gasto">—</div><div class="foot" id="k-gasto-f">—</div></div>
    <div class="card kpi"><div class="label">Resultado</div>
      <div class="v" id="k-res">—</div><div class="foot" id="k-res-f">—</div></div>
    <div class="card kpi"><div class="label">Resultado recorrente</div>
      <div class="v" id="k-rec">—</div><div class="foot" id="k-rec-f">—</div></div>
  </div>

  <section><h2>1 · A conta inteira, de cima a baixo</h2>
    <div class="card"><table><tbody id="ponte"></tbody></table>
      <div class="nota">A última linha é a variação de caixa medida pelos saldos
      das contas — não é calculada a partir das de cima. Bater as duas é a prova
      de que nenhuma fatia foi contada duas vezes ou esquecida:
      <span class="ok" id="residuo">—</span></div></div></section>

  <section><h2>2 · Mês a mês</h2>
    <div class="tg" id="tg"><button data-v="0" class="on">Tudo</button>
      <button data-v="1">Sem eventos únicos</button></div>
    <div class="card"><div class="ch"><canvas id="chMes"></canvas></div>
      <div class="nota" id="mes-nota">—</div></div></section>

  <section><h2>3 · Onde o dinheiro foi</h2>
    <div class="grid cols2">
      <div class="card"><div class="ch-sm"><canvas id="chPizza"></canvas></div>
        <div class="nota">Total: <b id="pizza-tot">—</b> — conta corrente e
        cartão somados, líquidos de estorno. Segue o botão da seção 2.
        <span id="pizza-neg"></span></div></div>
      <div class="card" style="max-height:520px;overflow:auto">
        <table><thead><tr><th>Grupo e categoria</th><th class="n">Valor</th>
        <th class="n">%</th></tr></thead><tbody id="tabCat"></tbody></table></div>
    </div></section>

  <section><h2>4 · Os resgates: o que cada um pagou</h2>
    <div class="card"><table><thead><tr><th>Mês</th><th class="n">Aplicou</th>
      <th class="n">Resgatou</th><th class="n">Líquido</th>
      <th class="n">Sobra do mês</th><th>Maiores gastos do mês</th></tr></thead>
      <tbody id="tabRes"></tbody></table>
      <div class="nota" id="res-nota">—</div></div></section>

  <section><h2>5 · Os eventos únicos que o botão tira</h2>
    <div class="card"><table><thead><tr><th>Data</th><th>Descrição</th>
      <th>Instituição</th><th class="n">Valor</th></tr></thead>
      <tbody id="tabUni"></tbody></table>
      <div class="nota">Regra: R$ 15 mil ou mais, entrada e saída pelo mesmo
      critério, fora salário e fora a troca dos carros, que já é excluída da
      análise normalizada por regra explícita.</div>
    </div></section>

  <section><h2>6 · Movimentações próprias fora do Open Finance</h2>
    <div class="card"><table><thead><tr><th>Data</th><th>Descrição</th>
      <th>Instituição</th><th class="n">Valor</th></tr></thead>
      <tbody id="tabExt"></tbody></table>
      <div class="nota">Líquido: <b id="ext-tot">—</b>. O coletor tentou casar
      cada um com a outra ponta em alguma conta conectada e não achou — por isso
      não virou transferência interna. Elas ficam nesta conferência, mas são
      excluídas da renda, do gasto e do resultado normalizado.</div></div></section>

  <div class="nota">Gerado em __DATA_BR__ · __N_LANC__ lançamentos ·
  __N_INST__ instituições · janela __JANELA__</div>
</div>
<script>__JS__</script></body></html>
"""


def render(P: dict) -> str:
    d1, d2 = P["janela"]
    r = P["resumo"]
    prem = json.loads((Path(__file__).resolve().parent / "premissas-fluxo.json")
                      .read_text(encoding="utf-8"))["renda_mensal"]
    renda_atual = prem["aleph_liquido"] + prem["bia_liquido"]
    veiculo = lambda t: any(x in (t.get("desc") or "").lower()
                            for x in ("kavak", "auto art"))
    cc = sum(abs(t["valor"]) for t in P["lancamentos"]
             if t["conta_tipo"] != "CREDIT" and t.get("natureza") == "consumo"
             and not t.get("externa") and not veiculo(t))
    card = sum(abs(t["valor"]) * (1 if t["tipo"] == "DEBIT" else -1)
               for t in P["lancamentos"] if t["conta_tipo"] == "CREDIT"
               and t.get("categoria") != "Credit card payment" and t.get("fatura"))
    meses = max(1, len({t["data"][:7] for t in P["lancamentos"]
                        if t["conta_tipo"] != "CREDIT"}) - 1)
    gasto_medio = (cc + card) / meses
    br = lambda s: "/".join(reversed(s.split("-")))
    ext = [t for t in P["lancamentos"]
           if t["conta_tipo"] != "CREDIT" and t.get("externa")]
    v_ext = sum(t["valor"] for t in ext)
    vendor = Path(__file__).resolve().parent / "vendor" / "chart.umd.min.js"
    chartjs = (vendor.read_text(encoding="utf-8") if vendor.exists()
               else 'document.write(\'<script src="https://cdn.jsdelivr.net/npm/'
                    'chart.js@4.4.1/dist/chart.umd.min.js"><\\/script>\')')
    return (HTML
            .replace("__CHARTJS__", chartjs)
            .replace("__CSS__", CSS + CSS_EXTRA)
            .replace("__JS__", JS.replace("__CLASSIFICADOR__", classificador())
                                 .replace("__PAYLOAD__",
                                          json.dumps(P, ensure_ascii=False)))
            .replace("__DATA_BR__", br(P["gerado_em"]))
            .replace("__JANELA__", f"{br(d1)} a {br(d2)}")
            .replace("__PERIODO__", periodo(d1, d2))
            .replace("__N_EXT__", str(len(ext)))
            .replace("__V_EXT__", money(v_ext))
            .replace("__N_LANC__", str(r["n_lancamentos"]))
            .replace("__N_INST__", str(r["n_instituicoes"]))
            .replace("__CAIXA__", money0(r["caixa"]))
            .replace("__INVEST__", money0(r["investimentos"]))
            .replace("__DIVIDA__", money0(r["divida"]))
            .replace("__RENDA_ATUAL__", money0(renda_atual))
            .replace("__RENDA_ALEPH__", money0(prem["aleph_liquido"]))
            .replace("__RENDA_BIA__", money0(prem["bia_liquido"]))
            .replace("__GASTO_MEDIO__", money0(gasto_medio))
            .replace("__MARGEM_ATUAL__", money0(renda_atual - gasto_medio))
            .replace("__MANUAL__", "" if not P.get("manual_total") else
                     f'(inclui {money0(P["manual_total"])} declarado, '
                     "fora do que a API devolve)"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    src = (Path(args.raw) if args.raw else
           WORKSPACE / "reports" / f"consolidado-{date.today()}.json")
    P = build(json.loads(src.read_text(encoding="utf-8")))
    aplica_contrapartes(P)
    aplica_mascara(P)
    # so mexe na FOTO do patrimonio (o rodape do cartao); o fluxo nao muda uma
    # virgula porque aplicacao e resgate ja vem pelo extrato da conta corrente
    aplica_posicoes_manuais(P)
    dest = (Path(args.out) if args.out else
            WORKSPACE / "reports" / f"fluxo-caixa-real-{date.today()}.html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render(P), encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
