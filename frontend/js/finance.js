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
export function competenceMonth(transaction, budget = {}) {
  if (transaction.competence) return transaction.competence;
  const month = transaction.date.slice(0, 7);
  const salary =
    transaction.kind === "income" &&
    (transaction.is_salary ||
      transaction.metodo === "Salário" ||
      transaction.categoria === "Salary" ||
      transaction.categoria === "Salaries");
  if (!salary || budget.salary_next_month === false) return month;
  const cutoff = budget.salary_cutoff_day ?? 25;
  if (Number(transaction.date.slice(8, 10)) < cutoff) return month;
  const [year, m] = month.split("-").map(Number);
  return `${m === 12 ? year + 1 : year}-${String(m === 12 ? 1 : m + 1).padStart(2, "0")}`;
}
