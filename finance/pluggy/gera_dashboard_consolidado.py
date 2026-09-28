#!/usr/bin/env python3
"""Dashboard HTML consolidado (multi-instituicao) a partir do payload Pluggy.

Uso: ./gera_dashboard_consolidado.py [--raw reports/consolidado-YYYY-MM-DD.json]
"""
import argparse, json, re
from datetime import date
import os
from pathlib import Path

from payload_consolidado import build

WORKSPACE = Path(__file__).resolve().parents[3]


def money(v: float) -> str:
    """R$ no padrao pt-BR, sem depender de locale."""
    return ("-" if v < 0 else "") + "R$ " + (
        f"{abs(v):,.2f}".replace(",", "@").replace(".", ",").replace("@", "."))


def money0(v: float) -> str:
    return "R$ " + f"{round(v):,}".replace(",", ".")

CSS = """
/* Mesmo sistema de design do painel.alophus.com.br: paleta navy, Inter Tight +
   Instrument Serif + JetBrains Mono, cartao branco de canto reto com fio de 1px.
   Os --accent/--indigo/--amber/--pos/--grid/--muted precisam de valor literal:
   o JS dos graficos le por getPropertyValue e nao resolve var() aninhado. */
:root{
--base:#0A0D12;--surface:#1C2B3A;--primary:#2E6DA4;--primary-light:#85B7EB;
--cool:#C8D4DF;--off:#F0F4F8;--white:#ffffff;--line:#dbe3eb;
--f-sans:"Inter Tight",-apple-system,BlinkMacSystemFont,sans-serif;
--f-serif:"Instrument Serif",Georgia,serif;
--f-mono:"JetBrains Mono",ui-monospace,monospace;
--bg:#F0F4F8;--panel:#ffffff;--panel-2:#F0F4F8;--border:#dbe3eb;
--text:#0A0D12;--text-strong:#0A0D12;--muted:#5d6b78;
--accent:#2E6DA4;--indigo:#1C2B3A;--amber:#d4a017;
--pos:#1f7a4d;--neg:#b54232;--grid:rgba(10,13,18,.10)}
*{box-sizing:border-box}
html,body{background:var(--bg);color:var(--text);margin:0;padding:0;
font-family:var(--f-sans);font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}

/* ── Cabecalho editorial (mesmo padrao de /apps, /calc3d, /tv) ── */
.wrap{max-width:1280px;margin:0 auto;padding:64px 48px 80px}
.page-label{font-family:var(--f-mono);font-size:11px;letter-spacing:2px;
text-transform:uppercase;color:var(--primary);margin-bottom:16px}
h1{font-family:var(--f-serif);font-weight:400;font-size:56px;line-height:1.05;
letter-spacing:-1px;margin:0 0 12px;color:var(--base)}
h1 em{font-style:italic;color:var(--primary)}
.subtitle{font-size:17px;color:var(--muted);max-width:640px;line-height:1.55;margin:0 0 32px}

/* ── Cartao do numero-cabeca, igual ao total-card da Calc 3D ── */
.total-card{background:var(--base);color:var(--off);padding:28px 32px;margin-bottom:44px}
.total-card .lbl{font-family:var(--f-mono);font-size:11px;letter-spacing:2px;
text-transform:uppercase;color:var(--primary-light);margin-bottom:6px}
.total-card .price{font-family:var(--f-serif);font-size:52px;line-height:1.05;
letter-spacing:-1px;font-variant-numeric:tabular-nums}
.total-card .sub{font-family:var(--f-mono);font-size:12px;color:var(--cool);
margin-top:14px;padding-top:14px;border-top:1px solid #2a3340;
display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}

h2{font-family:var(--f-mono);font-size:11px;font-weight:500;margin:0 0 14px;
letter-spacing:2px;text-transform:uppercase;color:var(--primary)}
section{margin-bottom:40px}
.grid{display:grid;gap:16px}
.kpis{grid-template-columns:repeat(4,1fr)}
.cols2{grid-template-columns:1.15fr .85fr;align-items:start}
.cols-inv{grid-template-columns:340px 1fr;align-items:start}
.cols-inst{grid-template-columns:repeat(4,1fr)}

.card{background:var(--white);border:1px solid var(--line);padding:22px 24px;
overflow:hidden;transition:border-color .15s}
.card:hover{border-color:var(--base)}
.kpi .label{color:var(--muted);font-family:var(--f-mono);font-size:10px;
text-transform:uppercase;letter-spacing:1.5px;font-weight:500}
.kpi .v{font-size:28px;font-weight:700;margin:8px 0 4px;letter-spacing:-.6px;
font-variant-numeric:tabular-nums;color:var(--base)}
.kpi .foot{color:var(--muted);font-size:12px}

.inst .top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:14px}
.inst .nome{font-family:var(--f-serif);font-size:20px;letter-spacing:-.3px;color:var(--base);line-height:1}
.inst .linha{display:flex;justify-content:space-between;padding:6px 0;font-size:13px;
border-bottom:1px solid var(--line)}
.inst .linha:last-of-type{border-bottom:none}
.inst .linha span:first-child{color:var(--muted)}
.inst .linha span:last-child{font-variant-numeric:tabular-nums;font-weight:600}
.inst .liq{margin-top:12px;padding-top:12px;border-top:1px solid var(--base);
display:flex;justify-content:space-between;font-weight:700;font-size:14px}

.decl{font-family:var(--f-mono);font-size:9px;letter-spacing:.5px;text-transform:uppercase;color:var(--amber);border:1px solid var(--amber);padding:1px 5px;margin-left:6px;white-space:nowrap;vertical-align:1px}
.chip{display:inline-flex;align-items:center;gap:5px;background:var(--off);border:1px solid var(--line);
color:var(--muted);padding:4px 10px;font-family:var(--f-mono);font-size:10px;
letter-spacing:1px;text-transform:uppercase}

table{width:100%;border-collapse:collapse;font-size:13px;table-layout:auto}
td:first-child{min-width:150px;word-break:break-word}
th{text-align:left;background:var(--off);color:var(--muted);font-family:var(--f-mono);
font-size:10px;text-transform:uppercase;letter-spacing:1.5px;font-weight:500;
padding:12px 12px;border-bottom:1px solid var(--line);position:sticky;top:0}
td{padding:11px 12px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
tr:hover td{background:var(--off)}
.num{text-align:right;white-space:nowrap}
.pos{color:var(--pos);font-weight:600}.neg{color:var(--neg);font-weight:600}
.tbl-wrap{overflow-x:auto;max-height:460px;overflow-y:auto;border:1px solid var(--line);
background:var(--white)}
.card>.tbl-wrap{border:none}
.bar{height:8px;background:var(--primary);min-width:3px}
.mini{color:var(--muted);font-size:12px}
.chart-box{position:relative;height:320px}
.chart-box canvas{position:absolute;inset:0}

.filtros{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.filtros.ciclos .btn{flex:0 0 auto}
/* o fluxo mostra a tabela inteira; rolagem so na horizontal */
#fluxo{max-height:none}
tr.fx-titulo td{background:var(--off);font-family:var(--f-mono);font-size:10px;
letter-spacing:1.5px;text-transform:uppercase;color:var(--primary);padding:10px 12px}
tr.fx-total td{border-top:1px solid var(--base);font-weight:700}
tr.fx-res td{font-weight:700;background:var(--off)}
tr.fx-var td{color:var(--muted);border-bottom:1px solid var(--base)}
tr.fx-res td.num{color:var(--base)}
/* deep dive: a linha aberta mostra um resumo e os filhos, indentados */
tr.fx-abrivel{cursor:pointer}
tr.fx-abrivel:hover td{background:var(--off)}
.fx-seta{display:inline-block;width:15px;font-family:var(--f-mono);
color:var(--primary);font-weight:700}
tr.fx-filho td{font-size:12.5px}
tr.fx-filho td:first-child{color:var(--muted)}
tr.fx-lanc td{color:var(--muted)}
/* a coluna da esquerda precisa de largura: com o deep dive ela recebe
   "04/05 Pix enviado AUTO ART · Itaú" e quebrava em quatro linhas */
#fluxo table td:first-child,#fluxo table th:first-child{min-width:300px}
tr.fx-info td{background:var(--off);padding:9px 12px;border-bottom:1px solid var(--line)}
tr.fx-info .chip{margin:2px 5px 2px 0;font-size:11px;background:var(--white)}
.btn{background:var(--off);border:1px solid var(--line);color:var(--base);
padding:9px 14px;font-family:var(--f-mono);font-size:11px;letter-spacing:.5px;
text-transform:uppercase;cursor:pointer;transition:background .15s,border-color .15s}
.btn:hover{background:var(--cool);border-color:var(--base)}
.btn.on{background:var(--base);border-color:var(--base);color:var(--off)}

footer{color:var(--muted);font-size:12px;border-top:1px solid var(--line);
padding-top:20px;line-height:1.7}
code{background:var(--off);border:1px solid var(--line);padding:1px 5px;
font-family:var(--f-mono);font-size:11.5px}

/* ── Telas medias ── */
@media(max-width:1080px){.wrap{padding:40px 24px 60px}
h1{font-size:44px}
.kpis{grid-template-columns:repeat(2,1fr)}
.cols2,.cols-inst,.cols-inv{grid-template-columns:1fr}
.chart-box{height:280px}}

/* ── Celular ─────────────────────────────────────────────────────────────
   Tabela financeira nao cabe em 390px. Em vez de espremer tudo, cada tabela
   perde as colunas acessorias e a primeira coluna gruda na esquerda, entao
   da pra rolar de lado sem perder de vista de que linha se trata. */
@media(max-width:620px){
.wrap{padding:24px 14px 56px}
.page-label{margin-bottom:12px}
h1{font-size:32px}
.subtitle{font-size:15px;margin-bottom:24px}
.total-card{padding:22px 18px;margin-bottom:32px}
.total-card .price{font-size:38px}
.total-card .sub{font-size:11px}
section{margin-bottom:30px}
.kpis{grid-template-columns:1fr 1fr;gap:10px}
.grid{gap:12px}
.card{padding:14px 15px}
.kpi .v{font-size:21px}
.kpi .label{font-size:9px;letter-spacing:1px}
.kpi .foot{font-size:10.5px;line-height:1.4;overflow-wrap:anywhere}
.chart-box{height:250px}
.tbl-wrap{max-height:70vh;-webkit-overflow-scrolling:touch}
table{font-size:12px}
th{padding:9px 8px;font-size:9px;letter-spacing:1px}
td{padding:9px 8px}
td:first-child{min-width:112px}
th:first-child,td:first-child{position:sticky;left:0;z-index:2;
background:var(--white);box-shadow:1px 0 0 var(--line)}
th:first-child{background:var(--off);z-index:3}
.inst .nome{font-size:18px}
.mini{font-size:11px}
.btn{padding:9px 12px}
footer{font-size:11.5px}
/* Investimentos: fica papel, onde, posicao e delta */
#invs th:nth-child(4),#invs td:nth-child(4),
#invs th:nth-child(6),#invs td:nth-child(6),
#invs th:nth-child(7),#invs td:nth-child(7){display:none}
/* Categorias do ciclo: sem grupo nem barra, fica valor e delta */
#cats th:nth-child(2),#cats td:nth-child(2),
#cats th:nth-child(6),#cats td:nth-child(6){display:none}
/* Lojistas: sem o % do ciclo */
#merch th:nth-child(3),#merch td:nth-child(3){display:none}
/* Parcelamentos: a instituicao ja esta no filtro acima */
#parc th:nth-child(2),#parc td:nth-child(2){display:none}
/* Internacionais: cambio se deduz de origem x reais */
#intl th:nth-child(5),#intl td:nth-child(5){display:none}
}
@media(max-width:344px){.kpis{grid-template-columns:1fr}}
"""

