import {
  cashflowCycle,
  cashflowSummary,
  defaultCashflowLines,
  cashflowLineId,
  sum,
  expense,
  monthSummary,
  competenceMonth,
  cycleMonth,
  transactionsForBasis,
  salaryBreakdown,
  budgetSummary,
  monthSequence,
  csvCell,
} from "./finance.js";
import {
  esc,
  icon,
  amount,
  money,
  monthName,
  dateName,
  percent,
  progress,
  empty,
  api,
  download,
} from "./ui.js";

const pages = {
  overview: "Visão geral",
  cashflow: "Fluxo por ciclo",
  transactions: "Transações",
  budget: "Orçamento",
  accounts: "Contas e cartões",
  goals: "Metas",
  settings: "Ajustes",
  kaleu: "Kaleu",
};
const mobileNames = {
  overview: "Início",
  cashflow: "Fluxo",
  transactions: "Transações",
  budget: "Orçamento",
  accounts: "Contas",
  goals: "Metas",
  settings: "Ajustes",
  kaleu: "Kaleu",
};
const state = {
  data: null,
  transactions: [],
  month: "",
  page: "overview",
  search: "",
  kind: "all",
  institution: "all",
  group: "all",
  pagination: 1,
  basis: "cycle",
  source: "all",
  includeDeclared: true,
  filtersOpen: false,
  reviewPrompted: false,
  kaleuMessages: [],
};
const content = document.querySelector("#content");
const modal = document.querySelector("#modal");
let toastTimer;
const chartColor = [
  "#435571",
  "#7288aa",
  "#9db2d2",
  "#bdcde4",
  "#a5b0c0",
  "#dae1eb",
];
let privateMode = false;
try {
  privateMode = localStorage.getItem("budget-private") === "true";
} catch {}
function privacy() {
  document.body.classList.toggle("private", privateMode);
  const button = document.querySelector("#privacy");
  button.innerHTML = icon("eye");
  button.setAttribute("aria-pressed", String(privateMode));
  button.setAttribute(
    "aria-label",
    privateMode ? "Mostrar valores" : "Ocultar valores",
  );
}
privacy();
document.querySelector("#privacy").onclick = () => {
  privateMode = !privateMode;
  try {
    localStorage.setItem("budget-private", String(privateMode));
  } catch {}
  privacy();
};
function toast(message) {
  const el = document.querySelector("#toast");
  el.textContent = message;
  el.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("visible"), 4500);
}
function options(items, selected) {
  return items
    .map(
      ([value, label]) =>
        `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(label)}</option>`,
    )
    .join("");
}
function pageHead(title, description, action = "", withMonth = true) {
  const months = [
    ...new Set([
      state.data.finance.gerado_em.slice(0, 7),
      ...state.transactions.flatMap((t) => [t.date.slice(0, 7), competenceMonth(t, state.data.budget), cycleMonth(t, state.data.budget)]),
    ]),
  ]
    .sort()
    .reverse();
  return `<div class="page-head"><div><div class="eyebrow">SEU DINHEIRO, COM CLAREZA</div><h1>${title}</h1><p>${description}</p></div><div class="head-actions">${
    withMonth
      ? `<select id="month" class="month-select" aria-label="Mês de referência">${options(
          months.map((m) => [m, monthName(m)]),
          state.month,
        )}</select>${["overview", "transactions"].includes(state.page) ? `<select id="basis" aria-label="Visão financeira">${options([["cycle", "Ciclo do salário"], ["cash", "Caixa · data bancária"], ["competence", "Competência"]], state.basis)}</select>` : ""}`
      : ""
  }${action}</div></div>`;
}
function kpi(title, value, note, symbol, featured = false, cls = "") {
  return `<article class="kpi ${featured ? "featured" : ""}"><div class="kpi-title">${title}${icon(symbol)}</div><div class="kpi-value ${cls}">${amount(value)}</div><div class="kpi-note">${note}</div></article>`;
}
function viewTransactions() {
  const basis = state.page === "budget" ? "cycle" : state.basis;
  return transactionsForBasis(state.transactions, basis, state.data.budget);
}
function matchesFilters(t) {
  const query = state.search.toLocaleLowerCase("pt-BR");
  return (state.kind === "all" || t.kind === state.kind)
    && (state.institution === "all" || t.instituicao === state.institution)
    && (state.group === "all" || t.group === state.group)
    && (state.source === "all" || Boolean(t.manual) === (state.source === "manual"))
    && [t.description, t.group, t.instituicao, t.note].some(v => String(v || "").toLocaleLowerCase("pt-BR").includes(query));
}
function getSummary() {
  const rows = viewTransactions();
  return monthSummary(state.page === "budget" ? rows : rows.filter(matchesFilters), state.month);
}
function basisNote() {
  return state.basis === "cash" ? "Caixa: entradas e saídas das contas na data bancária, incluindo faturas, aplicações e transferências. Compras no cartão não saem do caixa novamente."
    : state.basis === "competence" ? "Competência: mês informado do gasto ou da renda. Sem ajuste, usa a data do lançamento; salário recebido no dia 01 é atribuído ao mês trabalhado anterior."
    : "Ciclo: começa no salário de Aleph, soma a entrada de Bianca e acompanha os pagamentos até o próximo salário. Aqui entram faturas pagas; compras no cartão ficam na visão de competência. Sem salário identificado, a fronteira do ciclo é estimada.";
}

