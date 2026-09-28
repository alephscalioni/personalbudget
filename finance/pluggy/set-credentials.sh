#!/usr/bin/env bash
# Grava as credenciais Pluggy sem passar por chat nem por historico de shell.
# Uso: ./set-credentials.sh          (roda no terminal do servidor)
# Campo em branco = mantem o valor que ja esta no .env.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$DIR/.env"

# le o valor atual de uma chave do .env (vazio se nao existir)
cur() { [ -f "$CFG" ] && sed -n "s/^$1=//p" "$CFG" | head -1 || true; }

CUR_CID="$(cur PLUGGY_CLIENT_ID)"
CUR_CSEC="$(cur PLUGGY_CLIENT_SECRET)"
CUR_ITEMS="$(cur PLUGGY_ITEM_IDS)"
CUR_USER="$(cur PLUGGY_CLIENT_USER_ID)"; CUR_USER="${CUR_USER:-aleph}"
CUR_HOOK="$(cur PLUGGY_WEBHOOK_URL)"

echo "Credenciais Pluggy → $CFG"
echo "(pega em https://dashboard.pluggy.ai → sua Application)"
echo "Enter em branco mantem o valor atual."
echo

read -rp  "CLIENT_ID     [${CUR_CID:-vazio}] : " CID
read -rsp "CLIENT_SECRET [$([ -n "$CUR_CSEC" ] && echo 'ja preenchido' || echo vazio)] : " CSEC; echo
read -rp  "ITEM_IDS csv  [${CUR_ITEMS:-vazio}] : " ITEMS

CID="${CID:-$CUR_CID}"
CSEC="${CSEC:-$CUR_CSEC}"
ITEMS="${ITEMS:-$CUR_ITEMS}"

[ -n "$CID" ]  || { echo "✗ CLIENT_ID vazio";     exit 1; }
[ -n "$CSEC" ] || { echo "✗ CLIENT_SECRET vazio"; exit 1; }

umask 077
cat > "$CFG" <<CONF
# Pluggy · Open Finance BR — gerado por set-credentials.sh em $(date '+%d/%m/%Y %H:%M')
PLUGGY_CLIENT_ID=$CID
PLUGGY_CLIENT_SECRET=$CSEC
PLUGGY_ITEM_IDS=$ITEMS
PLUGGY_CLIENT_USER_ID=$CUR_USER
PLUGGY_WEBHOOK_URL=$CUR_HOOK
CONF
chmod 600 "$CFG"

echo
echo "✓ gravado (chmod 600, fora do git)"
echo "→ testando /auth..."
"$DIR/pluggy_client.py" --no-cache auth