JS = r"""
const D = __PAYLOAD__;
const fmt = v => (v<0?"-":"") + "R$ " + Math.abs(v).toLocaleString("pt-BR",
  {minimumFractionDigits:2, maximumFractionDigits:2});
const fmt0 = v => "R$ " + Math.round(v).toLocaleString("pt-BR");
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/* ---------- instituicoes ---------- */
document.getElementById("insts").innerHTML = D.instituicoes.map(i => `
  <div class="card inst">
    <div class="top"><span class="nome">${i.nome}</span>
      <span class="chip">${i.status === "UPDATED" ? "ok" : i.status}</span></div>
    <div class="linha"><span>Investimentos</span><span>${fmt(i.investimentos)}</span></div>
    <div class="linha"><span>Caixa</span><span>${fmt(i.caixa)}</span></div>
    <div class="linha"><span>Cartões</span><span class="${i.divida>0?'neg':''}">${fmt(-i.divida)}</span></div>
    <div class="liq"><span>Líquido</span>
      <span class="${i.liquido>=0?'pos':'neg'}">${fmt(i.liquido)}</span></div>
  </div>`).join("");

/* ---------- faturas ---------- */
const ciclosFat = [...new Set(D.cartoes.flatMap(c => Object.keys(c.faturas)))].sort();
const linhasFat = D.cartoes.map(c => {
  const tds = ciclosFat.map(k => {
    const f = c.faturas[k];
    return `<td class="num">${f ? fmt(f.total) : "<span class='mini'>—</span>"}</td>`;
  }).join("");
  return `<tr><td><b>${c.instituicao}</b><div class="mini">${c.nome}</div></td>
    ${tds}<td class="num ${c.saldo>0?'neg':''}">${fmt(c.saldo)}</td>
    <td class="num mini">${c.limite ? fmt0(c.limite) : "—"}</td></tr>`;
}).join("");
document.getElementById("faturas").innerHTML = `
  <table><thead><tr><th>Cartão</th>
  ${ciclosFat.map(k => `<th class="num">${k}</th>`).join("")}
  <th class="num">Em aberto</th><th class="num">Limite</th></tr></thead>
  <tbody>${linhasFat}</tbody></table>`;

const chFat = new Chart(document.getElementById("chFat"), {
  type: "bar",
  data: {labels: ciclosFat,
    datasets: D.cartoes.filter(c => Object.keys(c.faturas).length).map((c, n) => ({
      label: c.instituicao,
      data: ciclosFat.map(k => c.faturas[k] ? c.faturas[k].total : 0),
      backgroundColor: [css("--accent"), css("--indigo"), css("--amber"), css("--pos")][n % 4],
      borderRadius: 0}))},
  options: {responsive:true, maintainAspectRatio:false, animation:false,
    plugins:{legend:{labels:{color:css("--muted"), boxWidth:12, font:{size:11}}},
      tooltip:{callbacks:{label:c => `${c.dataset.label}: ${fmt(c.raw)}`}}},
    scales:{x:{stacked:true, ticks:{color:css("--muted")}, grid:{display:false}},
      y:{stacked:true, ticks:{color:css("--muted"), callback:v => fmt0(v)},
        grid:{color:css("--grid")}}}}
});

/* ---------- investimentos ---------- */
const chClasses = new Chart(document.getElementById("chClasses"), {
  type: "doughnut",
  data: {labels: D.classes.map(c => c.nome),
    datasets:[{data: D.classes.map(c => c.valor),
      backgroundColor:[css("--accent"), css("--indigo"), css("--amber"), css("--pos")],
      borderWidth:0}]},
  options:{responsive:true, maintainAspectRatio:false, animation:false, cutout:"62%",
    plugins:{legend:{position:"bottom", labels:{color:css("--muted"), boxWidth:12, font:{size:11}}},
      tooltip:{callbacks:{label:c => `${c.label}: ${fmt(c.raw)}`}}}}
});

document.getElementById("invs").innerHTML = `
  <table><thead><tr><th>Papel</th><th>Onde</th><th class="num">Posição</th>
  <th class="num">Aplicado</th><th class="num">Δ</th><th>Indexador</th><th>Vencimento</th></tr></thead>
  <tbody>${D.investimentos.map(v => {
    const ap = v.aplicado, d = ap ? v.saldo - ap : null;
    const idx = v.indexador ? `${v.indexador}${v.taxa ? " + " + v.taxa : ""}` : "—";
    /* posicao declarada a mao (o conector nao devolve) tem que se anunciar:
       sem a tarja ela passaria por conciliada igual as outras */
    const tag = v.manual ? ` <span class="decl" title="${v.origem||""}">declarado ${
      (v.referencia||"").split("-").reverse().join("/")}</span>` : "";
    return `<tr><td><b>${v.nome}</b>${tag}</td><td class="mini">${v.instituicao}</td>
      <td class="num">${fmt(v.saldo)}</td>
      <td class="num mini">${ap ? fmt(ap) : "—"}</td>
      <td class="num ${d === null ? "" : d >= 0 ? "pos" : "neg"}">${d === null ? "—" : fmt(d)}</td>
      <td class="mini">${idx}</td>
      <td class="mini">${v.vencimento ? v.vencimento.slice(0,10).split("-").reverse().join("/") : "—"}</td></tr>`;
  }).join("")}</tbody></table>`;


/* o grid so define a largura final depois do primeiro paint; sem este resize
   o Chart.js congela a medida provisoria e o canvas vaza pra fora do card */
const redimensiona = () => [chFat, chClasses, chGasto, chConta].forEach(c => c.resize());
window.addEventListener("load", redimensiona);
window.addEventListener("resize", redimensiona);
requestAnimationFrame(redimensiona);

__CLASSIFICADOR__

const mesDe = t => t.data.slice(0, 7);
const meses = [...new Set(D.lancamentos.filter(t => t.conta_tipo !== "CREDIT")
                          .map(mesDe))].sort();
const mesAberto = meses[meses.length - 1];       /* mes corrente, incompleto */
const mesParcial = meses[0];                     /* cortado pela janela */
const mesesCheios = meses.filter(m => m !== mesAberto && m !== mesParcial);
const rotuloMes = m => m + (m === mesAberto ? " (em curso)"
                       : m === mesParcial ? " (parcial)" : "");
const porMes = (arr, filtro) => {
  const m = {}; meses.forEach(k => m[k] = 0);
  arr.forEach(t => { if ((!filtro || filtro(t)) && mesDe(t) in m)
                       m[mesDe(t)] += vAbs(t); });
  return m;
};

/* Um PIX de R$ 91 mil pra concessionaria em maio/26 achata todo o resto do
   grafico — o eixo passa a medir um evento unico em vez do padrao de gasto.
   O corte e generoso de proposito: o mes tipico inteiro fica em R$ 10 mil, um
   unico lancamento acima de 20 mil nao e rotina, e o que sai fica dito em texto
   (nada some em silencio). */
const CORTE_EXTRA = 20000;
let semExtra = false;
const extraordinarios = saidasCC.filter(t => vAbs(t) > CORTE_EXTRA);
const saidasVis = () => semExtra
  ? saidasCC.filter(t => vAbs(t) <= CORTE_EXTRA) : saidasCC;

const totalGrupoCC = {};
saidasCC.forEach(t => {
  const g = grupoDe(t);
  totalGrupoCC[g] = (totalGrupoCC[g] || 0) + vAbs(t);
});
const gruposCC = ordenaGrupos(totalGrupoCC);

/* grupos que aparecem, do maior gasto pro menor */
const totalGrupo = {};
gastos.forEach(t => {
  const g = grupoDe(t);
  totalGrupo[g] = (totalGrupo[g] || 0) + t.valor;
});
const gruposUsados = ordenaGrupos(totalGrupo);

/* ---------- grafico: gasto por ciclo, empilhado por grupo ---------- */
let filtroGrupo = "todos";
const chGasto = new Chart(document.getElementById("chGasto"), {
  type: "bar",
  data: {labels: ciclos.map(rotuloCiclo), datasets: []},
  options: {responsive:true, maintainAspectRatio:false, animation:false,
    plugins:{legend:{labels:{color:css("--muted"), boxWidth:12, font:{size:11}}},
      tooltip:{callbacks:{label:c => `${c.dataset.label}: ${fmt(c.raw)}`}}},
    scales:{x:{stacked:true, ticks:{color:css("--muted")}, grid:{display:false}},
      y:{stacked:true, ticks:{color:css("--muted"), callback:v => fmt0(v)},
        grid:{color:css("--grid")}}}}
});

function renderGrafico() {
  if (filtroGrupo === "todos") {
    chGasto.data.datasets = gruposUsados.map((g, i) => ({
      label: g, backgroundColor: CORES[i % CORES.length],
      data: ciclos.map(c => +soma(gastos.filter(t =>
        t.fatura === c && grupoDe(t) === g), t => t.valor).toFixed(2)),
    }));
  } else {
    const serie = ciclos.map(c => +soma(gastos.filter(t =>
      t.fatura === c && grupoDe(t) === filtroGrupo), t => t.valor).toFixed(2));
    const base = fechados.map(c => serie[ciclos.indexOf(c)]);
    const media = base.length ? base.reduce((a, b) => a + b, 0) / base.length : 0;
    chGasto.data.datasets = [
      {label: filtroGrupo, backgroundColor: CORES[gruposUsados.indexOf(filtroGrupo) % CORES.length],
       data: serie},
      {label: "média dos ciclos fechados", type: "line", borderDash:[5,4],
       borderColor: css("--muted"), borderWidth: 1.5, pointRadius: 0,
       data: ciclos.map(() => +media.toFixed(2))},
    ];
  }
  chGasto.update();

  const alvo = filtroGrupo === "todos" ? gastos
    : gastos.filter(t => grupoDe(t) === filtroGrupo);
  const porC = porCiclo(alvo);
  const base = fechados.map(c => porC[c]);
  const media = base.length ? base.reduce((a, b) => a + b, 0) / base.length : 0;
  const ultimo = fechados[fechados.length - 1];
  const dif = media ? (porC[ultimo] - media) / media * 100 : 0;
  document.getElementById("gasto-resumo").innerHTML =
    `<b>${fmt(media)}</b>/ciclo na média dos ${fechados.length} ciclos fechados &nbsp;·&nbsp;
     último fechado (${ultimo}) <b>${fmt(porC[ultimo])}</b>
     <span class="${dif >= 0 ? "neg" : "pos"}">${dif >= 0 ? "+" : ""}${dif.toFixed(0)}% vs média</span>
     &nbsp;·&nbsp; ciclo aberto (${cicloAberto}) ${fmt(porC[cicloAberto])} até agora`;
}

document.getElementById("grupo-filtros").innerHTML =
  ["todos", ...gruposUsados].map((g, i) =>
    `<button class="btn${i === 0 ? " on" : ""}" data-grupo="${g}">${g}</button>`).join("");
document.getElementById("grupo-filtros").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  filtroGrupo = b.dataset.grupo;
  [...e.currentTarget.children].forEach(x => x.classList.toggle("on", x === b));
  renderGrafico();
});

/* ---------- detalhe de um ciclo: categorias e lojistas ---------- */
let cicloSel = fechados[fechados.length - 1] || ciclos[ciclos.length - 1];
const semParcela = d => (d || "?").replace(/\s*\d{1,2}\s*\/\s*\d{1,2}\s*$/, "").trim() || "?";

function renderCiclo() {
  const doCiclo = gastos.filter(t => t.fatura === cicloSel);
  const idx = ciclos.indexOf(cicloSel);
  const anterior = idx > 0 ? ciclos[idx - 1] : null;
  const antCat = {};
  if (anterior) gastos.filter(t => t.fatura === anterior).forEach(t => {
    const [k] = classifica(t);
    antCat[k] = (antCat[k] || 0) + t.valor;
  });

  const cat = {}, catN = {}, catG = {};
  doCiclo.forEach(t => {
    const [k, g] = classifica(t);
    cat[k] = (cat[k] || 0) + t.valor; catN[k] = (catN[k] || 0) + 1;
    catG[k] = g;
  });
  const total = soma(doCiclo, t => t.valor);
  const linhas = Object.entries(cat).sort((a, b) => b[1] - a[1]);
  const maior = linhas.length ? linhas[0][1] : 1;

  document.getElementById("cats").innerHTML = `
    <table><thead><tr><th>Categoria</th><th>Grupo</th><th class="num">Total</th>
    <th class="num">Δ mês ant.</th><th class="num">% ciclo</th>
    <th style="width:18%"></th></tr></thead>
    <tbody>${linhas.map(([k, v]) => {
      const d = anterior ? v - (antCat[k] || 0) : null;
      return `<tr><td>${k}</td><td class="mini">${catG[k]}</td>
        <td class="num">${fmt(v)}</td>
        <td class="num mini ${d === null ? "" : d > 0 ? "neg" : "pos"}">${
          d === null ? "—" : (d > 0 ? "+" : "") + fmt(d)}</td>
        <td class="num mini">${(v / total * 100).toFixed(1)}%</td>
        <td><div class="bar" style="width:${(v / maior * 100).toFixed(1)}%"></div></td></tr>`;
    }).join("")}
    <tr><td><b>Total do ciclo</b></td><td></td><td class="num"><b>${fmt(total)}</b></td>
    <td class="num mini">${doCiclo.length} lanç.</td><td></td><td></td></tr>
    </tbody></table>`;

  const merch = {}, rotulo = {};
  doCiclo.forEach(t => {
    const nome = semParcela(t.desc), k = nome.toUpperCase();
    rotulo[k] = nome; merch[k] = (merch[k] || 0) + t.valor;
  });
  const top = Object.entries(merch).sort((a, b) => b[1] - a[1]).slice(0, 15);
  document.getElementById("merch-titulo").textContent =
    `Onde o dinheiro foi no ciclo ${cicloSel} — top ${top.length} de ${Object.keys(merch).length}`;
  document.getElementById("merch").innerHTML = `
    <table><thead><tr><th>Estabelecimento</th><th class="num">Total</th>
    <th class="num">% ciclo</th></tr></thead>
    <tbody>${top.map(([k, v]) => `<tr><td>${rotulo[k]}</td>
      <td class="num">${fmt(v)}</td>
      <td class="num mini">${(v / total * 100).toFixed(1)}%</td></tr>`).join("")}
    </tbody></table>`;
}

document.getElementById("ciclo-filtros").innerHTML = ciclos.map(c =>
  `<button class="btn${c === cicloSel ? " on" : ""}" data-ciclo="${c}">${rotuloCiclo(c)}</button>`
).join("");
document.getElementById("ciclo-filtros").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  cicloSel = b.dataset.ciclo;
  [...e.currentTarget.children].forEach(x => x.classList.toggle("on", x === b));
  renderCiclo();
});

/* ---------- grafico: saidas da conta por mes, empilhado por grupo ---------- */
let filtroGrupoCC = "todos";
const chConta = new Chart(document.getElementById("chConta"), {
  type: "bar",
  data: {labels: meses.map(rotuloMes), datasets: []},
  options: {responsive:true, maintainAspectRatio:false, animation:false,
    plugins:{legend:{labels:{color:css("--muted"), boxWidth:12, font:{size:11}}},
      tooltip:{callbacks:{label:c => `${c.dataset.label}: ${fmt(c.raw)}`}}},
    scales:{x:{stacked:true, ticks:{color:css("--muted")}, grid:{display:false}},
      y:{stacked:true, ticks:{color:css("--muted"), callback:v => fmt0(v)},
        grid:{color:css("--grid")}}}}
});

const mediaCC = v => mesesCheios.length
  ? mesesCheios.reduce((s, m) => s + v[m], 0) / mesesCheios.length : 0;
/* Um mes com compra de carro (R$ 91 mil) leva a media pra um patamar que nunca
   se repete. A mediana diz qual e o mes tipico; as duas juntas mostram o quanto
   a serie e torta. */
const medianaCC = v => {
  const xs = mesesCheios.map(m => v[m]).sort((a, b) => a - b);
  if (!xs.length) return 0;
  const i = xs.length >> 1;
  return xs.length % 2 ? xs[i] : (xs[i - 1] + xs[i]) / 2;
};

function renderContaGrafico() {
  const base = saidasVis();
  if (filtroGrupoCC === "todos") {
    chConta.data.datasets = gruposCC.map((g, i) => ({
      label: g, backgroundColor: corDe(g),
      data: meses.map(m => +soma(base.filter(t =>
        mesDe(t) === m && grupoDe(t) === g), vAbs).toFixed(2))}));
  } else {
    const v = porMes(base, t => grupoDe(t) === filtroGrupoCC);
    const md = mediaCC(v);
    chConta.data.datasets = [
      {label: filtroGrupoCC, backgroundColor: corDe(filtroGrupoCC),
       data: meses.map(m => +v[m].toFixed(2))},
      {label: `média dos ${mesesCheios.length} meses cheios`, type: "line",
       borderColor: css("--muted"), borderDash: [5, 4], borderWidth: 1.5,
       pointRadius: 0, data: meses.map(() => +md.toFixed(2))}];
  }
  chConta.update();

  const alvo = filtroGrupoCC === "todos" ? base
             : base.filter(t => grupoDe(t) === filtroGrupoCC);
  const v = porMes(alvo);
  document.getElementById("conta-resumo").innerHTML =
    `<b>${fmt(soma(alvo, vAbs))}</b> em ${meses.length} meses ·
     média <b>${fmt(mediaCC(v))}</b>/mês e mediana <b>${fmt(medianaCC(v))}</b>
     nos ${mesesCheios.length} meses cheios · ${alvo.length} lançamentos.
     ${semExtra
       ? `<span class="mini">Fora ${extraordinarios.length} lançamento(s) acima de
          ${fmt0(CORTE_EXTRA)}, somando ${fmt(soma(extraordinarios, vAbs))} —
          ${extraordinarios.slice(0, 3).map(t =>
            `${limpaDesc(t.desc)} (${t.data.slice(0, 7)}, ${fmt0(vAbs(t))})`).join(", ")}.</span>`
       : `<span class="mini">Média bem acima da mediana = um mês atípico puxando a
          série (compra grande, não padrão de gasto).</span>`}`;
}

document.getElementById("conta-filtros").innerHTML =
  ["todos", ...gruposCC].map((g, i) =>
    `<button class="btn${i === 0 ? " on" : ""}" data-grupo="${g}">${g}</button>`).join("");
document.getElementById("conta-filtros").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  filtroGrupoCC = b.dataset.grupo;
  [...e.currentTarget.children].forEach(x => x.classList.toggle("on", x === b));
  renderContaGrafico();
});

document.getElementById("conta-extra").innerHTML = extraordinarios.length
  ? `<button class="btn on" data-v="0">todos os lançamentos</button>
     <button class="btn" data-v="1">sem extraordinários (acima de ${fmt0(CORTE_EXTRA)})</button>`
  : "";
document.getElementById("conta-extra").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  semExtra = b.dataset.v === "1";
  [...e.currentTarget.children].forEach(x => x.classList.toggle("on", x === b));
  renderContaGrafico();
});

/* meios de pagamento — o que o Aleph perguntou: quanto sai em PIX, quanto em
   boleto, quanto no debito. Cartao de debito quase nao aparece; o gasto da
   conta e PIX. */
const metodos = {};
saidasCC.forEach(t => {
  const k = t.metodo || "Outros";
  metodos[k] = (metodos[k] || 0) + vAbs(t);
});
const totalCC = soma(saidasCC, vAbs);
document.getElementById("conta-metodos").innerHTML =
  Object.entries(metodos).sort((a, b) => b[1] - a[1]).map(([k, v]) =>
    `<span class="chip">${k} <b>${fmt0(v)}</b> ·
     ${(v / totalCC * 100).toFixed(0)}%</span>`).join(" ");

/* ---------- detalhe de um mes da conta ---------- */
let mesSel = mesesCheios.length ? mesesCheios[mesesCheios.length - 1] : mesAberto;
function renderContaMes() {
  const doMes = saidasCC.filter(t => mesDe(t) === mesSel);
  const idx = meses.indexOf(mesSel);
  const anterior = idx > 0 ? meses[idx - 1] : null;
  const antCat = {};
  if (anterior) saidasCC.filter(t => mesDe(t) === anterior).forEach(t => {
    const [k] = classifica(t);
    antCat[k] = (antCat[k] || 0) + vAbs(t);
  });

  const cat = {}, catN = {}, catG = {};
  doMes.forEach(t => {
    const [k, g] = classifica(t);
    cat[k] = (cat[k] || 0) + vAbs(t); catN[k] = (catN[k] || 0) + 1; catG[k] = g;
  });
  const total = soma(doMes, vAbs);
  const linhas = Object.entries(cat).sort((a, b) => b[1] - a[1]);
  const maior = linhas.length ? linhas[0][1] : 1;

  document.getElementById("conta-cats").innerHTML = `
    <table><thead><tr><th>Categoria</th><th>Grupo</th><th class="num">Total</th>
    <th class="num">Δ mês ant.</th><th class="num">% mês</th>
    <th style="width:18%"></th></tr></thead>
    <tbody>${linhas.map(([k, v]) => {
      const d = anterior ? v - (antCat[k] || 0) : null;
      return `<tr><td>${k}</td><td class="mini">${catG[k]}</td>
        <td class="num">${fmt(v)}</td>
        <td class="num mini ${d === null ? "" : d > 0 ? "neg" : "pos"}">${
          d === null ? "—" : (d > 0 ? "+" : "") + fmt(d)}</td>
        <td class="num mini">${(v / total * 100).toFixed(1)}%</td>
        <td><div class="bar" style="width:${(v / maior * 100).toFixed(1)}%"></div></td></tr>`;
    }).join("")}
    <tr><td><b>Total do mês</b></td><td></td><td class="num"><b>${fmt(total)}</b></td>
    <td class="num mini">${doMes.length} lanç.</td><td></td><td></td></tr>
    </tbody></table>`;

  const dest = {}, rot = {}, met = {};
  doMes.forEach(t => {
    const nome = limpaDesc(t.desc), k = nome.toUpperCase();
    rot[k] = nome; dest[k] = (dest[k] || 0) + vAbs(t);
    met[k] = t.metodo || "—";
  });
  const top = Object.entries(dest).sort((a, b) => b[1] - a[1]).slice(0, 15);
  document.getElementById("conta-dest-titulo").textContent =
    `Para onde o dinheiro foi em ${mesSel} — top ${top.length} de ${Object.keys(dest).length}`;
  document.getElementById("conta-dest").innerHTML = `
    <table><thead><tr><th>Destino</th><th>Meio</th><th class="num">Total</th>
    <th class="num">% mês</th></tr></thead>
    <tbody>${top.map(([k, v]) => `<tr><td>${rot[k]}</td>
      <td class="mini">${met[k]}</td>
      <td class="num">${fmt(v)}</td>
      <td class="num mini">${(v / total * 100).toFixed(1)}%</td></tr>`).join("")}
    </tbody></table>`;
}

document.getElementById("mes-filtros").innerHTML = meses.map(m =>
  `<button class="btn${m === mesSel ? " on" : ""}" data-mes="${m}">${rotuloMes(m)}</button>`
).join("");
document.getElementById("mes-filtros").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  mesSel = b.dataset.mes;
  [...e.currentTarget.children].forEach(x => x.classList.toggle("on", x === b));
  renderContaMes();
});
renderContaGrafico();
renderContaMes();

/* ---------- fluxo de caixa ----------
   Duas leituras da mesma vida financeira, e elas nao sao intercambiaveis:

   cartao — competencia, por ciclo de fatura. Mostra o que foi consumido no
            cartao, no ciclo em que a compra caiu. Pagamento de fatura fica de
            fora dos dois lados: liquida o ciclo, nao e gasto novo.
   conta  — caixa, por mes calendario. Mostra o dinheiro que de fato saiu da
            conta: PIX, boleto, debito e o pagamento da fatura (aqui ele ENTRA,
            porque e nesse dia que o dinheiro sai). Transferencia entre contas
            proprias, aplicacao e resgate ficam fora — nao movem patrimonio.

   Somar as duas dobraria o cartao. Por isso e um seletor, nao duas colunas.

   O default e a CONTA: "fluxo de caixa" e o dinheiro que saiu. Abrir no cartao
   escondia atras de um botao justamente o que a pessoa procura na tabela —
   conta de casa, PIX, financiamento — e nada disso passa no cartao. */

/* ---------- niveis de quebra ----------
   O grupo sozinho esconde o que se quer achar: "Moradia" nao diz financiamento
   nem conta de luz, e PIX nem grupo e — e meio de pagamento. Os tres niveis sao
   os MESMOS lancamentos quebrados de outro jeito: a soma de qualquer um deles
   da o mesmo "Total de saidas". */
const detCat = (arr, agrupa, val) => {
  const SEP = "␟";                       /* nao aparece em nome nenhum */
  const tot = {};
  arr.forEach(t => { const k = grupoDe(t) + SEP + catDe(t);
                     tot[k] = (tot[k] || 0) + val(t); });
  return Object.keys(tot).sort((a, b) => {
      const d = rankGrupo(a.split(SEP)[0]) - rankGrupo(b.split(SEP)[0]);
      return d || tot[b] - tot[a];            /* grupo na ordem, maior primeiro */
    }).map(k => { const [g, c] = k.split(SEP);
      const dela = t => grupoDe(t) === g && catDe(t) === c;
      return [`<span class="mini">${g} · </span>${c}`, agrupa(arr, dela),
              arr.filter(dela), ["contraparte", "lancamento"]]; });
};

/* meio de pagamento so faz sentido na conta: no cartao tudo e cartao */
const detMeio = () => {
  const tot = {};
  saidasCC.forEach(t => { const m = t.metodo || "Outros";
                          tot[m] = (tot[m] || 0) + vAbs(t); });
  return Object.keys(tot).sort((a, b) => tot[b] - tot[a])
    .map(m => [m, porMes(saidasCC, t => (t.metodo || "Outros") === m),
               saidasCC.filter(t => (t.metodo || "Outros") === m),
               ["categoria", "contraparte", "lancamento"]]);
};
const tituloSaidas = nivel => nivel === "meio" ? "Saídas por meio de pagamento"
  : nivel === "categoria" ? "Saídas por categoria" : "Saídas por grupo";

const FX = {};
{
  const entradas = porCiclo(estornos);                 /* valores vem negativos */
  ciclos.forEach(c => entradas[c] = -entradas[c]);
  const saidas = porCiclo(gastos);
  const res = {};
  ciclos.forEach(c => res[c] = entradas[c] - saidas[c]);
  FX.cartao = {
    cols: ciclos, rotulo: rotuloCiclo, base: fechados, unidade: "ciclo",
    plural: "ciclos",
    parcial: cicloParcial,
    colDe: t => t.fatura,
    blocos: nivel => [
      ["Entradas", [["Estornos e cashback", entradas, estornos,
                     ["categoria", "lancamento"]]]],
      [tituloSaidas(nivel), nivel === "categoria"
        ? detCat(gastos, porCiclo, t => t.valor)
        : gruposUsados.map(g => [g, porCiclo(gastos, t => grupoDe(t) === g),
                                 gastos.filter(t => grupoDe(t) === g),
                                 ["categoria", "contraparte", "lancamento"]])]],
    total: ["<b>Total de saídas</b>", saidas],
    resultado: ["<b>Consumo líquido do ciclo</b>", res],
    memo: [],
  };
}
{
  const entradas = porMes(entradasCC);
  const consumo = porMes(saidasCC);
  const fatura = porMes(faturasCC);
  const aplic = porMes(aplicCC.filter(t => t.tipo === "DEBIT"));
  const resgate = porMes(aplicCC.filter(t => t.tipo === "CREDIT"));
  /* Conferencia de caixa. Todo lancamento da conta corrente cai em exatamente
     uma destas cinco naturezas, e "interna" soma zero por construcao (as duas
     pontas tem o mesmo valor). Entao:

       entradas − consumo − fatura − aplicado + resgatado = variacao do saldo

     nao e uma estimativa, e uma identidade. O saldo do fim de cada mes sai do
     saldo inicial da janela empilhando essa variacao mes a mes, e o ultimo tem
     que dar exatamente o saldo que os bancos reportam hoje. O residuo fica na
     tela: se deixar de ser zero, tem lancamento em bucket errado ou lancamento
     sumido — nao tem linha de ajuste pra esconder isso. */
  const saidas = {}, res = {}, poupado = {}, varCaixa = {}, saldoFim = {};
  let corrente = D.caixa_inicial;
  meses.forEach(m => {
    saidas[m] = consumo[m] + fatura[m];
    res[m] = entradas[m] - saidas[m];
    poupado[m] = aplic[m] - resgate[m];
    varCaixa[m] = res[m] - poupado[m];
    corrente += varCaixa[m];
    saldoFim[m] = corrente;
  });
  const residuo = corrente - D.caixa_final;
  FX.conta = {
    cols: meses, rotulo: rotuloMes, base: mesesCheios, unidade: "mês",
    plural: "meses",
    parcial: mesParcial,
    colDe: t => mesDe(t),
    blocos: nivel => [
      ["Entradas", [["Salário, PIX recebido e reembolsos", entradas, entradasCC,
                     ["contraparte", "lancamento"]]]],
      [tituloSaidas(nivel),
       nivel === "meio"      ? detMeio()
       : nivel === "categoria" ? detCat(saidasCC, porMes, vAbs)
       : gruposCC.map(g => [g, porMes(saidasCC, t => grupoDe(t) === g),
                            saidasCC.filter(t => grupoDe(t) === g),
                            ["categoria", "contraparte", "lancamento"]])],
      ["Cartão", [["Pagamento de fatura", fatura, faturasCC,
                   ["contraparte", "lancamento"]]]]],
    total: ["<b>Total de saídas</b>", saidas],
    resultado: ["<b>Sobra do mês</b>", res],
    memo: [["Aplicado em investimento", aplic,
            aplicCC.filter(t => t.tipo === "DEBIT"), ["contraparte", "lancamento"]],
           ["Resgatado", resgate,
            aplicCC.filter(t => t.tipo === "CREDIT"), ["contraparte", "lancamento"]],
           ["<b>Poupança líquida</b>", poupado]],
    conferencia: [["Variação de caixa no mês", varCaixa],
                  ["<b>Saldo no fim do mês</b>", saldoFim]],
    varCaixa, saldoFim, residuo,
  };
}

const INT = D.internas || {pares: 0, valor_par: 0, soltos_saida: 0,
  soltos_entrada: 0, valor_solto_saida: 0, valor_solto_entrada: 0};
let fonteFluxo = "conta";   /* fluxo de caixa e a conta; cartao e o outro botao */
let janelaFluxo = 6;
let nivelFluxo = "grupo";
/* linhas abertas no deep dive, pelo caminho ("b1.4.2"). Zera quando muda a
   fonte ou o nivel: o mesmo indice passaria a apontar pra outra linha. */
const abertosFX = new Set();

/* ---------- deep dive ----------
   Cada linha do fluxo carrega os lancamentos que a compoem. Abrir a linha e
   quebrar esse MESMO array de novo — nunca recalcular de outra fonte — entao a
   soma dos filhos e sempre o pai, e o lancamento que aparece na ponta e o mesmo
   que entrou no total la em cima. A cadeia default e
   grupo -> categoria -> contraparte -> lancamento; por meio de pagamento ela
   comeca no meio, e no nivel de categoria comeca na contraparte. */
const CHAVE_DRILL = {
  categoria:   t => catDe(t),
  grupo:       t => grupoDe(t),
  meio:        t => t.metodo || "Outros",
  contraparte: t => limpaDesc(t.desc) || "—",
};
const brDia = d => d.slice(8, 10) + "/" + d.slice(5, 7);
const nfmt = v => Math.abs(v).toLocaleString("pt-BR",
                    {minimumFractionDigits: 2, maximumFractionDigits: 2});
/* soma um punhado de lancamentos nas colunas da tabela. Sempre em modulo: a
   coluna mostra tamanho, o sinal ja esta dito pelo bloco (entrada ou saida). */
const valsDe = (F, arr) => { const m = {};
  F.cols.forEach(c => m[c] = 0);
  arr.forEach(t => { const c = F.colDe(t); if (c in m) m[c] += vAbs(t); });
  return m; };

const quebra = (F, arr, niveis) => {
  const [n, ...resto] = niveis;
  if (n === "lancamento")
    return arr.slice().sort((a, b) => a.data < b.data ? 1 : a.data > b.data ? -1
                                    : vAbs(b) - vAbs(a))
      .map(t => [rotuloLanc(t), valsDe(F, [t]), [t], []]);
  const chave = CHAVE_DRILL[n];
  const m = new Map();
  arr.forEach(t => { const k = chave(t);
                     if (!m.has(k)) m.set(k, []);
                     m.get(k).push(t); });
  /* nivel que devolve um filho so nao explica nada — pula pro proximo, senao o
     financiamento imobiliario pediria tres cliques pra mostrar 13 parcelas */
  if (m.size === 1 && resto.length) return quebra(F, arr, resto);
  return [...m.entries()].sort((a, b) => soma(b[1], vAbs) - soma(a[1], vAbs))
    .map(([k, ts]) => [k, valsDe(F, ts), ts, resto]);
};

const rotuloLanc = t =>
  `<span class="mini">${brDia(t.data)}</span>&nbsp; ${t.desc || "—"}`
  + `<span class="mini"> · ${t.instituicao}</span>`
  + (t.moeda && t.moeda !== "BRL"
     ? `<span class="mini"> · ${t.moeda} ${nfmt(t.valor_origem)}</span>` : "");

function renderFluxo() {
  const F = FX[fonteFluxo];
  /* Total e media olham a janela inteira, nao as colunas a vista; a media
     ignora a coluna aberta e a parcial, que fechariam o numero pra baixo sem
     significar economia nenhuma. */
  const mediaDe = v => F.base.length
    ? F.base.reduce((s, c) => s + v[c], 0) / F.base.length : 0;
  const totalDe = v => F.cols.reduce((s, c) => s + v[c], 0);
  const cols = janelaFluxo === 0 ? F.cols : F.cols.slice(-janelaFluxo);
  const cel = v => `<td class="num">${v ? fmt(v) : "<span class='mini'>—</span>"}</td>`;
  /* `saldo` = linha de estoque, nao de fluxo: somar doze saldos de fim de mes
     nao significa nada e a media menos ainda. Some as duas ultimas colunas. */
  const linha = (nome, vals, cls, saldo) => `<tr class="${cls || ""}">
    <td>${nome}</td>${cols.map(c => cel(vals[c])).join("")}
    ${saldo ? `<td class="num mini">—</td><td class="num mini">—</td>`
            : `<td class="num">${fmt(totalDe(vals))}</td>
               <td class="num">${fmt(mediaDe(vals))}</td>`}</tr>`;
  const titulo = txt => `<tr class="fx-titulo">
    <td colspan="${cols.length + 3}">${txt}</td></tr>`;
  const saidas = F.total[1];
  const totalJanela = totalDe(saidas) || 1;

  /* "outras informacoes" da linha: o que a soma por mes nao conta — quantos
     lancamentos, ticket, o maior deles, por onde saiu, desde quando, e o peso
     no total da janela. */
  const resumo = arr => {
    const n = arr.length, tot = soma(arr, vAbs);
    const maior = arr.reduce((a, b) => vAbs(b) > vAbs(a) ? b : a);
    const ativas = new Set(arr.map(t => F.colDe(t)).filter(Boolean));
    const fatia = campo => { const m = {};
      arr.forEach(t => { const k = campo(t) || "—";
                         m[k] = (m[k] || 0) + vAbs(t); });
      return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 3)
        .map(([k, v]) => `${k} ${(v / tot * 100).toFixed(0)}%`).join(" · "); };
    const datas = arr.map(t => t.data).sort();
    const chips = [`${n} lançamento${n > 1 ? "s" : ""}`,
      `ticket médio ${fmt(tot / n)}`,
      `maior ${fmt(vAbs(maior))} · ${maior.desc || "—"} em ${brDia(maior.data)}`,
      `${ativas.size} de ${F.cols.length} ${F.plural}`,
      `${brDia(datas[0])} a ${brDia(datas[n - 1])}`,
      `${(tot / totalJanela * 100).toFixed(1)}% das saídas da janela`];
    if (fonteFluxo === "conta") chips.splice(4, 0, `meio: ${fatia(t => t.metodo)}`);
    chips.splice(fonteFluxo === "conta" ? 5 : 4, 0,
                 `onde: ${fatia(t => t.instituicao)}`);
    return chips;
  };

  const linhasDrill = (linhas, base, prof) => linhas.map(
    ([nome, vals, arr, drill], i) => {
      const id = `${base}.${i}`;
      const folha = !!(arr && arr.length === 1 && !drill.length);
      const abre = !!(arr && arr.length) && !folha;
      const aberto = abre && abertosFX.has(id);
      let html = `<tr class="${prof ? "fx-filho " : ""}${folha ? "fx-lanc " : ""}${
          abre ? "fx-abrivel" : ""}"${abre ? ` data-fx="${id}"` : ""}>
        <td style="padding-left:${12 + prof * 20}px">${
          abre ? `<span class="fx-seta">${aberto ? "−" : "+"}</span>` : ""}${nome}</td>
        ${cols.map(c => cel(vals[c])).join("")}
        <td class="num">${fmt(totalDe(vals))}</td>
        ${folha ? `<td class="num mini">—</td>`
                : `<td class="num">${fmt(mediaDe(vals))}</td>`}</tr>`;
      if (aberto) {
        html += `<tr class="fx-info"><td colspan="${cols.length + 3}"
          style="padding-left:${12 + (prof + 1) * 20}px">${
          resumo(arr).map(x => `<span class="chip">${x}</span>`).join(" ")}</td></tr>`;
        if (drill.length) html += linhasDrill(quebra(F, arr, drill), id, prof + 1);
      }
      return html;
    }).join("");

  document.getElementById("fluxo").innerHTML = `
    <table><thead><tr><th>Linha</th>
    ${cols.map(c => `<th class="num">${F.rotulo(c)}</th>`).join("")}
    <th class="num">Total ${F.cols.length} ${F.plural}</th>
    <th class="num">Média/${F.unidade}</th></tr></thead>
    <tbody>
      ${F.blocos(nivelFluxo).map(([nome, ls], bi) =>
        titulo(nome) + linhasDrill(ls, "b" + bi, 0)).join("")}
      ${linha(F.total[0], saidas, "fx-total")}
      <tr class="fx-var"><td>Δ vs ${F.unidade} anterior</td>
        ${cols.map(c => {
          const i = F.cols.indexOf(c), prev = i > 0 ? F.cols[i - 1] : null;
          /* comparar com a coluna parcial da uma variacao de 5000% que so
             mede o corte da janela, nao mudanca de comportamento */
          const ant = prev && prev !== F.parcial ? saidas[prev] : 0;
          if (!ant) return `<td class="num mini">—</td>`;
          const d = (saidas[c] - ant) / ant * 100;
          return `<td class="num mini ${d >= 0 ? "neg" : "pos"}">${
            d >= 0 ? "+" : ""}${d.toFixed(0)}%</td>`;
        }).join("")}
        <td class="num mini">—</td><td class="num mini">—</td></tr>
      ${linha(F.resultado[0], F.resultado[1], "fx-res")}
      ${F.memo.length ? titulo("Fora do consumo — troca de bolso")
        + linhasDrill(F.memo, "m", 0) : ""}
      ${F.conferencia ? titulo("Conferência com o saldo das contas")
        + linha(F.conferencia[0][0], F.conferencia[0][1])
        + linha(F.conferencia[1][0], F.conferencia[1][1], "fx-res", true) : ""}
    </tbody></table>`;

  const mediaSaida = fmt(mediaDe(saidas));
  document.getElementById("fluxo-nota").innerHTML = fonteFluxo === "cartao"
    ? `<b>Cartão, por ciclo de fatura</b> — não é mês calendário: a coluna
       <b>${cicloAberto}</b> ainda está acumulando e <b>${cicloParcial}</b> entra
       cortada pela janela do extrato; a média usa só os ${fechados.length} ciclos
       fechados (<b>${mediaSaida}</b> de saída por ciclo). Pagamento de fatura não
       aparece dos dois lados: ele liquida o ciclo, não é gasto novo. Entrada aqui é
       só estorno e cashback. Total e média são sempre da janela inteira, não das
       colunas à vista.`
    : `<b>Conta corrente, regime de caixa por mês</b> — o dinheiro que realmente
       saiu: PIX, boleto, débito automático e o pagamento da fatura do cartão (é
       nesse dia que ele sai, e por isso o cartão não entra compra a compra aqui).
       Média sobre os ${mesesCheios.length} meses cheios: <b>${mediaSaida}</b> de
       saída por mês. <b>${mesAberto}</b> está em curso e <b>${mesParcial}</b> vem
       cortado pela janela. <b>Por categoria</b> as linhas fixas aparecem com
       nome próprio (financiamento imobiliário, condomínio, energia, internet,
       faculdade, igreja); <b>por meio de pagamento</b>, quanto sai em PIX,
       boleto e débito automático.
       <br><br><b>Transferência entre contas suas não aparece aqui — e isso é
       literal.</b> ${INT.pares} idas e voltas (<b>${fmt(INT.valor_par)}</b>)
       tiveram as duas pontas encontradas dentro das contas conectadas: saiu de
       uma, entrou na outra, nada mudou de patrimônio, sumiram das duas telas.
       O que <i>não</i> achou a outra ponta não é transferência interna, é
       dinheiro atravessando a fronteira do que o Open Finance enxerga — e conta
       como movimento de verdade: ${INT.soltos_saida} saídas
       (<b>${fmt(INT.valor_solto_saida)}</b>, quase tudo PIX do Mercado Pago) no
       grupo <b>Transferências</b>, e ${INT.soltos_entrada} entradas
       (<b>${fmt(INT.valor_solto_entrada)}</b>, o TED mensal no Itaú e o PIX de
       fev/26) junto do salário.
       <br><br><b>Por isso o fluxo fecha sozinho.</b> Cada lançamento cai em
       exatamente um balde, e a soma dos baldes é o extrato inteiro:
       entradas − saídas − poupança líquida = variação do saldo. Partindo de
       <b>${fmt(D.caixa_inicial)}</b> no começo da janela e empilhando mês a mês,
       o saldo chega em <b>${fmt(FX.conta.saldoFim[meses[meses.length - 1]])}</b>,
       contra <b>${fmt(D.caixa_final)}</b> que os bancos reportam hoje —
       ${Math.abs(FX.conta.residuo) < 0.05
         ? "residuo zero, nenhum lançamento perdido ou contado duas vezes"
         : `<b class="neg">resíduo de ${fmt(FX.conta.residuo)}</b>, ou seja tem
            lançamento classificado errado`}. O saldo inicial é deduzido de trás
       pra frente (saldo de hoje menos os lançamentos da janela), então o que
       essa linha prova é que <b>nada foi descartado na classificação</b> — não
       que o banco esteja certo. Uma pista de que o razão está completo: Nubank e
       XP nasceram dentro da janela e o saldo inicial delas deu exatamente zero.`;
}

/* ---------- ponte entre os dois regimes ----------
   Os dois lados do seletor olham o MESMO cartao por angulos diferentes: um
   conta a compra no dia da compra, o outro conta o dinheiro no dia em que a
   fatura e paga. O que liga os dois e a divida do cartao:

     divida no inicio + compras do periodo − faturas pagas = divida hoje

   Como a divida de hoje vem do banco e as duas pontas do meio saem do extrato,
   da pra deduzir com quanto de cartao ele entrou na janela — e e o unico jeito
   de encostar as duas telas sem contar o cartao duas vezes. */
{
  const compras = soma(gastos, t => t.valor);
  const devolvido = -soma(estornos, t => t.valor);
  const liquido = compras - devolvido;
  const pago = Object.values(porMes(faturasCC)).reduce((a, b) => a + b, 0);
  const hoje = D.resumo.divida;
  const inicio = hoje - liquido + pago;
  document.getElementById("fluxo-ponte").innerHTML = `
    <b>Como as duas telas conversam</b> — elas não se somam, se ligam pela dívida
    do cartão. Na janela entraram <b>${fmt(liquido)}</b> de compra líquida
    (${fmt(compras)} de compras menos ${fmt(devolvido)} de estorno e cashback) e
    saíram <b>${fmt(pago)}</b> da conta pagando fatura. Com a fatura em aberto hoje
    em <b>${fmt(hoje)}</b>, a dívida no começo da janela era <b>${fmt(inicio)}</b>
    — é essa diferença de calendário, não erro de conta, que faz o que você gastou
    e o que você pagou não baterem no mesmo mês.`;
}

/* o rotulo diz o CONTEUDO, nao o regime: "conta · por mes" nao avisa ninguem
   de que e ali que moram o financiamento e o PIX */
document.getElementById("fluxo-fonte").innerHTML =
  [["conta", "conta · PIX, boleto, financiamento"],
   ["cartao", "cartão · compras por ciclo"]].map(([v, r]) =>
    `<button class="btn${v === fonteFluxo ? " on" : ""}" data-fonte="${v}">${r}</button>`).join("");
document.getElementById("fluxo").addEventListener("click", e => {
  const tr = e.target.closest("tr.fx-abrivel"); if (!tr) return;
  const id = tr.dataset.fx;
  abertosFX.has(id) ? abertosFX.delete(id) : abertosFX.add(id);
  renderFluxo();
});

document.getElementById("fluxo-fonte").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  fonteFluxo = b.dataset.fonte;
  abertosFX.clear();
  [...e.currentTarget.children].forEach(x => x.classList.toggle("on", x === b));
  renderNiveis();
  renderFluxo();
});

const NIVEIS = [["grupo", "por grupo"], ["categoria", "por categoria"],
                ["meio", "por meio de pagamento"]];
function renderNiveis() {
  const disp = fonteFluxo === "conta" ? NIVEIS : NIVEIS.slice(0, 2);
  if (!disp.some(([v]) => v === nivelFluxo)) nivelFluxo = "grupo";
  document.getElementById("fluxo-nivel").innerHTML = disp.map(([v, r]) =>
    `<button class="btn${v === nivelFluxo ? " on" : ""}" data-nivel="${v}">${r}</button>`).join("");
}
document.getElementById("fluxo-nivel").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  nivelFluxo = b.dataset.nivel;
  abertosFX.clear();
  renderNiveis();
  renderFluxo();
});
renderNiveis();

document.getElementById("fluxo-filtros").innerHTML =
  [["6", "últimos 6"], ["12", "últimos 12"], ["0", "janela toda"]].map(([v, r], i) =>
    `<button class="btn${i === 0 ? " on" : ""}" data-janela="${v}">${r}</button>`).join("");
document.getElementById("fluxo-filtros").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  janelaFluxo = +b.dataset.janela;
  [...e.currentTarget.children].forEach(x => x.classList.toggle("on", x === b));
  renderFluxo();
});
renderFluxo();

renderGrafico();
renderCiclo();

/* ---------- parcelamentos ---------- */
let filtroParc = "todos";
function renderParc() {
  const lista = filtroParc === "todos" ? D.parcelas
    : D.parcelas.filter(p => p.instituicao === filtroParc);
  const aberto = lista.reduce((s, p) => s + p.aberto, 0);
  const mensal = lista.reduce((s, p) => s + (p.restantes > 0 ? p.valor : 0), 0);
  document.getElementById("parc-resumo").innerHTML =
    `<span class="chip">${lista.length} parcelamentos</span>
     &nbsp; a vencer <b>${fmt(aberto)}</b> &nbsp;·&nbsp; próxima leva <b>${fmt(mensal)}</b>/mês`;
  document.getElementById("parc").innerHTML = `
    <table><thead><tr><th>Compra</th><th>Onde</th><th class="num">Parcela</th>
    <th class="num">Restam</th><th class="num">A vencer</th></tr></thead>
    <tbody>${lista.map(p => `<tr>
      <td>${p.desc}</td><td class="mini">${p.instituicao}</td>
      <td class="num">${fmt(p.valor)}</td>
      <td class="num mini">${p.restantes} de ${p.total}</td>
      <td class="num ${p.aberto > 0 ? "neg" : ""}">${fmt(p.aberto)}</td>
    </tr>`).join("")}</tbody></table>`;
}
const instParc = ["todos", ...new Set(D.parcelas.map(p => p.instituicao))];
document.getElementById("parc-filtros").innerHTML = instParc.map((n, i) =>
  `<button class="btn${i === 0 ? " on" : ""}" data-inst="${n}">${n}</button>`).join("");
document.getElementById("parc-filtros").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  filtroParc = b.dataset.inst;
  [...e.currentTarget.children].forEach(x => x.classList.toggle("on", x === b));
  renderParc();
});
renderParc();

/* ---------- internacionais ---------- */
const intl = D.lancamentos.filter(t => t.moeda && t.moeda !== "BRL" && t.tipo === "DEBIT");
document.getElementById("intl").innerHTML = `
  <table><thead><tr><th>Data</th><th>Descrição</th><th class="num">Origem</th>
  <th class="num">Em reais</th><th class="num">Câmbio</th></tr></thead>
  <tbody>${intl.map(t => `<tr>
    <td class="mini">${t.data.split("-").reverse().join("/")}</td>
    <td>${t.desc}</td>
    <td class="num mini">${t.moeda} ${t.valor_origem.toFixed(2)}</td>
    <td class="num">${fmt(t.valor)}</td>
    <td class="num mini">${(t.valor / t.valor_origem).toFixed(2)}</td>
  </tr>`).join("")}</tbody></table>`;
"""

HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#F0F4F8">
<title>Finanças · Scalioni's Empire</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@300;400;500;600;700&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="icon" type="image/png" sizes="32x32" href="/static/favicon-32.png?v=2">
<link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png?v=2">
<link rel="stylesheet" href="/static/nav.css?v=2026-08-31">
<script>__CHARTJS__</script>
<style>__CSS__</style>
</head>
<body>
<!-- A nav do painel so existe quando a pagina e servida em /financas. No arquivo
     solto (Telegram) o /static nao resolve, o script nao roda e o cabecalho abaixo
     se vira sozinho. -->
<script src="/static/nav.js?v=2026-08-31"></script>

<div class="wrap">

<div class="page-label">— Finanças</div>
<h1>Patrimônio <em>consolidado</em></h1>
<p class="subtitle">__N_INST__ instituições · extrato de __JANELA__ · __N_LANC__ lançamentos.
Cartão agregado por ciclo de fatura, compra internacional pelo valor convertido.</p>

<div class="total-card">
  <div class="lbl">Patrimônio líquido</div>
  <div class="price">__LIQUIDO__</div>
  <div class="sub"><span>investimentos + caixa − cartões em aberto</span>
    <span>Kaleu · CFO · __DATA_BR__</span></div>
</div>

<section>
  <div class="grid kpis">
    <div class="card kpi"><div class="label">Investimentos</div>
      <div class="v">__INVEST__</div><div class="foot">__N_PAPEIS__ papéis ativos</div></div>
    <div class="card kpi"><div class="label">Caixa</div>
      <div class="v">__CAIXA__</div><div class="foot">saldo em conta corrente</div></div>
    <div class="card kpi"><div class="label">Cartões em aberto</div>
      <div class="v">__DIVIDA__</div><div class="foot">__N_CARTOES__ cartões</div></div>
    <div class="card kpi"><div class="label">Parcelado a vencer</div>
      <div class="v">__COMPROMETIDO__</div><div class="foot">__PROXIMA__/mês na próxima leva</div></div>
  </div>