function getBudget() {
  return budgetSummary(state.data.budget, monthSummary(transactionsForBasis(state.transactions, "cycle", state.data.budget), state.month));
}
function rowTable(rows, full = false) {
  if (!rows.length)
    return empty(
      "Nenhum lançamento por aqui",
      "Experimente outro mês ou ajuste os filtros.",
    );
  return `<div class="table-wrap ${full ? "full" : ""}"><table><thead><tr><th>Descrição</th><th>Categoria</th>${full ? "<th>Instituição</th>" : ""}<th>Data</th><th class="right">Valor</th>${full ? '<th><span class="chart-accessible">Ações</span></th>' : ""}</tr></thead><tbody>${rows
    .map((t) => {
      const positive = t.kind === "income" || t.kind === "refund";
      const signed = positive
        ? t.amount
        : t.kind === "expense"
          ? -t.amount
          : (t.valor ?? 0);
      return `<tr><td><div class="transaction-name"><span class="transaction-icon ${positive ? "income" : ""}">${icon(positive ? "down" : t.kind === "other" ? "transactions" : "arrow")}</span><div><b title="${esc(t.description)}">${esc(t.description)}</b><small>${t.manual ? "Registro manual" : esc(t.conta_tipo === "CREDIT" ? "Cartão de crédito" : t.instituicao)}${t.kind === "refund" ? " · Estorno" : t.kind === "other" ? " · Fora do resultado" : ""}</small></div></div></td><td><span class="pill">${esc(t.group)}</span></td>${full ? `<td class="note-small">${esc(t.instituicao)}</td>` : ""}<td class="note-small">${dateName(t.date).slice(0, 5)}${t.competence && t.competence !== t.date.slice(0, 7) ? `<br><span class="pill">Ref. ${esc(monthName(t.competence, true))}</span>` : ""}</td><td class="right money-cell ${positive ? "positive" : t.kind === "other" ? "neutral" : ""}">${amount(signed)}</td>${full ? `<td>${t.manual ? `<button class="icon-button" data-action="delete-transaction" data-id="${esc(t.id)}" aria-label="Excluir ${esc(t.description)}">×</button>` : `<button class="text-button" data-action="classify-transaction" data-id="${esc(t.id)}" aria-label="Ajustar competência de ${esc(t.description)}">Ajustar</button>`}</td>` : ""}</tr>`;
    })
    .join("")}</tbody></table></div>`;
}
function cashChart() {
  const months = monthSequence(state.month, 6);
  const records = months.map((m) => ({
    ...monthSummary(viewTransactions().filter(matchesFilters), m),
    month: m,
  }));
  const max = Math.max(
    1000,
    ...records.flatMap((r) => [r.income, Math.max(0, r.spending)]),
  );
  const scale = Math.ceil(max / 1000) * 1000;
  return `<div class="chart-wrap"><div class="chart-grid">${[1, 0.75, 0.5, 0.25, 0].map((x) => `<div><small class="money">${Math.round((scale * x) / 1000)} mil</small></div>`).join("")}</div><div class="bar-chart" role="img" aria-label="Receitas e despesas dos últimos seis meses">${records.map((r) => `<div class="bar-pair"><div class="bar" style="height:${(r.income / scale) * 100}%" title="${esc(monthName(r.month))}: receitas"></div><div class="bar out" style="height:${(Math.max(0, r.spending) / scale) * 100}%" title="Despesas"></div><small>${monthName(r.month, true).replace(".", "")}</small></div>`).join("")}</div></div><table class="chart-accessible"><caption>Receitas e despesas por mês</caption><thead><tr><th>Mês</th><th>${state.basis === "cash" ? "Entradas" : "Receitas"}</th><th>${state.basis === "cash" ? "Saídas" : "Despesas"}</th></tr></thead><tbody>${records.map((r) => `<tr><td>${monthName(r.month)}</td><td>${amount(r.income)}</td><td>${amount(r.spending)}</td></tr>`).join("")}</tbody></table>`;
}
function categoryChart(summary) {
  const sorted = Object.entries(summary.groups)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);
  if (!sorted.length)
    return empty(
      "Um mês sem despesas",
      "Os gastos por categoria aparecerão aqui.",
    );
  const groups = sorted;
  const total = sum(groups.map(([, v]) => v));
  let offset = 0;
  const rings = groups
    .map(([name, value], i) => {
      const dash = (value / total) * 100;
      const circle = `<circle cx="50" cy="50" r="40" fill="none" stroke="hsl(${215 + i * 47} 35% 55%)" stroke-width="11" pathLength="100" stroke-dasharray="${dash} ${100 - dash}" data-action="category-filter" data-group="${esc(name)}" style="cursor:pointer" stroke-dashoffset="${-offset}"><title>${esc(name)} · ${Math.round(value / total * 100)}%</title></circle>`;
      offset += dash;
      return circle;
    })
    .join("");
  return `<div class="donut-layout"><div class="donut"><svg viewBox="0 0 100 100" aria-hidden="true">${rings}</svg><div class="donut-center"><span>Categorias com gasto</span><b>${amount(total)}</b></div></div></div><div class="category-list">${groups.map(([name, value], i) => `<button type="button" class="category-row category-button" data-action="category-filter" data-group="${esc(name)}"><i style="background:hsl(${215 + i * 47} 35% 55%)"></i><span>${esc(name)} <small>${(value / total * 100).toFixed(1)}%</small></span><b>${amount(value)}</b></button>`).join("")}</div>`;
}
function budgetItem(line) {
  const ratio = percent(line.spent, line.teto);
  return `<div class="budget-item"><div class="budget-line"><span>${esc(line.nome)}</span><span>${amount(line.spent)} <small>/ ${amount(line.teto)}</small></span></div>${progress(line.spent, line.teto, line.spent > line.teto ? "over" : ratio > 80 ? "warn" : "")}<div class="budget-sub"><span>${line.spent > line.teto ? "Acima do limite" : `${Math.round(ratio)}% utilizado`}</span><span>${amount(Math.abs(line.teto - line.spent))} ${line.spent > line.teto ? "acima" : "restantes"}</span></div></div>`;
}
function wealth() {
  const d = structuredClone(state.data.finance);
  if (state.includeDeclared) return d;
  const declared = d.investimentos.filter(v => v.manual);
  const total = sum(declared.map(v => v.saldo));
  d.resumo.liquido -= total;
  d.resumo.investimentos -= total;
  d.investimentos = d.investimentos.filter(v => !v.manual);
  d.instituicoes.forEach(i => {
    const value = sum(declared.filter(v => v.instituicao === i.nome).map(v => v.saldo));
    i.investimentos -= value;
    i.liquido -= value;
  });
  return d;
}
function declaredControl() {
  return `<label class="declared-toggle"><input type="checkbox" id="include-declared" ${state.includeDeclared ? "checked" : ""}> Incluir saldos declarados no patrimônio <span class="money">(${money(state.data.finance.manual_total || 0)})</span></label>`;
}
function cycleDetails() {
  if (state.basis !== "cycle") return "";
  const bank = transactionsForBasis(state.transactions, "cash", state.data.budget);
  const due = bank.filter(t => !t.manual && t.date.slice(0, 7) === state.month && Number(t.date.slice(8, 10)) <= 15 && t.kind === "expense");
  const bills = sum(due.filter(t => t.natureza === "fatura").map(t => t.amount));
  return `<section class="panel cycle-note"><h2>Primeira quinzena · ${monthName(state.month)}</h2><p>Total bancário sem filtros, registrado até o dia 15: ${amount(sum(due.map(t => t.amount)))}. Pagamentos de cartões nesse período: ${amount(bills)}.</p><p>Seu calendário: cartões na primeira semana, condomínio no dia 10 e depois luz${state.month <= "2026-12" ? "; MBA previsto até dezembro de 2026" : ""}. Os valores acima são realizados; contas futuras ainda não pagas não estão incluídas.</p></section>`;
}
function salariesPanel() {
  const plan = state.data.salary_plan || [];
  if (!plan.length) return "";
  const rows = monthSequence(state.month, 6).reverse();
  const current = salaryBreakdown(state.transactions, state.month, state.data.budget);
  return `<section class="panel salary-panel"><div class="panel-head"><div><h2>Salários mês a mês</h2><p>Ciclo do salário · valores por pessoa, sem repetir receitas do extrato</p></div></div><div class="salary-plan">${plan.map(p => `<div><b>${esc(p.name)} · ${esc(p.regime)}</b><p>Líquido previsto: ${amount(p.net)}</p>${p.gross == null ? "" : `<small>Bruto de referência: ${amount(p.gross)}</small>`}</div>`).join("")}</div><p class="info-note">Estes são os valores atuais do planejamento, não recebimentos históricos confirmados. Os totais abaixo usam salários atribuídos a cada pessoa. “Não identificado” não significa que não houve pagamento.</p><div class="table-wrap"><table><thead><tr><th>Ciclo</th><th>Aleph · identificado</th><th>Bianca · identificado</th><th>Salários sem titular</th></tr></thead><tbody>${rows.map(month => {const s = salaryBreakdown(state.transactions, month, state.data.budget);return `<tr><td>${esc(monthName(month))}</td><td>${s.received.aleph ? amount(s.received.aleph) : '<span class="muted">Não identificado</span>'}</td><td>${s.received.bianca ? amount(s.received.bianca) : '<span class="muted">Não identificado</span>'}</td><td>${s.unassigned ? amount(s.unassigned) : '—'}</td></tr>`;}).join("")}</tbody></table></div>${current.candidates.length ? `<details><summary>Repasses da Bianca no mês: ${current.candidates.length} para conferir</summary><p class="info-note">PIX da Bianca pode ser salário, transferência ou reembolso. Confirme a finalidade antes de marcar como salário.</p>${current.candidates.map(t => `<div class="salary-candidate"><span>${dateName(t.date)} · ${esc(t.description)} · ${amount(t.amount)}</span><button class="text-button" data-action="classify-transaction" data-id="${esc(t.id)}">Identificar</button></div>`).join("")}</details>` : ""}<p class="info-note">Para atribuir um recebimento bancário, abra Transações → Ajustar → Titular do salário. Se o recebimento não está no extrato, registre um lançamento manual como salário e informe o titular.</p></section>`;
}
function currentCashflow(month = state.month) {
  return cashflowSummary(state.transactions,month,state.data.budget,(state.data.cashflow_plans || []).find(p=>p.month===month),state.data.salary_plan);
}
function cashflow() {
  const f=currentCashflow();
  const funding={pool:"Fundo conjunto",aleph:"Salário Aleph",bianca:"Salário Bianca"};
  const sources=(state.data.salary_plan||[]).map(p=>{
    const assigned=sum(f.rows.filter(l=>l.funding===p.person).map(l=>l.paid));
    return `<article class="panel"><h2>${esc(p.name)}</h2><div class="kpi-value">${amount(f.salary[p.person])}</div><p class="info-note">Recebido · previsto ${amount(p.net)}</p><small>Pagamentos atribuídos: ${amount(assigned)}</small></article>`;
  }).join("");
  return pageHead("Fluxo de caixa por ciclo", "Salários → contas → saldo do ciclo", `<button class="button primary" data-action="edit-cashflow">Editar budget e origem</button>`) +
   `<div class="cycle-window"><b>Contas de ${esc(monthName(state.month))}</b><span>Início ${dateName(f.start.start)}${f.start.estimated ? " · estimado" : " · salário Aleph"} → próximo salário ${dateName(f.end.start)}${f.end.estimated ? " · estimado" : ""}</span><small>Contas principais até dia 15. Antecipações e pagamentos posteriores também entram no ciclo.</small></div>
   <div class="kpis">${kpi("Entradas recebidas",f.income,"Salários e outras receitas","down")}${kpi("Contas pagas",f.paid,"Saídas efetivas · fatura contada uma vez","arrow")}${kpi("Saldo do ciclo",f.balance,`Saldo inicial informado: ${money(f.opening)}`,"leaf",true)}${kpi("Ainda orçado",f.remaining,f.unplanned ? `${f.unplanned} linhas sem budget definido` : "Budget menos pagamentos realizados","budget")}</div>
   <div class="salary-cards">${sources}</div>
   <section class="panel"><div class="panel-head"><div><h2>Aplicação dos salários</h2><p>A origem é a destinação planejada; valores sem divisão ficam no fundo conjunto.</p></div><button class="text-button" data-action="kaleu-analysis">Analisar com Kaleu ↗</button></div><div class="table-wrap"><table><thead><tr><th>Linha de custo</th><th>Até dia</th><th>Origem planejada</th><th class="right">Budget</th><th class="right">Pago</th><th class="right">Ainda orçado</th><th class="right">Desvio</th></tr></thead><tbody>${f.rows.map(l=>`<tr><td><details><summary>${esc(l.name)} <small>(${l.transactions.length})</small></summary>${l.transactions.map(t=>`<div class="flow-transaction">${dateName(t.date)} · ${esc(t.description)} · ${amount(t.amount)} <button class="text-button" data-action="classify-transaction" data-id="${esc(t.id)}">${t.manual ? "" : "Ajustar"}</button></div>`).join("") || '<small>Nenhum pagamento identificado.</small>'}</details></td><td>${l.due_day||'—'}</td><td>${funding[l.funding]}</td><td class="right">${l.budget==null?'<span class="muted">Definir</span>':amount(l.budget)}</td><td class="right">${amount(l.paid)}</td><td class="right">${l.remaining==null?'—':amount(l.remaining)}</td><td class="right ${l.variance<0?'negative':''}">${l.variance==null?'—':amount(l.variance)}</td></tr>`).join("")}</tbody><tfoot><tr><th colspan="3">Total</th><th class="right">${amount(f.planned)}</th><th class="right">${amount(f.paid)}</th><th class="right">${amount(f.remaining)}</th><th class="right">${amount(f.planned-f.paid)}</th></tr></tfoot></table></div></section>
   <div class="flow-footer"><span>Saldo após cumprir o budget: <b>${amount(f.projected)}</b>${f.unplanned ? " · previsão incompleta" : ""}</span><span>Pagamentos no fundo conjunto: ${amount(sum(f.rows.filter(l=>l.funding==='pool').map(l=>l.paid)))}</span></div>
   <p class="info-note">Este é o saldo do ciclo, não o saldo bancário. Compras no cartão aparecem na análise de consumo; aqui entra o pagamento da fatura. Transferências próprias e aplicações ficam fora do fluxo operacional. Limites estimados consideram fins de semana, sem calendário de feriados; ajuste o ciclo de um lançamento quando necessário.</p>`;
}
function cashflowForm() {
  const f=currentCashflow(), rows=f.rows.filter(l=>l.id!=='unallocated');
  const history=monthSequence(state.month,4).slice(0,3).map(m=>currentCashflow(m));
  openModal("Budget do ciclo", "Valores e origens valem somente para este ciclo. A média histórica é uma sugestão editável.",
   `<form><label>Saldo inicial destinado ao ciclo<input name="opening_balance" type="number" step="0.01" value="${f.opening}" required></label><div class="review-list">${rows.map((l,i)=>{
     const amounts=history.map(h=>h.rows.find(r=>r.id===l.id)?.paid||0).filter(v=>v>0);
     const suggested=amounts.length ? Math.round(sum(amounts)/amounts.length*100)/100 : '';
     return `<fieldset class="flow-edit"><legend>${esc(l.name)}</legend><div class="form-grid"><label>Budget (R$)<input name="amount-${i}" type="number" min="0" step="0.01" value="${l.budget??''}" placeholder="${suggested ? 'Histórico: '+suggested : 'Definir valor'}"></label><label>Até dia<input name="due-${i}" type="number" min="1" max="31" value="${l.due_day||''}"></label><label>Qual salário paga?<select name="fund-${i}">${options([["pool","Fundo conjunto"],["aleph","Aleph"],["bianca","Bianca"]],l.funding)}</select></label><label>Último ciclo (opcional)<input name="end-${i}" type="month" value="${l.end_month||''}"></label></div></fieldset>`;
   }).join("")}</div>${formFooter("Salvar budget deste ciclo")}</form>`);
  bindForm(form=>api("cashflow","PUT",{month:state.month,opening_balance:Number(form.get("opening_balance")),lines:rows.map((l,i)=>({id:l.id,name:l.name,budget:form.get(`amount-${i}`)===''?null:Number(form.get(`amount-${i}`)),due_day:form.get(`due-${i}`)?Number(form.get(`due-${i}`)):null,funding:form.get(`fund-${i}`),end_month:form.get(`end-${i}`)||null}))}));
}
function pendingReviews() {
  return state.transactions.filter(t => !t.manual && !t.reviewed &&
    ((t.salary_candidate && !t.salary_person) || (["expense", "refund"].includes(t.kind) && ["Outros", "Transferências", "Sem categoria"].includes(t.group)) ||
     (t.kind === "income" && (t.is_salary || t.metodo === "Salário") && !t.salary_person))).sort((a,b)=>Number(Boolean(b.salary_candidate))-Number(Boolean(a.salary_candidate)));
}
function syncLabel() {
  const sync = state.data.sync || {};
  if (sync.status === "running") return "Sincronizando bancos…";
  if (sync.status === "error") return "Coleta pendente · últimos dados preservados";
  if (sync.report_error) return "Bancos atualizados · relatório detalhado pendente";
  return sync.last_success ? `Atualizado ${new Date(sync.last_success * 1000).toLocaleString("pt-BR", {day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})} · a cada hora` : "Aguardando sincronização";
}
function guideStrip() {
  const count = pendingReviews().length;
  return `<div class="guide-strip"><a class="button small" href="#cashflow">Fluxo por ciclo →</a><span>${esc(syncLabel())}</span><div><button class="text-button" data-action="review-pending">${count ? `${count} lançamentos para revisar` : "Categorias revisadas"}</button><button class="button small" data-action="kaleu-analysis">Analisar com Kaleu ↗</button></div></div>`;
}
function reviewModal() {
  const pending = pendingReviews();
  if (modal.open) modal.close();
  openModal("Revisar lançamentos", "Confirme a categoria e o tratamento de cada movimento.",
    pending.length ? `<div class="review-list">${pending.slice(0,20).map(t => `<div class="salary-candidate"><span><b>${esc(t.description)}</b><br>${dateName(t.date)} · ${esc(t.instituicao)} · ${amount(t.amount)}</span><button class="button small" data-action="classify-transaction" data-id="${esc(t.id)}">Categorizar</button></div>`).join("")}</div><p class="info-note">${pending.length} pendentes. Você pode fechar e retomar pela visão geral.</p>` : empty("Tudo revisado", "Você pode ajustar qualquer categoria em Transações."));
}
function salaryCards() {
  const rows = getSummary().rows;
  return `<div class="salary-cards">${(state.data.salary_plan || []).map(p => {
    const received = sum(rows.filter(t => t.kind === "income" && t.salary_person === p.person).map(t => t.amount));
    return `<article class="salary-card"><div class="salary-avatar" aria-hidden="true">${esc(p.name[0])}</div><div><span>Salário · ${esc(p.name)}</span><strong>${received ? amount(received) : 'Não identificado'}</strong><small>Previsto ${amount(p.net)}</small></div><a class="text-button" href="#budget" aria-label="Histórico de salários de ${esc(p.name)}">↗</a></article>`;
  }).join("")}</div>`;
}
function overview() {
  const d = wealth(), s = getSummary(), b = getBudget();
  const savingRate = s.income ? Math.round((s.balance / s.income) * 100) : null;
  const recent = s.rows.filter(t => t.kind !== "other").slice(0, 5);
  const activeFilters = [state.search, ...[state.kind, state.institution, state.group, state.source].filter(v => v !== "all")].filter(Boolean).length;
  const basis = {cycle: "Ciclo do salário", cash: "Caixa", competence: "Competência"}[state.basis];
  return `<div class="financial-dashboard">` + pageHead("Visão geral", "", `<button class="button primary" data-action="new-transaction">${icon("plus")} Novo lançamento</button>`) +
    `<details class="dashboard-filters" ${state.filtersOpen ? "open" : ""}><summary>Filtros${activeFilters ? ` · ${activeFilters} ativos` : ""}<span>${esc(basis)} · ${esc(monthName(state.month))}</span></summary>${filterControls()}${declaredControl()}</details>
    ${guideStrip()}<div class="kpis">${kpi("Receitas", s.income, basis, "down", false, "positive")}${kpi("Despesas", s.spending, basis, "arrow")}${kpi("Resultado", s.balance, savingRate === null ? "Sem receita identificada" : `${savingRate}% das receitas`, "leaf", true)}${kpi("Patrimônio líquido", d.resumo.liquido, `Posição de ${dateName(d.gerado_em)} · ${state.includeDeclared ? "com" : "sem"} declarados`, "overview")}</div>
    ${salaryCards()}
    <div class="grid-main"><section class="panel"><div class="panel-head"><h2>Receitas e despesas</h2><div class="legend"><span><i></i>Receitas</span><span><i class="out"></i>Despesas</span></div></div>${cashChart()}<div class="chart-foot"><span>Últimos 6 meses · ${esc(basis)}</span><a class="text-button" href="#transactions">Ver extrato ↗</a></div></section>
    <section class="panel"><div class="panel-head"><h2>Despesas por categoria</h2><span class="pill">${monthName(state.month, true)}</span></div>${categoryChart(s)}</section>
    <section class="panel transactions-panel"><div class="panel-head"><h2>Últimas transações</h2><a class="text-button" href="#transactions">Ver todas →</a></div>${rowTable(recent)}</section>
    <section class="panel overview-budget"><div class="panel-head"><div><h2>Orçamento</h2><p>Ciclo completo · inclui VA/VR · sem filtros</p></div><a class="text-button" href="#budget">Detalhes ↗</a></div><div class="budget-balance"><span>${b.remaining < 0 ? "Acima do limite" : "Disponível"}</span><strong class="${b.remaining < 0 ? "negative" : "positive"}">${amount(Math.abs(b.remaining))}</strong></div><div class="budget-items">${b.lines.filter(l => l.grupos.length).sort((a,b) => (b.teto ? b.spent/b.teto : 1)-(a.teto ? a.spent/a.teto : 1)).slice(0,3).map(budgetItem).join("")}</div></section></div></div>`;
}
function filterControls() {
  return `<div class="filters"><label class="search-input">${icon("search")}<input type="search" id="search" placeholder="Buscar descrição, categoria…" aria-label="Buscar transações" value="${esc(state.search)}"></label><select id="kind" aria-label="Tipo de transação">${options(
   [
     ["all", "Todos os tipos"],
     ["expense", "Despesas"],
     ["income", "Receitas"],
     ["refund", "Estornos"],
     ["other", "Outras movimentações"],
   ],
   state.kind,
 )}</select><select id="institution" aria-label="Instituição">${options([["all", "Todas as instituições"], ...[...new Set(state.transactions.map((t) => t.instituicao))].sort().map((i) => [i, i])], state.institution)}</select><select id="group" aria-label="Categoria">${options([["all", "Todas as categorias"], ...[...new Set(viewTransactions().map((t) => t.group))].sort().map((i) => [i, i])], state.group)}</select><select id="source-filter" aria-label="Origem dos lançamentos">${options([["all", "Banco e manuais"], ["bank", "Somente banco"], ["manual", "Somente manuais"]], state.source)}</select><button class="text-button" data-action="clear-filters">Limpar filtros</button></div>`;
}
function filteredTransactions() {
  return getSummary().rows;
}
function transactionResults() {
  const rows = filteredTransactions(),
    pagesCount = Math.max(1, Math.ceil(rows.length / 20));
  state.pagination = Math.min(state.pagination, pagesCount);
  const start = (state.pagination - 1) * 20;
  return (
    rowTable(rows.slice(start, start + 20), true) +
    `<div class="pagination"><span>${rows.length ? `${start + 1}–${Math.min(start + 20, rows.length)} de ${rows.length}` : "0"} lançamentos</span><div><button class="button small" data-action="previous" ${state.pagination === 1 ? "disabled" : ""}>←</button><span>${state.pagination} / ${pagesCount}</span><button class="button small" data-action="next" ${state.pagination === pagesCount ? "disabled" : ""}>→</button></div></div>`
  );
}
function transactions() {
  const s = getSummary();
  return (
    pageHead(
      "Cada movimento, no seu lugar.",
      "Compare caixa, competência e ciclo do salário com os mesmos filtros.",
      `<button class="button primary" data-action="new-transaction">${icon("plus")} Novo lançamento</button>`,
    ) +
    `<p class="info-note">${basisNote()}</p><div class="metric-strip"><div class="panel"><span>${state.basis === "cash" ? "Entradas de caixa" : "Receitas"}</span><strong class="positive">${amount(s.income)}</strong></div><div class="panel"><span>${state.basis === "cash" ? "Saídas de caixa" : "Despesas líquidas"}</span><strong>${amount(s.spending)}</strong></div><div class="panel"><span>Resultado</span><strong class="${s.balance < 0 ? "negative" : "positive"}">${amount(s.balance)}</strong></div></div>
 <section class="panel"><div class="panel-head"><div><h2>Seu extrato</h2><p>Todos os movimentos, inclusive os que não compõem o resultado.</p></div><button class="text-button" data-action="export">Exportar CSV ↓</button></div>${filterControls()}<div id="transaction-results">${transactionResults()}</div></section>`
  );
}
function budget() {
  const b = getBudget(),
    config = state.data.budget;
  return (
    pageHead(
      "Um plano para o seu mês.",
      "Defina seus limites e acompanhe o que já foi utilizado.",
      `<button class="button primary" data-action="edit-budget">${icon("settings")} Editar planejamento</button>`,
    ) +
    `<div class="metric-strip"><div class="panel"><span>Limite total de consumo</span><strong>${amount(b.limit)}</strong></div><div class="panel"><span>Consumo + VA/VR estimado</span><strong>${amount(b.spent)}</strong></div><div class="panel"><span>${b.remaining < 0 ? "Acima do planejado" : "Disponível no orçamento"}</span><strong class="${b.remaining < 0 ? "negative" : "positive"}">${amount(Math.abs(b.remaining))}</strong></div></div>
 <div class="insight">${icon("goals")}<div><b>Guardar ${amount(config.monthly_saving)} por mês.</b><p>Renda mensal planejada de ${amount(config.monthly_income)}. VA/VR estimado de ${amount(config.benefits_spending)} incluído em alimentação; não é gasto bancário confirmado.</p></div></div>
 ${salariesPanel()}${cycleDetails()}
 ${b.unallocated ? `<div class="warning-banner" style="margin-top:18px">Há ${amount(b.unallocated)} em categorias sem limite associado. Esse valor já está incluído no consumo total.</div>` : ""}
 <h2 class="section-title">Seus limites por categoria <span class="pill">${b.lines.length} limites</span></h2><div class="budget-grid">${b.lines.map((l) => `<article class="panel budget-card"><div class="panel-head"><h3>${esc(l.nome)}</h3><span class="pill ${l.spent > l.teto ? "red" : ""}">${l.spent > l.teto ? "Acima do limite" : Math.round(percent(l.spent, l.teto)) + "%"}</span></div><div class="budget-amount">${amount(l.spent)} <small>de ${amount(l.teto)}</small></div>${progress(l.spent, l.teto, l.spent > l.teto ? "over" : "")}<div class="budget-sub"><span>${l.spent > l.teto ? "Excedido" : "Disponível"}</span><span>${amount(Math.abs(l.teto - l.spent))}</span></div></article>`).join("")}</div><p class="info-note">O planejamento é recorrente e vale para todos os meses. A edição altera os limites do app; os relatórios detalhados mantêm suas premissas originais.</p>`
  );
}
function accounts() {
  const d = wealth();
  return (
    pageHead(
      "Seu patrimônio, reunido.",
      "Contas, investimentos e cartões em uma única visão.",
      `<a class="button" href="/app/dashboard.html" target="_blank" rel="noopener">Relatório detalhado ↗</a>`,
      false,
    ) +
    `${declaredControl()}<div class="kpis">${kpi("Patrimônio líquido", d.resumo.liquido, "Ativos menos dívida de cartão", "overview", true)}${kpi("Saldo em contas", d.resumo.caixa, "Última posição disponível", "accounts")}${kpi("Investimentos", d.resumo.investimentos, "Inclui posições declaradas", "leaf")}${kpi("Dívida dos cartões", d.resumo.divida, "Posição informada pelo banco", "budget")}</div>
 <h2 class="section-title">Suas instituições <span class="pill">Posição de ${dateName(d.gerado_em)}</span></h2><div class="account-grid">${d.instituicoes.map((i) => `<article class="panel"><div class="panel-head"><h2>${esc(i.nome)}</h2>${icon("accounts")}</div><div class="kpi-value">${amount(i.liquido)}</div><small class="muted">Patrimônio líquido</small><div class="account-details"><div><small>Conta</small><b>${amount(i.caixa)}</b></div><div><small>Investimentos</small><b>${amount(i.investimentos)}</b></div><div><small>Cartões</small><b>${amount(i.divida)}</b></div></div><p class="info-note">Status do conector: ${esc(i.status)}</p></article>`).join("")}</div>
 <h2 class="section-title">Cartões de crédito</h2><div class="account-grid">${d.cartoes.map((c) => `<article class="account-card"><div class="account-head"><span>${esc(c.instituicao)} · ${esc(c.nome)}</span>${icon("accounts")}</div><h3>${amount(c.saldo)}</h3><div class="account-bottom"><div><small>Limite disponível</small><div>${c.disponivel == null ? "Não informado" : amount(c.disponivel)}</div></div><div><small>Vencimento informado</small><div>${dateName(c.vencimento)}</div></div></div></article>`).join("") || empty("Nenhum cartão conectado", "Os cartões serão exibidos quando estiverem no consolidado.")}</div>
 <button class="button" data-action="new-position">Adicionar saldo declarado</button><h2 class="section-title">Investimentos <span class="pill">${d.investimentos.length} posições</span></h2><section class="panel"><div class="table-wrap"><table><thead><tr><th>Investimento</th><th>Instituição</th><th>Origem</th><th class="right">Saldo</th></tr></thead><tbody>${d.investimentos.map((v) => `<tr><td>${esc(v.nome)}<br><small class="muted">${esc(v.subtipo || v.tipo)}</small></td><td>${esc(v.instituicao)}</td><td><span class="pill ${v.manual ? "warn" : ""}">${v.manual ? "Declarado" : "Open Finance"}</span>${v.manual ? `<br><small class="muted">${dateName(v.referencia)}</small><br><button class="text-button" data-action="edit-position" data-id="${esc(v.id)}">Editar saldo</button>` : ""}</td><td class="right">${amount(v.saldo)}</td></tr>`).join("")}</tbody></table></div></section><p class="info-note">Posições declaradas não são conciliadas automaticamente. A dívida é o saldo do cartão no consolidado; consulte o relatório detalhado para a composição por ciclo de fatura.</p>`
  );
}
function goals() {
  const goals = state.data.goals;
  return (
    pageHead(
      "Planos que saem do papel.",
      "Dê um destino ao dinheiro que você está guardando.",
      `<button class="button primary" data-action="new-goal">${icon("plus")} Criar meta</button>`,
      false,
    ) +
    `<div class="metric-strip"><div class="panel"><span>Reservado para metas</span><strong>${amount(sum(goals.map((g) => g.saved)))}</strong></div><div class="panel"><span>Objetivo total</span><strong>${amount(sum(goals.map((g) => g.target)))}</strong></div><div class="panel"><span>Metas concluídas</span><strong>${goals.filter((g) => g.saved >= g.target).length} <small class="muted">/ ${goals.length}</small></strong></div></div>
 ${!goals.length ? `<div class="insight">${icon("leaf")}<div><b>Todo plano começa com um primeiro passo.</b><p>Crie sua reserva, planeje uma viagem ou organize uma conquista. Você escolhe o destino.</p></div></div><br>` : ""}<div class="goal-grid">${goals.map((g) => `<article class="panel goal-card"><div class="goal-symbol">${icon("goals")}</div><h3>${esc(g.name)}</h3><p>${g.deadline ? "Até " + dateName(g.deadline) : "No seu próprio ritmo"}</p><div class="goal-value">${amount(g.saved)}</div><div class="goal-total">de ${amount(g.target)} · ${Math.round(percent(g.saved, g.target))}% concluído</div>${progress(g.saved, g.target)}<div class="budget-sub"><span>${g.saved >= g.target ? "Você chegou lá!" : "Falta " + amount(g.target - g.saved)}</span></div><button class="button" data-action="edit-goal" data-id="${esc(g.id)}">Atualizar progresso →</button></article>`).join("")}<button class="new-goal" data-action="new-goal">${icon("plus")}<b>Uma nova conquista</b><span>Adicionar uma meta pessoal</span></button></div><p class="info-note">Os valores das metas são informados por você. Eles não movimentam contas e não são somados novamente ao patrimônio.</p>`
  );
}
function settings() {
  const d = state.data;
  return (
    pageHead(
      "Do seu jeito.",
      "Transparência sobre os dados e controle sobre seu planejamento.",
      "",
      false,
    ) +
    `<div class="settings-grid"><section class="panel"><h2>Seus dados financeiros</h2><p>${esc(syncLabel())}</p><div class="settings-row"><span>Banco de dados</span><b>${state.data.storage === "postgresql" ? "PostgreSQL" : "SQLite local"}</b></div><p>As conexões bancárias são consultadas de hora em hora. A chegada de novos movimentos depende da disponibilidade de cada banco. Se a coleta falhar, os últimos dados válidos são preservados.</p><div class="settings-row"><span>Última coleta</span><b>${dateName(d.finance.gerado_em)}</b></div><div class="settings-row"><span>Janela do extrato</span><span>${dateName(d.finance.janela[0])} – ${dateName(d.finance.janela[1])}</span></div><div class="settings-row"><span>Instituições</span><span>${d.finance.instituicoes.length}</span></div><div class="settings-row"><span>Transações importadas</span><span>${d.finance.lancamentos.length}</span></div><p class="info-note">Fonte: ${esc(d.source)}</p><button class="button" data-action="refresh">↻ Sincronizar bancos</button></section>
 <section class="panel"><h2>Uma cópia do seu planejamento</h2><p>Exporte limites, metas e lançamentos manuais em JSON. Para uma cópia completa do app, preserve também a pasta data e suas configurações financeiras.</p><button class="button primary" data-action="backup">Exportar planejamento ↓</button><p class="info-note">A exportação contém informações pessoais. Guarde o arquivo em um local de sua escolha.</p><h2 style="margin-top:30px">Privacidade na tela</h2><p>Use o ícone de olho na barra superior para ocultar valores enquanto compartilha a tela.</p><button class="button" data-action="privacy">${icon("eye")} ${privateMode ? "Mostrar" : "Ocultar"} valores</button>${state.session?.required ? '<button class="button" data-action="change-password" style="margin-top:12px">Trocar senha</button> <button class="button" data-action="logout" style="margin-top:12px">Sair da conta</button>' : ""}</section>
 <section class="panel"><h2>Como os números são calculados</h2><p>Receitas e despesas seguem a competência do planejamento. A data bancária original é preservada; salários de fim de mês podem financiar o mês seguinte. Compras no cartão entram uma vez; o pagamento da fatura fica fora do resultado. Estornos reduzem despesas. Transferências próprias, aplicações e eventos patrimoniais identificados também ficam fora.</p><p>O orçamento inclui o consumo estimado de VA/VR informado no planejamento. Lançamentos manuais afetam os totais mensais, mas não atualizam o saldo recebido dos bancos.</p></section><section class="panel"><h2>Relatório para conferência</h2><p>A análise detalhada original continua disponível, com fluxo mensal, parcelas, projeções e reconciliação de caixa. Ela mantém as premissas do gerador original e não incorpora o planejamento salvo neste app.</p><a class="button" href="/app/dashboard.html" target="_blank" rel="noopener">Abrir análise detalhada ↗</a></section></div>`
  );
}
function kaleuPage() {
  return pageHead("Converse com o Kaleu.", "O mesmo planejamento no navegador e no Telegram.", "", false) +
    `<section class="panel kaleu-panel"><p id="kaleu-status" class="info-note">Conectando ao Kaleu…</p><div id="kaleu-messages" class="kaleu-messages" aria-live="polite"></div><form id="kaleu-form"><label for="kaleu-message">Sua mensagem</label><textarea id="kaleu-message" name="message" required maxlength="6000" rows="3" placeholder="Ex.: registre R$ 80 de mercado hoje, ou explique meu ciclo deste mês."></textarea><button class="button primary" type="submit">Enviar para o Kaleu</button><p class="info-note">Ele pode consultar e alterar o planejamento conforme seus pedidos. Não realiza pagamentos bancários. As alterações ficam registradas abaixo.</p></form></section><section class="panel" style="margin-top:20px"><h2>Histórico de alterações</h2><div id="kaleu-audit"></div></section>`;
}
async function loadKaleu() {
  if (state.page !== "kaleu" || !state.data) return;
  try {
    const [result, audit] = await Promise.all([api("kaleu/messages"), api("audit")]);
    const completed = result.messages.some(m => ["done", "failed"].includes(m.status) && state.kaleuMessages.some(old => old.id === m.id && ["queued", "running"].includes(old.status)));
    state.kaleuMessages = result.messages;
    const container = document.querySelector("#kaleu-messages");
    if (!container) return;
    document.querySelector("#kaleu-status").textContent = result.available ? "Kaleu conectado" : "Kaleu sem conexão no momento. Seu pedido ficará na fila.";
    container.innerHTML = result.messages.map(m => `<article class="chat-pair"><div class="chat-user"><b>Você</b><p>${esc(m.message)}</p></div><div class="chat-agent"><b>Kaleu</b><p>${esc(m.reply || (m.status === "running" ? "Analisando seu pedido…" : "Aguardando atendimento…"))}</p></div></article>`).join("") || '<p class="info-note">Pergunte sobre o mês, confira saldos ou peça um ajuste no planejamento.</p>';
    document.querySelector("#kaleu-audit").innerHTML = audit.entries.slice(0,20).map(e => `<details class="audit-entry"><summary>${esc(new Date(e.at * 1000).toLocaleString("pt-BR"))} · ${esc(e.actor)} · ${esc(({position:"Saldo declarado",transaction:"Lançamento",override:"Classificação",goal:"Meta",budget:"Orçamento"})[e.kind] || e.kind)}</summary><pre>${esc(JSON.stringify({antes: e.before, depois: e.after},null,2))}</pre></details>`).join("") || '<p class="info-note">Nenhuma alteração registrada ainda.</p>';
    if (completed) {
      const fresh = await api("data");
      state.data = fresh;
    }
  } catch (error) {
    const status = document.querySelector("#kaleu-status");
    if (status) status.textContent = error.message;
  }
}

