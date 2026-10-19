#!/usr/bin/env python3
"""Gerador estático do Tico Lab Kitchen.

Lê data/receitas/*.json (fonte de verdade) e gera:
  - receitas/<categoria>/<slug>.html
  - os cards do index.html, entre <!-- RECEITAS:INICIO --> e <!-- RECEITAS:FIM -->

Uso:
  python build.py           # gera/atualiza os HTMLs
  python build.py --check   # falha (exit 1) se algum HTML estiver desatualizado

Só biblioteca padrão. Arquivos JSON que começam com "_" (ex.: _modelo.json) são ignorados.
"""

import html
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIR_DADOS = RAIZ / "data" / "receitas"
DIR_RECEITAS = RAIZ / "receitas"
INDEX = RAIZ / "index.html"

MARCADOR_INICIO = "<!-- RECEITAS:INICIO -->"
MARCADOR_FIM = "<!-- RECEITAS:FIM -->"

# Categorias conhecidas: pasta -> chave do filtro no index, nome no card, nome na página.
# O card e a tag da página já são exibidos em maiúsculas pelo CSS.
CATEGORIAS = {
    "proteinas-e-batch-prep": {"filtro": "proteinas", "card": "Proteínas & Batch Prep", "pagina": "Proteínas e Batch Prep"},
    "massas-classicas": {"filtro": "massas", "card": "Massas Clássicas", "pagina": "Massas Clássicas"},
    "molhos-e-conservas": {"filtro": "conservas", "card": "Molhos & Conservas", "pagina": "Molhos e Conservas"},
    "paes-e-fermentacao": {"filtro": "paes", "card": "Pães & Fermentação", "pagina": "Pães e Fermentação"},
    "sobremesas": {"filtro": "sobremesas", "card": "Sobremesas", "pagina": "Sobremesas"},
}

# Campos de metadado exibidos na página, na ordem em que aparecem no JSON.
CAMPOS_META = {"prep": "Prep", "espera": "Espera", "forno": "Forno", "rendimento": "Rendimento"}
# Rótulo padrão do campo no card (pode ser sobrescrito em card_meta.rotulo).
ROTULO_CARD = {"prep": "PREP", "espera": "ESPERA", "forno": "FORNO", "rendimento": "REND"}

OBRIGATORIOS = ["slug", "categoria", "titulo", "resumo", "descricao", "prep", "ingredientes", "passos", "card_meta"]
CAMPOS_CONHECIDOS = set(OBRIGATORIOS) | set(CAMPOS_META) | {
    "ordem", "destaque", "subtitulo", "titulo_card", "tag_pagina", "titulo_processo",
    "notas", "imagem", "imagem_placeholder",
}

ESTILO_H3_INGREDIENTES = "margin-top: 1.5rem; color: var(--accent); font-size: 0.85rem; letter-spacing: 0.05em; text-transform: uppercase;"


class ErroValidacao(Exception):
    pass


# --------------------------------------------------------------------------
# Texto
# --------------------------------------------------------------------------

def esc(texto):
    """Escapa &, < e > para texto dentro de elementos."""
    return html.escape(texto, quote=False)


def esc_attr(texto):
    return html.escape(texto, quote=True)


def inline(texto):
    """Escapa e aplica ênfase mínima: **negrito** e *itálico*."""
    s = esc(texto)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s


def valor_meta(v):
    """Campo de metadado: string ou {"texto": ..., "curto": ...}."""
    return v if isinstance(v, str) else v["texto"]


def valor_card(v):
    if isinstance(v, dict) and v.get("curto"):
        return v["curto"]
    return valor_meta(v).upper()


def normaliza_card_meta(r):
    cm = r["card_meta"]
    if isinstance(cm, str):
        return cm, ROTULO_CARD[cm]
    return cm["campo"], cm.get("rotulo") or ROTULO_CARD[cm["campo"]]


# --------------------------------------------------------------------------
# Validação
# --------------------------------------------------------------------------

def _str_nao_vazia(v):
    return isinstance(v, str) and v.strip() != ""


def _valida_meta(nome, v, erros):
    if isinstance(v, str):
        if not v.strip():
            erros.append(f"campo '{nome}' está vazio")
    elif isinstance(v, dict):
        if not _str_nao_vazia(v.get("texto")):
            erros.append(f"campo '{nome}' precisa de 'texto' (string não vazia)")
        if "curto" in v and not _str_nao_vazia(v["curto"]):
            erros.append(f"campo '{nome}.curto' está vazio")
        extras = set(v) - {"texto", "curto"}
        if extras:
            erros.append(f"campo '{nome}' tem chaves desconhecidas: {sorted(extras)}")
    else:
        erros.append(f"campo '{nome}' deve ser string ou objeto {{texto, curto}}")


