# Estoque consolidado de dois QuickBooks Online — unidades e quilos

Este programa conecta **duas empresas diferentes do QuickBooks Online**, lê os itens de estoque e apresenta:

- SKU e nome do produto;
- quantidade em unidades (`QtyOnHand`) da Empresa A;
- quantidade em unidades (`QtyOnHand`) da Empresa B;
- total de unidades das duas empresas;
- peso de cada unidade;
- quantidade convertida para kg em cada empresa;
- total consolidado em kg;
- resumo por produto-base, somando potes de 250g e 500g;
- itens existentes somente em uma empresa;
- gramaturas não identificadas ou conflitantes;
- exportação em Excel e CSV.

O programa é **somente leitura**. Ele não cria, altera nem exclui itens no QuickBooks.

## Exemplo da conversão

Se o QuickBooks mostra:

| SKU | Produto | QtyOnHand |
|---|---|---:|
| RANU06-250 | Rapé Nukini Onça 250g | 20 |
| RANU06-500 | Rapé Nukini Onça 500g | 8 |

O programa calcula:

- 20 × 0,250 kg = **5,000 kg**;
- 8 × 0,500 kg = **4,000 kg**;
- total do produto-base = **9,000 kg**.

## Como o peso é identificado

A identificação é conservadora para evitar cálculos errados.

O programa reconhece gramaturas explícitas no nome, por exemplo:

- `Pote 250g`;
- `Pote 500 g`;
- `7,1g`;
- `1 kg`;
- nomes terminados em `Kg`, quando o `QtyOnHand` já representa quilos.

Também reconhece sufixos seguros no SKU, por exemplo:

- `RANU06-250`;
- `RANU06-500`;
- `FVNU06-07`;
- `FVNU06-14`;
- `FVNU06-28`;
- `RANU06-500G`.

O programa **não interpreta números colados no código como peso**. Por exemplo, `RAKU2500` não é considerado automaticamente um pote de 500g, porque `2500` pode fazer parte do código-base.

Quando a gramatura não está clara:

- o campo de kg fica como `—`;
- o item aparece em **Revisar peso**;
- o programa não inclui aquele item no total em kg.

Quando SKU e nome indicam pesos diferentes, o item é marcado como **Conflito** e também não entra no total em kg.

## 1. Testar agora, sem credenciais

### Windows

1. Extraia o arquivo ZIP.
2. Dê dois cliques em `iniciar_windows.bat`.
3. Aguarde a instalação das dependências.
4. O navegador será aberto em `http://localhost:8000`.
5. Clique em **Carregar demonstração 250g/500g**.

### macOS/Linux

```bash
./iniciar_mac_linux.sh
```

## 2. O que é necessário para as empresas reais

Crie um aplicativo no **Intuit Developer Portal** e obtenha:

- `Client ID`;
- `Client Secret`;
- uma `Redirect URI` cadastrada no aplicativo.

Para Sandbox, o exemplo local é:

```text
http://localhost:8000/oauth/callback
```

Para dados reais de produção, use credenciais de produção e uma URL HTTPS pública cadastrada exatamente igual no aplicativo da Intuit.

## 3. Configurar o arquivo `.env`

Na primeira execução, o programa cria `.env` copiando `.env.example`.

Para Sandbox:

```env
QBO_CLIENT_ID=seu_client_id
QBO_CLIENT_SECRET=seu_client_secret
QBO_ENVIRONMENT=sandbox
QBO_REDIRECT_URI=http://localhost:8000/oauth/callback
COMPANY_A_LABEL=Empresa A
COMPANY_B_LABEL=Empresa B
```

Para empresas reais:

```env
QBO_CLIENT_ID=seu_client_id_de_producao
QBO_CLIENT_SECRET=seu_client_secret_de_producao
QBO_ENVIRONMENT=production
QBO_REDIRECT_URI=https://seu-dominio.com/oauth/callback
COMPANY_A_LABEL=Nome da Empresa A
COMPANY_B_LABEL=Nome da Empresa B
APP_PASSWORD=crie-uma-senha-forte
```

Depois de editar `.env`, feche e abra novamente o programa.

## 4. Conectar as duas empresas

1. Clique em **Conectar Empresa A**.
2. Entre na conta Intuit e selecione a primeira empresa.
3. Ao retornar ao painel, o estoque será lido automaticamente.
4. Clique em **Conectar Empresa B**.
5. Selecione a segunda empresa.
6. Clique em **Atualizar as duas** sempre que quiser uma leitura nova.

Uma única aplicação Intuit pode guardar duas autorizações diferentes, identificadas pelo `realmId` de cada empresa.

## 5. Como os produtos são comparados

A chave principal é o SKU. Para melhorar a conferência, o programa normaliza diferenças simples:

- `FVNU06-28` e `FVNU0628` são tratados como o mesmo SKU;
- maiúsculas e minúsculas são ignoradas;
- espaços, hífens, pontos, barras e acentos são ignorados.

A tabela continua mostrando o SKU original de cada empresa para revisão.

Se não houver SKU, o programa tenta unir pelo nome e mostra o aviso **sem SKU (unido pelo nome)**. Esses casos devem ser conferidos manualmente.

## 6. Telas e exportações

O painel possui duas visões:

### Resumo por rapé

Combina variações de 250g e 500g quando o código-base pode ser identificado com segurança.

### Detalhamento por SKU e gramatura

Mostra:

