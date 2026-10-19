# Tico Lab Kitchen — guia para agentes e colaboradores

Site estático de receitas (GitHub Pages). Não há framework nem dependências: só HTML, um CSS e um gerador em Python (stdlib).

## Estrutura

```
data/receitas/<slug>.json   ← FONTE DE VERDADE de cada receita
data/receitas/_modelo.json  ← modelo para novas receitas (ignorado pelo build)
build.py                    ← gerador (python build.py / python build.py --check)
index.html                  ← página inicial; os cards e o total de receitas do hero são gerados
receitas/<categoria>/<slug>.html  ← páginas GERADAS (commitadas, pois o site é estático)
css/style.css               ← único CSS do site
assets/                     ← logo-mark.svg (emblema T, usado no cabeçalho e hero), logo.svg (marca completa, uso externo) e favicon.svg
```

## Regras

1. **O JSON é a fonte de verdade.** Qualquer mudança de conteúdo de receita é feita em `data/receitas/<slug>.json`.
2. **Os HTMLs de receita são gerados. Não edite à mão** `receitas/**/*.html` nem o trecho do `index.html` entre `<!-- RECEITAS:INICIO -->` e `<!-- RECEITAS:FIM -->` (nem o número entre `<!-- RECEITAS:TOTAL -->` e `<!-- /RECEITAS:TOTAL -->` no hero). O que estiver fora dos marcadores no `index.html` (hero, filtros, "DNA do Lab", rodapé) é editado à mão normalmente.
3. **Nunca invente nem "melhore" conteúdo culinário** (quantidades, tempos, temperaturas, proporções, rendimentos, passos). Se algo parecer errado ou divergente, aponte e pergunte ao dono do repo; não escolha sozinho.
4. O HTML gerado usa as classes do `style.css`. O cabeçalho da marca é o mesmo no index e nas receitas (mudou um, mude o outro no `build.py`). Os cards do index são inteiros clicáveis via `.card-cta::after`; não aplique `transform` no `.card-cta` (quebra a área clicável), anime só a `.cta-arrow`.
5. Sempre rode `python build.py --check` antes de commitar. Ele falha se algum HTML estiver desatualizado em relação aos JSONs ou se existir página em `receitas/` sem JSON correspondente.

## Fluxo: nova receita

1. Copie `data/receitas/_modelo.json` para `data/receitas/<slug>.json` (o nome do arquivo deve ser igual ao `slug`).
2. Preencha os campos com o conteúdo real da receita.
3. `python build.py` — gera a página e o card.
4. `python build.py --check` — deve terminar com `OK`.
5. Confira no navegador e faça commit do JSON **e** dos HTMLs gerados.

## Campos do JSON

| Campo | Obrigatório | Descrição |
|---|---|---|
| `slug` | sim | Igual ao nome do arquivo. Minúsculas, números e hífens. |
| `categoria` | sim | Uma das pastas em `CATEGORIAS` no `build.py`: `proteinas-e-batch-prep`, `massas-classicas`, `molhos-e-conservas`, `paes-e-fermentacao`, `sobremesas`. Para criar categoria nova, adicione-a em `CATEGORIAS` e o botão de filtro no `index.html`. |
| `titulo` | sim | Título da página (e do card). |
| `subtitulo` | não | Complemento menor ao lado do título, ex.: `(Tipo Flã)`. O card mostra `titulo + subtitulo`. |
| `resumo` | sim | Texto do card no index. |
| `descricao` | sim | Texto de abertura da página. |
| `prep`, `espera`, `forno`, `rendimento` | `prep` sim | Metadados da página. Cada um é um texto (`"40 min"`) ou `{"texto": "48h (cura mínima)", "curto": "48H"}`. **A ordem em que aparecem no JSON é a ordem na página.** Convenção: `prep` = tempo de trabalho ativo; `espera` = tempo passivo total (descansos, fermentação, geladeira); `forno` = tempo de cocção. Card e página saem dos mesmos campos, então não podem divergir. |
| `card_meta` | sim | Qual metadado aparece no card ao lado do PREP: `"espera"` ou `{"campo": "rendimento", "rotulo": "LOTE"}`. No card, o valor é o `curto` (se houver) ou o `texto` em maiúsculas. |
| `ingredientes` | sim | Lista de textos, ou lista de grupos `{"grupo": "Massa", "itens": [...]}`. |
| `titulo_processo` | não | Título da seção de passos (padrão: `O Processo`). |
| `passos` | sim | Lista de `{"titulo", "texto"}`, ou grupos `{"grupo": "Dia 1", "itens": [...]}` (a numeração continua entre grupos). Prefira durações ("deixe descansar 1 hora", "dobras a cada 30 min") a horários de relógio. |
| `notas` | não | Lista de observações exibidas após os passos. |
| `imagem` | não | Caminho a partir da raiz, ex.: `assets/fotos/pudim.jpg`. Sem ele, a página não exibe bloco de foto. |
| `imagem_placeholder` | não | Lembrete de qual foto tirar; não é exibido no site. |
| `ordem` | não | Ordem do card no index (menor primeiro). |
| `destaque` | não | `true`/`false`, reservado para uso futuro. |

Textos são escapados automaticamente (`<65°C`, `>230°C` e `&` podem ser escritos literalmente). Para ênfase, use `**negrito**` e `*itálico*`; HTML cru não é aceito.

## Observações técnicas

- O repo usa `core.autocrlf`; o `build.py` grava com LF e o `--check` ignora diferença CRLF/LF.
- Para ver o site localmente: `python -m http.server` na raiz e abra `http://localhost:8000`.
