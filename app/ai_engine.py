from collections import Counter
from datetime import datetime
from typing import Any

from app import database as db


def _risk_level(dias: int | None) -> str:
    if dias is None:
        return "desconhecido"
    if dias > 365:
        return "crítico"
    if dias > 180:
        return "alto"
    if dias > 90:
        return "médio"
    if dias > 30:
        return "baixo"
    return "ativo"


def analyze_portfolio(rows: list[dict]) -> dict[str, Any]:
    if not rows:
        return {"resumo": "Sem dados para analisar.", "insights": [], "acoes": []}

    dias_list = [r.get("dias_desde_ultima_compra") for r in rows if r.get("dias_desde_ultima_compra") is not None]
    total = len(rows)
    inativos_90 = sum(1 for d in dias_list if d > 90)
    criticos = sum(1 for d in dias_list if d > 365)
    ativos = sum(1 for d in dias_list if d <= 30)
    media_dias = sum(dias_list) / len(dias_list) if dias_list else 0

    comerciais = Counter(r.get("comercial", "") for r in rows if r.get("comercial"))
    distritos = Counter(r.get("provincia_factura") or r.get("distrito", "") for r in rows)
    top_comercial = comerciais.most_common(1)[0] if comerciais else ("N/A", 0)
    top_distrito = distritos.most_common(1)[0] if distritos else ("N/A", 0)

    pct_inativos = (inativos_90 / total * 100) if total else 0

    insights = [
        f"📊 {total} clientes analisados — {ativos} ativos (<30d), {inativos_90} inativos (>90d).",
        f"⏱️ Média de {media_dias:.0f} dias desde a última compra.",
        f"🏆 Comercial com mais clientes: {top_comercial[0]} ({top_comercial[1]}).",
        f"📍 Distrito principal: {top_distrito[0]} ({top_distrito[1]} clientes).",
    ]

    if pct_inativos > 40:
        insights.append(f"⚠️ ALERTA: {pct_inativos:.0f}% dos clientes estão inativos há mais de 90 dias.")
    if criticos > 0:
        insights.append(f"🔴 {criticos} clientes em risco crítico (>365 dias sem compra) — prioridade de reativação.")

    acoes = []
    if criticos > 0:
        acoes.append("Enviar campanha de reativação aos clientes >365 dias.")
    if inativos_90 > total * 0.3:
        acoes.append("Agendar follow-up telefónico para segmento 90-180 dias.")
    if ativos > 0:
        acoes.append("Propor cross-selling aos clientes ativos com base no último produto.")
    if not acoes:
        acoes.append("Manter acompanhamento regular — carteira saudável.")

    return {
        "resumo": f"Análise IA — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "insights": insights,
        "acoes": acoes,
        "metricas": {
            "total": total,
            "ativos": ativos,
            "inativos_90": inativos_90,
            "criticos": criticos,
            "media_dias": round(media_dias, 1),
        },
    }


def suggest_email(tipo: str, cliente: dict) -> str:
    nome = cliente.get("cliente_nome", "Cliente")
    dias = cliente.get("dias_desde_ultima_compra", 0)
    produto = cliente.get("produto_ultima", "os nossos produtos")

    templates = {
        "seguimento": (
            f"Exmo(a). Sr(a). {nome},\n\n"
            f"Esperamos que se encontre bem. Entrámos em contacto para acompanhar "
            f"a sua experiência com {produto} e saber se podemos ser úteis.\n\n"
            f"A Soretrac Portuguesa está ao seu dispor para qualquer necessidade.\n\n"
            f"Com os melhores cumprimentos,\nEquipa Comercial Soretrac"
        ),
        "proposta": (
            f"Exmo(a). Sr(a). {nome},\n\n"
            f"Temos o prazer de apresentar uma proposta personalizada com base no seu perfil "
            f"e na sua última aquisição ({produto}).\n\n"
            f"Gostaríamos de agendar uma breve conversa para apresentar as nossas "
            f"novidades e condições especiais.\n\n"
            f"Com os melhores cumprimentos,\nEquipa Comercial Soretrac"
        ),
        "reativacao": (
            f"Exmo(a). Sr(a). {nome},\n\n"
            f"Notámos que faz {dias} dias desde a sua última compra connosco. "
            f"Gostaríamos de o(a) convidar a redescobrir as soluções Soretrac.\n\n"
            f"Temos condições especiais de reativação e novos produtos que podem "
            f"interessar ao seu negócio.\n\n"
            f"Com os melhores cumprimentos,\nEquipa Comercial Soretrac"
        ),
        "xselling": (
            f"Exmo(a). Sr(a). {nome},\n\n"
            f"Com base na sua compra de {produto}, identificámos produtos complementares "
            f"que podem otimizar a sua operação.\n\n"
            f"A nossa equipa técnica pode apresentar-lhe uma solução integrada "
            f"adaptada às suas necessidades.\n\n"
            f"Com os melhores cumprimentos,\nEquipa Comercial Soretrac"
        ),
    }
    return templates.get(tipo, templates["seguimento"])


def get_churn_clients(limit: int = 20) -> list[dict]:
    return db.query(
        "SELECT * FROM clientes WHERE dias_desde_ultima_compra > 180 "
        "ORDER BY dias_desde_ultima_compra DESC LIMIT ?",
        (limit,),
    )


def score_client(cliente: dict) -> dict:
    dias = cliente.get("dias_desde_ultima_compra") or 0
    risk = _risk_level(dias)
    score = max(0, 100 - min(dias, 100))
    return {
        "cliente": cliente.get("cliente_nome", ""),
        "score": score,
        "risco": risk,
        "dias": dias,
        "acao_recomendada": {
            "crítico": "Reativação urgente + visita comercial",
            "alto": "Email reativação + chamada telefónica",
            "médio": "Email de seguimento",
            "baixo": "Proposta cross-selling",
            "ativo": "Manter relacionamento",
        }.get(risk, "Avaliar"),
    }
