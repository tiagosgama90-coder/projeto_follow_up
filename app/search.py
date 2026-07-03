"""Pesquisa inteligente unificada — sem dependências externas."""
import re
import unicodedata
from typing import Any

from app import database as db

SEARCH_FIELDS = {
    "clientes": [
        "cliente_nome", "cliente_codigo", "comercial", "cif",
        "email_factura", "cidade_factura", "provincia_factura",
        "telefone_factura", "produto_ultima", "distrito", "notas",
    ],
    "vendas": [
        "cliente_nome", "cliente_codigo", "comercial", "produto",
        "categoria", "distrito", "status",
    ],
    "emails": [
        "cliente_nome", "cliente_codigo", "email", "tipo", "assunto", "status",
    ],
}

SYNONYMS = {
    "inativo": "dias_desde_ultima_compra > 90",
    "inativos": "dias_desde_ultima_compra > 90",
    "critico": "dias_desde_ultima_compra > 365",
    "ativos": "dias_desde_ultima_compra <= 30",
    "lisboa": "provincia_factura LIKE '%lisboa%' OR cidade_factura LIKE '%lisboa%'",
    "porto": "provincia_factura LIKE '%porto%' OR cidade_factura LIKE '%porto%'",
}


def _normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _tokens(query: str) -> list[str]:
    q = _normalize(query)
    q = re.sub(r"[^\w\s@.\-]", " ", q)
    return [t for t in q.split() if len(t) >= 2]


def _score_row(row: dict, tokens: list[str], fields: list[str]) -> int:
    if not tokens:
        return 0
    score = 0
    for field in fields:
        val = _normalize(str(row.get(field, "")))
        if not val:
            continue
        for tok in tokens:
            if val == tok:
                score += 100
            elif val.startswith(tok):
                score += 60
            elif tok in val:
                score += 30
            # Telefone: ignorar espaços e hífens
            if field.endswith("telefone") or field == "cif":
                clean = re.sub(r"[\s\-+]", "", val)
                clean_tok = re.sub(r"[\s\-+]", "", tok)
                if clean_tok and clean_tok in clean:
                    score += 50
    return score


def smart_search(query: str, table: str = "clientes", limit: int = 1000) -> list[dict]:
    query = query.strip()
    if not query:
        return db.query(f"SELECT * FROM {table} ORDER BY id LIMIT ?", (limit,))

    norm_q = _normalize(query)
    fields = SEARCH_FIELDS.get(table, SEARCH_FIELDS["clientes"])

    # Atalhos em linguagem natural
    for key, sql_extra in SYNONYMS.items():
        if key in norm_q and table == "clientes":
            rows = db.query(f"SELECT * FROM {table} WHERE {sql_extra} ORDER BY id LIMIT ?", (limit,))
            if rows:
                return rows

    tokens = _tokens(query)
    if not tokens:
        return []

    # Pesquisa SQL ampla
    conditions = []
    params: list[Any] = []
    for field in fields:
        for tok in tokens:
            conditions.append(f"{field} LIKE ?")
            params.append(f"%{tok}%")

    where = " OR ".join(conditions)
    sql = f"SELECT * FROM {table} WHERE ({where}) LIMIT ?"
    params.append(limit * 3)
    rows = db.query(sql, tuple(params))

    # Ordenar por relevância
    scored = [( _score_row(r, tokens, fields), r) for r in rows]
    scored.sort(key=lambda x: x[0], reverse=True)
    seen_ids = set()
    result = []
    for score, row in scored:
        if score <= 0:
            continue
        rid = row.get("id")
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        result.append(row)
        if len(result) >= limit:
            break
    return result


def search_suggestions(query: str, table: str = "clientes") -> list[str]:
    """Sugestões rápidas enquanto o utilizador escreve."""
    if len(query) < 2:
        return []
    tokens = _tokens(query)
    if not tokens:
        return []
    tok = tokens[0]
    suggestions = []
    for field in ("cliente_nome", "comercial", "produto_ultima", "produto", "cidade_factura"):
        if field not in SEARCH_FIELDS.get(table, []):
            continue
        try:
            rows = db.query(
                f"SELECT DISTINCT {field} as v FROM {table} "
                f"WHERE {field} LIKE ? AND {field} != '' LIMIT 5",
                (f"%{tok}%",),
            )
            for r in rows:
                v = r.get("v", "")
                if v and v not in suggestions:
                    suggestions.append(v)
        except Exception:
            pass
        if len(suggestions) >= 6:
            break
    return suggestions[:6]
