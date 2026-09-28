#!/usr/bin/env python3
"""
Cliente Pluggy (Open Finance BR) — Kaleu / Aleph.

Fluxo:
  1. POST /auth com clientId+clientSecret  -> apiKey (cacheada em disco, TTL 100min)
  2. GET  /accounts?itemId=...             -> contas do vinculo
  3. GET  /v2/transactions?accountId=...   -> extrato (cursor-based)
  4. GET  /investments?itemId=...          -> posicao de investimentos

Credenciais (ordem de precedencia):
  1. env vars PLUGGY_CLIENT_ID / PLUGGY_CLIENT_SECRET
  2. scripts/finance/pluggy/.env  (KEY=VALUE por linha)
  3. --config CAMINHO

Uso:
  ./pluggy_client.py auth
  ./pluggy_client.py connectors [--busca nubank]
  ./pluggy_client.py connect-token
  ./pluggy_client.py connect-page                 # gera HTML pro widget de vinculo
  ./pluggy_client.py items
  ./pluggy_client.py accounts [--item-id UUID]
  ./pluggy_client.py transactions --account-id UUID [--dias 30]
  ./pluggy_client.py investments [--item-id UUID]
  ./pluggy_client.py summary                      # saldo consolidado de todos os itens

Flags globais: --json (saida crua), --config CAMINHO
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

BASE_URL = "https://api.pluggy.ai"
TIMEOUT = 45

SERVICE_DIR = Path(__file__).resolve().parent            # .../scripts/finance/pluggy
WORKSPACE = SERVICE_DIR.parents[2]                      # .../workspaces/kaleu
DEFAULT_CONFIG = SERVICE_DIR / ".env"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kaleu"
CACHE_FILE = CACHE_DIR / "pluggy-apikey.json"
APIKEY_TTL = 100 * 60          # Pluggy expira em 2h; renovo antes por seguranca


# --------------------------------------------------------------------------- config
def load_config(path: Optional[Path] = None) -> Dict[str, str]:
    """env vars vencem o arquivo; arquivo e KEY=VALUE, # comenta."""
    cfg: Dict[str, str] = {}
    path = path or DEFAULT_CONFIG
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    for key in ("PLUGGY_CLIENT_ID", "PLUGGY_CLIENT_SECRET", "PLUGGY_ITEM_IDS",
                "PLUGGY_CLIENT_USER_ID", "PLUGGY_WEBHOOK_URL"):
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    return cfg


class PluggyError(RuntimeError):
    pass


