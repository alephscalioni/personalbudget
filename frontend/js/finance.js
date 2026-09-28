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
      else if (t.natureza === "interna" || t.externa) group = "Transferências próprias";
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
