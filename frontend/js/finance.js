export const round = (value) =>
  Math.round((value + Number.EPSILON) * 100) / 100;
export const sum = (values) =>
  values.reduce((total, value) => total + Math.round(value * 100), 0) / 100;
export const expense = (t) =>
  t.kind === "expense" ? t.amount : t.kind === "refund" ? -t.amount : 0;
export function monthSummary(transactions, month) {
  const rows = transactions.filter(
    (t) => (t.competence || t.date.slice(0, 7)) === month,
  );
  const income = sum(
    rows.filter((t) => t.kind === "income").map((t) => t.amount),
  );
  const spending = sum(rows.map(expense));
  const groups = {};
  rows.forEach((t) => {
    if (t.kind === "expense" || t.kind === "refund")
      groups[t.group] = round((groups[t.group] || 0) + expense(t));
  });
  return { rows, income, spending, balance: round(income - spending), groups };
}
export function budgetSummary(budget, summary) {
  const lines = budget.lines.map((line) => ({
    ...line,
    spent:
      sum(line.grupos.map((g) => summary.groups[g] || 0)) +
      (line.grupos.includes("Alimentação") ? budget.benefits_spending : 0),
  }));
  const limit = sum(lines.map((l) => l.teto));
  const spent = round(summary.spending + budget.benefits_spending);
  const covered = new Set(lines.flatMap((l) => l.grupos));
  const unallocated = sum(
    Object.entries(summary.groups)
      .filter(([g]) => !covered.has(g))
      .map(([, v]) => v),
  );
  return { lines, limit, spent, remaining: round(limit - spent), unallocated };
}
export function monthSequence(end, count) {
  const [y, m] = end.split("-").map(Number);
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(y, m - count + i, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
}
export function csvCell(value) {
  let text = String(value ?? "");
  if (/^[\s]*[=+@-]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}

// Posting date remains unchanged; only the planning month moves.
export function cycleMonth(transaction, budget = {}) {
  if (transaction.cycle) return transaction.cycle;
  if (transaction.competence) return transaction.competence;
  if (transaction.conta_tipo === "CREDIT" && transaction.fatura) return transaction.fatura.slice(0, 7);
  const month = transaction.date.slice(0, 7);
  const salary =
    transaction.kind === "income" &&
    (transaction.is_salary || transaction.salary_person ||
      transaction.metodo === "Salário" ||
      transaction.categoria === "Salary" ||
      transaction.categoria === "Salaries");
  if (!salary || budget.salary_next_month === false) return month;
  const cutoff = budget.salary_cutoff_day ?? 25;
  if (Number(transaction.date.slice(8, 10)) < cutoff) return month;
  const [year, m] = month.split("-").map(Number);
  return `${m === 12 ? year + 1 : year}-${String(m === 12 ? 1 : m + 1).padStart(2, "0")}`;
}

export function competenceMonth(transaction, budget = {}) {
  if (transaction.competence) return transaction.competence;
  const month = transaction.date.slice(0, 7);
  const salary = transaction.kind === "income" && (transaction.is_salary || transaction.salary_person || transaction.metodo === "Salário" || ["Salary", "Salaries"].includes(transaction.categoria));
  if (salary && Number(transaction.date.slice(8, 10)) === 1 && budget.salary_next_month !== false) {
    return monthSequence(month, 2)[0];
  }
  return month;
}

// Cash shows actual bank movements; card purchases affect cash when the bill is paid.
export function transactionsForBasis(transactions, basis = "cycle", budget = {}) {
  return transactions.filter(t => basis !== "cash" || t.conta_tipo !== "CREDIT").map((t) => {
    if (basis !== "cash") return { ...t, competence: basis === "cycle" ? cycleMonth(t, budget) : competenceMonth(t, budget) };
    let kind = t.kind, group = t.group;
    if (t.conta_tipo === "CREDIT") kind = "other";
    else if (!t.manual) {
      kind = t.valor < 0 ? "expense" : t.valor > 0 ? "income" : "other";
      if (t.natureza === "fatura") group = "Pagamento de fatura";
      else if (t.natureza === "investimento") group = "Aplicações e resgates";
      else if (t.natureza === "interna" || (t.externa && !t.is_salary)) group = "Transferências próprias";
    }
    return { ...t, kind, group, competence: t.date.slice(0, 7) };
  });
}


export function salaryBreakdown(transactions, month, budget = {}) {
  const received = {aleph: 0, bianca: 0};
  let unassigned = 0;
  const candidates = [];
  for (const t of transactions) {
    if (t.kind !== "income") continue;
    const salary = t.is_salary || t.salary_person || t.metodo === "Salário" || ["Salary", "Salaries"].includes(t.categoria);
    if (salary && cycleMonth(t, budget) === month) {
      if (t.salary_person in received) received[t.salary_person] = round(received[t.salary_person] + t.amount);
      else unassigned = round(unassigned + t.amount);
    }
    // Display transfers as candidates only; payer names alone do not prove salary.
    if (!salary && /bianca/i.test(t.description || "") && cycleMonth(t, budget) === month) candidates.push(t);
  }
  return {received, unassigned, candidates};
}

// Cash planning follows the salary funding window, not purchase competence.
export function salaryWindow(transactions, month, budget = {}) {
  const previous = monthSequence(month, 2)[0];
  const anchors = transactions.filter(t => t.kind === 'income' && t.salary_person === 'aleph' && cycleMonth(t,budget) === month && ((t.date.slice(0,7) === previous && Number(t.date.slice(8,10)) >= (budget.salary_cutoff_day ?? 25)) || (t.date.slice(0,7) === month && Number(t.date.slice(8,10)) <= 3)));
  if (anchors.length) return {start: anchors.map(t => t.date).sort()[0], estimated:false};
  const [year, m] = month.split('-').map(Number);
  const date = new Date(year, m-1, 0);
  while ([0,6].includes(date.getDay())) date.setDate(date.getDate()-1);
  return {start:`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`,estimated:true};
}
export function cashflowCycle(t, transactions, budget = {}) {
  if (t.cycle) return t.cycle;
  if (t.kind === 'income' && (t.is_salary || t.salary_person || t.metodo === 'Salário')) return cycleMonth(t,budget);
  const month=t.date.slice(0,7), [year,m]=month.split('-').map(Number);
  const next=`${m===12?year+1:year}-${String(m===12?1:m+1).padStart(2,'0')}`;
  return t.date >= salaryWindow(transactions,next,budget).start ? next : month;
}
export function defaultCashflowLines(transactions, budget) {
  const fixed=[
    {id:'cards',name:'Faturas dos cartões',due_day:7},
    {id:'condo',name:'Condomínio',due_day:10},
    {id:'electricity',name:'Luz',due_day:15},
    {id:'mba',name:'MBA',end_month:'2026-12'},
    {id:'housing',name:'Financiamento imobiliário'},
  ];
  const groups=[...new Set([...budget.lines.flatMap(l=>l.grupos),...transactions.filter(t=>t.kind==='expense'&&t.conta_tipo!=='CREDIT').map(t=>t.group)])].filter(Boolean).sort();
  return [...fixed,...groups.map(group=>({id:'group_'+Array.from(group).map(c=>c.codePointAt(0).toString(16)).join('_'),name:group,group}))].map(l=>({...l,budget:null,funding:'pool'}));
}
export function cashflowLineId(t, lines) {
  if(t.cashflow_line && lines.some(l=>l.id===t.cashflow_line))return t.cashflow_line;
  if(t.natureza==='fatura')return 'cards';
  const text=(t.description||t.desc||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  if(/harmonia morumbi|condominio/.test(text))return 'condo';
  if(/enel|eletric|energia/.test(text)||t.categoria==='Electricity')return 'electricity';
  if(/fundacao pesquisa e desen|\bmba\b/.test(text))return 'mba';
  if(/credito imobiliario|financiamento imobiliario/.test(text))return 'housing';
  return lines.find(l=>l.group===t.group || l.name===t.group)?.id || 'unallocated';
}
export function cashflowSummary(transactions, month, budget, savedPlan, salaryPlan=[]) {
  const defaults=defaultCashflowLines(transactions,budget);
  const plan=savedPlan || {opening_balance:0,lines:defaults};
  const definitions=[...plan.lines.map(l=>({...defaults.find(d=>d.id===l.id),...l})),...defaults.filter(d=>!plan.lines.some(l=>l.id===d.id))];
  const all=transactions.filter(t=>t.conta_tipo!=='CREDIT'&&cashflowCycle(t,transactions,budget)===month);
  const incomes=all.filter(t=>t.kind==='income' && (t.manual || t.valor>0));
  const payments=all.filter(t=> (t.manual?t.kind==='expense':t.valor<0&&(t.kind==='expense'||t.natureza==='fatura')));
  const rows=[...definitions,{id:'unallocated',name:'Sem linha definida',budget:null,funding:'pool'}].map(l=>{
    const tx=payments.filter(t=>cashflowLineId(t,definitions)===l.id);
    const paid=sum(tx.map(t=>t.amount));
    const planned=l.end_month && month>l.end_month ? 0 : l.budget;
    return {...l,budget:planned,paid,transactions:tx,remaining:planned==null?null:round(Math.max(0,planned-paid)),variance:planned==null?null:round(planned-paid)};
  }).filter(l=>l.id!=='unallocated'||l.paid);
  const salary={aleph:0,bianca:0};
  for(const person of Object.keys(salary))salary[person]=sum(incomes.filter(t=>t.salary_person===person).map(t=>t.amount));
  const income=sum(incomes.map(t=>t.amount)), paid=sum(rows.map(l=>l.paid)), remaining=sum(rows.map(l=>l.remaining||0));
  const [year,m]=month.split('-').map(Number),next=`${m===12?year+1:year}-${String(m===12?1:m+1).padStart(2,'0')}`;
  return {rows,salary,incomes,income,paid,remaining,opening:plan.opening_balance||0,balance:round((plan.opening_balance||0)+income-paid),projected:round((plan.opening_balance||0)+income-paid-remaining),planned:sum(rows.map(l=>l.budget||0)),unplanned:rows.filter(l=>l.budget==null).length,start:salaryWindow(transactions,month,budget),end:salaryWindow(transactions,next,budget),salaryPlan};
}

export function cashflowTransactions(transactions, budget={}) {
  const lines=defaultCashflowLines(transactions,budget);
  return transactions.filter(t=>t.conta_tipo!=='CREDIT').map(t=>{
    const kind=t.natureza==='fatura'&&t.valor<0?'expense':t.kind;
    const line=cashflowLineId(t,lines);
    const group=kind==='expense' ? lines.find(l=>l.id===line)?.name || t.group : t.group;
    return {...t,kind,group,competence:cashflowCycle(t,transactions,budget)};
  });
}
