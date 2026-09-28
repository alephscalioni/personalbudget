#!/usr/bin/env bash
# Atualiza o consolidado financeiro: dump -> coleta -> dashboard.
# O painel (painel.alophus.com.br/financas) sempre serve o HTML mais recente,
# entao este job e o que mantem a pagina viva.
set -euo pipefail

BASE="/home/aleph/brain-panel/workspaces/kaleu"
DIR="$BASE/scripts/finance/pluggy"
LOG="$BASE/memory/pluggy-consolidado.log"
DIAS_LEDGER=365     # janela pedida a API; o ledger acumula alem disso
DIAS_REPORT=365     # janela do dashboard, lida do ledger local

exec >>"$LOG" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="

cd "$DIR"

# 1) dump bruto (snapshot do dia + ledger acumulado)
./dump_pluggy.py --dias "$DIAS_LEDGER"

# 2) payload consolidado a partir do dump local (sem rede)
./coleta_consolidada.py --dias "$DIAS_REPORT" --fonte dump

# 3) dashboards HTML — patrimonio, fluxo do ano e fluxo mes a mes.
#    Os tres saem do MESMO consolidado do passo 2 e do mesmo classificador.js,
#    entao ou nascem juntos ou passam a discordar entre si sobre o mesmo gasto.
HTML=$(./gera_dashboard_consolidado.py)
echo "dashboard:    $HTML"
FLUXO=$(./gera_fluxo_real.py)
echo "fluxo ano:    $FLUXO"
MENSAL=$(./gera_fluxo_mensal.py)
echo "fluxo mensal: $MENSAL"

# 4) limpeza: mantem 60 dias de snapshot e de HTML (o ledger nunca e podado)
find "$BASE/financial-data/pluggy/snapshots" -maxdepth 1 -type d -mtime +60 \
     -exec rm -rf {} + 2>/dev/null || true
for padrao in 'patrimonio-consolidado-*.html' 'fluxo-caixa-real-*.html' \
               'fluxo-mensal-*.html'; do
  find "$BASE/reports" -maxdepth 1 -name "$padrao" -mtime +60 \
       -delete 2>/dev/null || true
done

echo "ok"
