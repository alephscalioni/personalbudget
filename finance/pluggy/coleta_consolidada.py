#!/usr/bin/env python3
"""Coleta consolidada multi-instituicao via Pluggy -> JSON unico.

Une contas, cartoes (com FX aplicado e agregacao por ciclo de fatura),
extrato bancario e posicao de investimentos de todos os itens do .env.

Uso: ./coleta_consolidada.py [--dias 90] [--out caminho.json]
"""
import argparse, json, re, sys, unicodedata
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pluggy_client import (Pluggy, PluggyError, load_config, resolve_item_ids,
                           tx_amount)

# nomes bonitos por itemId nao existem na API; derivamos do conjunto de contas
def apelido(accounts):
    nomes = [(a.get("name") or "") for a in accounts]
    for chave, label in (("nu ", "Nubank"), ("ultraviolet", "Nubank"),
                         ("xp", "XP"), ("itau", "Itaú"),
                         ("personnalite", "Itaú"), ("mercado pago", "Mercado Pago")):
        if any(chave in n.lower() for n in nomes):
            return label
    return nomes[0][:24] if nomes else "?"


# --------------------------------------------------------------------------
# Natureza do lancamento bancario
#
# O extrato da conta corrente mistura coisas que o dashboard precisa separar,
# senao o "gasto" vira ficcao:
#
#   interna      as DUAS pontas de uma transferencia entre contas do Aleph que
#                estao conectadas aqui (sai R$ 5.000 do Itau, entram R$ 5.000 no
#                Nubank no mesmo dia). Se anulam, nao movem patrimonio nem
#                consumo — somem do dashboard inteiro.
#   investimento aplicacao/resgate, caixinha do Mercado Pago, compra de CDB.
#                Troca de bolso, nao consumo, mas SAI da conta.
#   fatura       pagamento de fatura de cartao. O gasto ja foi contado compra a
#                compra no cartao — somar de novo dobra tudo.
#   consumo      o que sobra saindo (PIX, boleto, TED, debito automatico).
#   entrada      o que sobra entrando (salario, PIX de terceiro, reembolso).
#
# O ponto delicado e o "entre contas". Uma transferencia so e interna quando as
# duas pontas aparecem: o dinheiro nunca saiu do perimetro. Quando so uma ponta
# aparece — PIX pra corretora, pra banco nao conectado — o dinheiro atravessou a
# fronteira do que o Open Finance enxerga. Isso e saida (ou entrada) de caixa de
# verdade: esconder como "entre contas" faz o fluxo nao fechar com o saldo.
#
# Por isso a classificacao tem duas fases. `natureza()` marca o candidato como
# "propria?" e `casa_internas()` decide, olhando todas as contas juntas, quem
# achou a outra ponta (vira "interna") e quem nao achou (vira consumo/entrada).
#
# So a conta corrente passa por aqui; lancamento de cartao fica com natureza
# None e a logica de ciclo de fatura segue intacta.
# --------------------------------------------------------------------------

RX_INVEST = re.compile(
    r"aplica[çc][ãa]o|resgate|vencimento cdb|compra cdb|compra [a-z0-9]{4,} \|"
    r"|dinheiro (reservado|retirado|guardado)|conta investimento|conta digital"
    # a caixinha do Nubank sai como "Valor transferido para Investimentos" e
    # volta como "Valor recebido de Investimentos" — as duas pontas sao troca
    # de bolso, nao consumo
    r"|valor (recebido de|transferido para) investimentos"
    r"|retirada em c/c|compra de criptomoeda"
    r"|rendimento", re.I)
# "Pagamento Cartao de credito" (Mercado Pago) nao traz nem a categoria
# "Credit card payment" nem a palavra "fatura" — mas numa conta corrente pagar
# cartao de credito e liquidar fatura, nao gasto novo.
RX_FATURA = re.compile(
    r"pagamento (de |da )?(fatura|cart[ãa]o de cr[ée]dito)|fatura paga"
    r"|pagamento de boleto int mc", re.I)
CAT_INVEST = {"Investments", "Fixed income", "Mutual funds", "Variable income",
              "Proceeds interests and dividends"}
OP_INVEST = {"RESGATE_APLIC_FINANCEIRA", "RENDIMENTO_APLIC_FINANCEIRA",
             "TRANSFERENCIA_SALDO_RESERVADO"}
