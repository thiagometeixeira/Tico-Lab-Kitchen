# Tico Lab Kitchen

Receitas tratadas como protocolos de engenharia: gramas, temperaturas e tempos precisos, sem olhômetro.

Site estático: abra o `index.html` ou sirva a pasta com `python -m http.server`.

## Como funciona

Cada receita vive em um arquivo `data/receitas/<slug>.json`. O script `build.py` (Python 3, sem dependências) gera a partir deles as páginas em `receitas/` e os cards do `index.html`.

```bash
python build.py          # gera os HTMLs
python build.py --check  # confere se os HTMLs estão em dia com os JSONs
```

Para adicionar uma receita, copie `data/receitas/_modelo.json`, preencha, rode o build e faça commit. Detalhes em [CLAUDE.md](CLAUDE.md).
