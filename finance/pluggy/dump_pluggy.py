#!/usr/bin/env python3
"""Dump completo da Pluggy em .json — snapshot do dia + ledger acumulado.

    financial-data/pluggy/
    ├── snapshots/AAAA-MM-DD/          um retrato completo por execucao
    │   ├── items.json                 itens (conexoes) com connector e status
    │   ├── accounts.json              todas as contas de todos os itens
    │   ├── investments.json           posicoes (inclusive as zeradas)
    │   ├── identity.json              identidade, quando o conector expoe
    │   └── transactions/<conta>.json  extrato bruto por conta
    ├── ledger/
    │   ├── transacoes.json            TODAS as transacoes ja vistas, por id
    │   └── posicoes.jsonl             1 linha por (data, papel) — serie historica
    └── latest.json                    atalho pro snapshot mais recente

O ledger existe porque a API so devolve uma janela movel: o que sai da janela
some da API mas fica aqui. Reexecutar e idempotente — transacao ja vista e
atualizada no lugar, nao duplicada.

Uso: ./dump_pluggy.py [--dias 365] [--dest DIR]
"""
import argparse, json, sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pluggy_client import Pluggy, PluggyError, load_config, resolve_item_ids

WORKSPACE = Path(__file__).resolve().parents[3]
DEST = WORKSPACE / "financial-data" / "pluggy"


def gravar(caminho: Path, dados) -> int:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(dados, indent=2, ensure_ascii=False)
    caminho.write_text(txt, encoding="utf-8")
    return len(txt)


def dump(dias: int, dest: Path) -> dict:
    cfg = load_config()
    pg = Pluggy(cfg["PLUGGY_CLIENT_ID"], cfg["PLUGGY_CLIENT_SECRET"])
    ids = resolve_item_ids(pg, cfg, None)
    hoje = date.today().isoformat()
    d_from = (date.today() - timedelta(days=dias)).isoformat()
    snap = dest / "snapshots" / hoje
    stats = {"itens": 0, "contas": 0, "transacoes": 0, "posicoes": 0, "erros": []}

    itens, contas, invests, ident = [], [], [], []
    for iid in ids:
        try:
            itens.append(pg.item(iid))
        except PluggyError as e:
            stats["erros"].append(f"item {iid[:8]}: {e}")
            itens.append({"id": iid, "erro": str(e)})
        stats["itens"] += 1

        try:
            accs = pg.accounts(iid)
        except PluggyError as e:
            stats["erros"].append(f"accounts {iid[:8]}: {e}")
            accs = []
        for a in accs:
            a["_itemId"] = iid
        contas.extend(accs)

        try:
            for v in pg.investments(iid):
                v["_itemId"] = iid
                invests.append(v)
        except PluggyError as e:
            stats["erros"].append(f"investments {iid[:8]}: {e}")

        try:
            ident.append(pg.identity(iid))
        except PluggyError:
            pass          # muitos conectores nao expoem IDENTITY — nao e erro

    stats["contas"] = len(contas)
    stats["posicoes"] = len(invests)
    gravar(snap / "items.json", itens)
    gravar(snap / "accounts.json", contas)
    gravar(snap / "investments.json", invests)
    if ident:
        gravar(snap / "identity.json", ident)

    # ── extrato por conta + ledger acumulado ──────────────────────────────────
    ledger_path = dest / "ledger" / "transacoes.json"
    ledger = {}
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    antes = len(ledger)

    for a in contas:
        try:
            txs = pg.transactions(a["id"], date_from=d_from, date_to=hoje)
        except PluggyError as e:
            stats["erros"].append(f"transactions {a['id'][:8]}: {e}")
            continue
        for t in txs:
            t["_itemId"] = a["_itemId"]
            t["_accountId"] = a["id"]
            t["_accountName"] = a.get("name")
            t["_accountType"] = a.get("type")
            ledger[t["id"]] = t
        gravar(snap / "transactions" / f"{a['id']}.json", txs)
        stats["transacoes"] += len(txs)

    gravar(ledger_path, ledger)
    stats["ledger_total"] = len(ledger)
    stats["ledger_novas"] = len(ledger) - antes

    # ── serie historica de posicoes (append-only) ─────────────────────────────
    pos_path = dest / "ledger" / "posicoes.jsonl"
    pos_path.parent.mkdir(parents=True, exist_ok=True)
    ja = set()
    if pos_path.exists():
        for linha in pos_path.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                r = json.loads(linha)
                ja.add((r["data"], r["id"]))
    novas = [
        {"data": hoje, "id": v["id"], "nome": v.get("name"), "codigo": v.get("code"),
         "itemId": v["_itemId"], "saldo": v.get("balance"), "pu": v.get("value"),
         "quantidade": v.get("quantity"), "aplicado": v.get("amountOriginal")}
        for v in invests if (hoje, v["id"]) not in ja
    ]
    if novas:
        with pos_path.open("a", encoding="utf-8") as fh:
            for r in novas:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    stats["posicoes_novas"] = len(novas)

    gravar(snap / "_stats.json", stats)
    gravar(dest / "latest.json", {"snapshot": hoje, "caminho": str(snap), **stats})
    return {**stats, "snapshot": str(snap)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=365)
    ap.add_argument("--dest", default=None)
    args = ap.parse_args()
    r = dump(args.dias, Path(args.dest) if args.dest else DEST)
    print(f"snapshot: {r['snapshot']}")
    print(f"  {r['itens']} itens · {r['contas']} contas · {r['posicoes']} posições")
    print(f"  {r['transacoes']} transações na janela · ledger {r['ledger_total']} "
          f"(+{r['ledger_novas']} novas)")
    print(f"  série de posições: +{r['posicoes_novas']} registros")
    for e in r["erros"]:
        print(f"  ! {e}")


if __name__ == "__main__":
    main()