def _valida_lista_ou_grupos(nome, lista, valida_item, erros):
    if not isinstance(lista, list) or not lista:
        erros.append(f"'{nome}' deve ser uma lista não vazia")
        return
    agrupada = isinstance(lista[0], dict) and "grupo" in lista[0]
    for i, item in enumerate(lista, 1):
        if agrupada:
            if not (isinstance(item, dict) and _str_nao_vazia(item.get("grupo")) and isinstance(item.get("itens"), list) and item["itens"]):
                erros.append(f"'{nome}' item {i}: grupo precisa de 'grupo' e 'itens' (lista não vazia); não misture itens soltos com grupos")
                continue
            for j, sub in enumerate(item["itens"], 1):
                valida_item(f"{nome} grupo {i} item {j}", sub, erros)
        else:
            valida_item(f"{nome} item {i}", item, erros)


def _valida_ingrediente(onde, item, erros):
    if not _str_nao_vazia(item):
        erros.append(f"{onde}: ingrediente deve ser texto não vazio")


def _valida_passo(onde, item, erros):
    if not (isinstance(item, dict) and _str_nao_vazia(item.get("titulo")) and _str_nao_vazia(item.get("texto"))):
        erros.append(f"{onde}: passo deve ser {{\"titulo\": ..., \"texto\": ...}} com os dois preenchidos")


def valida(r, arquivo):
    erros = []
    if not isinstance(r, dict):
        raise ErroValidacao(f"{arquivo}: o JSON deve ser um objeto")
    for campo in OBRIGATORIOS:
        if campo not in r:
            erros.append(f"campo obrigatório ausente: '{campo}'")
    desconhecidos = set(r) - CAMPOS_CONHECIDOS
    if desconhecidos:
        erros.append(f"campos desconhecidos: {sorted(desconhecidos)}")
    for campo in ["slug", "titulo", "resumo", "descricao", "subtitulo", "titulo_card", "tag_pagina",
                  "titulo_processo", "imagem", "imagem_placeholder"]:
        if campo in r and not _str_nao_vazia(r[campo]):
            erros.append(f"campo '{campo}' deve ser texto não vazio")
    if "slug" in r and isinstance(r["slug"], str):
        if r["slug"] != arquivo.stem:
            erros.append(f"slug '{r['slug']}' difere do nome do arquivo '{arquivo.stem}'")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", r["slug"]):
            erros.append(f"slug '{r['slug']}' inválido (use minúsculas, números e hífens)")
    if "categoria" in r and r["categoria"] not in CATEGORIAS:
        erros.append(f"categoria desconhecida '{r['categoria']}'. Conhecidas: {', '.join(CATEGORIAS)}")
    for campo in CAMPOS_META:
        if campo in r:
            _valida_meta(campo, r[campo], erros)
    if "card_meta" in r:
        cm = r["card_meta"]
        campo = cm if isinstance(cm, str) else (cm.get("campo") if isinstance(cm, dict) else None)
        if campo not in CAMPOS_META:
            erros.append(f"card_meta deve apontar para um de {list(CAMPOS_META)}")
        elif campo not in r:
            erros.append(f"card_meta aponta para '{campo}', que não existe nesta receita")
        if isinstance(cm, dict) and "rotulo" in cm and not _str_nao_vazia(cm["rotulo"]):
            erros.append("card_meta.rotulo está vazio")
    if "ordem" in r and not isinstance(r["ordem"], (int, float)):
        erros.append("'ordem' deve ser número")
    if "destaque" in r and not isinstance(r["destaque"], bool):
        erros.append("'destaque' deve ser true/false")
    if "notas" in r and not (isinstance(r["notas"], list) and all(_str_nao_vazia(n) for n in r["notas"])):
        erros.append("'notas' deve ser lista de textos")
    if "ingredientes" in r:
        _valida_lista_ou_grupos("ingredientes", r["ingredientes"], _valida_ingrediente, erros)
    if "passos" in r:
        _valida_lista_ou_grupos("passos", r["passos"], _valida_passo, erros)
    if erros:
        raise ErroValidacao(f"{arquivo.relative_to(RAIZ)}:\n  - " + "\n  - ".join(erros))