</section>

<section>
  <h2>Fluxo de caixa — __PERIODO__</h2>
  <div class="mini" style="margin:-8px 0 14px"><b>Clique em qualquer linha pra
    abrir.</b> Cada linha guarda os lançamentos que a formam, e abrir vai
    descendo <b>grupo → categoria → contraparte → lançamento</b>, com data,
    descrição e banco na ponta. A faixa cinza que aparece ao abrir traz o que a
    soma do mês não conta: quantos lançamentos, ticket médio, o maior deles, por
    qual meio saiu, em qual banco, desde quando e quanto pesa na janela. A soma
    dos filhos é sempre o pai — não tem linha de ajuste em lugar nenhum.
    <br><br>Abre pela <b>conta</b>: o dinheiro que de fato saiu — PIX, boleto,
    débito automático, financiamento imobiliário, condomínio, faculdade, contas
    de casa — mais o pagamento da fatura do cartão. O segundo botão troca pro
    <b>cartão</b> em regime de competência (a compra no ciclo em que caiu).
    <b>Os dois não se somam</b>: a fatura apareceria duas vezes. A segunda linha
    de botões quebra as mesmas saídas por grupo, por categoria ou por meio de
    pagamento — e os três dão exatamente o mesmo total.
    <br><br><b>PIX pra pessoa física</b> ganha linha própria com o nome e o
    número de vezes quando se repete (3x ou mais) ou quando passa de R$ 1.000 na
    janela; o resto vai pra <i>PIX eventual a pessoas</i>. O que cada pessoa
    <i>é</i> — diarista, psicóloga, manicure, família — o extrato não diz e o
    dashboard não inventa: é uma linha no <code>contrapartes.json</code>.</div>
  <div class="card">
    <div class="filtros" id="fluxo-fonte"></div>
    <div class="filtros" id="fluxo-nivel" style="margin-top:-4px"></div>
    <div class="filtros" id="fluxo-filtros" style="margin-top:-4px"></div>
    <div class="tbl-wrap" id="fluxo"></div>
  </div>
  <div class="mini" id="fluxo-nota" style="margin-top:10px"></div>
  <div class="mini" id="fluxo-ponte" style="margin-top:10px"></div>
