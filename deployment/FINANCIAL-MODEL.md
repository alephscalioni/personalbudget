# Fluxo financeiro da família

O problema anterior era usar o mês civil para os pagamentos, deslocar apenas o salário para o mês seguinte e misturar compras no cartão com caixa. Isso separava a fonte do dinheiro das contas que ela financia.

## Modelo implementado

1. **Ciclo:** mês das contas. Começa no salário regular identificado de Aleph no fim do mês anterior e termina antes do próximo. A data real prevalece sobre a expectativa de último dia útil. Na ausência de salário identificado, a fronteira é estimada pelo último dia de segunda a sexta, sem presumir feriados ou recebimento.
2. **Fontes:** salário de Aleph, salário de Bianca, outras receitas e saldo inicial informado. Previsões não são receitas realizadas. Salários extraordinários e transferências duvidosas permanecem para revisão.
3. **Aplicações:** faturas dos cartões, condomínio, luz, MBA, financiamento e demais grupos de custo. Cada pagamento aparece uma vez. As compras do cartão ficam na análise de consumo; no fluxo entra o pagamento da fatura.
4. **Budget mensal:** cada linha possui valor planejado, dia de referência, origem planejada e término opcional. Compare budget, pago, ainda orçado e desvio. Valores ainda não definidos não equivalem a zero nem a dívida. A média dos três ciclos anteriores com pagamentos é apenas sugestão no formulário.
5. **Financiamento:** cada linha pode ser destinada a Aleph, Bianca ou fundo conjunto. Essa atribuição representa planejamento, não prova de rastreamento da moeda. Sem escolha explícita, não inventar quem pagou.
6. **Primeira quinzena:** marco de gestão, sem esconder despesas posteriores. Datas bancárias permanecem intactas; ajustes explícitos de ciclo têm prioridade.

## Persistência e sincronização

PostgreSQL com documentos JSONB preserva contas de acesso, senhas, sessões versionadas, ajustes, orçamento, ciclos, auditoria, fila do Kaleu e o consolidado bancário corrente. SQLite serve apenas para desenvolvimento e como cópia de recuperação da migração. A migração é transacional e idempotente.

A coleta roda no Railway a cada 3.600 segundos, sem depender do computador local. Um lock PostgreSQL impede sobreposição entre réplicas. Falhas e respostas incompletas preservam a última versão válida. Dados anteriores à janela móvel são mantidos. A disponibilidade dos movimentos continua dependente dos bancos e da Pluggy; consultar a API não força atualização instantânea do banco.

## Revisão

Pendências de categoria e possíveis salários aparecem no pop-up. Alterações são feitas no lançamento existente, sem duplicar renda. O Kaleu lê a mesma base e propõe ações; dados duvidosos não se tornam fatos por recorrência ou semelhança de nome.
