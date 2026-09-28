# Publicação

Vercel entrega apenas o frontend e encaminha a API ao Railway. Railway executa o backend com autenticação obrigatória e volume em `/data`.

`seed/` é opcional e **nunca entra no Git**: serve apenas para importar os dados privados na primeira publicação por CLI. O volume preserva relatórios, configuração e planejamento nos próximos deploys. Arquivos existentes no volume não são sobrescritos.

Variáveis obrigatórias no Railway:

- `PERSONALBUDGET_PASSWORD_HASH`: senha provisória derivada com scrypt para inicialização das duas contas; nunca é reaplicada às contas existentes.
- `PERSONALBUDGET_SESSION_SECRET`: segredo aleatório para assinar sessões.
- `PERSONALBUDGET_PUBLIC_ORIGINS`: URLs HTTPS autorizadas da Vercel, separadas por vírgula.
- `PERSONALBUDGET_ALLOWED_HOSTS`: hosts autorizados; o domínio Railway é incluído automaticamente.

A API retorna 401 sem sessão. O relatório detalhado também exige autenticação. Sessões duram 12 horas; senha incorreta tem limitação de tentativas. A aplicação se recusa a iniciar no modo cloud sem autenticação configurada.


As contas iniciais são `alephscalioni` e `biancascalioni`, com troca obrigatória de senha. Configure `PERSONALBUDGET_ALEPH_EMAIL` e `PERSONALBUDGET_BIANCA_EMAIL` para recuperação. Configure o SMTP somente no backend. A senha do Google não deve aparecer no frontend nem no repositório.
