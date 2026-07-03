import csv
import io
from pathlib import Path
from typing import Any

from app import database as db

CLIENTES_MAP = {
    "cliente_codigo": ["cliente_codigo", "codigo", "cod_cliente", "id_cliente"],
    "cliente_nome": ["cliente_nome", "nome", "cliente", "nome_cliente"],
    "comercial": ["comercial", "vendedor", "representante"],
    "cif": ["cif", "nif", "contribuinte"],
    "email_factura": ["email_factura", "email", "e-mail"],
    "cidade_factura": ["cidade_factura", "cidade", "localidade"],
    "provincia_factura": ["provincia_factura", "provincia", "distrito"],
    "telefone_factura": ["telefone_factura", "telefone", "tel", "telemovel"],
    "data_ultima_compra": ["data_ultima_compra", "ultima_compra", "data_compra"],
    "dias_desde_ultima_compra": ["dias_desde_ultima_compra", "dias", "dias_inativo"],
    "produto_ultima": ["produto_ultima", "produto", "ultimo_produto"],
    "distrito": ["distrito", "regiao"],
    "notas": ["notas", "observacoes", "obs"],
}

VENDAS_MAP = {
    "cliente_codigo": ["cliente_codigo", "codigo", "cod_cliente"],
    "cliente_nome": ["cliente_nome", "nome", "cliente"],
    "comercial": ["comercial", "vendedor"],
    "produto": ["produto", "artigo", "referencia"],
    "quantidade": ["quantidade", "qtd", "qty"],
    "valor": ["valor", "total", "montante", "preco"],
    "data_venda": ["data_venda", "data", "date"],
    "distrito": ["distrito", "regiao"],
    "categoria": ["categoria", "familia", "tipo"],
    "status": ["status", "estado"],
}

EMAILS_MAP = {
    "cliente_codigo": ["cliente_codigo", "codigo"],
    "cliente_nome": ["cliente_nome", "nome", "cliente"],
    "email": ["email", "e-mail"],
    "tipo": ["tipo", "type"],
    "data_envio": ["data_envio", "data", "date"],
    "assunto": ["assunto", "subject"],
    "status": ["status", "estado"],
}

TABLE_CONFIG = {
    "clientes": {"map": CLIENTES_MAP, "table": "clientes"},
    "vendas": {"map": VENDAS_MAP, "table": "vendas"},
    "emails": {"map": EMAILS_MAP, "table": "emails"},
}


def _normalize_header(h: str) -> str:
    return h.strip().lower().replace(" ", "_").replace("-", "_")


def _detect_mapping(headers: list[str], field_map: dict) -> dict[str, str]:
    norm = {_normalize_header(h): h for h in headers}
    result: dict[str, str] = {}
    for target, aliases in field_map.items():
        for alias in aliases:
            if alias in norm:
                result[target] = norm[alias]
                break
    return result


def read_csv_file(path: Path, encoding: str = "utf-8-sig") -> tuple[list[str], list[dict]]:
    text = path.read_text(encoding=encoding, errors="replace")
    return parse_csv_text(text)


def parse_csv_text(text: str) -> tuple[list[str], list[dict]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return [], []
    headers = [h.strip() for h in reader.fieldnames if h]
    rows = []
    for raw in reader:
        row = {h: (raw.get(h) or "").strip() for h in headers}
        if any(row.values()):
            rows.append(row)
    return headers, rows


def import_csv(path: Path, table_key: str, db_path: Path | None = None, replace: bool = True) -> dict:
    cfg = TABLE_CONFIG[table_key]
    headers, rows = read_csv_file(path)
    if not rows:
        return {"ok": False, "error": "Ficheiro CSV vazio ou inválido.", "imported": 0}

    mapping = _detect_mapping(headers, cfg["map"])
    if not mapping:
        return {
            "ok": False,
            "error": f"Não foi possível mapear colunas do CSV para {table_key}.",
            "imported": 0,
        }

    mapped_rows: list[dict[str, Any]] = []
    for raw in rows:
        item: dict[str, Any] = {}
        for target, source in mapping.items():
            val = raw.get(source, "")
            if target == "dias_desde_ultima_compra":
                try:
                    item[target] = int(float(str(val).replace(",", "."))) if val else None
                except ValueError:
                    item[target] = None
            elif target in ("quantidade", "valor"):
                try:
                    item[target] = float(str(val).replace(",", ".").replace("€", "").strip()) if val else 0
                except ValueError:
                    item[target] = 0
            else:
                item[target] = val
        mapped_rows.append(item)

    columns = list(mapping.keys())
    if replace:
        db.clear_table(cfg["table"], db_path)
    count = db.insert_rows(cfg["table"], columns, mapped_rows, db_path)
    from datetime import datetime
    db.set_meta("atualizado_em", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), db_path)
    return {"ok": True, "imported": count, "columns": columns, "mapping": mapping}


def export_csv(path: Path, table: str, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    columns = list(rows[0].keys())
    if "id" in columns:
        columns.remove("id")
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def auto_detect_table(headers: list[str]) -> str:
    norm = {_normalize_header(h) for h in headers}
    scores = {}
    for key, cfg in TABLE_CONFIG.items():
        score = 0
        for aliases in cfg["map"].values():
            if any(a in norm for a in aliases):
                score += 1
        scores[key] = score
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "clientes"