- SKU;
- nome;
- peso unitário;
- unidades da Empresa A;
- kg da Empresa A;
- unidades da Empresa B;
- kg da Empresa B;
- total de unidades;
- total em kg;
- alertas de conferência.

O Excel exportado possui três abas:

1. `Estoque por SKU`;
2. `Resumo por Rapé`;
3. `Resumo`.

## 7. Segurança

- Os tokens OAuth são criptografados antes de serem salvos em `instance/quickbooks_stock.db`.
- A chave fica em `instance/token_encryption.key`.
- Não apague essa chave enquanto houver conexões ativas.
- Não envie `.env`, o banco ou os arquivos `.key` para GitHub ou terceiros.
- Para uso público, configure `APP_PASSWORD` e HTTPS.
- O servidor local inicia em `127.0.0.1`, não ficando acessível na rede por padrão.

### URLs públicas para publicação na Intuit

O aplicativo disponibiliza rotas públicas que continuam acessíveis mesmo com
`APP_PASSWORD` configurada:

- contrato de licença: `/eula` (alternativa: `/termos-de-uso`);
- política de privacidade: `/privacy` (alternativa: `/politica-de-privacidade`);
- lançamento do aplicativo: `/launch`;
- desconexão: `/disconnect`;
- conexão ou reconexão: `/connect` (alternativa: `/reconnect`).

Em produção, cadastre URLs HTTPS completas, por exemplo
`https://seu-dominio.com/eula` e `https://seu-dominio.com/privacy`. O campo Host domain
recebe apenas o domínio, sem `https://`. Antes de publicar, confirme
`LEGAL_BUSINESS_NAME`, `LEGAL_CONTACT_EMAIL` e `LEGAL_COUNTRY` no arquivo `.env`.

## 8. Publicar na Vercel com SQLite persistente

A Vercel detecta `app.py` como uma única Function Flask. O arquivo `vercel.json` fixa a região
em São Paulo, permite até 60 segundos por execução e exclui arquivos de desenvolvimento do
pacote. Durante a execução, o SQLite fica na área gravável temporária da Function.

Para manter o banco, o estoque e os tokens OAuth entre cold starts, conecte um Vercel Blob:

1. Abra o projeto `controle-estoque` no painel da Vercel.
2. Entre em **Storage** e selecione **Create Database**.
3. Escolha **Blob**, configure o acesso como **Private** e conecte ao projeto.
4. A Vercel criará automaticamente a variável `BLOB_READ_WRITE_TOKEN`.
5. Em **Settings > Environment Variables**, cadastre:
   - `APP_PASSWORD` com uma senha forte;
   - `FLASK_SECRET_KEY` com um valor aleatório longo;
   - `TOKEN_ENCRYPTION_KEY` com uma chave Fernet;
   - `QBO_CLIENT_ID` e `QBO_CLIENT_SECRET`;
   - `QBO_ENVIRONMENT=production`;
   - `QBO_REDIRECT_URI=https://controle-estoque-pi-two.vercel.app/oauth/callback`.
6. Faça um redeploy da produção.

Gere os dois segredos localmente, sem colocá-los no GitHub:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Sem `BLOB_READ_WRITE_TOKEN`, as páginas públicas continuam disponíveis e o erro de filesystem
não ocorre, mas conexões e estoque ficam temporários e podem desaparecer em um cold start.

Com o endereço atual da Vercel, preencha a Intuit assim:

```text
Host domain:              controle-estoque-pi-two.vercel.app
Launch URL:               https://controle-estoque-pi-two.vercel.app/launch
Disconnect URL:           https://controle-estoque-pi-two.vercel.app/disconnect
Connect/Reconnect URL:    https://controle-estoque-pi-two.vercel.app/connect
End-user license URL:     https://controle-estoque-pi-two.vercel.app/eula
Privacy policy URL:       https://controle-estoque-pi-two.vercel.app/privacy
OAuth Redirect URI:       https://controle-estoque-pi-two.vercel.app/oauth/callback
```

## 9. Estrutura do projeto

```text
app.py                         painel, filtros, Excel e CSV
qbo_stock/qbo.py               OAuth e leitura do QuickBooks
qbo_stock/db.py                SQLite e snapshots de estoque
qbo_stock/consolidation.py     união dos dois estoques e resumo por produto
qbo_stock/weights.py           identificação de gramatura e conversão para kg
qbo_stock/security.py          criptografia dos tokens
templates/                     interface HTML
static/                        aparência do painel
tests/                         testes da lógica
```

## 10. Rodar testes

```bash
python -m pytest
python -m compileall -q .
```

## 11. Limitações desta versão

- Consolida somente dois QuickBooks Online.
- Lê itens com controle de quantidade (`TrackQtyOnHand` ou tipo `Inventory`).
- Usa o estoque atual `QtyOnHand`; não calcula mercadoria em trânsito.
- Não cria pedidos de compra nem altera estoque.
- O resumo por produto-base depende de um padrão identificável de SKU ou nome.
- Gramaturas não explícitas precisam ser corrigidas no nome/SKU do QuickBooks ou tratadas em uma futura tabela manual de equivalências.

## 12. Próximas evoluções possíveis

1. estoque da terceira empresa/ERP;
2. carregamentos em trânsito;
3. estoque mínimo;
4. indicação automática de compra;
5. histórico de vendas e consumo médio;
6. tela manual de equivalência de SKUs e pesos.
