# Contribuição

## Branches

- `main`: produção.
- `develop`: homologação.
- `feature/<descricao>`: novas funcionalidades.
- `fix/<descricao>`: correções.
- `chore/<descricao>`: manutenção e configuração.

## Fluxo obrigatório

1. Crie sua branch a partir de `develop`.
2. Faça mudanças pequenas e documentadas.
3. Abra Pull Request para `develop`.
4. Aguarde pelo menos uma aprovação e resolva as conversas.
5. A promoção para produção ocorre por Pull Request de `develop` para `main`.

Commits diretos e force push em `develop` e `main` são bloqueados.

## Regras

- Não versionar senhas, tokens, chaves ou arquivos `.env`.
- Documentar variáveis em `.env.example` quando aplicável.
- Atualizar testes e README junto com mudanças de comportamento.
- Registrar decisões permanentes em ADR e decisões em discussão em RFC.
- Informar no Pull Request os comandos de validação realmente executados.