</section>

<section>
  <h2>Por instituição</h2>
  <div class="grid cols-inst" id="insts"></div>
</section>

<section>
  <h2>Cartões — fechamento por ciclo de fatura</h2>
  <div class="grid">
    <div class="card"><div class="chart-box"><canvas id="chFat"></canvas></div></div>
    <div class="card"><div class="tbl-wrap" id="faturas"></div></div>
  </div>
</section>

<section>
  <h2>Investimentos</h2>
  <div class="grid cols-inv">
    <div class="card"><div class="chart-box"><canvas id="chClasses"></canvas></div></div>
    <div class="card"><div class="tbl-wrap" id="invs"></div></div>
  </div>
</section>

<section>
  <h2>Gastos no cartão — por ciclo de fatura</h2>
  <div class="card">
    <div class="filtros" id="grupo-filtros"></div>
    <div class="chart-box"><canvas id="chGasto"></canvas></div>
    <div class="mini" id="gasto-resumo" style="margin-top:14px"></div>
  </div>
  <div class="grid cols2" style="margin-top:16px">
    <div class="card">
      <div class="filtros ciclos" id="ciclo-filtros"></div>
      <div class="tbl-wrap" id="cats"></div>
    </div>
    <div class="card">
      <div class="mini" id="merch-titulo" style="margin-bottom:12px"></div>
      <div class="tbl-wrap" id="merch"></div>
    </div>
  </div>