const renderers = { cashflow, overview, transactions, budget, accounts, goals, settings, kaleu: kaleuPage };
function render() {
  state.page =
    location.hash.slice(1) in pages ? location.hash.slice(1) : "overview";
  document.title = `${pages[state.page]} · Personal Budget`;
  document.querySelector("#crumb").textContent = pages[state.page];
  document.querySelector("#navigation").innerHTML = Object.entries(pages)
    .map(
      ([key, label]) =>
        `<a href="#${key}" class="nav-link ${key === state.page ? "active" : ""}" ${key === state.page ? 'aria-current="page"' : ""} title="${label}">${icon(key)}<span>${innerWidth <= 680 ? mobileNames[key] : label}</span></a>`,
    )
    .join("");
  if (!state.data) return;
  document.body.classList.remove("auth-mode");
  content.innerHTML = renderers[state.page]();
  const age = Math.floor(
    (Date.now() - new Date(state.data.finance.gerado_em).getTime()) / 86400000,
  );
  if (age > 2)
    content.insertAdjacentHTML(
      "afterbegin",
      `<div class="warning-banner">O último consolidado é de ${dateName(state.data.finance.gerado_em)} (${age} dias). Os valores refletem essa coleta.</div>`,
    );
  document.querySelector("#source").textContent =
    `Dados de ${dateName(state.data.finance.gerado_em)}`;
  bindFilters();
  if (state.page === "kaleu") {
    document.querySelector("#kaleu-form").onsubmit = async event => {
      event.preventDefault();
      const form = event.target, button = form.querySelector("button");
      button.disabled = true;
      try {
        await api("kaleu/messages", "POST", {message: new FormData(form).get("message")});
        form.reset();
        await loadKaleu();
      } catch (error) { toast(error.message); }
      finally { button.disabled = false; }
    };
    loadKaleu();
  }
}
function bindFilters() {
  document.querySelector("#include-declared")?.addEventListener("change", event => {
    state.includeDeclared = event.target.checked;
    render();
  });
  document.querySelector("#basis")?.addEventListener("change", (event) => {
    state.basis = event.target.value;
    state.group = "all";
    state.pagination = 1;
    render();
  });
  document.querySelector("#source-filter")?.addEventListener("change", (event) => {
    state.source = event.target.value;
    state.pagination = 1;
    render();
  });
  document.querySelector("#month")?.addEventListener("change", (event) => {
    state.month = event.target.value;
    state.pagination = 1;
    render();
  });
  document.querySelector("#search")?.addEventListener("input", (event) => {
    state.search = event.target.value;
    state.pagination = 1;
    const input = event.target;
    const position = input.selectionStart;
    render();
    const replacement = document.querySelector("#search");
    replacement?.focus();
    replacement?.setSelectionRange(position, position);
  });
  for (const field of ["kind", "institution", "group"])
    document.querySelector("#" + field)?.addEventListener("change", (event) => {
      state[field] = event.target.value;
      state.pagination = 1;
      render();
    });
}
async function load() {
  if (location.hash.startsWith("#reset=")) {
    renderReset(decodeURIComponent(location.hash.slice(7)));
    return;
  }
  const session = await api("session");
  state.session = session;
  if (!session.authenticated) {
    renderLogin(session.configured);
    return;
  }
  if (session.must_change_password) {
    renderPasswordChange(true);
    return;
  }
  document.querySelector("#refresh").hidden = false;
  const data = await api("data");
  const { classifyPayload } = await import("./classifier.js");
  state.data = data;
  state.transactions = [
    ...classifyPayload(data.finance),
    ...data.manual.map((t) => ({
      ...t,
      manual: true,
      instituicao: "Manual",
      conta: "Registro manual",
      conta_tipo: "MANUAL",
      category: t.group,
    })),
  ]
    .map((t) => {
      const override = data.overrides?.find((o) => o.id === t.id);
      if (override) {
        t = {
          ...t,
          ...Object.fromEntries(
            Object.entries(override).filter(([key, value]) => value !== null || ["salary_person", "cashflow_line"].includes(key)),
          ),
        };
        t.adjusted = true;
      }
      return t;
    })
    .sort((a, b) => b.date.localeCompare(a.date));
  if (!state.month) state.month = data.finance.gerado_em.slice(0, 7);
  render();
  if (!state.reviewPrompted && state.page === "overview" && !modal.open && pendingReviews().length) {
    state.reviewPrompted = true;
    reviewModal();
  }
}
function authScreen(title, description, fields, button, extra = "") {
  document.body.classList.add("auth-mode");
  document.title = "Entrar · Personal Budget";
  state.data = null;
  state.transactions = [];
  document.querySelector("#navigation").innerHTML = "";
  document.querySelector("#source").textContent = "";
  document.querySelector("#refresh").hidden = true;
  content.innerHTML = `<div class="login-shell"><form class="login-card" id="access-form"><div class="brand login-brand"><span class="brand-icon">▥</span><span>personal<span class="brand-second">budget.</span></span></div><h1>${title}</h1><p>${description}</p>${fields}<button class="button primary" type="submit">${button}</button><p id="login-error" class="form-error" role="alert"></p>${extra}</form></div>`;
}
function accessForm(handler) {
  document.querySelector("#access-form").onsubmit = async (event) => {
    event.preventDefault();
    const button = event.target.querySelector("[type=submit]");
    button.disabled = true;
    try {
      await handler(new FormData(event.target));
    } catch (error) {
      const el = document.querySelector("#login-error");
      if (el) el.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
}
function renderLogin(configured = true) {
  authScreen(
    "Seu espaço, protegido.",
    configured
      ? "Entre para acompanhar as finanças de vocês."
      : "O acesso privado está sendo configurado.",
    '<label>Usuário<input name="username" autocomplete="username" required autofocus></label><label style="margin-top:15px">Senha<input type="password" name="password" autocomplete="current-password" required maxlength="256"></label>',
    "Entrar no meu espaço →",
    '<button class="text-button" type="button" data-action="forgot-password" style="margin-top:18px">Esqueci minha senha</button>',
  );
  if (!configured)
    document.querySelector("#access-form button[type=submit]").disabled = true;
  accessForm(async (f) => {
    await api("session", "POST", {
      username: f.get("username"),
      password: f.get("password"),
    });
    await load();
  });
}
function renderPasswordChange(mandatory = false) {
  authScreen(
    mandatory ? "Crie sua senha pessoal." : "Trocar minha senha",
    mandatory
      ? "Antes de abrir suas finanças, substitua a senha provisória."
      : "A mudança encerra as outras sessões desta conta.",
    '<label>Senha atual<input type="password" name="current_password" autocomplete="current-password" required></label><label style="margin-top:15px">Nova senha<input type="password" name="new_password" autocomplete="new-password" required minlength="12" maxlength="256" placeholder="Pelo menos 12 caracteres"></label><label style="margin-top:15px">Confirme a nova senha<input type="password" name="confirmation" autocomplete="new-password" required minlength="12" maxlength="256"></label>',
    "Salvar nova senha",
    mandatory
      ? '<button class="text-button" type="button" data-action="logout">Sair</button>'
      : '<button class="text-button" type="button" data-action="back-to-app">Voltar</button>',
  );
  accessForm(async (f) => {
    if (f.get("new_password") !== f.get("confirmation"))
      throw new Error("As novas senhas precisam ser iguais.");
    await api("password/change", "POST", {
      current_password: f.get("current_password"),
      new_password: f.get("new_password"),
    });
    await load();
    toast("Sua senha foi atualizada.");
  });
}
function renderForgot() {
  authScreen(
    "Vamos recuperar seu acesso.",
    "Informe seu usuário. O link será enviado ao e-mail cadastrado.",
    '<label>Usuário<input name="username" autocomplete="username" required autofocus></label>',
    "Enviar link de recuperação",
    '<button class="text-button" type="button" data-action="back-to-login">Voltar ao login</button>',
  );
  accessForm(async (f) => {
    const result = await api("password/forgot", "POST", {
      username: f.get("username"),
    });
    document.querySelector("#login-error").textContent = result.message;
  });
}
function renderReset(token) {
  authScreen(
    "Uma nova senha.",
    "Escolha uma senha pessoal com pelo menos 12 caracteres.",
    '<label>Nova senha<input type="password" name="new_password" autocomplete="new-password" required minlength="12" maxlength="256" autofocus></label><label style="margin-top:15px">Confirme a nova senha<input type="password" name="confirmation" autocomplete="new-password" required minlength="12" maxlength="256"></label>',
    "Redefinir senha",
    '<button class="text-button" type="button" data-action="forgot-password">Solicitar outro link</button>',
  );
  accessForm(async (f) => {
    if (f.get("new_password") !== f.get("confirmation"))
      throw new Error("As senhas precisam ser iguais.");
    await api("password/reset", "POST", {
      token,
      new_password: f.get("new_password"),
    });
    history.replaceState(null, "", location.pathname + "#overview");
    await load();
    toast("Senha redefinida.");
  });
}

function openModal(title, subtitle, body) {
  modal.innerHTML = `<div class="modal-header"><div><h2 id="modal-title">${title}</h2><p>${subtitle}</p></div><button class="icon-button" data-action="close" aria-label="Fechar">×</button></div>${body}`;
  modal.showModal();
}
function formFooter(label = "Salvar") {
  return `<p class="form-error" role="alert" id="form-error"></p><div class="form-actions"><button class="button" type="button" data-action="close">Cancelar</button><button class="button primary" type="submit">${label}</button></div>`;
}
function bindForm(handler) {
  modal.querySelector("form").onsubmit = async (event) => {
    event.preventDefault();
    const button = event.target.querySelector("[type=submit]");
    button.disabled = true;
    try {
      await handler(new FormData(event.target));
    } catch (error) {
      document.querySelector("#form-error").textContent = error.message;
      button.disabled = false;
      return;
    }
    modal.close();
    try {
      await load();
      toast("Salvo. Seu planejamento está atualizado.");
    } catch (error) {
      toast("Registro salvo, mas a tela não atualizou. Recarregue a página.");
    } finally {
      button.disabled = false;
    }
  };
}
function classificationForm(id) {
  const t = state.transactions.find((t) => t.id === id);
  if (modal.open) modal.close();
  openModal(
    "Categorizar lançamento",
    t.salary_candidate ? `Possível salário de ${t.salary_candidate === "aleph" ? "Aleph" : "Bianca"}. Confirme a origem antes de salvar.` : "A data e o valor bancários são preservados.",
    `<form><p class="info-note">${esc(t.description)} · ${dateName(t.date)} · ${amount(t.amount)}</p><div class="form-grid"><label class="full">Categoria<select name="group">${options([...new Set([...state.transactions.map(t => t.group), ...state.data.budget.lines.flatMap(l => l.grupos), "Salário", "Outros"])].sort().map(g => [g,g]),t.group)}</select></label><label>Tratamento<select name="kind">${options(
      [
        ["income", "Receita"],
        ["expense", "Despesa"],
        ["refund", "Estorno"],
        ["other", "Fora do resultado"],
      ],
      t.kind,
    )}</select></label><label class="full">Linha no fluxo de caixa<select name="cashflow_line">${options([["","Automática"],...currentCashflow().rows.map(l=>[l.id,l.name])],t.cashflow_line||"")}</select></label><label>Competência<input name="competence" type="month" value="${esc(competenceMonth(t, state.data.budget))}" required></label><label>Ciclo de pagamento<input name="cycle" type="month" value="${esc(cashflowCycle(t, state.transactions, state.data.budget))}"></label><label class="full">Origem da renda<select name="is_salary"><option value="false">Outra movimentação</option><option value="true" ${t.is_salary || t.metodo === "Salário" ? "selected" : ""}>Salário / portabilidade de salário</option></select></label><label>Titular do salário<select name="salary_person">${options([["", "Não informado"], ["aleph", "Aleph"], ["bianca", "Bianca"]], t.salary_person || "")}</select></label></div><p class="info-note">Se esta entrada for portabilidade de salário, marque como receita. Transferências entre suas próprias contas devem continuar fora do resultado.</p>${t.adjusted ? `<button type="button" class="text-button" data-action="reset-classification" data-id="${esc(id)}">Restaurar classificação original</button>` : ""}${formFooter("Salvar ajuste")}</form>`,
  );
  bindForm(async (f) =>
    api("transactions/" + id + "/classification", "PUT", {
      group: f.get("group"),
      reviewed: true,
      cashflow_line: f.get("cashflow_line") || null,
      kind: f.get("kind"),
      competence: f.get("competence"),
      cycle: f.get("cycle") || null,
      salary_person: f.get("salary_person") || null,
      is_salary: f.get("is_salary") === "true" || Boolean(f.get("salary_person")),
    }),
  );
}

function positionForm(id) {
  const v = (state.data.positions || []).find(v => v.id === id);
  openModal(v ? "Editar saldo declarado" : "Adicionar saldo declarado", "Posição patrimonial informada por você; não cria receita nem despesa.",
    `<form><div class="form-grid"><label>Nome<input name="name" required maxlength="120" value="${esc(v?.name || "")}"></label><label>Instituição<input name="institution" required maxlength="80" value="${esc(v?.institution || "")}"></label><label>Saldo (R$)<input name="balance" type="number" min="0" step="0.01" required value="${v?.balance ?? ""}"></label><label>Data de referência<input name="reference" type="date" required value="${v?.reference || new Date().toISOString().slice(0,10)}"></label><label>Classe<input name="asset_class" required maxlength="80" value="${esc(v?.asset_class || "Declarado")}"></label></div>${formFooter("Salvar saldo")}</form>`);
  bindForm(f => api("positions" + (id ? "/" + id : ""), id ? "PUT" : "POST", {
    name: f.get("name"), institution: f.get("institution"), balance: Number(f.get("balance")), reference: f.get("reference"), asset_class: f.get("asset_class")
  }));
}
function transactionForm() {
  const groups = [
    ...new Set(state.data.budget.lines.flatMap((l) => l.grupos)),
  ].sort();
  const today = new Date();
  const date = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  openModal(
    "Novo lançamento",
    "Para receitas e despesas que ainda não estão no extrato.",
    `<form><div class="form-grid"><label class="full">Descrição<input name="description" required maxlength="180" placeholder="Ex.: almoço, pagamento extra" autofocus></label><label>Tipo<select name="kind"><option value="expense">Despesa</option><option value="income">Receita</option></select></label><label>Valor (R$)<input name="amount" type="number" min="0.01" max="10000000000" step="0.01" required placeholder="0,00"></label><label>Data<input name="date" type="date" value="${date}" required></label><label>Categoria<select name="group">${options(
      groups.map((g) => [g, g]),
      "Outros",
    )}</select></label><label>Competência (opcional)<input name="competence" type="month"></label><label>Origem<select name="is_salary"><option value="false">Movimento comum</option><option value="true">Salário</option></select></label><label>Titular do salário<select name="salary_person"><option value="">Não informado</option><option value="aleph">Aleph</option><option value="bianca">Bianca</option></select></label><label class="full">Observação (opcional)<textarea name="note" maxlength="500" placeholder="Um detalhe para lembrar depois"></textarea></label></div><p class="info-note">Este registro entra no resultado mensal, sem alterar o saldo bancário. Se aparecer numa coleta futura, exclua o registro manual para evitar duplicidade.</p>${formFooter("Adicionar lançamento")}</form>`,
  );
  bindForm(async (f) => {
    await api("transactions", "POST", {
      description: f.get("description"),
      amount: Number(f.get("amount")),
      date: f.get("date"),
      kind: f.get("kind"),
      group: f.get("group"),
      note: f.get("note"),
      salary_person: f.get("salary_person") || null,
      competence: f.get("competence") || null,
      is_salary: f.get("is_salary") === "true" || Boolean(f.get("salary_person")),
    });
    state.month = (state.basis === "cycle" ? cycleMonth : state.basis === "competence" ? competenceMonth : t => t.date.slice(0,7))(
      {
        date: f.get("date"),
        kind: f.get("kind"),
        is_salary: f.get("is_salary") === "true" || Boolean(f.get("salary_person")),
        competence: f.get("competence") || null,
      },
      state.data.budget,
    );
  });
}
function goalForm(id) {
  const goal = state.data.goals.find((g) => g.id === id);
  openModal(
    goal ? "Seu objetivo, mais perto." : "Qual é o próximo plano?",
    "Acompanhe o valor reservado para uma conquista.",
    `<form><div class="form-grid"><label class="full">Nome da meta<input name="name" required maxlength="80" value="${esc(goal?.name || "")}" placeholder="Ex.: reserva de emergência" autofocus></label><label>Objetivo (R$)<input name="target" type="number" min="0.01" step="0.01" required value="${goal?.target || ""}"></label><label>Já guardado (R$)<input name="saved" type="number" min="0" step="0.01" required value="${goal?.saved || 0}"></label><label class="full">Prazo (opcional)<input name="deadline" type="date" value="${goal?.deadline || ""}"></label></div>${goal ? `<button class="text-button negative" type="button" data-action="delete-goal" data-id="${esc(id)}" style="margin-top:18px">Excluir esta meta</button>` : ""}${formFooter(goal ? "Atualizar meta" : "Criar meta")}</form>`,
  );
  bindForm(async (f) =>
    api(goal ? "goals/" + id : "goals", goal ? "PUT" : "POST", {
      name: f.get("name"),
      target: Number(f.get("target")),
      saved: Number(f.get("saved")),
      deadline: f.get("deadline") || null,
    }),
  );
}
function budgetForm() {
  const b = state.data.budget;
  openModal(
    "Um orçamento que faz sentido.",
    "Limites recorrentes para organizar o consumo de cada mês.",
    `<form><div class="form-grid"><label>Renda planejada (R$)<input name="monthly_income" type="number" min="0" step="0.01" required value="${b.monthly_income}"></label><label>Meta de poupança (R$)<input name="monthly_saving" type="number" min="0" step="0.01" required value="${b.monthly_saving}"></label><label class="full">Consumo estimado de VA/VR por mês (R$)<input name="benefits_spending" type="number" min="0" step="0.01" required value="${b.benefits_spending}"></label></div><label class="info-note" style="display:block">Salários no fim do mês<select name="salary_next_month" style="width:100%"><option value="true" ${b.salary_next_month !== false ? "selected" : ""}>Usar no orçamento do mês seguinte</option><option value="false" ${b.salary_next_month === false ? "selected" : ""}>Usar no próprio mês do recebimento</option></select></label><label class="info-note">A partir do dia<input name="salary_cutoff_day" type="number" min="1" max="31" value="${b.salary_cutoff_day ?? 25}" style="width:75px;margin-left:12px" required></label><div class="budget-form-list">${b.lines.map((l, i) => `<label>${esc(l.nome)}<input type="number" name="limit-${i}" min="0" step="0.01" value="${l.teto}" required aria-label="Limite de ${esc(l.nome)}"></label>`).join("")}</div>${formFooter("Salvar planejamento")}</form>`,
  );
  bindForm(async (f) =>
    api("budget", "PUT", {
      salary_next_month: f.get("salary_next_month") === "true",
      salary_cutoff_day: Number(f.get("salary_cutoff_day")),
      monthly_income: Number(f.get("monthly_income")),
      monthly_saving: Number(f.get("monthly_saving")),
      benefits_spending: Number(f.get("benefits_spending")),
      lines: b.lines.map((l, i) => ({
        ...l,
        teto: Number(f.get("limit-" + i)),
      })),
    }),
  );
}
function confirmDelete(kind, id) {
  const goal = kind === "goals";
  if (modal.open) modal.close();
  openModal(
    goal ? "Excluir esta meta?" : "Excluir o lançamento manual?",
    goal
      ? "Os valores nas contas não serão alterados."
      : "A transação será removida do resultado mensal.",
    `<form><p class="info-note">Esta ação remove apenas o registro selecionado do planejamento local.</p>${formFooter("Confirmar exclusão")}</form>`,
  );
  bindForm(async () => api(kind + "/" + id, "DELETE"));
}
async function refresh() {
  const button = document.querySelector("#refresh");
  if (button.disabled) return;
  button.disabled = true;
  button.innerHTML = "↻ Atualizando…";
  try {
    await api("refresh", "POST");
    await load();
    toast(
      "Sincronização solicitada. Os dados aparecerão assim que a coleta terminar.",
    );
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = "↻ <span>Atualizar dados</span>";
  }
}
document.querySelector("#refresh").onclick = refresh;
document.addEventListener("toggle", event => {
  if (event.target.matches?.(".dashboard-filters")) state.filtersOpen = event.target.open;
}, true);
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  if (action === "logout") {
    await api("session", "DELETE");
    renderLogin();
    return;
  }
  try {
    if (action === "edit-cashflow") cashflowForm();
    if (action === "review-pending") reviewModal();
    if (action === "kaleu-analysis") {
      button.disabled = true;
      try {
        await api("kaleu/messages", "POST", {message: `Analise meu orçamento no ciclo ${state.month}, os salários de Aleph e Bianca, categorias pendentes, limites excedidos e contas da primeira quinzena. Consulte os dados atuais e overrides. Salários podem chegar antes do último dia útil e financiar o próximo ciclo. Dê até cinco ações concretas, separando valores confirmados de previstos. Nesta análise, proponha correções sem alterar os registros.`});
        location.hash = "#kaleu";
      } finally { button.disabled = false; }
    }
    if (action === "clear-filters") {
      Object.assign(state, {search: "", kind: "all", institution: "all", group: "all", source: "all", pagination: 1});
      render();
    }
    if (action === "category-filter") {
      state.group = button.dataset.group;
      state.kind = "all";
      state.pagination = 1;
      location.hash = "transactions";
      render();
    }
    if (action === "forgot-password") {
      history.replaceState(null, "", location.pathname);
      renderForgot();
    }
    if (action === "back-to-login") {
      history.replaceState(null, "", location.pathname);
      renderLogin();
    }
    if (action === "change-password") renderPasswordChange();
    if (action === "back-to-app") await load();
    if (action === "new-position") positionForm();
    if (action === "edit-position") positionForm(button.dataset.id);
    if (action === "new-transaction") transactionForm();
    if (action === "classify-transaction")
      classificationForm(button.dataset.id);
    if (action === "new-goal") goalForm();
    if (action === "edit-goal") goalForm(button.dataset.id);
    if (action === "edit-budget") budgetForm();
    if (action === "close") modal.close();
    if (action === "reset-classification") {
      await api(
        "transactions/" + button.dataset.id + "/classification",
        "DELETE",
      );
      modal.close();
      await load();
      toast("Classificação original restaurada.");
    }
    if (action === "delete-goal") confirmDelete("goals", button.dataset.id);
    if (action === "delete-transaction")
      confirmDelete("transactions", button.dataset.id);
    if (action === "previous" || action === "next") {
      state.pagination += action === "next" ? 1 : -1;
      render();
    }
    if (action === "export") {
      const rows = filteredTransactions();
      const csv = [
        [
          "Data bancária",
          "Competência",
          "Descrição",
          "Categoria",
          "Instituição",
          "Tipo",
          "Valor BRL",
          "Origem",
        ],
        ...rows.map((t) => [
          t.date,
          t.competence,
          t.description,
          t.group,
          t.instituicao,
          t.kind,
          t.amount.toFixed(2).replace(".", ","),
          t.manual ? "Manual" : "Open Finance",
        ]),
      ]
        .map((row) => row.map(csvCell).join(";"))
        .join("\r\n");
      download("\uFEFF" + csv, `transacoes-${state.month}.csv`);
      toast(`${rows.length} lançamentos exportados com os filtros atuais.`);
    }
    if (action === "backup") {
      download(
        JSON.stringify(await api("backup"), null, 2),
        "personal-budget-planejamento.json",
        "application/json",
      );
      toast("Cópia do planejamento exportada.");
    }
    if (action === "refresh") await refresh();
    if (action === "privacy") {
      document.querySelector("#privacy").click();
      render();
    }
    if (action === "retry") {
      button.disabled = true;
      button.textContent = "Conectando…";
      try {
        await load();
      } finally {
        button.disabled = false;
        button.textContent = "Tentar novamente";
      }
    }
  } catch (error) {
    toast(error.message);
  }
});
window.addEventListener("hashchange", () => {
  if (location.hash.startsWith("#reset=")) {
    load();
    return;
  }
  if (state.data) load().catch(error => toast(error.message));
  else render();
  window.scrollTo({ top: 0 });
});
load().catch((error) => {
  content.innerHTML = `<div class="loading-state">${icon("leaf")}<h1>Não foi possível carregar os dados.</h1><p>${esc(error.message)}</p><button class="button primary" data-action="retry">Tentar novamente</button></div>`;
});

setInterval(() => {
  if (document.visibilityState === "visible" && state.page === "kaleu") loadKaleu();
}, 7000);
setInterval(() => {
  if (state.data && state.page !== "kaleu" && document.visibilityState === "visible" && !modal.open && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) load().catch(() => {});
}, 60000);
