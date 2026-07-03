from dataclasses import dataclass, field
from typing import Any


@dataclass
class FilterRule:
    campo: str
    operador: str
    valor: str
    valor2: str = ""


@dataclass
class FilterState:
    cliente: str = ""
    comercial: str = ""
    produto: str = ""
    distrito: str = ""
    data_de: str = ""
    data_ate: str = ""
    segmento: str = "todos"
    regras: list[FilterRule] = field(default_factory=list)
    logica: str = "AND"


def _seg_sql(segmento: str) -> str:
    mapping = {
        "lt30": "dias_desde_ultima_compra < 30",
        "30_60": "dias_desde_ultima_compra BETWEEN 30 AND 60",
        "60_90": "dias_desde_ultima_compra BETWEEN 60 AND 90",
        "90_180": "dias_desde_ultima_compra BETWEEN 90 AND 180",
        "180_365": "dias_desde_ultima_compra BETWEEN 180 AND 365",
        "gt365": "dias_desde_ultima_compra > 365",
    }
    return mapping.get(segmento, "")


def _text_op(col: str, op: str, val: str) -> tuple[str, list]:
    v = val.strip()
    if not v:
        return "", []
    ops = {
        "contém": (f"{col} LIKE ?", [f"%{v}%"]),
        "igual a": (f"{col} = ?", [v]),
        "começa com": (f"{col} LIKE ?", [f"{v}%"]),
        "termina com": (f"{col} LIKE ?", [f"%{v}"]),
        "não contém": (f"{col} NOT LIKE ?", [f"%{v}%"]),
    }
    return ops.get(op, (f"{col} LIKE ?", [f"%{v}%"]))


def _num_op(col: str, op: str, val: str, val2: str = "") -> tuple[str, list]:
    try:
        n = float(val.replace(",", "."))
    except ValueError:
        return "", []
    try:
        n2 = float(val2.replace(",", ".")) if val2 else 0
    except ValueError:
        n2 = 0

    ops = {
        "=": (f"{col} = ?", [n]),
        "≠": (f"{col} != ?", [n]),
        ">": (f"{col} > ?", [n]),
        ">=": (f"{col} >= ?", [n]),
        "<": (f"{col} < ?", [n]),
        "<=": (f"{col} <= ?", [n]),
        "entre": (f"{col} BETWEEN ? AND ?", [min(n, n2), max(n, n2)]),
    }
    return ops.get(op, ("", []))


def _date_op(col: str, op: str, val: str, val2: str = "") -> tuple[str, list]:
    v = val.strip()
    if not v:
        return "", []
    ops = {
        "=": (f"date({col}) = date(?)", [v]),
        ">": (f"date({col}) > date(?)", [v]),
        ">=": (f"date({col}) >= date(?)", [v]),
        "<": (f"date({col}) < date(?)", [v]),
        "<=": (f"date({col}) <= date(?)", [v]),
        "entre": (f"date({col}) BETWEEN date(?) AND date(?)", [val, val2]),
    }
    return ops.get(op, ("", []))


NUM_FIELDS = {"dias_desde_ultima_compra", "quantidade", "valor"}
DATE_FIELDS = {"data_ultima_compra", "data_venda", "data_envio"}


def build_query(table: str, state: FilterState) -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if state.cliente:
        conditions.append("(cliente_nome LIKE ? OR cliente_codigo LIKE ?)")
        params.extend([f"%{state.cliente}%", f"%{state.cliente}%"])

    if state.comercial:
        conditions.append("comercial = ?")
        params.append(state.comercial)

    if state.produto and table in ("clientes", "vendas"):
        col = "produto_ultima" if table == "clientes" else "produto"
        conditions.append(f"{col} LIKE ?")
        params.append(f"%{state.produto}%")

    if state.distrito:
        conditions.append("distrito LIKE ? OR provincia_factura LIKE ?")
        params.extend([f"%{state.distrito}%", f"%{state.distrito}%"])

    date_col = {
        "clientes": "data_ultima_compra",
        "vendas": "data_venda",
        "emails": "data_envio",
    }.get(table, "data_ultima_compra")

    if state.data_de:
        conditions.append(f"date({date_col}) >= date(?)")
        params.append(state.data_de)
    if state.data_ate:
        conditions.append(f"date({date_col}) <= date(?)")
        params.append(state.data_ate)

    if table == "clientes" and state.segmento != "todos":
        seg = _seg_sql(state.segmento)
        if seg:
            conditions.append(seg)

    rule_parts: list[str] = []
    rule_params: list[Any] = []
    for rule in state.regras:
        if not rule.campo or not rule.valor:
            continue
        col = rule.campo
        if col in NUM_FIELDS:
            clause, p = _num_op(col, rule.operador, rule.valor, rule.valor2)
        elif col in DATE_FIELDS:
            clause, p = _date_op(col, rule.operador, rule.valor, rule.valor2)
        else:
            clause, p = _text_op(col, rule.operador, rule.valor)
        if clause:
            rule_parts.append(clause)
            rule_params.extend(p)

    if rule_parts:
        joiner = " OR " if state.logica == "OR" else " AND "
        conditions.append(f"({joiner.join(rule_parts)})")
        params.extend(rule_params)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM {table}{where} ORDER BY id"
    return sql, params
