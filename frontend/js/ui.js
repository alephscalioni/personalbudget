export const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export const icons = {
  overview:
    '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  transactions: '<path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"/>',
  budget:
    '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h3m-3 4h8"/>',
  accounts:
    '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 10h18m-5 5h2"/>',
  goals:
    '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  settings:
    '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  arrow: '<path d="M6 18 18 6M6 6h12v12"/>',
  down: '<path d="m6 6 12 12M6 18h12V6"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  leaf: '<path d="M5 18C0 6 15 3 21 3c0 11-4 20-16 15ZM5 18 16 8"/>',
};
export const icon = (name, cls = "") =>
  `<svg class="icon ${cls}" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.overview}</svg>`;
export const money = (n) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(
    n || 0,
  );
export const amount = (n) => `<span class="money">${money(n)}</span>`;
export const monthName = (m, short = false) =>
  new Date(m + "-02T12:00:00").toLocaleDateString("pt-BR", {
    month: short ? "short" : "long",
    ...(short ? {} : { year: "numeric" }),
  });
export const dateName = (d) =>
  d
    ? new Date(d.slice(0, 10) + "T12:00:00").toLocaleDateString("pt-BR")
    : "Não informado";
export const percent = (v, t) =>
  Math.max(0, Math.min(100, t ? (v / t) * 100 : v > 0 ? 100 : 0));
export const progress = (v, t, cls = "") =>
  `<div class="progress ${cls}" role="meter" aria-label="Progresso" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(percent(v, t))}"><span style="width:${percent(v, t)}%"></span></div>`;
export const empty = (title, detail, action = "") =>
  `<div class="empty">${icon("leaf")}<h3>${esc(title)}</h3><p>${esc(detail)}</p>${action}</div>`;
export async function api(path, method = "GET", body) {
  const response = await fetch("/api/" + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Confira os campos e tente novamente.",
    );
  }
  return response.status === 204 ? null : response.json();
}
export function download(content, filename, type = "text/csv;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