</section>

<section>
  <h2>Conta corrente — PIX, boleto e débito</h2>
  <div class="card">
    <div class="mini" id="conta-metodos" style="margin-bottom:14px"></div>
    <div class="filtros" id="conta-extra"></div>
    <div class="filtros" id="conta-filtros" style="margin-top:-4px"></div>
    <div class="chart-box"><canvas id="chConta"></canvas></div>
    <div class="mini" id="conta-resumo" style="margin-top:14px"></div>
  </div>
  <div class="grid cols2" style="margin-top:16px">
    <div class="card">
      <div class="filtros ciclos" id="mes-filtros"></div>
      <div class="tbl-wrap" id="conta-cats"></div>
    </div>
    <div class="card">
      <div class="mini" id="conta-dest-titulo" style="margin-bottom:12px"></div>
      <div class="tbl-wrap" id="conta-dest"></div>
    </div>
  </div>
  <div class="mini" style="margin-top:10px">Só o que é gasto de verdade. Ficam de
    fora aplicação/resgate, o pagamento da fatura (o gasto do cartão já foi contado
    compra a compra na seção acima) e a transferência entre contas suas —
    <b>esta última só quando as duas pontas aparecem</b>: saiu do Itaú, entrou no
    Nubank. PIX que saiu de uma conta daqui e não entrou em nenhuma outra saiu do
    seu campo de visão de verdade, e conta como saída, no grupo
    <b>Transferências</b>.</div>
