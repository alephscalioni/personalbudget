#!/usr/bin/env python3
"""Fluxo mes a mes: o ano inteiro, um mes por linha.

O `gera_fluxo_real.py` responde "queimando ou gerando" com um numero do ano. Ele
tem um "mes a mes", mas e um grafico de barras — da pra ver que marco foi ruim e
nao da pra perguntar por que. Esta pagina inverte: o mes a mes E a pagina, e cada
mes abre ate o lancamento.

Duas regras de contagem, ditas na cara em vez de misturadas — foi essa mistura
que deixou a leitura suja:

  COMPETENCIA (secoes 1 a 3) — o gasto do cartao conta no mes da COMPRA. E a que
  responde "vivi acima do que ganhei neste mes?". A fatura nao aparece: ela e a
  liquidacao de um gasto ja contado.

  CAIXA (secao 4) — o que de fato entrou e saiu da conta no mes, fatura paga e
  aplicacao/resgate inclusos. Fecha, mes a mes, com a variacao do SALDO medido
  pelo extrato. E a prova de que nada aqui foi inventado.

Reusa build() do payload_consolidado e classificador.js — mesma taxonomia dos
outros dois dashboards, pra um gasto nao cair em grupo diferente em cada tela.
"""
import argparse, json, os
from datetime import date
from pathlib import Path

from payload_consolidado import build
from gera_dashboard_consolidado import (CSS, WORKSPACE, classificador, money,
                                        money0, periodo, aplica_contrapartes,
                                        aplica_mascara, aplica_posicoes_manuais)

CSS_EXTRA = """
.app-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}
.brand{display:flex;align-items:center;gap:12px;font-family:var(--f-serif);font-size:25px}
.brand-mark{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#1b1830,#7865ed);color:#fff;display:grid;place-items:center;font-family:var(--f-mono);font-size:14px}
.date-pill{font-family:var(--f-mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:9px 13px;background:#fff}
.home{background:linear-gradient(145deg,#fff 0%,#fff9fc 52%,#f7f3ff 100%);border:1px solid #e9e3ee;border-radius:24px;padding:28px;box-shadow:0 18px 60px rgba(38,30,64,.08);margin-bottom:34px}
.home-head{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:22px}
.home h1{font-size:38px;margin:0 0 5px}.home .hello{color:var(--muted);font-size:14px}
.home-actions{display:flex;gap:8px}.home-actions a{font-family:var(--f-mono);font-size:10px;text-transform:uppercase;letter-spacing:.7px;text-decoration:none;border:1px solid #ded6ea;border-radius:999px;padding:10px 14px;color:var(--base);background:#fff}
.home-actions a.primary{background:#201b35;color:#fff;border-color:#201b35}
.balance{background:#fff;border:1px solid #eee8f1;border-radius:18px;padding:24px;display:grid;grid-template-columns:1.15fr .85fr;gap:20px;margin-bottom:14px}
.balance .eyebrow,.dash-card .eyebrow{font-family:var(--f-mono);font-size:9px;letter-spacing:1.4px;text-transform:uppercase;color:#8e8498}
.balance .big{font-family:var(--f-serif);font-size:44px;line-height:1;margin:9px 0 12px}.balance-meta{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:12px}.balance-meta b{color:var(--base)}
.spark{display:flex;align-items:flex-end;gap:5px;height:92px;padding-top:12px}.spark i{display:block;flex:1;min-width:5px;border-radius:5px 5px 2px 2px;background:linear-gradient(#917af1,#d8cef8)}
.dash-tip{display:flex;align-items:center;justify-content:space-between;gap:16px;background:#fbf3ff;border:1px solid #ecdff3;border-radius:14px;padding:15px 18px;margin-bottom:14px;font-size:13px}.dash-tip b{color:#5e3fc6}.tip-dot{width:10px;height:10px;border-radius:50%;background:#a862ec;box-shadow:0 0 0 6px #efe0fb;flex:0 0 auto}
.dash-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}.dash-card{background:#fff;border:1px solid #eee8f1;border-radius:16px;padding:20px}.dash-card h3{font-size:16px;margin:5px 0 17px}
.app-tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:5px;margin-bottom:14px;background:#eee9f3;border-radius:14px;position:sticky;top:8px;z-index:8;box-shadow:0 8px 24px rgba(35,27,55,.08)}
.app-tab{border:0;border-radius:10px;background:transparent;color:#776d82;padding:11px 8px;font:600 11px var(--f-mono);cursor:pointer}.app-tab.on{background:#fff;color:#241c38;box-shadow:0 2px 10px rgba(35,27,55,.09)}
.tab-panel{display:none}.tab-panel.on{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}.today-kpis{grid-column:1/-1;margin-bottom:0}.meta-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.meta-box{background:#faf7fd;border:1px solid #eee7f3;border-radius:13px;padding:15px}.meta-box span{display:block;font-family:var(--f-mono);font-size:8px;letter-spacing:.8px;text-transform:uppercase;color:#95899e}.meta-box b{display:block;margin-top:8px;font-size:18px}
.goal{margin-bottom:16px}.goal:last-child{margin-bottom:0}.goal-line{display:flex;justify-content:space-between;gap:12px;font-size:12px;margin-bottom:7px}.goal-line strong{font-size:12px}.progress{height:7px;background:#eeeaf2;border-radius:99px;overflow:hidden}.progress span{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#d05fdb,#7865ed)}
.next-row,.recent-row{display:grid;grid-template-columns:42px 1fr auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid #f0ebf3}.next-row:first-of-type,.recent-row:first-of-type{border-top:0}.cal{height:38px;border-radius:10px;background:#f4eff8;display:grid;place-items:center;font-family:var(--f-mono);font-size:10px;color:#694ea2}.row-main{font-size:12px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row-sub{font-size:10px;color:var(--muted);margin-top:3px}.row-val{font-family:var(--f-mono);font-size:11px;white-space:nowrap}.recent{grid-column:1/-1}.dash-section-link{font-family:var(--f-mono);font-size:9px;text-transform:uppercase;letter-spacing:.7px;color:#7659bf;text-decoration:none}
.dash-data{grid-column:1/-1}.dash-table{width:100%;border-collapse:collapse}.dash-table th{font-family:var(--f-mono);font-size:8px;letter-spacing:1px;text-transform:uppercase;color:#968ba0;text-align:left;padding:8px 10px;border-bottom:1px solid #ece6ef}.dash-table td{font-size:11px;padding:10px;border-bottom:1px solid #f1edf3}.dash-table th:not(:first-child),.dash-table td:not(:first-child){text-align:right}.dash-table tr:last-child td{border-bottom:0}.dash-footer{text-align:center;margin:18px 0 0;font-family:var(--f-mono);font-size:9px;letter-spacing:.7px;color:#968ba0}
.projection-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px}.projection-kpi{background:#faf7fd;border:1px solid #eee7f3;border-radius:12px;padding:12px}.projection-kpi span{display:block;font-family:var(--f-mono);font-size:8px;text-transform:uppercase;letter-spacing:.8px;color:#95899e}.projection-kpi b{display:block;margin-top:7px;font-size:16px}
.ch{position:relative;height:340px}
.ch canvas{position:absolute;inset:0}
.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.nota{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.55}
.ok{font-family:var(--f-mono);font-size:11px;color:var(--pos)}
.tg{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.tg button{background:var(--off);border:1px solid var(--line);color:var(--base);
padding:9px 14px;font-family:var(--f-mono);font-size:11px;letter-spacing:.5px;
text-transform:uppercase;cursor:pointer}
.tg button.on{background:var(--base);border-color:var(--base);color:var(--off)}
.tg .sep{width:1px;background:var(--line);margin:0 4px}
.alerta{background:#fdf6e3;border:1px solid #e8d9a8;border-left:3px solid var(--amber);
padding:16px 20px;margin-bottom:18px;font-size:13px;line-height:1.6}
.alerta b{color:var(--base)}

/* Nenhuma tabela desta pagina rola por dentro: o CSS compartilhado corta em
   460px, e era isso que escondia jul/ago da ponte de caixa e metade dos grupos
   do mapa — sem barra de rolagem a vista, entao parecia que o mes nao existia.
   Aqui a pagina inteira e uma tabela so; quem rola e o navegador. */
.tbl-wrap{max-height:none}

/* ── a espinha: uma linha por mes, que abre em cadeia ───────────────────── */
#mm td:first-child,#mm th:first-child{min-width:290px}
tr.m-mes{cursor:pointer}
tr.m-mes td{font-weight:700;border-bottom:1px solid var(--line)}
tr.m-mes td:first-child{font-size:14px}
tr.m-mes:hover td{background:var(--off)}
tr.m-mes.aberto td{background:var(--off)}
tr.m-bloco td{background:var(--base);color:var(--off);font-family:var(--f-mono);
font-size:10px;letter-spacing:1.5px;text-transform:uppercase;padding:8px 12px}
tr.m-no{cursor:pointer}
tr.m-no:hover td{background:var(--off)}
tr.m-no td{font-size:12.5px}
tr.m-no td:first-child{color:var(--muted)}
tr.m-folha td{font-size:12px;color:var(--muted);cursor:default}
tr.m-folha:hover td{background:transparent}
tr.m-resumo td{background:var(--off);padding:10px 12px}
tr.m-resumo .chip{margin:2px 5px 2px 0;font-size:11px;background:var(--white)}
.seta{display:inline-block;width:15px;font-family:var(--f-mono);
color:var(--primary);font-weight:700}
.seta.vazia{color:transparent}
.rot{overflow-wrap:anywhere}

/* ── mapa de calor grupo x mes ─────────────────────────────────────────── */
#mapa table{table-layout:fixed}
#mapa td:first-child,#mapa th:first-child{min-width:150px;width:150px}
#mapa th{text-align:right}
#mapa th:first-child{text-align:left}
#mapa td.cel{text-align:right;cursor:pointer;font-size:11.5px;padding:8px 8px;
position:relative;font-variant-numeric:tabular-nums}
#mapa td.cel:hover{outline:2px solid var(--base);outline-offset:-2px}
#mapa td.cel.zero{color:var(--line)}
#mapa tr.tot td{font-weight:700;border-top:1px solid var(--base);background:var(--white)}

@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}
.wrap{padding:32px 20px 48px}h1{font-size:36px}.ch{height:280px}.dash-grid,.tab-panel.on{grid-template-columns:1fr}.recent{grid-column:auto}}
@media(max-width:620px){
.wrap{padding:20px 12px 38px}.app-top{align-items:center;margin-bottom:16px}.brand{font-size:20px}.brand-mark{width:34px;height:34px}.date-pill{display:none}
.home{padding:16px;border-radius:18px;margin:0 -2px 28px}.home-head{display:block;margin-bottom:17px}.home h1{font-size:31px;line-height:1.02}.home .hello{font-size:12px}.home-actions{margin-top:15px;display:grid;grid-template-columns:1fr 1fr}.home-actions a{text-align:center;padding:12px 8px}
.balance{grid-template-columns:1fr;padding:18px;gap:10px}.balance .big{font-size:38px}.balance-meta{display:grid;gap:7px}.spark{height:70px}.dash-tip{align-items:flex-start;padding:14px}.dash-tip .dash-section-link{display:none}.dash-grid{gap:10px}.dash-card{padding:17px}.goal-line{align-items:flex-end}.goal-line span{max-width:45%}.goal-line strong{text-align:right}.next-row,.recent-row{grid-template-columns:38px minmax(0,1fr) auto}.recent-row{padding:11px 0}.row-main{max-width:170px}.row-val{font-size:10px}.cal{height:35px}
.page-label{margin-top:30px}.subtitle{font-size:13px}.total-card{padding:20px}.total-card .price{font-size:38px}.total-card .sub{display:grid;gap:7px}.alerta{padding:14px}.kpis{grid-template-columns:1fr 1fr!important;gap:8px!important;margin-bottom:28px!important}.kpi{padding:14px!important}.kpi .v{font-size:22px!important}.kpi .foot{font-size:10px}.tg{position:sticky;top:0;z-index:5;background:var(--bg);padding:8px 0;margin-bottom:8px}
.card{padding:14px}.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}.tbl-wrap table{min-width:720px}.tbl-wrap th,.tbl-wrap td{padding:9px 8px;font-size:11px}.ch{height:240px}section{margin-top:34px}section h2{font-size:10px}
.dash-data{overflow:hidden}.dash-data .tbl-wrap table{min-width:610px}.dash-table th,.dash-table td{padding:9px 7px}
.projection-kpis{grid-template-columns:1fr 1fr}.projection-kpi b{font-size:14px}
.app-tabs{top:4px}.app-tab{font-size:9px;padding:11px 3px}.today-kpis{grid-column:auto}.meta-grid{grid-template-columns:1fr}.meta-box{padding:13px}
#mm td:first-child,#mm th:first-child{min-width:170px}
#mapa td:first-child,#mapa th:first-child{min-width:110px;width:110px}
#mapa td.cel{font-size:10px;padding:6px 4px}}
"""

