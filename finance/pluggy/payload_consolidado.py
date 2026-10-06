#!/usr/bin/env python3
"""Transforma o JSON bruto da coleta num payload pronto pro dashboard."""
import json, re, sys
from collections import defaultdict
from pathlib import Path

PARCELA = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\s*$")


def build(raw: dict) -> dict:
    inst_out, cartoes, invs, lanc = [], [], [], []
    for inst in raw["instituicoes"]:
        caixa = divida = 0.0
        for c in inst["contas"]:
            if c["tipo"] == "CREDIT":
                divida += c["saldo"]
                cartoes.append({
                    "instituicao": inst["nome"], "nome": c["nome"],
                    "saldo": c["saldo"], "limite": c.get("limite"),
                    "disponivel": c.get("disponivel"), "vencimento": c.get("vencimento"),
                    "minimo": c.get("minimo"), "faturas": c["faturas"],
                })
            else:
                caixa += c["saldo"]
            for t in c["lancamentos"]:
                t = dict(t, instituicao=inst["nome"], conta=c["nome"],
                         conta_tipo=c["tipo"], conta_id=c.get("id"))
                lanc.append(t)
        inv_total = 0.0
        for v in inst["investimentos"]:
            inv_total += v["saldo"]
            invs.append(dict(v, instituicao=inst["nome"]))
        inst_out.append({"nome": inst["nome"], "caixa": round(caixa, 2),
                         "divida": round(divida, 2), "investimentos": round(inv_total, 2),
                         "liquido": round(caixa + inv_total - divida, 2),
                         "status": inst["status"], "zeradas": inst["zeradas"]})

    caixa = sum(i["caixa"] for i in inst_out)
    divida = sum(i["divida"] for i in inst_out)
    invest = sum(i["investimentos"] for i in inst_out)

    # --- gastos por categoria (so cartao, DEBIT, ja com FX) ---
    cat = defaultdict(float); cat_n = defaultdict(int)
    por_inst = defaultdict(float)
    for t in lanc:
        if t["conta_tipo"] != "CREDIT" or t["tipo"] != "DEBIT":
            continue
        cat[t["categoria"] or "Sem categoria"] += t["valor"]
        cat_n[t["categoria"] or "Sem categoria"] += 1
        por_inst[t["instituicao"]] += t["valor"]
    categorias = sorted(({"nome": k, "valor": round(v, 2), "n": cat_n[k]}
                         for k, v in cat.items()), key=lambda x: -x["valor"])

    # --- parcelamentos em aberto ---
    parcelas = []
    for t in lanc:
        if t["conta_tipo"] != "CREDIT" or t["tipo"] != "DEBIT":
            continue
        m = PARCELA.search(t["desc"] or "")
        if not m:
            continue
        atual, total = int(m.group(1)), int(m.group(2))
        if total < 2 or atual > total:
            continue
        parcelas.append({"desc": (t["desc"] or "").strip(), "valor": t["valor"],
                         "atual": atual, "total": total,
                         "restantes": total - atual, "instituicao": t["instituicao"],
                         "aberto": round(t["valor"] * (total - atual), 2),
                         "data": t["data"]})
    # so a ocorrencia mais recente de cada parcelamento
    vistos = {}
    for p in sorted(parcelas, key=lambda x: x["data"]):
        chave = re.sub(PARCELA, "", p["desc"]).strip().lower() + f"|{p['total']}"
        vistos[chave] = p
    parcelas = sorted(vistos.values(), key=lambda x: -x["aberto"])
    comprometido = round(sum(p["aberto"] for p in parcelas), 2)
    proxima = round(sum(p["valor"] for p in parcelas if p["restantes"] > 0), 2)

    # --- top merchants ---
    merch, rotulo = defaultdict(float), {}
    for t in lanc:
        if t["conta_tipo"] != "CREDIT" or t["tipo"] != "DEBIT":
            continue
        nome = re.sub(PARCELA, "", (t["desc"] or "?")).strip() or "?"
        chave = nome.upper()          # o banco varia o caixa do mesmo lojista
        rotulo.setdefault(chave, nome)
        merch[chave] += t["valor"]
    top = sorted(({"nome": rotulo[k], "valor": round(v, 2)} for k, v in merch.items()),
                 key=lambda x: -x["valor"])[:20]

    # --- internacionais ---
    intl = [t for t in lanc if t.get("moeda") not in (None, "BRL")]
    intl_total = round(sum(t["valor"] for t in intl if t["tipo"] == "DEBIT"), 2)
    intl_usd = round(sum(t["valor_origem"] for t in intl if t["tipo"] == "DEBIT"), 2)

    # --- investimentos por classe ---
    classes = defaultdict(float)
    for v in invs:
        rot = {"TREASURY": "Tesouro Direto", "DEBENTURES": "Debêntures",
               "FIXED_INCOME_FUND": "Fundo RF"}.get(v.get("subtipo") or "", v.get("subtipo") or v["tipo"])
        classes[rot] += v["saldo"]
    classes = sorted(({"nome": k, "valor": round(v, 2)} for k, v in classes.items()),
                     key=lambda x: -x["valor"])

    return {
        "gerado_em": raw["gerado_em"], "janela": raw["janela"],
        # ancoras da conferencia de caixa: onde o saldo das contas correntes
        # comecou a janela, onde terminou, e quanto de "entre contas" foi
        # anulado por ter as duas pontas conectadas
        "caixa_inicial": raw.get("caixa_inicial", 0.0),
        "caixa_final": raw.get("caixa_final", 0.0),
        "internas": raw.get("internas", {}),
        "resumo": {"caixa": round(caixa, 2), "divida": round(divida, 2),
                   "investimentos": round(invest, 2),
                   "liquido": round(caixa + invest - divida, 2),
                   "comprometido": comprometido, "proxima_parcela": proxima,
                   "intl_brl": intl_total, "intl_usd": intl_usd,
                   "n_instituicoes": len(inst_out), "n_lancamentos": len(lanc)},
        "instituicoes": inst_out, "cartoes": cartoes,
        "investimentos": sorted(invs, key=lambda x: -x["saldo"]),
        "classes": classes, "categorias": categorias, "top_merchants": top,
        "parcelas": parcelas,
        "gasto_por_instituicao": sorted(({"nome": k, "valor": round(v, 2)}
                                         for k, v in por_inst.items()),
                                        key=lambda x: -x["valor"]),
        "lancamentos": sorted(lanc, key=lambda x: x["data"], reverse=True),
    }


if __name__ == "__main__":
    src = Path(sys.argv[1])
    print(json.dumps(build(json.loads(src.read_text(encoding="utf-8"))),
                     ensure_ascii=False, indent=2))