</section>

<section>
  <h2>Parcelamentos em aberto</h2>
  <div class="card">
    <div class="filtros" id="parc-filtros"></div>
    <div class="mini" id="parc-resumo" style="margin-bottom:12px"></div>
    <div class="tbl-wrap" id="parc"></div>
  </div>
</section>

<section>
  <h2>Compras internacionais — conversão aplicada</h2>
  <div class="card"><div class="tbl-wrap" id="intl"></div></div>
</section>

<footer>
  <b>Metodologia.</b> Dados via Pluggy (Open Finance) em __DATA_BR__.
  Compra internacional entra pelo valor convertido (<code>amountInAccountCurrency</code>),
  não pelo valor em moeda estrangeira — somar o campo cru subestima o gasto em ~5,3x.
  Cartão é agregado por <b>ciclo de fatura</b> (<code>creditCardMetadata.billForecastDate</code>),
  nunca por mês calendário: mês calendário produz um número que não existe no extrato do banco.
  Posições de investimento zeradas (liquidadas) ficam fora das tabelas.
  Na conta corrente, só entra como gasto o que é gasto: aplicação/resgate e pagamento de fatura
  são separados na origem — somar o extrato cru multiplicaria a despesa por seis. Transferência
  entre contas do titular só é anulada quando as <b>duas pontas</b> são encontradas (mesmo valor,
  até 3 dias, contas diferentes); ponta solta vira saída ou entrada de verdade, porque é dinheiro
  cruzando a fronteira do que o Open Finance enxerga. Isso é o que faz
  <b>entradas − saídas − poupança líquida</b> fechar exatamente com a variação do saldo das contas.
  Categorias vêm da Pluggy e erram em SaaS — confira antes de usar como verdade.