INFO_FATURA = {"PAGAMENTO_FATURA", "Pagamento de fatura", "PAGAMENTO DE FATURA"}
CAT_PROPRIA = {"Same person transfer", "Transfer - Internal"}
# A XP mantem conta digital e conta investimento separadas e o extrato nomeia a
# irma na descricao. E movimento interno, nao aplicacao nova — precisa vencer o
# RX_INVEST, que casa o mesmo texto.
RX_IRMA = re.compile(r"conta (investimento|digital)", re.I)


def _sem_acento(s: str) -> str:
    return (unicodedata.normalize("NFKD", s or "")
            .encode("ascii", "ignore").decode().upper())


def _doc(pagamento: dict, lado: str):
    d = ((pagamento or {}).get(lado) or {}).get("documentNumber") or {}
    return d.get("value")


def payer_document_root(transaction):
    """Preserve the company identity even when bank descriptions are abbreviated."""
    document = (((transaction.get('paymentData') or {}).get('payer') or {}).get('documentNumber') or {})
    digits = re.sub(r'\D', '', document.get('value') or '')
    return digits[:8] if document.get('type') == 'CNPJ' and len(digits) == 14 else None


def num_conta(s: str) -> str:
    """'00416215-3' -> '4162153'. O extrato de TED cita a conta destino sem os
    zeros a esquerda e sem hifen ("TED BCO 260 AGE 1 CTA 4162153"), entao a
    unica forma de reconhecer a outra ponta e comparar so os digitos. Abaixo de
    6 digitos devolve vazio: numero curto casa por acaso dentro de qualquer
    descricao com data ou valor."""
    d = re.sub(r"\D", "", s or "").lstrip("0")
    return d if len(d) >= 6 else ""


def titular_de(identidades) -> dict:
    """Nome(s) e CPF(s) do dono das contas, pra reconhecer transferencia propria.

    O CPF e o sinal forte (payer == receiver). O nome cobre o resto: alguns
    conectores mandam so um dos lados do paymentData.
    """
    nomes, cpfs = set(), set()
    for i in (identidades or []):
        if not isinstance(i, dict):
            continue
        if i.get("fullName"):
            nomes.add(_sem_acento(i["fullName"]))
        if i.get("document"):
            cpfs.add(i["document"])
    # "Pix enviado PIX TRANSF ALEPH B15/12" — o banco corta o nome. O primeiro
    # nome logo depois de TRANSF/PIX so aparece em transferencia pra si mesmo.
    curtos = [re.escape(n.split()[0]) for n in nomes if n.split()]
    rx = (re.compile(r"TRANSF\w*\s+(" + "|".join(sorted(set(curtos))) + r")\b")
          if curtos else None)
    return {"nomes": nomes, "cpfs": cpfs, "rx_curto": rx}


METODOS = {"PIX": "PIX", "BOLETO": "Boleto", "TED": "TED"}
OP_METODO = {"CARTAO": "Cartão de débito", "OPERACAO_CREDITO": "Débito automático",
             "CONVENIO_ARRECADACAO": "Convênio", "TARIFA_SERVICOS_AVULSOS": "Tarifa",
             "FOLHA_PAGAMENTO": "Salário", "BOLETO": "Boleto", "TED": "TED",
             "PIX": "PIX"}


def metodo_de(t: dict) -> str:
    """Meio de pagamento em pt-BR. `paymentMethod` OTHER nao diz nada — nesse
    caso o `operationType` costuma dizer (CARTAO = debito, OPERACAO_CREDITO =
    parcela debitada em conta)."""
    m = METODOS.get((t.get("paymentData") or {}).get("paymentMethod"))
    return m or OP_METODO.get(t.get("operationType"), "Outros")


