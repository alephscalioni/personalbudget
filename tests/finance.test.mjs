import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import {
  monthSummary,
  competenceMonth,
  cycleMonth,
  transactionsForBasis,
  budgetSummary,
  csvCell,
  monthSequence,
  sum,
} from "../frontend/js/finance.js";

// Execute the exact shared classifier and adapter without duplicating the rules.
const python = readFileSync(
  new URL("../backend/service.py", import.meta.url),
  "utf8",
);
const adapter = python
  .split("return 'export function classifyPayload(D) {\\n' + source + '''")[1]
  .split("'''", 1)[0];
const source = readFileSync(
  new URL("../finance/pluggy/classificador.js", import.meta.url),
  "utf8",
);
const classifyPayload = vm.runInNewContext(
  "(function(D){" + source + adapter.slice(0, adapter.lastIndexOf("}")) + "})",
);
const base = {
  data: "2026-09-10",
  desc: "Lançamento teste",
  valor: 100,
  categoria: "Groceries",
  conta_tipo: "BANK",
  tipo: "DEBIT",
  natureza: "consumo",
};

test("payments, investments and own transfers are not counted twice", () => {
  const D = {
    lancamentos: [
      { ...base, conta_tipo: "CREDIT", fatura: "2026-10" },
      { ...base, natureza: "fatura", valor: -100 },
      { ...base, natureza: "interna", valor: -500 },
      { ...base, natureza: "interna", tipo: "CREDIT", valor: 500 },
      { ...base, natureza: "investimento", valor: -600 },
      { ...base, externa: true, valor: -400 },
      { ...base, desc: "Auto Art", valor: -20000 },
      { ...base, natureza: "entrada", tipo: "CREDIT", valor: 1000 },
    ],
  };
  const rows = classifyPayload(D);
  const totals = monthSummary(rows, "2026-09");
  assert.equal(totals.spending, 100);
  assert.equal(totals.income, 1000);
  assert.equal(totals.balance, 900);
  assert.equal(rows.filter((t) => t.kind === "other").length, 6);
});
test("refunds reduce spending and card payment is not income", () => {
  const rows = classifyPayload({
    lancamentos: [
      { ...base, conta_tipo: "CREDIT", fatura: "2026-10", valor: 150 },
      {
        ...base,
        conta_tipo: "CREDIT",
        fatura: "2026-10",
        tipo: "CREDIT",
        valor: 30,
      },
      {
        ...base,
        conta_tipo: "CREDIT",
        fatura: "2026-10",
        tipo: "CREDIT",
        categoria: "Credit card payment",
        valor: 150,
      },
    ],
  });
  const s = monthSummary(rows, "2026-09");
  assert.equal(s.spending, 120);
  assert.equal(s.income, 0);
  assert.equal(s.groups["Alimentação"], 120);
});
test("explicit groups override merchant and bank category", () => {
  const [t] = classifyPayload({
    lancamentos: [
      { ...base, grupo: "Moradia", categoria: "Condomínio", desc: "Railway" },
    ],
  });
  assert.equal(t.group, "Moradia");
  assert.equal(t.category, "Condomínio");
});
test("manual records and benefits have separate, predictable effects", () => {
  const rows = [
    { kind: "expense", amount: 10.1, date: "2026-09-01", group: "Alimentação" },
    { kind: "expense", amount: 0.2, date: "2026-09-02", group: "Outros" },
    { kind: "income", amount: 100, date: "2026-08-01", group: "Outros" },
  ];
  const s = monthSummary(rows, "2026-09");
  assert.equal(s.spending, 10.3);
  assert.equal(s.income, 0);
  const b = budgetSummary(
    {
      lines: [{ nome: "Comida", grupos: ["Alimentação"], teto: 200 }],
      benefits_spending: 50,
    },
    s,
  );
  assert.equal(b.spent, 60.3);
  assert.equal(b.lines[0].spent, 60.1);
  assert.equal(b.unallocated, 0.2);
  assert.equal(b.remaining, 139.7);
});
test("calendar rollover, cent arithmetic and safe CSV export", () => {
  assert.deepEqual(monthSequence("2026-02", 3), [
    "2025-12",
    "2026-01",
    "2026-02",
  ]);
  assert.equal(sum([0.1, 0.2, 0.3]), 0.6);
  assert.equal(csvCell('=HYPERLINK("x")'), '"\'=HYPERLINK(""x"")"');
  assert.equal(csvCell('Mercado; "Centro"'), '"Mercado; ""Centro"""');
});

test("salary cycle rolls over without modifying posting date", () => {
  const salary = {
    kind: "income",
    metodo: "Salário",
    date: "2026-08-31",
    amount: 1000,
  };
  assert.equal(cycleMonth(salary), "2026-09");
  assert.equal(salary.date, "2026-08-31");
  assert.equal(cycleMonth({ ...salary, date: "2026-12-31" }), "2027-01");
  assert.equal(cycleMonth({ ...salary, date: "2026-08-14" }), "2026-08");
  assert.equal(
    cycleMonth(salary, { salary_next_month: false }),
    "2026-08",
  );
  assert.equal(
    cycleMonth({ ...salary, kind: "other", externa: true }),
    "2026-08",
  );
  assert.equal(cycleMonth({ ...salary, metodo: "PIX" }), "2026-08");
  assert.equal(
    cycleMonth({ ...salary, competence: "2026-10" }),
    "2026-10",
  );
  const classified = { ...salary, competence: cycleMonth(salary) };
  assert.equal(monthSummary([classified], "2026-08").income, 0);
  assert.equal(monthSummary([classified], "2026-09").income, 1000);
});


test("cash, earned month and salary cycle remain distinct across year boundaries", () => {
  const december = {kind: "income", is_salary: true, date: "2026-12-31", amount: 1000, valor: 1000};
  const january = {...december, date: "2027-01-01"};
  assert.equal(competenceMonth(december), "2026-12");
  assert.equal(competenceMonth(january), "2026-12");
  assert.equal(cycleMonth(december), "2027-01");
  assert.equal(cycleMonth(january), "2027-01");
  const purchase = {kind: "expense", date: "2026-12-20", fatura: "2027-01-05", conta_tipo: "CREDIT", amount: 300, valor: 300, group: "Compras"};
  const payment = {kind: "other", date: "2027-01-05", natureza: "fatura", amount: 300, valor: -300};
  assert.equal(monthSummary(transactionsForBasis([purchase, payment], "cycle"), "2027-01").spending, 300);
  assert.equal(monthSummary(transactionsForBasis([purchase, payment], "cash"), "2027-01").spending, 300);
  assert.equal(monthSummary(transactionsForBasis([purchase, payment], "cash"), "2026-12").spending, 0);
  assert.equal(monthSummary(transactionsForBasis([purchase, payment], "competence"), "2026-12").spending, 300);
});