</footer>
</div>
<script>__JS__</script>
</body></html>
"""


def periodo(d1: str, d2: str) -> str:
    dias = (date.fromisoformat(d2) - date.fromisoformat(d1)).days
    if dias >= 350:
        return "últimos 12 meses"
    if dias >= 27:
        return f"últimos {round(dias / 30)} meses"
    return f"últimos {dias} dias"


CLASSIFICADOR = Path(__file__).resolve().parent / "classificador.js"


def classificador() -> str:
    """Taxonomia + fatias da conta corrente + contraparte, em arquivo separado.

    Saiu de dentro do JS pra o gera_fluxo_real.py usar a MESMA classificacao:
    duas copias do CATS/POR_NOME/contraparte divergiriam na primeira regra nova
    e os dois dashboards passariam a dar numeros diferentes pro mesmo gasto,
    sem ninguem perceber. Injetado literalmente, entao o HTML gerado nao muda.
    """
    # sem o \n final: o marcador ja ocupa uma linha inteira do JS, e o
    # newline do arquivo viraria uma linha em branco a mais no HTML.
    return CLASSIFICADOR.read_text(encoding="utf-8").rstrip("\n")


def render(P: dict) -> str:
    r = P["resumo"]
    d1, d2 = P["janela"]
    br = lambda s: "/".join(reversed(s.split("-")))

    vendor = Path(__file__).resolve().parent / "vendor" / "chart.umd.min.js"
    chartjs = (vendor.read_text(encoding="utf-8") if vendor.exists()
               else 'document.write(\'<script src="https://cdn.jsdelivr.net/npm/'
                    'chart.js@4.4.1/dist/chart.umd.min.js"><\\/script>\')')
    return (HTML
            .replace("__CHARTJS__", chartjs)
            .replace("__CSS__", CSS)
            .replace("__JS__", JS.replace("__CLASSIFICADOR__", classificador())
                                 .replace("__PAYLOAD__",
                                          json.dumps(P, ensure_ascii=False)))
            .replace("__DATA_BR__", br(P["gerado_em"]))
            .replace("__JANELA__", f"{br(d1)} a {br(d2)}")
            .replace("__PERIODO__", periodo(d1, d2))
            .replace("__N_INST__", str(r["n_instituicoes"]))
            .replace("__N_LANC__", str(r["n_lancamentos"]))
            .replace("__N_PAPEIS__", str(len(P["investimentos"])))
            .replace("__N_CARTOES__", str(len(P["cartoes"])))
            .replace("__LIQUIDO__", money(r["liquido"]))
            .replace("__INVEST__", money0(r["investimentos"]))
            .replace("__CAIXA__", money(r["caixa"]))
            .replace("__DIVIDA__", money0(r["divida"]))
            .replace("__COMPROMETIDO__", money0(r["comprometido"]))
            .replace("__PROXIMA__", money0(r["proxima_parcela"])))


MANUAIS = Path(os.getenv("PERSONALBUDGET_FINANCE_CONFIG", Path(__file__).resolve().parent)) / "posicoes-manuais.json"


def aplica_posicoes_manuais(P: dict) -> float:
    """Soma no patrimonio a posicao que o conector nao devolve.

    O conector do Nubank so expoe Tesouro Direto no /investments: RDB, CDB,
    Caixinha e cripto nao vem, e nao estao escondidos em conta nenhuma (conferido
    no accounts.json e no investments.json crus). Sem isto o patrimonio aparecia
    R$ 55 mil menor do que e — e o dashboard passava a impressao de que ele tinha
    quase nada.

    NAO mexe em lancamento nenhum, de proposito: aplicacao e resgate ja chegam
    pelo extrato da conta corrente com natureza "investimento". Somar a posicao
    aqui E o fluxo la seriam a mesma grana contada duas vezes. Por isso a ponte
    do fluxo de caixa continua fechando igual depois desta funcao rodar.

    Cada posicao carrega manual=True pra tela poder dizer que e declarado, nao
    conciliado.
    """
    if not MANUAIS.exists():
        return 0.0
    itens = json.loads(MANUAIS.read_text(encoding="utf-8")).get("posicoes", [])
    total = 0.0
    for m in itens:
        saldo = float(m.get("saldo") or 0)
        if not saldo:
            continue
        total += saldo
        pos = {"nome": m.get("nome"), "instituicao": m.get("instituicao"),
               "tipo": "FIXED_INCOME", "subtipo": m.get("classe"),
               "codigo": None, "isin": None, "quantidade": None, "pu": None,
               "compra": "", "saldo": saldo, "emissor": None, "vencimento": None,
               "taxa": None, "indexador": None, "aplicado": None, "lucro": None,
               "manual": True, "referencia": m.get("referencia"),
               "origem": m.get("origem")}
        P["investimentos"].append(pos)
        for i in P["instituicoes"]:
            if i["nome"] == m.get("instituicao"):
                i["investimentos"] = round(i["investimentos"] + saldo, 2)
                i["liquido"] = round(i["liquido"] + saldo, 2)
                break
        classe = m.get("classe") or "Declarado"
        for c in P["classes"]:
            if c["nome"] == classe:
                c["valor"] = round(c["valor"] + saldo, 2)
                break
        else:
            P["classes"].append({"nome": classe, "valor": round(saldo, 2)})
    if total:
        P["investimentos"].sort(key=lambda x: -x["saldo"])
        P["classes"].sort(key=lambda x: -x["valor"])
        P["resumo"]["investimentos"] = round(P["resumo"]["investimentos"] + total, 2)
        P["resumo"]["liquido"] = round(P["resumo"]["liquido"] + total, 2)
        P["manual_total"] = round(total, 2)
    return total


CONTRAPARTES = Path(os.getenv("PERSONALBUDGET_FINANCE_CONFIG", Path(__file__).resolve().parent)) / "contrapartes.json"


def aplica_contrapartes(P: dict) -> int:
    """Da finalidade a um PIX que so tem nome do outro lado.

    O dashboard consegue deduzir a FORMA da contraparte (pessoa recorrente,
    pessoa eventual, gateway) mas nunca a finalidade: se a Fabiana e diarista,
    professora ou aluguel informal so quem paga sabe. Cada regra aqui e uma
    linha desse conhecimento, e vence toda a classificacao automatica porque
    chega no JS como `t.grupo` — o primeiro teste do classifica().

    Diferente do mascara.json, o nome do lojista NAO e trocado: a intencao aqui
    e explicar o lancamento, nao esconder. Pra esconder, use o mascara.json.
    """
    if not CONTRAPARTES.is_file():
        return 0
    regras = json.loads(CONTRAPARTES.read_text(encoding="utf-8")).get("regras", [])
    compiladas = [(re.compile(r["padrao"], re.I), r) for r in regras
                  if r.get("padrao") and r.get("categoria")]
    if not compiladas:
        return 0
    n, ignorados = 0, []
    for t in P["lancamentos"]:
        if t.get("conta_tipo") == "CREDIT":
            continue                      # cartao ja vem com lojista de verdade
        desc = t.get("desc") or ""
        for rx, r in compiladas:
            if not rx.search(desc):
                continue
            # So DEBITO de consumo recebe rotulo. O mesmo nome aparece dos dois
            # lados: "Karine" e psicologa numa saida mensal e tambem um PIX de
            # R$ 155 RECEBIDO de outra Karine. Sem esta guarda a regra pintaria
            # a entrada de "Psicologa/Saude" e o dinheiro que entrou viraria
            # despesa no grafico. Vale igual pra transferencia interna e pra
            # aplicacao: nenhuma das duas e gasto com a contraparte.
            if t.get("tipo") != "DEBIT" or t.get("natureza") != "consumo":
                ignorados.append((r["padrao"], t.get("data"), t.get("tipo"),
                                  t.get("natureza"), t.get("valor")))
                break
            t["categoria"] = r["categoria"]
            t["grupo"] = r.get("grupo", "Serviços e taxas")
            n += 1
            break
    for pad, data, tipo, nat, val in ignorados:
        print(f"  contrapartes: regra {pad!r} casou com {tipo}/{nat} "
              f"de R$ {val:,.2f} em {data} — ignorado (nao e saida de consumo)")
    return n


MASCARA = Path(os.getenv("PERSONALBUDGET_FINANCE_CONFIG", Path(__file__).resolve().parent)) / "mascara.json"


def aplica_mascara(P: dict) -> int:
    """Troca o nome do lojista pelo rotulo neutro do mascara.json.

    So o nome sai — o valor continua somando em categoria, grupo, fatura e total,
    entao nenhum numero do dashboard muda. Regra com "grupo" tambem tira a compra
    do grupo real (util pra jogar em Outros). Sem o arquivo, nada e mascarado.
    """
    if not MASCARA.is_file():
        return 0
    regras = json.loads(MASCARA.read_text(encoding="utf-8")).get("regras", [])
    compiladas = [(re.compile(r["padrao"], re.I), r) for r in regras if r.get("padrao")]
    if not compiladas:
        return 0
    n = 0
    for grupo_lanc in (P["lancamentos"], P["parcelas"]):
        for t in grupo_lanc:
            desc = t.get("desc") or ""
            for rx, r in compiladas:
                if rx.search(desc):
                    t["desc"] = r.get("rotulo", "Lançamento privado")
                    if r.get("grupo"):
                        t["grupo"] = r["grupo"]
                        t["categoria"] = t["desc"]
                    n += 1
                    break
    # top_merchants sai do payload cru; recalcula pra nao vazar pelo JSON
    P["top_merchants"] = []
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None, help="JSON da coleta_consolidada")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    src = Path(args.raw) if args.raw else (
        WORKSPACE / "reports" / f"consolidado-{date.today()}.json")
    P = build(json.loads(src.read_text(encoding="utf-8")))
    # contrapartes antes da mascara: a mascara e a ultima palavra sobre o nome
    rotuladas = aplica_contrapartes(P)
    mascarados = aplica_mascara(P)
    manual = aplica_posicoes_manuais(P)
    dest = Path(args.out) if args.out else (
        WORKSPACE / "reports" / f"patrimonio-consolidado-{date.today()}.html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render(P), encoding="utf-8")
    if rotuladas:
        print(f"{rotuladas} lançamentos rotulados por contrapartes.json")
    if mascarados:
        print(f"{mascarados} lançamentos mascarados por mascara.json")
    if manual:
        print(f"{money(manual)} de posição declarada por posicoes-manuais.json")
    print(dest)


if __name__ == "__main__":
    main()