def natureza(t: dict, titular: dict, numeros=frozenset()) -> str:
    """Classifica um lancamento de conta corrente.

    `numeros` sao os numeros das OUTRAS contas conectadas, ja normalizados por
    num_conta(). "propria?" e provisorio — quem decide e casa_internas().
    """
    desc = t.get("description") or ""
    cat = t.get("category")
    if (cat == "Credit card payment" or RX_FATURA.search(desc)
            or t.get("operationTypeAdditionalInfo") in INFO_FATURA):
        return "fatura"

    # Sinal estrutural: a descricao aponta a conta irma pelo nome ou cita o
    # numero de outra conta conectada. Vem antes de investimento de proposito —
    # "Transferencia enviada para a conta investimento" e movimento interno da
    # XP, e "TED ... CTA 4162153 - RETIRADA EM C/C" e a XP mandando pro Nubank.
    digitos = re.sub(r"\D", "", desc)
    if RX_IRMA.search(desc) or any(n in digitos for n in numeros):
        return "propria?"

    if (cat in CAT_INVEST or t.get("operationType") in OP_INVEST
            or RX_INVEST.search(desc)):
        return "investimento"

    pag = t.get("paymentData")
    pagador, recebedor = _doc(pag, "payer"), _doc(pag, "receiver")
    ndesc = _sem_acento(desc)
    if (cat in CAT_PROPRIA
            or (pagador and recebedor and pagador == recebedor)
            or any(n in ndesc for n in titular["nomes"])
            or (titular["rx_curto"] and titular["rx_curto"].search(ndesc))):
        return "propria?"
    return "consumo" if t.get("type") == "DEBIT" else "entrada"


TOL_DIAS = 3


def casa_internas(contas: list, tol_dias: int = TOL_DIAS) -> dict:
    """Casa as duas pontas de cada transferencia entre contas conectadas.

    Um DEBIT na conta A e um CREDIT na conta B (A != B), mesmo valor absoluto,
    ate `tol_dias` de distancia. Casou: os dois viram "interna" e saem de todas
    as visoes — o dinheiro nunca deixou o patrimonio, contar como gasto de um
    lado e receita do outro e ficcao dos dois jeitos.

    Nao casou: nao e transferencia interna, e dinheiro atravessando a fronteira
    do que o Open Finance enxerga. DEBIT vira saida de caixa, CREDIT vira
    entrada, os dois no grupo Transferencias com rotulo proprio pra dar pra
    achar na tela. E o que faz a soma dos lancamentos bater com o saldo.

    Como os pares tem valor identico, a soma das internas e exatamente zero:
    tirar as duas pontas nao mexe na conferencia de caixa.
    """
    pernas = [(c, t) for c in contas for t in c["lancamentos"]
              if t.get("natureza") == "propria?"]
    cre = [(c, t) for c, t in pernas if t["tipo"] == "CREDIT"]
    livres = set(range(len(cre)))
    pares = 0
    for c, t in sorted((p for p in pernas if p[1]["tipo"] == "DEBIT"),
                       key=lambda p: p[1]["data"]):
        d0 = date.fromisoformat(t["data"])
        alvo = round(abs(t["valor"]), 2)
        melhor = None
        for i in livres:
            cc, tc = cre[i]
            if cc["id"] == c["id"] or round(abs(tc["valor"]), 2) != alvo:
                continue
            dd = abs((date.fromisoformat(tc["data"]) - d0).days)
            if dd <= tol_dias and (melhor is None or dd < melhor[0]):
                melhor = (dd, i)
        if melhor is None:
            continue
        livres.discard(melhor[1])
        cc, tc = cre[melhor[1]]
        t["natureza"] = tc["natureza"] = "interna"
        t["par"] = {"conta": cc["nome"], "data": tc["data"]}
        tc["par"] = {"conta": c["nome"], "data": t["data"]}
        pares += 1

    soltos = {"DEBIT": 0, "CREDIT": 0}
    valor_solto = {"DEBIT": 0.0, "CREDIT": 0.0}
    for _, t in pernas:
        if t.get("natureza") != "propria?":
            continue
        saiu = t["tipo"] == "DEBIT"
        t["natureza"] = "consumo" if saiu else "entrada"
        t["externa"] = True
        t["categoria"] = ("Transferência para conta externa" if saiu
                          else "Transferência de conta externa")
        t["grupo"] = "Transferências"
        soltos[t["tipo"]] += 1
        valor_solto[t["tipo"]] += abs(t["valor"])
    return {"pares": pares, "soltos_saida": soltos["DEBIT"],
            "soltos_entrada": soltos["CREDIT"],
            "valor_par": round(sum(abs(t["valor"]) for _, t in pernas
                                   if t.get("natureza") == "interna") / 2, 2),
            "valor_solto_saida": round(valor_solto["DEBIT"], 2),
            "valor_solto_entrada": round(valor_solto["CREDIT"], 2)}