# --------------------------------------------------------------------------- client
class Pluggy:
    def __init__(self, client_id: str, client_secret: str, *, use_cache: bool = True):
        if not client_id or not client_secret:
            raise PluggyError(
                "PLUGGY_CLIENT_ID / PLUGGY_CLIENT_SECRET ausentes.\n"
                f"Preencha {DEFAULT_CONFIG} (modelo em .env.example) ou exporte as env vars."
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.use_cache = use_cache
        self._api_key: Optional[str] = None
        self.s = requests.Session()

    # ---- auth
    def _cached_key(self) -> Optional[str]:
        if not self.use_cache or not CACHE_FILE.exists():
            return None
        try:
            blob = json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if blob.get("client_id") != self.client_id:
            return None
        if time.time() - blob.get("obtained_at", 0) > APIKEY_TTL:
            return None
        return blob.get("apiKey")

    def _store_key(self, api_key: str) -> None:
        if not self.use_cache:
            return
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(
            {"apiKey": api_key, "obtained_at": time.time(), "client_id": self.client_id}
        ))
        CACHE_FILE.chmod(0o600)

    def authenticate(self, force: bool = False) -> str:
        if not force:
            cached = self._cached_key()
            if cached:
                self._api_key = cached
                return cached
        r = self.s.post(
            f"{BASE_URL}/auth",
            json={"clientId": self.client_id, "clientSecret": self.client_secret},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        if r.status_code == 400:
            raise PluggyError(
                "400 no /auth — payload rejeitado. O clientId tem que ser um UUID "
                f"(ex 550e8400-e29b-41d4-a716-446655440000). Resposta: {r.text[:300]}"
            )
        if r.status_code in (401, 403):
            raise PluggyError(
                f"{r.status_code} no /auth — clientId/clientSecret invalidos ou aplicacao "
                "desabilitada. Confira em https://dashboard.pluggy.ai (Applications)."
            )
        r.raise_for_status()
        key = r.json().get("apiKey")
        if not key:
            raise PluggyError(f"/auth respondeu sem apiKey: {r.text[:300]}")
        self._api_key = key
        self._store_key(key)
        return key

    @property
    def api_key(self) -> str:
        return self._api_key or self.authenticate()

    # ---- http
    def _request(self, method: str, path: str, *, params=None, json_body=None, _retry=True):
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        r = self.s.request(
            method, url,
            params=params, json=json_body,
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        # apiKey expirada -> reautentica uma vez
        if r.status_code in (401, 403) and _retry:
            self.authenticate(force=True)
            return self._request(method, path, params=params, json_body=json_body, _retry=False)
        if r.status_code >= 400:
            raise PluggyError(f"{method} {url} -> HTTP {r.status_code}: {r.text[:500]}")
        return r.json() if r.content else {}

    def get(self, path, **params):
        return self._request("GET", path, params={k: v for k, v in params.items() if v is not None})

    def post(self, path, body=None):
        return self._request("POST", path, json_body=body or {})

    # ---- paginacao
    def _paginate_page(self, path: str, **params) -> List[dict]:
        """Endpoints v1: {page,total,totalPages,results}."""
        out: List[dict] = []
        page = 1
        while True:
            data = self.get(path, page=page, pageSize=500, **params)
            out.extend(data.get("results", []))
            if page >= int(data.get("totalPages") or 1):
                break
            page += 1
        return out

    def _paginate_cursor(self, path: str, **params) -> List[dict]:
        """Endpoints v2: {results, next}. next vem como querystring pronta ou URL."""
        out: List[dict] = []
        data = self.get(path, **params)
        out.extend(data.get("results", []))
        nxt = data.get("next")
        while nxt:
            if nxt.startswith("http"):
                data = self._request("GET", nxt)
            elif nxt.startswith("?"):
                data = self._request("GET", f"{BASE_URL}{path}{nxt}")
            else:                                    # so o token do cursor
                data = self.get(path, after=nxt, **params)
            out.extend(data.get("results", []))
            new_next = data.get("next")
            if new_next == nxt:                      # trava anti-loop
                break
            nxt = new_next
        return out

    # ---- produtos
    def connect_token(self, item_id=None, client_user_id=None, webhook_url=None) -> str:
        body: Dict[str, Any] = {}
        if item_id:
            body["itemId"] = item_id
        opts = {}
        if client_user_id:
            opts["clientUserId"] = client_user_id
        if webhook_url:
            opts["webhookUrl"] = webhook_url
        if opts:
            body["options"] = opts
        return self.post("/connect_token", body)["accessToken"]

    def connectors(self, name=None, countries="BR") -> List[dict]:
        return self.get("/connectors", name=name, countries=countries).get("results", [])

    def items(self) -> List[dict]:
        """GET /v2/items exige opt-in no time da Pluggy; 403 => use PLUGGY_ITEM_IDS."""
        return self._paginate_cursor("/v2/items")

    def item(self, item_id: str) -> dict:
        return self.get(f"/items/{item_id}")

    def accounts(self, item_id: str, type_=None) -> List[dict]:
        return self._paginate_page("/accounts", itemId=item_id, type=type_)

    def transactions(self, account_id: str, date_from=None, date_to=None) -> List[dict]:
        return self._paginate_cursor(
            "/v2/transactions", accountId=account_id, dateFrom=date_from, dateTo=date_to
        )

    def investments(self, item_id: str, type_=None) -> List[dict]:
        return self._paginate_page("/investments", itemId=item_id, type=type_)

    def identity(self, item_id: str) -> dict:
        return self.get("/identity", itemId=item_id)


# --------------------------------------------------------------------------- helpers
def brl(v) -> str:
    if v is None:
        return "—"
    s = f"{float(v):,.2f}"
    return "R$ " + s.replace(",", "@").replace(".", ",").replace("@", ".")


def resolve_item_ids(pg: Pluggy, cfg: Dict[str, str], explicit: Optional[str]) -> List[str]:
    """--item-id > PLUGGY_ITEM_IDS (csv) > GET /v2/items."""
    if explicit:
        return [explicit]
    raw = cfg.get("PLUGGY_ITEM_IDS", "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    try:
        ids = [it["id"] for it in pg.items()]
    except PluggyError as e:
        raise PluggyError(
            "Nao consegui descobrir os itemIds automaticamente "
            f"(GET /v2/items exige opt-in no seu time: {e}).\n"
            "Passe --item-id UUID ou preencha PLUGGY_ITEM_IDS no config/pluggy.env."
        ) from e
    if not ids:
        raise PluggyError(
            "Nenhum item vinculado ainda. Rode `connect-page`, abra o HTML, "
            "conecte o banco e cole aqui o itemId que aparecer na tela."
        )
    return ids


CONNECT_HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pluggy Connect — vincular conta</title>
<style>
  :root{--bg:#0b0e14;--card:#141922;--line:#232b39;--text:#e6edf3;--muted:#8b98a9;
        --accent:#7c5cff;--accent2:#ff4d9d;--ok:#3fb950}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
       font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
       display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;
        padding:28px;max-width:560px;width:100%}
  h1{margin:0 0 6px;font-size:20px;
     background:linear-gradient(90deg,var(--accent),var(--accent2));
     -webkit-background-clip:text;background-clip:text;color:transparent}
  p{color:var(--muted);margin:0 0 18px;font-size:14px}
  button{background:linear-gradient(90deg,var(--accent),var(--accent2));border:0;color:#fff;
         font-weight:600;font-size:15px;padding:12px 22px;border-radius:10px;cursor:pointer;width:100%}
  #out{margin-top:20px;display:none}
  .ok{color:var(--ok);font-weight:600;margin-bottom:8px}
  code{display:block;background:#0b0e14;border:1px solid var(--line);border-radius:8px;
       padding:12px;font-size:13px;word-break:break-all;color:var(--text);margin-bottom:10px}
  .hint{font-size:13px;color:var(--muted)}
  .warn{margin-top:18px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:12px}
</style></head>
<body><div class="card">
  <h1>Vincular conta — Pluggy</h1>
  <p>Token gerado em __GENERATED__ · vale ~30 min. Conecte o banco e me mande o
     <b>itemId</b> que aparecer aqui embaixo.</p>
  <button id="go">Conectar banco</button>
  <div id="out"></div>
  <div class="warn">As credenciais do banco vao direto pra Pluggy — nao passam por este arquivo
     nem pelo servidor do Kaleu.</div>
</div>
<script src="https://cdn.pluggy.ai/pluggy-connect/v2.8.2/pluggy-connect.js"></script>
<script>
  var TOKEN = "__TOKEN__";
  var out = document.getElementById('out');
  function show(html){ out.style.display='block'; out.innerHTML = html; }
  document.getElementById('go').onclick = function(){
    var pc = new PluggyConnect({
      connectToken: TOKEN,
      includeSandbox: __SANDBOX__,
      onSuccess: function(itemData){
        var id = (itemData && itemData.item && itemData.item.id) ||
                 (itemData && itemData.id) || JSON.stringify(itemData);
        show('<div class="ok">Conectado!</div><code>' + id + '</code>' +
             '<div class="hint">Manda esse itemId pro Kaleu no Telegram.</div>');
      },
      onError: function(err){
        show('<div class="ok" style="color:#ff4d9d">Erro</div><code>' +
             JSON.stringify(err) + '</code>');
      }
    });
    pc.init();
  };
</script></body></html>
"""


# --------------------------------------------------------------------------- commands
def cmd_auth(pg, args, cfg):
    key = pg.authenticate(force=True)
    if args.json:
        print(json.dumps({"apiKey": key}))
    else:
        print(f"✓ autenticado — apiKey {key[:12]}…{key[-6:]} (cache: {CACHE_FILE})")


def cmd_connectors(pg, args, cfg):
    res = pg.connectors(name=args.busca)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False)); return
    for c in res:
        print(f"{c['id']:>5}  {c['name']:<34} {c.get('type',''):<18} {c.get('country','')}")
    print(f"\n{len(res)} conectores")


def cmd_connect_token(pg, args, cfg):
    tok = pg.connect_token(
        item_id=args.item_id,
        client_user_id=cfg.get("PLUGGY_CLIENT_USER_ID"),
        webhook_url=cfg.get("PLUGGY_WEBHOOK_URL"),
    )
    print(json.dumps({"accessToken": tok}) if args.json else tok)


def cmd_connect_page(pg, args, cfg):
    tok = pg.connect_token(
        item_id=args.item_id,
        client_user_id=cfg.get("PLUGGY_CLIENT_USER_ID"),
        webhook_url=cfg.get("PLUGGY_WEBHOOK_URL"),
    )
    html = (CONNECT_HTML
            .replace("__TOKEN__", tok)
            .replace("__SANDBOX__", "true" if args.sandbox else "false")
            .replace("__GENERATED__", time.strftime("%d/%m/%Y %H:%M")))
    dest = Path(args.out) if args.out else WORKSPACE / "reports" / f"pluggy-connect-{date.today()}.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    print(dest)


def cmd_items(pg, args, cfg):
    items = pg.items()
    if args.json:
        print(json.dumps(items, indent=2, ensure_ascii=False)); return
    for it in items:
        conn = (it.get("connector") or {}).get("name", "?")
        print(f"{it['id']}  {conn:<28} status={it.get('status')} "
              f"exec={it.get('executionStatus')} upd={it.get('lastUpdatedAt')}")
    print(f"\n{len(items)} itens")


def cmd_accounts(pg, args, cfg):
    ids = resolve_item_ids(pg, cfg, args.item_id)
    allacc = []
    for iid in ids:
        allacc.extend(pg.accounts(iid, type_=args.tipo))
    if args.json:
        print(json.dumps(allacc, indent=2, ensure_ascii=False)); return
    total = 0.0
    for a in allacc:
        bal = a.get("balance")
        total += float(bal or 0) * (-1 if a.get("type") == "CREDIT" else 1)
        print(f"{a['id']}  {a.get('type','?'):<7} {str(a.get('subtype') or ''):<16} "
              f"{(a.get('name') or '')[:30]:<30} {brl(bal):>16}")
    print(f"\n{len(allacc)} contas · liquido {brl(total)}")


def tx_amount(t) -> float:
    """Valor do lancamento SEMPRE na moeda da conta (BRL).

    Compras internacionais vem com currencyCode != BRL e `amount` na moeda
    estrangeira; o valor convertido fica em `amountInAccountCurrency`.
    Somar `amount` cru mistura USD com BRL e subestima o gasto em ~5x.
    """
    conv = t.get("amountInAccountCurrency")
    if t.get("currencyCode") not in (None, "BRL") and conv is not None:
        return float(conv)
    return float(t.get("amount") or 0)


def cmd_transactions(pg, args, cfg):
    d_to = args.ate or date.today().isoformat()
    d_from = args.de or (date.fromisoformat(d_to) - timedelta(days=args.dias)).isoformat()
    txs = pg.transactions(args.account_id, date_from=d_from, date_to=d_to)
    if args.json:
        print(json.dumps(txs, indent=2, ensure_ascii=False)); return
    entradas = sum(v for v in map(tx_amount, txs) if v > 0)
    saidas = sum(v for v in map(tx_amount, txs) if v < 0)
    for t in txs:
        moeda = t.get("currencyCode")
        tag = ""
        if moeda not in (None, "BRL"):
            tag = f" [{moeda} {float(t.get('amount') or 0):,.2f}]"
        print(f"{t['date'][:10]}  {brl(tx_amount(t)):>14}  "
              f"{str(t.get('category') or '-')[:18]:<18} {(t.get('description') or '')[:44]}{tag}")
    print(f"\n{len(txs)} lancamentos ({d_from} → {d_to}) · "
          f"entradas {brl(entradas)} · saidas {brl(saidas)} · liquido {brl(entradas + saidas)}")


def cmd_investments(pg, args, cfg):
    ids = resolve_item_ids(pg, cfg, args.item_id)
    inv = []
    for iid in ids:
        inv.extend(pg.investments(iid, type_=args.tipo))
    if args.json:
        print(json.dumps(inv, indent=2, ensure_ascii=False)); return
    total = 0.0
    for i in inv:
        total += float(i.get("balance") or 0)
        print(f"{str(i.get('type') or '?'):<14} {str(i.get('subtype') or '')[:18]:<18} "
              f"{(i.get('name') or '')[:34]:<34} {brl(i.get('balance')):>16} "
              f"a.a.={i.get('annualRate') or '—'}")
    print(f"\n{len(inv)} posicoes · total {brl(total)}")


def cmd_summary(pg, args, cfg):
    ids = resolve_item_ids(pg, cfg, args.item_id)
    payload = []
    for iid in ids:
        try:
            it = pg.item(iid)
            conn = (it.get("connector") or {}).get("name", "?")
            status = it.get("status")
        except PluggyError:
            conn, status = "?", "?"
        accs = pg.accounts(iid)
        try:
            invs = pg.investments(iid)
        except PluggyError:
            invs = []
        payload.append({"itemId": iid, "connector": conn, "status": status,
                        "accounts": accs, "investments": invs})
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False)); return
    grand = 0.0
    for p in payload:
        print(f"\n── {p['connector']}  ({p['itemId'][:8]}…, status={p['status']})")
        for a in p["accounts"]:
            sign = -1 if a.get("type") == "CREDIT" else 1
            grand += float(a.get("balance") or 0) * sign
            print(f"   {a.get('type','?'):<7} {(a.get('name') or '')[:32]:<32} {brl(a.get('balance')):>16}")
        inv_total = sum(float(i.get("balance") or 0) for i in p["investments"])
        if p["investments"]:
            grand += inv_total
            print(f"   INVEST  {len(p['investments'])} posicoes{'':<24} {brl(inv_total):>16}")
    print(f"\n═══ patrimonio liquido consolidado: {brl(grand)}")


COMMANDS = {
    "auth": cmd_auth, "connectors": cmd_connectors, "connect-token": cmd_connect_token,
    "connect-page": cmd_connect_page, "items": cmd_items, "accounts": cmd_accounts,
    "transactions": cmd_transactions, "investments": cmd_investments, "summary": cmd_summary,
}


def main(argv=None):
    p = argparse.ArgumentParser(description="Cliente Pluggy (Open Finance BR)")
    p.add_argument("--json", action="store_true", help="saida crua em JSON")
    p.add_argument("--config", help=f"arquivo .env alternativo (default {DEFAULT_CONFIG})")
    p.add_argument("--no-cache", action="store_true", help="nao usa a apiKey cacheada")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth")
    sp = sub.add_parser("connectors"); sp.add_argument("--busca")
    sp = sub.add_parser("connect-token"); sp.add_argument("--item-id")
    sp = sub.add_parser("connect-page")
    sp.add_argument("--item-id"); sp.add_argument("--out")
    sp.add_argument("--sandbox", action="store_true", help="inclui conectores sandbox")
    sub.add_parser("items")
    sp = sub.add_parser("accounts")
    sp.add_argument("--item-id"); sp.add_argument("--tipo", choices=["BANK", "CREDIT"])
    sp = sub.add_parser("transactions")
    sp.add_argument("--account-id", required=True)
    sp.add_argument("--dias", type=int, default=30)
    sp.add_argument("--de"); sp.add_argument("--ate")
    sp = sub.add_parser("investments")
    sp.add_argument("--item-id")
    sp.add_argument("--tipo", choices=["COE", "EQUITY", "ETF", "FIXED_INCOME",
                                       "MUTUAL_FUND", "SECURITY", "OTHER"])
    sp = sub.add_parser("summary"); sp.add_argument("--item-id")

    args = p.parse_args(argv)
    cfg = load_config(Path(args.config) if args.config else None)
    try:
        pg = Pluggy(cfg.get("PLUGGY_CLIENT_ID", ""), cfg.get("PLUGGY_CLIENT_SECRET", ""),
                    use_cache=not args.no_cache)
        COMMANDS[args.cmd](pg, args, cfg)
    except PluggyError as e:
        print(f"✗ {e}", file=sys.stderr); return 2
    except requests.RequestException as e:
        print(f"✗ rede: {e}", file=sys.stderr); return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
