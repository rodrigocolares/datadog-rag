# Como contribuir

Obrigado pelo interesse em contribuir com o Datadog Docs RAG.

## Fluxo recomendado

1. Faça um fork do repositório.
2. Crie uma branch a partir de `main`:

   ```bash
   git checkout -b feature/nome-da-melhoria
   ```

3. Instale as dependências e execute os testes.
4. Faça commits objetivos, preferencialmente seguindo Conventional Commits.
5. Envie a branch e abra um Pull Request.

## Antes do Pull Request

```powershell
.\.venv\Scripts\python.exe -m compileall -q app
.\.venv\Scripts\python.exe -m pytest -q
```

O Pull Request deve explicar o problema, a solução, os testes executados e qualquer impacto na configuração ou na indexação.

## Segurança

Nunca envie chaves, tokens, arquivos `.env`, bancos locais, documentos privados ou dados obtidos de ambientes Datadog. Para vulnerabilidades, siga [SECURITY.md](SECURITY.md).