JS = r"""
const D = __PAYLOAD__;
const fmt  = v => (v<0?"-":"") + "R$ " + Math.abs(v).toLocaleString("pt-BR",
                  {minimumFractionDigits:2, maximumFractionDigits:2});
const fmt0 = v => (v<0?"-":"") + "R$ " + Math.round(Math.abs(v)).toLocaleString("pt-BR");
const css  = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const esc  = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
/* Sem animacao de proposito: e pagina pra ler numero, nao pra assistir — e o
   screenshot de conferencia so prova alguma coisa com o grafico ja parado. */
Chart.defaults.animation = false;

__CLASSIFICADOR__

/* ==================== os meses ====================
   O extrato abre no meio do mes: a janela comeca em 31/08, entao agosto e um
   toco de um dia. Virar uma barra de R$ 686 ao lado de meses inteiros mentiria
   na comparacao, entao o toco entra no mes seguinte e o ROTULO diz isso
   ("ago–set/25"). Regra mecanica: so funde se a janela nao comeca no dia 1. */
const NOMES = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"];
const mesDe = s => s.slice(0, 7);
const prox  = m => { let [a, b] = m.split("-").map(Number);
                     if (++b > 12) { b = 1; a++; }
                     return a + "-" + String(b).padStart(2, "0"); };
const [D1, D2] = D.janela;
const MES0  = mesDe(D1), FUNDE = D1.slice(8) !== "01";
const balde = t => (FUNDE && mesDe(t.data) === MES0) ? prox(MES0) : mesDe(t.data);
const nomeMes = k => { const [a, b] = k.split("-"); return NOMES[+b-1] + "/" + a.slice(2); };
const rotMes  = k => (FUNDE && k === prox(MES0))
                     ? nomeMes(MES0).split("/")[0] + "–" + nomeMes(k) : nomeMes(k);

/* ==================== as fatias ====================
   entradasCC / saidasCC / faturasCC / aplicCC / gastos / estornos vem do
   classificador. A unica peneira nova e `externa`: transferencia com o nome do
   Aleph dos dois lados cuja outra ponta nao esta conectada. Nao e alguem
   pagando ele — por padrao entra como financiamento, e o botao 2 diz o
   contrario quando ele mandar. */
const ehExt = t => !!t.externa;
const RENDA    = entradasCC.filter(t => !ehExt(t) && !ehEventoPatrimonial(t));
const ENTRAEXT = entradasCC.filter(ehExt);
const GASTOCC  = saidasCC.filter(t => !ehExt(t) && !ehEventoPatrimonial(t));
const SAIEXT   = saidasCC.filter(ehExt);
const RENDA_META = D.premissas_fluxo.renda_mensal.aleph_liquido
                 + D.premissas_fluxo.renda_mensal.bia_liquido;
const VA_ALICIA = D.premissas_fluxo.controle_mensal.va_alicia;
const VA_CREDITO = D.premissas_fluxo.controle_mensal.va_credito || 0;
const VR_ALEPH = D.premissas_fluxo.controle_mensal.vr_aleph || 0;
const VR_CREDITO = D.premissas_fluxo.controle_mensal.vr_credito || 0;
const BENEFICIO_USO = (VA_ALICIA || 0) + VR_ALEPH;
const BENEFICIO_CREDITO = VA_CREDITO + VR_CREDITO;
const RENDA_CONTROLE = RENDA_META + BENEFICIO_CREDITO;
const ORCAMENTO = D.premissas_fluxo.orcamento_mensal;
const FIXOS = [
  ["Financiamento imobiliário", /cr[ée]dito imobili|financ\w* imobili/i],
  ["Condomínio", /harmonia morumbi|\blello\b|condom[íi]nio/i],
  ["Luz", /\benel\b|eletropaulo|\bcpfl\b|cemig|coelba|energisa/i],
  ["MBA", /funda[cç][aã]o.*(pesq|adm|contab)|fipecafi|\bmba\b/i],
];
const fixoDe = t => { const x = FIXOS.find(([,rx]) => rx.test(t.desc || ""));
                      return x ? x[0] : null; };

/* no cartao o gasto vem positivo e o estorno abate: uma funcao de valor so, pra
   estorno poder viajar junto na arvore sem virar gasto */
const vSai = t => (t.conta_tipo === "CREDIT" && t.tipo !== "DEBIT") ? -vAbs(t) : vAbs(t);
const S  = (arr, f) => arr.reduce((s, t) => s + f(t), 0);
const Sa = arr => S(arr, vAbs);
const Ss = arr => S(arr, vSai);

/* ==================== estado ==================== */
let semUnicos = false;    /* botao 1: tira os eventos unicos dos dois lados */
const extRenda = false;   /* movimentação própria nunca entra no normalizado */
const abertos = new Set();  /* caminhos abertos na espinha: "2026-05", "2026-05/s/Transporte" */

/* ---------- eventos unicos ----------
   Mesma regra do gera_fluxo_real.py, de proposito: se as duas paginas cortarem
   em lugares diferentes, o mesmo mes aparece com dois resultados. >= CORTE, dos
   dois lados, fora salario. Simetrica: tirar a compra do carro sem tirar a
   venda dele faria maio parecer um desastre que nao foi.

   O corte OLHA PRA PREMISSA DO BOTAO 2. Enquanto a conta externa e
   financiamento (extRenda desligado) ela nao esta no resultado, entao nao ha o
   que tirar dela — e a regra fica identica a do gera_fluxo_real.py, que so tem
   este botao. Quando ele diz que aquela conta e renda, os lancamentos dela
   entram no resultado e passam a ser cortaveis como qualquer outro: senao o
   Pix de R$ 75.302 de 27/02 sobreviveria a "sem eventos unicos", fevereiro
   fecharia +R$ 61.795 e o ano inteiro daria +R$ 68.645 — a pagina diria
   "sobrando" com os dois botoes ligados e "queimando" com um so. */
const CORTE = 15000;
const ehUnico = t => t.conta_tipo !== "CREDIT" && (extRenda || !ehExt(t))
                  && !ehEventoPatrimonial(t)
                  && Math.abs(t.valor) >= CORTE && t.metodo !== "Salário"
                  && (t.natureza === "entrada" || t.natureza === "consumo");
/* funcao, nao const: a lista muda quando o botao 2 muda */
const unicos = () => D.lancamentos.filter(ehUnico)
                                  .sort((a,b) => a.data.localeCompare(b.data));

const vivo = t => !(semUnicos && ehUnico(t));

/* Monta as linhas do zero a cada troca de botao. Cada mes carrega os ARRAYS que
   o formaram — abrir uma linha e quebrar esse mesmo array de novo, nunca
   recalcular de outra fonte. Por isso a soma dos filhos e o pai por construcao,
   e nao por coincidencia. */
function monta() {
  const M = new Map();
  const g = k => { let r = M.get(k);
                   if (!r) M.set(k, r = {k, renda:[], saiu:[], caixa:0});
                   return r; };
  D.lancamentos.forEach(t => { if (t.conta_tipo !== "CREDIT") g(balde(t)); });

  RENDA.filter(vivo).forEach(t => g(balde(t)).renda.push(t));
  GASTOCC.filter(vivo).forEach(t => g(balde(t)).saiu.push(t));
  gastos.forEach(t => g(balde(t)).saiu.push(t));
  estornos.forEach(t => g(balde(t)).saiu.push(t));
  if (extRenda) {
    ENTRAEXT.filter(vivo).forEach(t => g(balde(t)).renda.push(t));
    SAIEXT.filter(vivo).forEach(t => g(balde(t)).saiu.push(t));
  }
  /* caixa NAO segue botao: e medida, nao premissa. Todo lancamento de conta
     entra com o sinal do extrato, e a soma tem que dar a variacao de saldo. */
  D.lancamentos.forEach(t => { if (t.conta_tipo !== "CREDIT") g(balde(t)).caixa += t.valor; });

  const L = [...M.values()].sort((a,b) => a.k.localeCompare(b.k));
  let acum = 0, saldo = D.caixa_inicial;
  L.forEach(r => {
    r.entrou   = Sa(r.renda);
    r.saiuCC   = Ss(r.saiu.filter(t => t.conta_tipo !== "CREDIT"));
    r.saiuCard = Ss(r.saiu.filter(t => t.conta_tipo === "CREDIT"));
    r.total    = r.saiuCC + r.saiuCard;
    r.res      = r.entrou - r.total;
    r.acum     = (acum += r.res);
    r.saldo    = (saldo += r.caixa);
  });
  return L;
}
let LIN = monta();

/* ==================== a arvore ====================
   Um nivel de cada vez, sob demanda: abrir e agrupar o array do pai pela chave
   do proximo nivel. Nunca ha uma segunda fonte de verdade pra divergir. */
const NIV_SAI = [
  {ch: grupoDe,  ordem: (a,b) => rankGrupo(a.rot) - rankGrupo(b.rot) || b.val - a.val},
  {ch: catDe,    ordem: (a,b) => b.val - a.val},
  {ch: t => limpaDesc(t.desc), ordem: (a,b) => b.val - a.val},
];
const NIV_REN = [
  {ch: catDe,    ordem: (a,b) => b.val - a.val},
  {ch: t => limpaDesc(t.desc), ordem: (a,b) => b.val - a.val},
];

/* `d` e o nivel em que o no foi realmente quebrado (manda na recursao); `ind` e
   o recuo na tela. Sao diferentes justamente quando um nivel e pulado. */
function quebra(lancs, niv, d, val, ind) {
  if (ind === undefined) ind = d;
  if (d >= niv.length) return [];
  const m = new Map();
  lancs.forEach(t => { const k = niv[d].ch(t) || "?";
                       (m.get(k) || m.set(k, []).get(k)).push(t); });
  const nos = [...m].map(([rot, ls]) => ({rot, lancs: ls, val: S(ls, val), d, ind}));
  nos.sort(niv[d].ordem);
  /* Um nivel que devolveria UM filho so nao ensina nada e cobra um clique: o
     financiamento imobiliario pediria tres cliques pra mostrar 13 parcelas
     iguais. Pula direto pro proximo, mantendo o recuo do nivel pulado. */
  if (nos.length === 1 && d + 1 < niv.length) {
    const f = quebra(lancs, niv, d + 1, val, ind);
    if (f.length > 1) return f;
  }
  return nos;
}

/* ==================== a espinha (secao 2) ==================== */
const cel = (v, cls) => `<td class="n ${cls||""}">${fmt(v)}</td>`;
const seta = ab => `<span class="seta">${ab ? "▾" : "▸"}</span>`;
/* O recuo e PADDING DA CELULA, nao um espacador inline. Com espacador, a
   segunda linha de uma descricao longa ("FUNDACAO PESQUISA E DESEN.ADM.
   CONTABILIDADE E ECON · Mercado Pago") voltava pra coluna zero e vazava por
   baixo do recuo — o texto parecia de outra linha. */
const pad  = d => ` style="padding-left:${12 + d*16}px"`;

function resumoMes(r) {
  const n = r.renda.length + r.saiu.length;
  const gs = r.saiu.filter(t => vSai(t) > 0);
  const maior = gs.slice().sort((a,b) => vSai(b) - vSai(a))[0];
  const uni = r.saiu.concat(r.renda).filter(ehUnico);
  const pctCard = r.total ? r.saiuCard / r.total * 100 : 0;
  const c = [];
  c.push(`${n} lançamentos`);
  c.push(`ticket médio ${fmt0(gs.length ? Ss(gs)/gs.length : 0)}`);
  if (maior) c.push(`maior: ${esc(limpaDesc(maior.desc))} ${fmt0(vSai(maior))} (${maior.data.slice(8)}/${maior.data.slice(5,7)})`);
  c.push(`${pctCard.toFixed(0)}% no cartão`);
  c.push(`saldo em conta no fim: ${fmt0(r.saldo)}`);
  if (uni.length) c.push(`${uni.length} evento${uni.length>1?"s":""} único${uni.length>1?"s":""}: ${uni.map(t => esc(limpaDesc(t.desc))).join(", ")}`);
  return `<tr class="m-resumo"><td colspan="5"${pad(1)}>${
    c.map(s => `<span class="chip">${s}</span>`).join("")}</td></tr>`;
}

function folha(t, ind, val, sinal, out) {
  out.push(`<tr class="m-folha"><td${pad(ind)}><span class="seta vazia">·</span>
    <span class="rot">${t.data.slice(8)}/${t.data.slice(5,7)} ${esc(limpaDesc(t.desc))}
    · ${esc(t.instituicao)}${t.fatura ? " · fatura " + t.fatura : ""}${
      t.moeda && t.moeda !== "BRL" ? " · " + t.moeda + " " + Math.abs(t.valor_origem) : ""
    }</span></td><td colspan="3"></td>${cel(sinal * val(t))}</tr>`);
}

function ramo(base, lancs, niv, d, val, sinal, out) {
  quebra(lancs, niv, d, val).forEach(n => {
    /* Um lancamento sozinho nao vira pasta — ja e o fundo. Menos no primeiro
       nivel: um PIX solto entre "Moradia" e "Transporte", sem o nome do grupo,
       tira do leitor a unica coisa que aquela coluna existe pra dar. Ali a
       linha de grupo fica, mesmo custando um clique pra um filho so. */
    if (n.lancs.length === 1 && n.d > 0)
      return folha(n.lancs[0], n.ind + 2, val, sinal, out);
    const p = base + "/" + n.rot;
    const ab = abertos.has(p);
    out.push(`<tr class="m-no" data-p="${esc(p)}"><td${pad(n.ind+2)}>${seta(ab)}
      <span class="rot">${esc(n.rot)}</span>
      <span class="mini"> · ${n.lancs.length}</span></td>
      <td colspan="3"></td>${cel(sinal * n.val)}</tr>`);
    if (!ab) return;
    if (n.d + 1 < niv.length) ramo(p, n.lancs, niv, n.d + 1, val, sinal, out);
    /* acabaram os niveis de agrupamento: o ultimo passo sao os lancamentos */
    else n.lancs.slice().sort((a,b) => a.data.localeCompare(b.data))
                .forEach(t => folha(t, n.ind + 3, val, sinal, out));
  });
}

function pintaEspinha() {
  const out = [];
  LIN.forEach(r => {
    const ab = abertos.has(r.k);
    out.push(`<tr class="m-mes ${ab?"aberto":""}" data-p="${r.k}">
      <td>${seta(ab)} ${rotMes(r.k)}</td>
      ${cel(r.entrou, "pos")}${cel(-r.saiuCC)}${cel(-r.saiuCard)}
      <td class="n ${r.res>=0?"pos":"neg"}">${fmt(r.res)}</td></tr>`);
    if (!ab) return;
    out.push(resumoMes(r));
    out.push(`<tr class="m-bloco"><td colspan="4"${pad(1)}>Entrou — ${fmt(r.entrou)}</td>
      <td class="n">${fmt(r.entrou)}</td></tr>`);
    ramo(r.k + "/e", r.renda, NIV_REN, 0, vAbs, 1, out);
    out.push(`<tr class="m-bloco"><td colspan="4"${pad(1)}>Saiu — ${fmt(r.total)}</td>
      <td class="n">${fmt(-r.total)}</td></tr>`);
    ramo(r.k + "/s", r.saiu, NIV_SAI, 0, vSai, -1, out);
  });
  const T = {e: S(LIN, r => r.entrou), cc: S(LIN, r => r.saiuCC),
             cd: S(LIN, r => r.saiuCard)};
  out.push(`<tr class="fx-total"><td>Ano inteiro</td>${cel(T.e,"pos")}
    ${cel(-T.cc)}${cel(-T.cd)}
    <td class="n ${T.e-T.cc-T.cd>=0?"pos":"neg"}">${fmt(T.e-T.cc-T.cd)}</td></tr>`);
  document.getElementById("tabMM").innerHTML = out.join("");
}

/* O listener mora no container, que sobrevive ao innerHTML da tabela. */
document.getElementById("mm")?.addEventListener("click", ev => {
  const tr = ev.target.closest("tr[data-p]");
  if (!tr) return;
  const p = tr.dataset.p;
  abertos.has(p) ? abertos.delete(p) : abertos.add(p);
  pintaEspinha();
});

/* ==================== 1 · a regua do ano ==================== */
let chRegua = null;
function pintaRegua() {
  const ctx = document.getElementById("chRegua");
  if (chRegua) chRegua.destroy();
  chRegua = new Chart(ctx, {
    type: "bar",
    data: {labels: LIN.map(r => rotMes(r.k)), datasets: [
      {type:"bar", label:"Entrou", data: LIN.map(r => r.entrou),
       backgroundColor: css("--pos"), order: 3},
      {type:"bar", label:"Saiu", data: LIN.map(r => -r.total),
       backgroundColor: css("--neg"), order: 3},
      /* mesma escala das barras de proposito: um segundo eixo a direita deixava
         a linha subir e descer em unidade que nao e a das barras, e o olho
         compara altura de qualquer jeito */
      {type:"line", label:"Resultado acumulado", data: LIN.map(r => r.acum),
       borderColor: css("--base"), borderWidth: 2, pointRadius: 3,
       order: 1, tension: .2},
    ]},
    options: {maintainAspectRatio:false, interaction:{mode:"index",intersect:false},
      plugins:{legend:{labels:{boxWidth:10}},
        tooltip:{callbacks:{label: c => c.dataset.label + ": " + fmt(c.parsed.y)}}},
      scales:{
        y:{grid:{color:css("--grid")}, ticks:{callback: v => fmt0(v)}},
        x:{grid:{display:false}}}}
  });
  const neg = LIN.filter(r => r.res < 0);
  const virada = LIN.findIndex((r,i) => r.res < 0 && LIN.slice(i).every(x => x.res < 0));
  document.getElementById("regua-nota").innerHTML =
    `${neg.length} de ${LIN.length} meses fecharam no vermelho.` +
    (virada > 0 ? ` A partir de <b>${rotMes(LIN[virada].k)}</b> não sobrou em
      nenhum: é ali que a linha preta vira pra baixo e não volta.` : "") +
    ` A linha preta é o resultado acumulado — o eixo da direita.`;
}

/* ==================== 3 · o mapa: grupo x mes ====================
   Branco ou preto no texto da celula NAO pode sair do alfa: o mesmo alfa sobre
   o navy da Moradia e sobre o cinza-claro da Viagem da fundos opostos, e foi
   assim que a linha Viagem saiu branco-no-branco. Mistura a cor com o branco do
   fundo e mede a luminancia do que sobrou. */
const rgbDe = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const textoSobre = (hex, a) => {
  const [r, g, b] = rgbDe(hex).map(c => (1 - a) * 255 + a * c);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 145
         ? "color:#fff;font-weight:600" : "";
};
function pintaMapa() {
  const gs = new Map();
  LIN.forEach(r => r.saiu.forEach(t => {
    const g = grupoDe(t), row = gs.get(g) || gs.set(g, {}).get(g);
    row[r.k] = (row[r.k] || 0) + vSai(t);
  }));
  const tot = {}; gs.forEach((row, g) => tot[g] = Object.values(row).reduce((a,b)=>a+b,0));
  const ord = ordenaGrupos(tot).filter(g => Math.abs(tot[g]) > 0.005);
  const head = `<tr><th>Grupo</th>${LIN.map(r =>
    `<th>${rotMes(r.k)}</th>`).join("")}<th>Total</th></tr>`;
  const corpo = ord.map(g => {
    const row = gs.get(g);
    /* intensidade RELATIVA A LINHA: o pico de cada grupo e o que interessa.
       Fosse relativa a tabela toda, so o carro de maio teria cor. */
    const max = Math.max(...LIN.map(r => Math.abs(row[r.k] || 0)), 1);
    const cor = corDe(g);
    return `<tr><td><b>${g}</b></td>${LIN.map(r => {
      const v = row[r.k] || 0, a = Math.abs(v) / max * .88;
      return `<td class="cel ${v ? "" : "zero"}" data-g="${esc(g)}" data-m="${r.k}"
        style="background:${v ? cor + Math.round(a*255).toString(16).padStart(2,"0") : "transparent"};
        ${v ? textoSobre(cor, a) : ""}">${v ? fmt0(v) : "—"}</td>`;
    }).join("")}<td class="cel"><b>${fmt0(tot[g])}</b></td></tr>`;
  }).join("");
  const soma = LIN.map(r => r.total);
  const rodape = `<tr class="tot"><td>Total do mês</td>${soma.map(v =>
    `<td class="cel">${fmt0(v)}</td>`).join("")}<td class="cel">${
    fmt0(soma.reduce((a,b)=>a+b,0))}</td></tr>`;
  document.getElementById("tabMapa").innerHTML = head + corpo + rodape;
}

/* clicar numa celula abre exatamente aquele mes naquele grupo, la embaixo */
document.getElementById("mapa")?.addEventListener("click", ev => {
  const td = ev.target.closest("td.cel[data-m]");
  if (!td) return;
  abertos.add(td.dataset.m);
  abertos.add(td.dataset.m + "/s/" + td.dataset.g);
  pintaEspinha();
  document.querySelector(`tr.m-mes[data-p="${td.dataset.m}"]`)
          .scrollIntoView({behavior:"smooth", block:"center"});
});

/* ==================== 4 · a prova: caixa mes a mes ==================== */
/* as duas pontas de uma transferencia entre contas CONECTADAS: some no mes em
   que as duas caem. Fica no somatorio de proposito — se um dia uma ponta cair
   no mes seguinte, a linha para de fechar em vez de errar calada. */
const INTERNAS = D.lancamentos.filter(t => t.conta_tipo !== "CREDIT"
                                      && t.natureza === "interna");
function pintaCaixa() {
  const fatia = (arr, k, f) => S(arr.filter(t => balde(t) === k), f || vAbs);
  let pior = 0;
  const linhas = LIN.map(r => {
    const ent  = fatia(RENDA, r.k) + fatia(ENTRAEXT, r.k);
    const sai  = fatia(GASTOCC, r.k) + fatia(SAIEXT, r.k);
    const fat  = fatia(faturasCC, r.k);
    const apl  = -fatia(aplicCC, r.k, t => t.valor);   /* >0 aplicou, <0 resgatou */
    const int  = fatia(INTERNAS, r.k, t => t.valor);
    const calc = ent - sai - fat - apl + int;
    pior = Math.max(pior, Math.abs(calc - r.caixa));
    return `<tr><td><b>${rotMes(r.k)}</b></td>${cel(ent,"pos")}${cel(-sai)}
      ${cel(-fat)}<td class="n ${apl>=0?"":"pos"}">${fmt(-apl)}</td>
      <td class="n ${calc>=0?"pos":"neg"}">${fmt(calc)}</td>
      ${cel(r.saldo)}</tr>`;
  }).join("");
  const T = {e: S(LIN, r => r.caixa)};
  document.getElementById("tabCaixa").innerHTML = linhas +
    `<tr class="fx-total"><td>Ano inteiro</td>
     ${cel(Sa(entradasCC),"pos")}${cel(-Sa(saidasCC))}${cel(-Sa(faturasCC))}
     <td class="n">${fmt(S(aplicCC, t => t.valor))}</td>
     <td class="n ${T.e>=0?"pos":"neg"}">${fmt(T.e)}</td>${cel(D.caixa_final)}</tr>`;
  const medido = D.caixa_final - D.caixa_inicial;
  document.getElementById("caixa-res").innerHTML =
    `resíduo do ano ${(T.e - medido).toExponential(1)}, pior mês
     ${pior.toExponential(1)} — bate`;
}

/* ==================== 5 · eventos unicos ==================== */
function pintaUnicos() {
  const U = unicos();
  document.getElementById("tabUni").innerHTML = U.map(t =>
    `<tr><td>${t.data.split("-").reverse().join("/")}</td>
     <td>${esc(limpaDesc(t.desc))}</td><td>${esc(t.instituicao)}</td>
     <td class="n ${t.valor>0?"pos":"neg"}">${fmt(t.valor)}</td></tr>`).join("");
  document.getElementById("uni-res").textContent = U.length + " lançamentos"
    + (extRenda ? " — inclui a conta externa, que o botão 2 pôs no resultado" : "");
}

/* ==================== cabeca ==================== */
function pintaInicio() {
  const atual = LIN[LIN.length-1] || {total:0,res:0};
  const completos = LIN.length > 2 ? LIN.slice(0,-1) : LIN;
  const mesAtual = atual.k;
  const movAtual = GASTOCC.filter(t => {
    const m = fixoDe(t) === 'Financiamento imobiliário' && Number(t.data.slice(8,10)) >= 28
      ? prox(mesDe(t.data)) : balde(t);
    return m === mesAtual;
  }).concat(gastos.filter(t=>balde(t)===mesAtual), estornos.filter(t=>balde(t)===mesAtual));
  const porGrupo = {};
  movAtual.forEach(t => { const g=grupoDe(t), v=t.conta_tipo==='CREDIT'?vSai(t):vAbs(t);
                         porGrupo[g]=(porGrupo[g]||0)+v; });
  const gastoMes = ORCAMENTO.linhas.reduce((s,l) => s+l.grupos.reduce((a,g)=>a+(porGrupo[g]||0),0),0)
                 + BENEFICIO_USO;
  const teto = ORCAMENTO.teto_consumo_com_beneficios;
  const livre = teto - gastoMes;
  const pctTeto = Math.max(0, Math.min(100, gastoMes / teto * 100));
  const pctMeta = Math.max(0, Math.min(100, (RENDA_CONTROLE-gastoMes) / ORCAMENTO.meta_poupanca * 100));
  document.getElementById('dash-saldo').textContent = fmt0(D.resumo.liquido);
  document.getElementById('dash-meta').textContent = fmt0(ORCAMENTO.meta_poupanca) + '/mês';
  document.getElementById('dash-livre').textContent = fmt0(livre);
  const [anoAtual, numeroMes] = D.gerado_em.slice(0,7).split('-').map(Number);
  const diasNoMes = new Date(anoAtual, numeroMes, 0).getDate();
  const diasRestantes = Math.max(1, diasNoMes-Number(D.gerado_em.slice(8,10))+1);
  const limiteDiario = Math.max(0, livre)/diasRestantes;
  document.getElementById('today-daily').textContent = fmt0(limiteDiario);
  document.getElementById('today-weekly').textContent = fmt0(limiteDiario*7);
  document.getElementById('today-committed').textContent = fmt0(D.resumo.divida);
  document.getElementById('dash-tip-text').innerHTML = livre >= 0
    ? `Disponível no orçamento: <b>${fmt0(livre)}</b>`
    : `Orçamento excedido: <b>${fmt0(Math.abs(livre))}</b>`;
  document.getElementById('goal-spend').style.width = pctTeto + '%';
  document.getElementById('goal-spend-txt').textContent = fmt0(gastoMes) + ' de ' + fmt0(teto);
  document.getElementById('goal-save').style.width = pctMeta + '%';
  document.getElementById('goal-save-txt').textContent = fmt0(Math.max(0,RENDA_CONTROLE-gastoMes)) + ' de ' + fmt0(ORCAMENTO.meta_poupanca);
  const usoBen = BENEFICIO_CREDITO ? BENEFICIO_USO/BENEFICIO_CREDITO*100 : 0;
  document.getElementById('goal-benefit').style.width = Math.min(100,usoBen) + '%';
  document.getElementById('goal-benefit-txt').textContent = fmt0(BENEFICIO_USO) + ' de ' + fmt0(BENEFICIO_CREDITO);
  document.getElementById('spark').innerHTML = LIN.slice(-10).map(r => {
    const p = Math.max(12, Math.min(100, r.total/Math.max(...LIN.map(x=>x.total),1)*100));
    return `<i style="height:${p}%" title="${rotMes(r.k)}: ${fmt0(r.total)}"></i>`;
  }).join('');
  const proximos = D.cartoes.map(c => {
    const ciclos=Object.keys(c.faturas||{}).sort(), ciclo=ciclos[ciclos.length-1];
    return {nome:c.instituicao+' · '+c.nome, ciclo, valor:ciclo?Number(c.faturas[ciclo].total||0):0};
  }).filter(x=>x.valor>0).sort((a,b)=>b.valor-a.valor).slice(0,3);
  document.getElementById('dash-next').innerHTML = proximos.map(x => `<div class="next-row">
    <div class="cal">${x.ciclo ? nomeMes(x.ciclo).toUpperCase() : '—'}</div><div><div class="row-main">${esc(x.nome)}</div>
    <div class="row-sub">fatura identificada</div></div><div class="row-val">${fmt0(x.valor)}</div></div>`).join('');
  const recentes = D.lancamentos.filter(t => t.natureza !== 'interna' && !ehEventoPatrimonial(t))
    .slice().sort((a,b)=>b.data.localeCompare(a.data)).slice(0,6);
  document.getElementById('dash-recent').innerHTML = recentes.map(t => { const gasto=t.natureza==='consumo'||t.tipo==='DEBIT'; const val=gasto?-vAbs(t):vAbs(t); return `<div class="recent-row">
    <div class="cal">${t.data.slice(8)}/${t.data.slice(5,7)}</div><div><div class="row-main">${esc(limpaDesc(t.desc))}</div>
    <div class="row-sub">${esc(grupoDe(t))} · ${esc(t.instituicao)}</div></div>
    <div class="row-val ${val<0?'neg':'pos'}">${fmt(val)}</div></div>`; }).join('');
  const mediana = vals => { const a=vals.slice().sort((x,y)=>x-y),n=a.length;
    return n ? (n%2?a[(n-1)/2]:(a[n/2-1]+a[n/2])/2) : 0; };
  const budgetRows = ORCAMENTO.linhas.map(l => {
    let base = mediana(completos.map(r => r.saiu.filter(t=>!ehUnico(t)&&l.grupos.includes(grupoDe(t))).reduce((a,t)=>a+vSai(t),0)));
    if(l.grupos.includes('Alimentação')) base+=BENEFICIO_USO;
    const ajuste=l.teto-base;
    return {l,base,ajuste};
  });
  document.getElementById('dash-budget').innerHTML = budgetRows.map(({l,base,ajuste}) =>
    `<tr><td>${esc(l.nome)}</td><td>${fmt0(base)}</td><td>${fmt0(l.teto)}</td><td class="${ajuste<0?'neg':'pos'}"><b>${fmt0(ajuste)}</b></td></tr>`).join('');
  const cortaveis=['Compras pessoais','Pessoas e cuidados','Lazer e viagem','Assinaturas e infra','Doações'];
  const cuts=budgetRows.filter(x=>cortaveis.includes(x.l.nome)&&x.ajuste<0).sort((a,b)=>a.ajuste-b.ajuste);
  document.getElementById('dash-cuts').innerHTML = cuts.map((x,i)=>`<tr><td>${i+1}</td><td>${esc(x.l.nome)}</td>
    <td>${fmt0(x.base)}</td><td>${fmt0(x.l.teto)}</td><td class="neg"><b>${fmt0(-x.ajuste)}</b></td></tr>`).join('');
  const compras=gastos.filter(t=>grupoDe(t)==='Compras'&&t.fatura);
  const cicloCompra=[...new Set(compras.map(t=>t.fatura))].sort().at(-1);
  const comprasCiclo=compras.filter(t=>t.fatura===cicloCompra);
  const parcelas=comprasCiclo.map(t=>{const m=(t.desc||'').match(/(\d{1,2})\/(\d{1,2})/),v=vAbs(t);
    return {t,v,atual:m?+m[1]:0,total:m?+m[2]:0,rest:m?v*Math.max(0,+m[2]- +m[1]):0};});
  const series=new Map();
  compras.forEach(t=>{const m=(t.desc||'').match(/(\d{1,2})\/(\d{1,2})/); if(!m)return;
    const v=vAbs(t), atual=+m[1], total=+m[2];
    const base=(t.desc||'').replace(/\s*\d{1,2}\/\d{1,2}\s*$/,'').trim();
    const key=[t.instituicao,base,v.toFixed(2),total].join('|'), old=series.get(key);
    if(!old||t.fatura>old.t.fatura||(t.fatura===old.t.fatura&&atual>old.atual))
      series.set(key,{t,v,atual,total,rest:v*Math.max(0,total-atual)});
  });
  const cicloAnterior=(()=>{let [a,m]=cicloCompra.split('-').map(Number);if(--m<1){m=12;a--}return `${a}-${String(m).padStart(2,'0')}`})();
  const ativas=[...series.values()].filter(x=>x.rest>0&&x.t.fatura>=cicloAnterior), totalCompras=parcelas.reduce((s,x)=>s+x.v,0);
  const comprasMes=atual.saiu.filter(t=>grupoDe(t)==='Compras').reduce((s,t)=>s+vSai(t),0);
  const proximo=ativas.reduce((s,x)=>s+x.v,0), futuro=ativas.reduce((s,x)=>s+x.rest,0);
  document.getElementById('buy-cycle').textContent=fmt0(totalCompras);
  document.getElementById('buy-month').textContent=fmt0(comprasMes);
  document.getElementById('buy-next').textContent=fmt0(proximo);
  document.getElementById('buy-future').textContent=fmt0(futuro);
  document.getElementById('dash-installments').innerHTML=ativas.sort((a,b)=>b.rest-a.rest).map(x=>`<tr>
    <td>${esc((x.t.desc||'').replace(/\s*\d{1,2}\/\d{1,2}\s*$/,''))}</td><td>${x.atual}/${x.total}</td>
    <td>${fmt0(x.v)}</td><td class="neg"><b>${fmt0(x.rest)}</b></td></tr>`).join('');
  let ciclo=prox(cicloCompra);
  document.getElementById('dash-installment-flow').innerHTML=Array.from({length:9},(_,i)=>{
    if(i)ciclo=prox(ciclo); const valor=ativas.filter(x=>x.total-x.atual>=i+1).reduce((s,x)=>s+x.v,0);
    return valor?`<tr><td>${nomeMes(ciclo)}</td><td><b>${fmt0(valor)}</b></td></tr>`:'';
  }).join('');
  const ehParcelaCompra=t=>grupoDe(t)==='Compras'&&/(\d{1,2})\/(\d{1,2})/.test(t.desc||'');
  const ehPontual=t=>ehUnico(t)||(vSai(t)>=ORCAMENTO.corte_evento_pontual&&!fixoDe(t));
  const normalizados=completos.map(r=>({k:r.k,total:r.saiu
    .filter(t=>!ehPontual(t)&&!ehParcelaCompra(t)).reduce((s,t)=>s+vSai(t),0)}));
  const media = a => a.reduce((s,r)=>s+r.total,0)/Math.max(1,a.length);
  const mediaMovel=media(normalizados.slice(-6));
  let pm = prox(D.gerado_em.slice(0,7)), acum = 0;
  const proj = Array.from({length:12}, (_,i) => {
    if(i) pm=prox(pm);
    const comprometido=ativas.filter(x=>x.total-x.atual>=i+1).reduce((s,x)=>s+x.v,0);
    return {m:pm,movel:mediaMovel,parcelas:comprometido,gasto:mediaMovel+comprometido};
  });
  const gastoBase=proj.reduce((s,r)=>s+r.gasto,0)/proj.length;
  const sobraBase=RENDA_META-gastoBase;
  document.getElementById('projection-base').textContent = fmt0(mediaMovel) + '/mês';
  document.getElementById('projection-base-save').textContent = fmt0(sobraBase) + '/mês';
  document.getElementById('projection-base-save').className = sobraBase<0?'neg':'pos';
  document.getElementById('today-save').textContent = fmt0(sobraBase);
  document.getElementById('today-save').className = sobraBase<0?'neg':'pos';
  document.getElementById('dash-projection').innerHTML = proj.map(r => {
    acum += ORCAMENTO.meta_poupanca; const sobra=RENDA_META-r.gasto;
    return `<tr><td>${nomeMes(r.m)}</td><td>${fmt0(r.movel)}</td><td>${fmt0(r.parcelas)}</td>
      <td>${fmt0(r.gasto)}</td><td class="${sobra<0?'neg':'pos'}"><b>${fmt0(sobra)}</b></td>
      <td class="pos"><b>${fmt0(acum)}</b></td></tr>`;
  }).join('');
  document.getElementById('dash-months').innerHTML = LIN.slice(-6).reverse().map(r => `<tr><td>${rotMes(r.k)}</td>
    <td class="pos">${fmt0(r.entrou)}</td><td>${fmt0(r.total)}</td><td class="${r.res<0?'neg':'pos'}"><b>${fmt0(r.res)}</b></td></tr>`).join('');
  document.getElementById('dash-accounts').innerHTML = D.instituicoes.map(i => `<tr><td>${esc(i.nome)}</td>
    <td>${fmt0(i.caixa)}</td><td>${fmt0(i.investimentos)}</td><td>${fmt0(i.divida)}</td>
    <td class="${i.liquido<0?'neg':'pos'}"><b>${fmt0(i.liquido)}</b></td></tr>`).join('');
}

function pintaCabeca() {
  const T = {e: S(LIN, r => r.entrou), s: S(LIN, r => r.total)};
  T.res = T.e - T.s;
  const n = LIN.length, mm = T.res / n;
  const u6 = LIN.slice(-6), res6 = S(u6, r => r.res) / u6.length;
  const margem = RENDA_META - T.s/n;
  document.getElementById("veredito").innerHTML =
    `Controle mensal · <em>${margem>=0?'sobra':'falta'} ${fmt0(Math.abs(margem))}</em>`;
  document.getElementById("hero-v").textContent = fmt0(RENDA_META) + "/mês";
  document.getElementById("hero-sub").innerHTML =
    `<span>renda líquida familiar atual</span>
     <span>gasto normalizado médio: <b>${fmt0(T.s/n)}/mês</b></span>
     <span>bônus fora da conta</span>`;
  const k = (id, v, f) => { document.getElementById("k-"+id).textContent = v;
                            document.getElementById("k-"+id+"-f").innerHTML = f; };
  k("renda", fmt0(RENDA_META), `R$ 14 mil Aleph + R$ 10 mil Bia`);
  k("gasto", fmt0(T.s / n), `média normalizada de ${n} meses`);
  k("res",   fmt0(margem),  `renda meta menos gasto médio`);
  k("ult",   fmt0(S(u6, r => r.saiuCard)/u6.length), `cartão médio nos últimos 6 meses`);
}

/* ==================== botoes ==================== */
function redesenha() {
  LIN = monta();
  pintaInicio();
}

function pintaControle() {
  const meses = LIN.map(r => r.k), ult = meses.slice(-4);
  /* O financiamento vence no começo, mas às vezes é debitado no último dia do
     mês anterior. Para controle ele pertence à competência seguinte; sem isso
     junho aparece com duas parcelas e setembro com nenhuma. */
  const mesControle = t => fixoDe(t) === "Financiamento imobiliário"
    && Number(t.data.slice(8,10)) >= 28 ? prox(mesDe(t.data)) : balde(t);
  const contaMes = m => GASTOCC.filter(t => mesControle(t) === m);
  const cardMes = m => gastos.filter(t => balde(t) === m)
    .concat(estornos.filter(t => balde(t) === m));
  const linhas = ult.map(m => {
    const cc = contaMes(m), ca = cardMes(m);
    const fix = S(cc.filter(fixoDe), vAbs);
    const outros = S(cc.filter(t => !fixoDe(t)), vAbs);
    const cartao = Ss(ca), va = BENEFICIO_USO;
    const total = fix + outros + cartao + va;
    return {m, fix, outros, cartao, va, total, sobra:RENDA_CONTROLE-total};
  });
  document.getElementById("controle-corpo").innerHTML = linhas.map((r,i) =>
    `<tr${i===linhas.length-1?' class="tot"':''}><td>${rotMes(r.m)}</td>
      <td class="n">${fmt0(RENDA_CONTROLE)}</td><td class="n">${fmt0(r.fix)}</td>
      <td class="n ${r.cartao>RENDA_META*.35?'neg':''}">${fmt0(r.cartao)}</td>
      <td class="n">${fmt0(r.outros)}</td>
      <td class="n">${fmt0(r.va)}</td>
      <td class="n">${fmt0(r.total)}</td>
      <td class="n ${r.sobra<0?'neg':'pos'}"><b>${fmt0(r.sobra)}</b></td></tr>`).join("");
  const atual = linhas[linhas.length-1], pct = atual ? 100*atual.cartao/RENDA_META : 0;
  document.getElementById("controle-nota").innerHTML =
    `Cartão no mês atual: <b>${pct.toFixed(1)}% da renda líquida familiar</b>. `
    + `Uso mensal estimado dos benefícios: ${fmt0(BENEFICIO_USO)} `
    + `(VA ${fmt0(VA_ALICIA)} + VR ${fmt0(VR_ALEPH)}). Créditos recebidos: ${fmt0(BENEFICIO_CREDITO)}/mês. `
    + `Renda em dinheiro: ${fmt0(RENDA_META)}/mês; bônus ficam fora.`;
  document.getElementById("fixos-head").innerHTML = `<th>Conta fixa</th>${ult.map(nomeMes).map(x=>`<th class="n">${x}</th>`).join('')}<th class="n">média</th>`;
  document.getElementById("fixos-corpo").innerHTML = FIXOS.map(([nome]) => {
    const vals = ult.map(m => S(contaMes(m).filter(t => fixoDe(t)===nome),vAbs));
    const vistos = vals.filter(v => v>0);
    return `<tr><td>${nome}</td>${vals.map(v=>`<td class="n">${v?fmt0(v):'—'}</td>`).join('')}
      <td class="n"><b>${vistos.length?fmt0(vistos.reduce((a,v)=>a+v,0)/vistos.length):'—'}</b></td></tr>`;
  }).join('');
  let somaAberta = 0, somaSaldo = 0;
  document.getElementById("cartoes-corpo").innerHTML = D.cartoes.map(c => {
    const ciclos = Object.keys(c.faturas || {}).sort();
    const ciclo = ciclos[ciclos.length-1], f = ciclo ? c.faturas[ciclo] : null;
    const aberta = f ? Number(f.total || 0) : 0;
    const saldo = Number(c.saldo || 0), futuras = Math.max(0, saldo-aberta);
    somaAberta += aberta; somaSaldo += saldo;
    return `<tr><td>${esc(c.instituicao)}</td><td>${esc(c.nome)}</td>
      <td>${ciclo || 'sem ciclo'}</td><td class="n">${fmt0(aberta)}</td>
      <td class="n">${fmt0(saldo)}</td><td class="n">${fmt0(futuras)}</td></tr>`;
  }).join('');
  document.getElementById("cartoes-total").innerHTML =
    `Faturas abertas identificadas: <b>${fmt0(somaAberta)}</b>. `
    + `Saldo comprometido informado pelos cartões: <b>${fmt0(somaSaldo)}</b>. `
    + `A diferença de <b>${fmt0(Math.max(0,somaSaldo-somaAberta))}</b> é principalmente parcelamento futuro `
    + `ou lançamento sem ciclo; ela não pode desaparecer do controle.`;

  const movAtual = atual ? contaMes(atual.m).concat(cardMes(atual.m)) : [];
  const realGrupo = {};
  movAtual.forEach(t => { const g=grupoDe(t), v=t.conta_tipo==='CREDIT'?vSai(t):vAbs(t);
                         realGrupo[g]=(realGrupo[g]||0)+v; });
  let tetoTotal=0, realTotal=0;
  document.getElementById("orcamento-corpo").innerHTML = ORCAMENTO.linhas.map(l => {
    let real=l.grupos.reduce((s,g)=>s+(realGrupo[g]||0),0);
    if (l.grupos.includes('Alimentação')) real += BENEFICIO_USO;
    const resta=l.teto-real; tetoTotal+=l.teto; realTotal+=real;
    return `<tr><td>${esc(l.nome)}</td><td class="n">${fmt0(l.teto)}</td>
      <td class="n">${real?fmt0(real):'—'}</td>
      <td class="n ${resta<0?'neg':'pos'}"><b>${fmt0(resta)}</b></td></tr>`;
  }).join('') + `<tr class="tot"><td>Total</td><td class="n">${fmt0(tetoTotal)}</td>
    <td class="n">${fmt0(realTotal)}</td><td class="n ${tetoTotal-realTotal<0?'neg':'pos'}">
    <b>${fmt0(tetoTotal-realTotal)}</b></td></tr>`;
  document.getElementById("orcamento-nota").innerHTML =
    `Meta: investir <b>${fmt0(ORCAMENTO.meta_poupanca)}</b> assim que a renda cair e viver com `
    + `<b>${fmt0(ORCAMENTO.teto_gastos)}</b> em dinheiro, mais <b>${fmt0(BENEFICIO_USO)}</b> de VA/VR. `
    + `O orçamento total de consumo é <b>${fmt0(ORCAMENTO.teto_consumo_com_beneficios)}</b>; `
    + `valores realizados são do mês atual, ainda parcial.`;
}
document.querySelectorAll(".tg button").forEach(b => b.addEventListener("click", () => {
  const grupo = b.parentElement.querySelectorAll("button[data-g='" + b.dataset.g + "']");
  grupo.forEach(x => x.classList.toggle("on", x === b));
  semUnicos = b.dataset.v === "1";
  /* o mesmo caminho aberto passaria a apontar pra outro conjunto quando a
     premissa muda; fechar tudo e mais honesto do que manter um estado que
     nao significa mais a mesma coisa */
  abertos.clear();
  redesenha();
}));

document.querySelectorAll('.app-tab').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.app-tab').forEach(x => x.classList.toggle('on', x===b));
  document.querySelectorAll('[data-tab-panel]').forEach(x => x.classList.toggle('on', x.dataset.tabPanel===b.dataset.tab));
  history.replaceState(null, '', '#'+b.dataset.tab);
  window.scrollTo({top:0,behavior:'smooth'});
}));
const abaInicial = location.hash.slice(1);
const botaoInicial = document.querySelector(`.app-tab[data-tab="${abaInicial}"]`);
if (botaoInicial) botaoInicial.click();

redesenha();
"""

HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Controle financeiro mensal — __DATA_BR__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>__CSS__</style><script>__CHARTJS__</script></head><body>
<div class="wrap">
  <div class="app-top"><div class="brand"><span class="brand-mark">K</span>Kaleu Finance</div>
    <div class="date-pill">Atualizado em __DATA_BR__</div></div>

  <main class="home">
    <div class="home-head"><div><div class="hello">Aleph + Bia</div>
      <h1>Painel financeiro</h1></div>
      <div class="home-actions"><a href="#dash-budget-card">Orçamento</a><a class="primary" href="#dash-recent-card">Transações</a></div></div>
    <nav class="app-tabs" aria-label="Seções do painel">
      <button class="app-tab on" data-tab="hoje">Hoje</button><button class="app-tab" data-tab="orcamento">Orçamento</button>
      <button class="app-tab" data-tab="futuro">Futuro</button><button class="app-tab" data-tab="metas">Metas</button>
    </nav>
    <div class="tab-panel on" data-tab-panel="hoje">
    <div class="balance"><div><div class="eyebrow">Patrimônio financeiro líquido</div>
      <div class="big" id="dash-saldo">—</div>
      <div class="balance-meta"><span>Meta mensal <b id="dash-meta">—</b></span>
      <span>Ainda pode gastar <b id="dash-livre">—</b></span></div></div>
      <div><div class="eyebrow">Ritmo dos gastos · últimos meses</div><div class="spark" id="spark"></div></div></div>
    <div class="dash-tip"><span class="tip-dot"></span><div id="dash-tip-text">Calculando sua dica do mês…</div>
      <a class="dash-section-link" href="#controle">ver detalhes</a></div>
      <div class="dash-card today-kpis"><div class="eyebrow">Limite disponível</div><h3>Quanto posso gastar</h3>
        <div class="projection-kpis"><div class="projection-kpi"><span>Hoje</span><b id="today-daily">—</b></div>
        <div class="projection-kpi"><span>Próximos 7 dias</span><b id="today-weekly">—</b></div>
        <div class="projection-kpi"><span>Cartões comprometidos</span><b id="today-committed">—</b></div>
        <div class="projection-kpi"><span>Poupança projetada</span><b id="today-save">—</b></div></div></div>
      <div class="dash-card"><div class="eyebrow">Objetivos</div><h3>Seu plano mensal</h3>
        <div class="goal"><div class="goal-line"><span>Controle do orçamento</span><strong id="goal-spend-txt">—</strong></div><div class="progress"><span id="goal-spend"></span></div></div>
        <div class="goal"><div class="goal-line"><span>Guardar 30% da renda</span><strong id="goal-save-txt">—</strong></div><div class="progress"><span id="goal-save"></span></div></div>
        <div class="goal"><div class="goal-line"><span>Uso de VA e VR</span><strong id="goal-benefit-txt">—</strong></div><div class="progress"><span id="goal-benefit"></span></div></div>
      </div>
      <div class="dash-card"><div class="eyebrow">Próximos</div><h3>Faturas e compromissos</h3><div id="dash-next"></div></div>
      <div class="dash-card recent" id="dash-recent-card"><div class="eyebrow">Transações recentes</div><h3>Últimos lançamentos</h3><div id="dash-recent"></div></div>
    </div>
    <div class="tab-panel" data-tab-panel="orcamento">
      <div class="dash-card dash-data" id="dash-budget-card"><div class="eyebrow">Orçamento</div><h3>Mediana mensal normalizada × teto</h3>
        <div class="tbl-wrap"><table class="dash-table"><thead><tr><th>Categoria</th><th>Mediana mensal</th><th>Teto alvo</th><th>Ajuste</th></tr></thead><tbody id="dash-budget"></tbody></table></div></div>
      <div class="dash-card dash-data"><div class="eyebrow">Plano de redução</div><h3>Prioridade de cortes</h3>
        <div class="tbl-wrap"><table class="dash-table"><thead><tr><th>Prioridade</th><th>Categoria</th><th>Base mensal</th><th>Teto</th><th>Redução</th></tr></thead><tbody id="dash-cuts"></tbody></table></div></div>
      <div class="dash-card dash-data"><div class="eyebrow">Compras</div><h3>Parcelas ativas</h3>
        <div class="projection-kpis"><div class="projection-kpi"><span>Compras no mês</span><b id="buy-month">—</b></div>
        <div class="projection-kpi"><span>Compras no ciclo</span><b id="buy-cycle">—</b></div>
        <div class="projection-kpi"><span>Travado no próximo</span><b id="buy-next">—</b></div>
        <div class="projection-kpi"><span>Parcelas restantes</span><b id="buy-future">—</b></div></div>
        <div class="tbl-wrap"><table class="dash-table"><thead><tr><th>Compra</th><th>Parcela</th><th>Valor mensal</th><th>Saldo futuro</th></tr></thead><tbody id="dash-installments"></tbody></table></div>
        <div class="tbl-wrap" style="margin-top:12px"><table class="dash-table"><thead><tr><th>Próximos ciclos</th><th>Parcelas já contratadas</th></tr></thead><tbody id="dash-installment-flow"></tbody></table></div></div>
    </div>
    <div class="tab-panel" data-tab-panel="futuro">
      <div class="dash-card dash-data"><div class="eyebrow">Projeção</div><h3>Fluxo de caixa · próximos 12 meses</h3>
        <div class="projection-kpis"><div class="projection-kpi"><span>Média móvel 6m</span><b id="projection-base">—</b></div>
        <div class="projection-kpi"><span>Sobra na tendência</span><b id="projection-base-save">—</b></div>
        <div class="projection-kpi"><span>Meta acumulada · 6 meses</span><b>R$ 43.200</b></div>
        <div class="projection-kpi"><span>Meta acumulada · 12 meses</span><b>R$ 86.400</b></div></div>
        <div class="tbl-wrap"><table class="dash-table"><thead><tr><th>Mês</th><th>Média móvel</th><th>Parcelas</th><th>Gasto projetado</th><th>Sobra projetada</th><th>Acumulado alvo</th></tr></thead><tbody id="dash-projection"></tbody></table></div></div>
      <div class="dash-card dash-data"><div class="eyebrow">Histórico</div><h3>Últimos 6 meses</h3>
        <div class="tbl-wrap"><table class="dash-table"><thead><tr><th>Mês</th><th>Entradas</th><th>Gastos</th><th>Resultado</th></tr></thead><tbody id="dash-months"></tbody></table></div></div>
    </div>
    <div class="tab-panel" data-tab-panel="metas">
      <div class="dash-card dash-data"><div class="eyebrow">Reserva</div><h3>Marcos de poupança</h3><div class="meta-grid">
        <div class="meta-box"><span>3 meses</span><b>R$ 21.600</b></div><div class="meta-box"><span>6 meses</span><b>R$ 43.200</b></div><div class="meta-box"><span>12 meses</span><b>R$ 86.400</b></div>
      </div></div>
      <div class="dash-card dash-data"><div class="eyebrow">Posições</div><h3>Contas e investimentos</h3>
        <div class="tbl-wrap"><table class="dash-table"><thead><tr><th>Instituição</th><th>Caixa</th><th>Investimentos</th><th>Cartão</th><th>Líquido</th></tr></thead><tbody id="dash-accounts"></tbody></table></div></div>
    </div>
  </main>
  <div class="dash-footer">__DATA_BR__ · __N_LANC__ lançamentos · __N_INST__ instituições</div>
