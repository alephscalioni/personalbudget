#!/usr/bin/env python3
"""Atualiza a Pluggy e pergunta no Telegram sobre novas compras online."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path("/home/aleph/brain-panel/workspaces/kaleu")
DIR = BASE / "scripts/finance/pluggy"
LEDGER = BASE / "financial-data/pluggy/ledger/transacoes.json"
STATE = BASE / "financial-data/pluggy/monitor-compras-state.json"
LOCK = BASE / "financial-data/pluggy/monitor-compras.lock"
TOKEN_FILE = Path("/home/aleph/claude/channels/tg-kaleu/.env")
CHAT_ID = "1004635249"

SHOP_CATEGORIES = {
    "Shopping", "Online shopping", "Electronics", "Clothing", "Kids and toys",
    "Sports goods", "Bookstore", "Office supplies", "Pet supplies and vet",
}
SHOP_RX = re.compile(
    r"amazon|mercado\s*livre|mercadolivre|shopee|temu|aliexpress|shein|magalu|"
    r"kabum|pichau|terabyte|riachuelo|renner|dafiti|netshoes|daiso|dufry",
    re.I,
)


def env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip("'\"")
    return out


def is_purchase(tx: dict) -> bool:
    if tx.get("type") != "DEBIT" or tx.get("status") not in (None, "POSTED"):
        return False
    desc = " ".join(str(tx.get(k) or "") for k in ("description", "descriptionRaw"))
    merchant = tx.get("merchant") or {}
    desc += " " + str(merchant.get("name") or "")
    category = str(tx.get("category") or "")
    if category in {"Credit card payment", "Transfers"}:
        return False
    return category in SHOP_CATEGORIES or bool(SHOP_RX.search(desc))


def label(tx: dict) -> str:
    merchant = tx.get("merchant") or {}
    raw = merchant.get("name") or tx.get("description") or tx.get("descriptionRaw") or "Compra"
    return re.sub(r"\s+", " ", str(raw)).strip()


def money(value: float) -> str:
    return f"R$ {abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def send(text: str, dry_run: bool) -> None:
    if dry_run:
        print(text)
        return
    cfg = env_file(TOKEN_FILE)
    token = cfg.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(f"TELEGRAM_BOT_TOKEN ausente em {TOKEN_FILE}")
    data = urllib.parse.urlencode({"chat_id": cfg.get("TELEGRAM_CHAT_ID", CHAT_ID), "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if not body.get("ok"):
        raise RuntimeError(f"Telegram recusou mensagem: {body}")


def refresh() -> None:
    subprocess.run(
        [str(DIR / "dump_pluggy.py"), "--dias", "30"],
        cwd=DIR, check=True, timeout=12 * 60,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", action="store_true")
    ap.add_argument("--no-refresh", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("monitor já está em execução")
            return 0

        if not args.no_refresh:
            refresh()
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
        seen = set(state.get("seen", []))

        if args.bootstrap or not state:
            state = {"seen": sorted(ledger), "pending": [], "updated_at": datetime.now().isoformat()}
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"baseline criado: {len(ledger)} transações")
            return 0

        new_ids = [txid for txid in ledger if txid not in seen]
        purchases = [(txid, ledger[txid]) for txid in new_ids if is_purchase(ledger[txid])]
        pending = list(state.get("pending", []))

        for txid, tx in sorted(purchases, key=lambda x: str(x[1].get("date") or "")):
            code = txid.split("-")[0].upper()
            date = str(tx.get("date") or "")[:10]
            account = tx.get("_accountName") or tx.get("_accountType") or ""
            text = (
                f"🧾 Compra nova [{code}]\n"
                f"{date} · {label(tx)} · {money(float(tx.get('amount') or 0))}\n"
                f"{account}\n"
                "O que foi? Responda: código + categoria + descrição."
            )
            send(text, args.dry_run)
            pending.append({
                "code": code, "transaction_id": txid, "date": date,
                "description": label(tx), "amount": abs(float(tx.get("amount") or 0)),
                "asked_at": datetime.now().isoformat(), "status": "waiting",
            })

        seen.update(new_ids)
        state = {
            "seen": sorted(seen), "pending": pending[-200:],
            "updated_at": datetime.now().isoformat(),
            "last_new": len(new_ids), "last_questions": len(purchases),
        }
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"novas={len(new_ids)} perguntas={len(purchases)}")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"erro: {exc}", file=sys.stderr)
        raise