DUMP = WORKSPACE_FIN = Path(__file__).resolve().parents[3] / "financial-data" / "pluggy"


def _do_dump(dias: int):
    """Le do dump local (dump_pluggy.py) em vez de bater na API.

    Vantagem: o ledger guarda TUDO que ja foi visto, entao a janela nao fica
    presa ao que a API devolve hoje. Sem rede, reproduzivel.
    """
    snaps = sorted((DUMP / "snapshots").glob("*"))
    if not snaps:
        raise SystemExit("nenhum snapshot em financial-data/pluggy/snapshots — "
                         "rode ./dump_pluggy.py primeiro")
    snap = snaps[-1]
    itens = json.loads((snap / "items.json").read_text(encoding="utf-8"))
    contas = json.loads((snap / "accounts.json").read_text(encoding="utf-8"))
    invs = json.loads((snap / "investments.json").read_text(encoding="utf-8"))
    ledger = json.loads((DUMP / "ledger" / "transacoes.json").read_text(encoding="utf-8"))

    corte = (date.today() - timedelta(days=dias)).isoformat()
    por_conta = defaultdict(list)
    for t in ledger.values():
        if t["date"][:10] >= corte:
            por_conta[t["_accountId"]].append(t)

    status = {i["id"]: i.get("status", "?") for i in itens}
    contas_por_item = defaultdict(list)
    for a in contas:
        contas_por_item[a["_itemId"]].append(a)
    invs_por_item = defaultdict(list)
    for v in invs:
        invs_por_item[v["_itemId"]].append(v)
    ident_f = snap / "identity.json"
    ident = (json.loads(ident_f.read_text(encoding="utf-8"))
             if ident_f.is_file() else [])
    return snap, status, contas_por_item, invs_por_item, por_conta, ident