</div>
<script>__JS__</script></body></html>
"""


def render(P: dict) -> str:
    d1, d2 = P["janela"]
    r = P["resumo"]
    prem = json.loads((Path(os.getenv("PERSONALBUDGET_FINANCE_CONFIG", Path(__file__).resolve().parent)) / "premissas-fluxo.json")
                      .read_text(encoding="utf-8"))
    renda = prem["renda_mensal"]
    renda_atual = renda["aleph_liquido"] + renda["bia_liquido"]
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
    # a janela abre no meio do mes: o primeiro balde e um toco e o rotulo funde
    toco = ("O extrato abre em " + br(d1) + ", então o primeiro mês entra junto "
            "com o seguinte e o rótulo diz isso." if d1[8:] != "01" else "")
    return (HTML
            .replace("__CHARTJS__", chartjs)
            .replace("__CSS__", CSS + CSS_EXTRA)
            .replace("__JS__", JS.replace("__CLASSIFICADOR__", classificador())
                                 .replace("__PAYLOAD__",
                                          json.dumps(dict(P, premissas_fluxo=prem), ensure_ascii=False)))
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
            .replace("__RENDA_ALEPH__", money0(renda["aleph_liquido"]))
            .replace("__RENDA_BIA__", money0(renda["bia_liquido"]))
            .replace("__GASTO_MEDIO__", money0(gasto_medio))
            .replace("__MARGEM_ATUAL__", money0(renda_atual - gasto_medio))
            .replace("__TOCO__", toco))


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
    # so mexe na FOTO do patrimonio (o rodape); o fluxo nao muda uma virgula
    aplica_posicoes_manuais(P)
    dest = (Path(args.out) if args.out else
            WORKSPACE / "reports" / f"fluxo-mensal-{date.today()}.html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render(P), encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