def carrega_receitas():
    receitas, erros, slugs = [], [], {}
    arquivos = sorted(p for p in DIR_DADOS.glob("*.json") if not p.name.startswith("_"))
    if not arquivos:
        raise ErroValidacao(f"nenhuma receita encontrada em {DIR_DADOS.relative_to(RAIZ)}")
    for arq in arquivos:
        try:
            r = json.loads(arq.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            erros.append(f"{arq.relative_to(RAIZ)}: JSON inválido (linha {e.lineno}, coluna {e.colno}): {e.msg}")
            continue
        except UnicodeDecodeError:
            erros.append(f"{arq.relative_to(RAIZ)}: arquivo não está em UTF-8")
            continue
        try:
            valida(r, arq)
        except ErroValidacao as e:
            erros.append(str(e))
            continue
        if r["slug"] in slugs:
            erros.append(f"slug duplicado '{r['slug']}' em {arq.name} e {slugs[r['slug']]}")
            continue
        slugs[r["slug"]] = arq.name
        receitas.append(r)
    if erros:
        raise ErroValidacao("\n".join(erros))
    receitas.sort(key=lambda r: (r.get("ordem", float("inf")), r["slug"]))
    return receitas


# --------------------------------------------------------------------------
# Renderização
# --------------------------------------------------------------------------

def caminho_pagina(r):
    return f"receitas/{r['categoria']}/{r['slug']}.html"


def _grupos(lista):
    """Normaliza lista simples ou agrupada para [(grupo|None, itens)]."""
    if isinstance(lista[0], dict) and "grupo" in lista[0]:
        return [(g["grupo"], g["itens"]) for g in lista]
    return [(None, lista)]


def render_pagina(r):
    cat = CATEGORIAS[r["categoria"]]
    tag = r.get("tag_pagina", cat["pagina"])
    h1 = esc(r["titulo"])
    if r.get("subtitulo"):
        h1 += f' <span style="font-size: 0.6em; font-weight: normal; opacity: 0.8;">{esc(r["subtitulo"])}</span>'

    meta = [
        f'                <div class="meta-item"><strong>{rotulo}:</strong> {esc(valor_meta(r[campo]))}</div>'
        for campo, rotulo in ((c, CAMPOS_META[c]) for c in r if c in CAMPOS_META)
    ]

    if r.get("imagem"):
        imagem = f'            <img src="../../{esc_attr(r["imagem"])}" alt="{esc_attr(r["titulo"])}">'
    else:
        texto = r.get("imagem_placeholder", f"[Inserir foto de {r['titulo']} aqui]")
        imagem = f"            <span>{esc(texto)}</span>"

    ingr = ["                <h2>Ingredientes</h2>"]
    for grupo, itens in _grupos(r["ingredientes"]):
        if grupo:
            ingr.append("                ")
            ingr.append(f'                <h3 style="{ESTILO_H3_INGREDIENTES}">{esc(grupo)}</h3>')
        ingr.append("                <ul>")
        ingr += [f"                    <li>{inline(i)}</li>" for i in itens]
        ingr.append("                </ul>")
        if grupo:
            ingr.append("")
    if ingr[-1] == "":
        ingr.pop()

    proc = [f"                <h2>{esc(r.get('titulo_processo', 'O Processo'))}</h2>"]
    numero = 1
    for n, (grupo, itens) in enumerate(_grupos(r["passos"])):
        if grupo:
            proc.append("                ")
            estilo = ' style="margin-top: 2rem;"' if n > 0 else ""
            proc.append(f"                <h3{estilo}>{esc(grupo)}</h3>")
        start = f' start="{numero}"' if numero > 1 else ""
        proc.append(f"                <ol{start}>")
        proc += [
            f"                    <li><strong>{inline(p['titulo'])}:</strong> {inline(p['texto'])}</li>"
            for p in itens
        ]
        proc.append("                </ol>")
        numero += len(itens)
    if r.get("notas"):
        proc.append("")
        proc.append('                <h3 style="margin-top: 2rem;">Notas</h3>')
        proc += [f'                <p class="descricao">{inline(n)}</p>' for n in r["notas"]]

    linhas = [
        "<!DOCTYPE html>",
        '<html lang="pt-BR">',
        "<head>",
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"    <title>{esc(r['titulo'])} | Tico Lab Kitchen</title>",
        '    <link rel="stylesheet" href="../../css/style.css">',
        '    <link rel="icon" type="image/svg+xml" href="../../assets/favicon.svg">',
        "</head>",
        "<body>",
        "    <!-- GERADO por build.py a partir de data/receitas/" + r["slug"] + ".json. Não edite à mão. -->",
        '    <nav class="breadcrumb">',
        '        <a href="../../index.html">← Voltar para o Tico Lab Kitchen</a>',
        "    </nav>",
        "",
        '    <article class="receita-container">',
        '        <header class="receita-header">',
        f'            <span class="tag">{esc(tag)}</span>',
        f"            <h1>{h1}</h1>",
        f'            <p class="descricao">{inline(r["descricao"])}</p>',
        "            ",
        '            <div class="metadata">',
        *meta,
        "            </div>",
        "        </header>",
        "",
        "        <!-- Espaço para imagem (opcional) -->",
        '        <div class="imagem-placeholder">',
        imagem,
        "        </div>",
        "",
        '        <div class="grid-receita">',
        '            <aside class="ingredientes">',
        *ingr,
        "            </aside>",
        "",
        '            <section class="passo-a-passo">',
        *proc,
        "            </section>",
        "        </div>",
        "    </article>",
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(linhas)


def render_card(n, r):
    cat = CATEGORIAS[r["categoria"]]
    titulo = r.get("titulo_card") or (f"{r['titulo']} {r['subtitulo']}" if r.get("subtitulo") else r["titulo"])
    campo, rotulo = normaliza_card_meta(r)
    return "\n".join([
        f"            <!-- Card {n}: {esc(titulo)} -->",
        f'            <article class="recipe-card" data-category="{cat["filtro"]}">',
        '                <div class="card-header">',
        f'                    <span class="card-tag">{esc(cat["card"].upper())}</span>',
        f'                    <h3 class="card-title">{esc(titulo)}</h3>',
        "                </div>",
        '                <div class="card-body">',
        f'                    <p class="card-description">{inline(r["resumo"])}</p>',
        "                </div>",
        '                <div class="card-footer">',
        '                    <div class="card-meta">',
        f"                        <span>PREP: {esc(valor_card(r['prep']))}</span> • <span>{esc(rotulo)}: {esc(valor_card(r[campo]))}</span>",
        "                    </div>",
        f'                    <a href="{caminho_pagina(r)}" class="card-cta">',
        "                        Acessar Protocolo →",
        "                    </a>",
        "                </div>",
        "            </article>",
    ])


def render_index(receitas, atual):
    ini, fim = atual.find(MARCADOR_INICIO), atual.find(MARCADOR_FIM)
    if ini == -1 or fim == -1 or fim < ini:
        raise ErroValidacao(f"index.html: marcadores {MARCADOR_INICIO} / {MARCADOR_FIM} ausentes ou fora de ordem")
    cards = "\n\n".join(render_card(n, r) for n, r in enumerate(receitas, 1))
    bloco = (
        MARCADOR_INICIO
        + "\n            <!-- Bloco GERADO por build.py a partir de data/receitas/*.json. Não edite à mão. -->\n\n"
        + cards
        + "\n\n            "
    )
    return atual[:ini] + bloco + atual[fim:]


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def _normaliza(texto):
    return texto.replace("\r\n", "\n")


def main(argv):
    for fluxo in (sys.stdout, sys.stderr):
        fluxo.reconfigure(encoding="utf-8", errors="replace")  # acentos no console do Windows
    check = "--check" in argv[1:]
    desconhecidos = [a for a in argv[1:] if a != "--check"]
    if desconhecidos:
        print(f"argumento desconhecido: {' '.join(desconhecidos)}\nuso: python build.py [--check]", file=sys.stderr)
        return 2

    try:
        receitas = carrega_receitas()
        index_atual = INDEX.read_text(encoding="utf-8")
        alvos = {RAIZ / caminho_pagina(r): render_pagina(r) for r in receitas}
        alvos[INDEX] = render_index(receitas, index_atual)
    except ErroValidacao as e:
        print(f"ERRO de validação:\n{e}", file=sys.stderr)
        return 1

    # Páginas em receitas/ que não vêm de nenhum JSON (ex.: receita renomeada ou removida).
    orfas = sorted(p for p in DIR_RECEITAS.glob("*/*.html") if p not in alvos)

    desatualizados = []
    for caminho, conteudo in alvos.items():
        existente = _normaliza(caminho.read_text(encoding="utf-8")) if caminho.exists() else None
        if existente != conteudo:
            desatualizados.append(caminho)
            if not check:
                caminho.parent.mkdir(parents=True, exist_ok=True)
                caminho.write_text(conteudo, encoding="utf-8", newline="\n")

    rel = lambda p: p.relative_to(RAIZ).as_posix()
    if check:
        if desatualizados or orfas:
            for p in desatualizados:
                print(f"DESATUALIZADO: {rel(p)}", file=sys.stderr)
            for p in orfas:
                print(f"ÓRFÃO (sem JSON correspondente): {rel(p)}", file=sys.stderr)
            print("Rode `python build.py` e faça commit dos HTMLs gerados.", file=sys.stderr)
            return 1
        print(f"OK: {len(receitas)} receitas, todos os HTMLs estão em dia.")
        return 0

    for p in desatualizados:
        print(f"gerado: {rel(p)}")
    for p in orfas:
        print(f"AVISO: {rel(p)} não corresponde a nenhum JSON (remova se a receita foi renomeada/apagada).")
    print(f"{len(receitas)} receitas, {len(desatualizados)} arquivo(s) atualizado(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