def coletar(dias: int, fonte: str = "api", strict: bool = False):
    d_to = date.today().isoformat()
    d_from = (date.today() - timedelta(days=dias)).isoformat()
    pg = None
    if fonte == "dump":
        _, status_map, contas_map, invs_map, tx_map, ident = _do_dump(dias)
        ids = list(contas_map)
    else:
        cfg = load_config()
        pg = Pluggy(cfg["PLUGGY_CLIENT_ID"], cfg["PLUGGY_CLIENT_SECRET"])
        ids = resolve_item_ids(pg, cfg, None)
        ident = []
        for iid in ids:                      # nem todo conector expoe identidade
            try:
                ident.append(pg.identity(iid))
            except PluggyError:
                pass
    titular = titular_de(ident)

    # As contas de TODOS os itens antes do loop: pra reconhecer um TED entre
    # contas do Aleph e preciso saber o numero das outras contas conectadas
    # antes de classificar a primeira ("TED BCO 260 AGE 1 CTA 4162153").
    contas_de, invs_de, status_de = {}, {}, {}
    for iid in ids:
        if fonte == "dump":
            status_de[iid] = status_map.get(iid, "?")
            contas_de[iid] = contas_map[iid]
            invs_de[iid] = invs_map.get(iid, [])
        else:
            try:
                status_de[iid] = pg.item(iid).get("status")
            except PluggyError:
                if strict: raise
                status_de[iid] = "?"
            contas_de[iid] = pg.accounts(iid)
            try:
                invs_de[iid] = pg.investments(iid)
            except PluggyError:
                if strict: raise
                invs_de[iid] = []
    num_de = {a["id"]: num_conta(a.get("number")) for lst in contas_de.values()
              for a in lst}
    outros_numeros = {aid: {n for outro, n in num_de.items()
                            if n and outro != aid} for aid in num_de}

    out = {"gerado_em": date.today().isoformat(), "janela": [d_from, d_to],
           "instituicoes": []}
    bancarias = []                 # todas as contas correntes, pra casar pares

    for iid in ids:
        status, accs, invs = status_de[iid], contas_de[iid], invs_de[iid]

        inst = {"itemId": iid, "nome": apelido(accs), "status": status,
                "contas": [], "investimentos": []}

        for a in accs:
            conta = {"id": a["id"], "tipo": a.get("type"),
                     "subtipo": a.get("subtype"), "nome": a.get("name"),
                     "saldo": float(a.get("balance") or 0),
                     "lancamentos": [], "faturas": {}}
            cd = a.get("creditData") or {}
            if a.get("type") == "CREDIT":
                conta["limite"] = cd.get("creditLimit")
                conta["disponivel"] = cd.get("availableCreditLimit")
                conta["vencimento"] = cd.get("balanceDueDate")
                conta["minimo"] = cd.get("minimumPayment")

            if fonte == "dump":
                txs = sorted(tx_map.get(a["id"], []), key=lambda t: t["date"],
                             reverse=True)
            else:
                try:
                    txs = pg.transactions(a["id"], date_from=d_from, date_to=d_to)
                except PluggyError as e:
                    txs = []
                    conta["erro_extrato"] = str(e)

            faturas = defaultdict(lambda: {"debitos": 0.0, "estornos": 0.0,
                                           "pagamentos": 0.0, "n": 0})
            for t in txs:
                v = tx_amount(t)
                conta["lancamentos"].append({
                    "provider_id": t.get("id"),
                    "payer_document_root": payer_document_root(t),
                    "data": t["date"][:10], "desc": t.get("description"),
                    "categoria": t.get("category"), "tipo": t.get("type"),
                    "valor": v, "moeda": t.get("currencyCode"),
                    "valor_origem": float(t.get("amount") or 0),
                    "fatura": (t.get("creditCardMetadata") or {}).get("billForecastDate"),
                    # so a conta corrente precisa de natureza/meio de pagamento
                    "natureza": (None if a.get("type") == "CREDIT" else
                                 natureza(t, titular,
                                          outros_numeros.get(a["id"], ()))),
                    "metodo": (None if a.get("type") == "CREDIT" else
                               metodo_de(t)),
                })
                b = (t.get("creditCardMetadata") or {}).get("billForecastDate")
                if b:
                    f = faturas[b]; f["n"] += 1
                    if t.get("type") == "DEBIT":
                        f["debitos"] += v
                    elif t.get("category") == "Credit card payment":
                        f["pagamentos"] += -v
                    else:
                        f["estornos"] += -v
            for b, f in faturas.items():
                f["total"] = round(f["debitos"] - f["estornos"], 2)
                for k in ("debitos", "estornos", "pagamentos"):
                    f[k] = round(f[k], 2)
            conta["faturas"] = dict(sorted(faturas.items()))
            if a.get("type") != "CREDIT":
                # Saldo no primeiro dia da janela, deduzido de tras pra frente:
                # o saldo de hoje menos tudo que entrou e saiu desde entao. E o
                # ancoradouro da conferencia — se a soma dos lancamentos
                # classificados nao levar deste numero ate o saldo atual, tem
                # lancamento no lugar errado.
                conta["saldo_inicial"] = round(
                    conta["saldo"] - sum(l["valor"] for l in conta["lancamentos"]), 2)
                bancarias.append(conta)
            inst["contas"].append(conta)

        for i in invs:
            saldo = float(i.get("balance") or 0)
            if saldo == 0:
                continue                      # posicao zerada/liquidada
            inst["investimentos"].append({
                "nome": i.get("name"), "tipo": i.get("type"),
                "codigo": i.get("code"), "isin": i.get("isin"),
                "quantidade": i.get("quantity"), "pu": i.get("value"),
                "compra": (i.get("purchaseDate") or "")[:10],
                "subtipo": i.get("subtype"), "saldo": saldo,
                "emissor": i.get("issuer"), "vencimento": i.get("dueDate"),
                "taxa": i.get("rate"), "indexador": i.get("rateType"),
                "aplicado": i.get("amountOriginal"), "lucro": i.get("amountProfit"),
            })
        inst["zeradas"] = sum(1 for i in invs if not float(i.get("balance") or 0))
        out["instituicoes"].append(inst)

    out["internas"] = casa_internas(bancarias)
    out["caixa_inicial"] = round(sum(c["saldo_inicial"] for c in bancarias), 2)
    out["caixa_final"] = round(sum(c["saldo"] for c in bancarias), 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=90)
    ap.add_argument("--fonte", choices=("api", "dump"), default="dump",
                    help="dump = le financial-data/pluggy (default); api = bate na Pluggy")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    data = coletar(args.dias, args.fonte)
    dest = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[3] / "reports" /
        f"consolidado-{date.today()}.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
