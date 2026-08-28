# Instruções para o Codex

## Objetivo

Manter um painel em português que conecte exatamente dois QuickBooks Online, consolide o estoque atual por SKU e converta produtos em unidades para kg conforme a gramatura.

## Restrições obrigatórias

- A integração deve permanecer **somente leitura**.
- Não criar chamadas POST/PUT/DELETE para entidades contábeis do QuickBooks.
- OAuth e renovação de tokens podem usar POST apenas nos endpoints oficiais de autenticação.
- Nunca registrar `Client Secret`, access token ou refresh token em logs.
- Nunca versionar `.env`, `instance/*.db` ou `instance/*.key`.
- A correspondência padrão deve continuar sendo pelo SKU normalizado.
- Qualquer correspondência pelo nome deve ficar claramente marcada para revisão.
- A conversão de peso deve ser conservadora: nunca adivinhar gramaturas ambíguas.
- Produtos sem peso confiável devem ficar com kg nulo/indisponível, não zero falso.
- Divergências entre nome e SKU devem ser exibidas como conflito.
- Toda mudança na consolidação ou identificação de pesos deve incluir testes em `tests/`.
- Interface e mensagens destinadas ao usuário devem permanecer em português.

## Regras de peso atuais

- Reconhecer gramaturas explícitas no nome, como `250g`, `500g`, `7,1g` e `1 kg`.
- Reconhecer sufixos seguros no SKU, como `-250`, `-500`, `-07`, `-14`, `-28` e `500G`.
- Não interpretar números colados e ambíguos como peso; por exemplo, `RAKU2500` não é automaticamente 500g.
- Nome terminado em `Kg`, sem outra gramatura, significa que `QtyOnHand` já está em kg.

## Comandos de verificação

```bash
python -m pytest
python -m compileall -q .
```

## Arquivos principais

- `app.py`: rotas, interface, filtros e exportações.
- `qbo_stock/qbo.py`: OAuth e leitura da API do QuickBooks.
- `qbo_stock/db.py`: armazenamento local e snapshots.
- `qbo_stock/consolidation.py`: união dos dois estoques e resumo por produto-base.
- `qbo_stock/weights.py`: detecção de gramatura e conversão para kg.
