import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import get_db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_codigo TEXT,
    cliente_nome TEXT,
    comercial TEXT,
    cif TEXT,
    email_factura TEXT,
    cidade_factura TEXT,
    provincia_factura TEXT,
    telefone_factura TEXT,
    data_ultima_compra TEXT,
    dias_desde_ultima_compra INTEGER,
    produto_ultima TEXT,
    distrito TEXT,
    notas TEXT
);

CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_codigo TEXT,
    cliente_nome TEXT,
    comercial TEXT,
    produto TEXT,
    quantidade REAL,
    valor REAL,
    data_venda TEXT,
    distrito TEXT,
    categoria TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_codigo TEXT,
    cliente_nome TEXT,
    email TEXT,
    tipo TEXT,
    data_envio TEXT,
    assunto TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
"""


@contextmanager
def connect(db_path: Path | None = None):
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR REPLACE INTO meta (chave, valor) VALUES (?, ?)",
            ("atualizado_em", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def set_meta(chave: str, valor: str, db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (chave, valor) VALUES (?, ?)",
            (chave, valor),
        )


def get_meta(chave: str, default: str = "", db_path: Path | None = None) -> str:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT valor FROM meta WHERE chave = ?", (chave,)
        ).fetchone()
    return row["valor"] if row else default


def get_atualizado_em(db_path: Path | None = None) -> str:
    return get_meta("atualizado_em", "N/A", db_path)


def clear_table(table: str, db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute(f"DELETE FROM {table}")


def insert_rows(table: str, columns: list[str], rows: list[dict], db_path: Path | None = None) -> int:
    if not rows:
        return 0
    cols = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    values = [tuple(row.get(c) for c in columns) for row in rows]
    with connect(db_path) as conn:
        conn.executemany(sql, values)
    return len(values)


def query(sql: str, params: tuple = (), db_path: Path | None = None) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def get_distinct(table: str, column: str, db_path: Path | None = None) -> list[str]:
    sql = f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}"
    rows = query(sql, db_path=db_path)
    return [r[column] for r in rows]


def count_table(table: str, db_path: Path | None = None) -> int:
    row = query(f"SELECT COUNT(*) as n FROM {table}", db_path=db_path)
    return row[0]["n"] if row else 0


def get_stats(db_path: Path | None = None) -> dict:
    clientes = count_table("clientes", db_path)
    vendas = count_table("vendas", db_path)
    emails = count_table("emails", db_path)
    inativos = query(
        "SELECT COUNT(*) as n FROM clientes WHERE dias_desde_ultima_compra > 90",
        db_path=db_path,
    )[0]["n"]
    return {
        "clientes": clientes,
        "vendas": vendas,
        "emails": emails,
        "inativos_90d": inativos,
    }
