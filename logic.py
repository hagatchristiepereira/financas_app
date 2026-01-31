import pandas as pd
from db import normalizar_int

# ================= DATAFRAMES BASE =================

classificacao_base_df = pd.DataFrame([
    {"id_classificacao": 1, "codigo": "CFE", "nome": "Custos fixos", "ideal_pct": 0.50, "ativa": True},
    {"id_classificacao": 2, "codigo": "DZM", "nome": "Dízimo", "ideal_pct": 0.10, "ativa": True},
    {"id_classificacao": 3, "codigo": "ROS", "nome": "Reserva", "ideal_pct": 0.10, "ativa": True},
    {"id_classificacao": 4, "codigo": "ILF", "nome": "Investimentos", "ideal_pct": 0.10, "ativa": True},
    {"id_classificacao": 5, "codigo": "EDC", "nome": "Educação", "ideal_pct": 0.10, "ativa": True},
    {"id_classificacao": 6, "codigo": "LEN", "nome": "Lazer", "ideal_pct": 0.10, "ativa": True},
    ])

# ================= FUNÇÕES AUXILIARES =================

def calcular_renda_total(rendas_df, visao, mes, ano, id_usuario):
    if rendas_df.empty:
        return 0.0

    if visao == "Mensal":
        return rendas_df.query(
            "mes == @mes and ano == @ano and id_usuario == @id_usuario"
            )["valor"].sum()

    return rendas_df.query(
        "ano == @ano and id_usuario == @id_usuario"
        )["valor"].sum()


def aplicar_indicadores(resumo):
    resumo["real_pct"] = resumo["real_pct"].fillna(0)
    resumo["pct_barra"] = resumo["real_pct"].clip(upper=1.5)

    resumo["status"] = pd.cut(
        resumo["real_pct"],
        bins=[-1, 0.9, 1.1, 100],
        labels=["Abaixo do ideal", "Dentro do ideal", "Acima do ideal"]
        )

    resumo["icone"] = pd.cut(
        resumo["real_pct"],
        bins=[-1, 0.9, 1.1, 100],
        labels=["🟢", "🟡", "🔴"]
        )

    return resumo


# ================= RESUMOS =================

def resumo_mensal_classificacao(
    rendas_df,
    gastos_df,
    classificacao_df,
    mes,
    ano,
    id_usuario
    ):
    renda_total = calcular_renda_total(
        rendas_df, "Mensal", mes, ano, id_usuario
        )

    gastos_mes = gastos_df.query(
        "mes == @mes and ano == @ano and id_usuario == @id_usuario"
        )

    gastos_df = normalizar_int(gastos_df, ["id_classificacao", "mes", "ano"])
    classificacao_df = normalizar_int(classificacao_df, ["id_classificacao"])

    resumo = (
        gastos_mes
        .groupby("id_classificacao", as_index=False)["valor"]
        .sum()
        .merge(classificacao_df, on="id_classificacao", how="right")
        .fillna({"valor": 0})
        )

    resumo["valor_ideal"] = resumo["ideal_pct"] * renda_total
    resumo["real_pct"] = resumo["valor"] / renda_total if renda_total > 0 else 0

    resumo = aplicar_indicadores(resumo)
    return renda_total, resumo


def resumo_anual_classificacao(
    rendas_df,
    gastos_df,
    classificacao_df,
    ano,
    id_usuario
    ):
    renda_total = calcular_renda_total(
        rendas_df, "Anual", None, ano, id_usuario
        )

    gastos_ano = gastos_df.query(
        "ano == @ano and id_usuario == @id_usuario"
        )

    resumo = (
        gastos_ano
        .groupby("id_classificacao", as_index=False)["valor"].sum()
        .merge(classificacao_df, on="id_classificacao", how="right")
        .fillna({"valor": 0})
        )

    resumo["valor_ideal"] = resumo["ideal_pct"] * renda_total
    resumo["real_pct"] = resumo["valor"] / renda_total if renda_total > 0 else 0

    resumo = aplicar_indicadores(resumo)
    return renda_total, resumo


# ================= ORQUESTRADOR =================

def gerar_resumo(
    rendas_df,
    gastos_df,
    classificacao_df,
    visao,
    mes,
    ano,
    id_usuario
    ):
    if visao == "Mensal":
        return resumo_mensal_classificacao(
            rendas_df,
            gastos_df,
            classificacao_df,
            mes,
            ano,
            id_usuario
            )

    return resumo_anual_classificacao(
        rendas_df,
        gastos_df,
        classificacao_df,
        ano,
        id_usuario
        )


def gerar_evolucao_mensal(gastos_df, rendas_df, ano):
    gastos = (
        gastos_df[gastos_df["ano"] == ano]
        .groupby("mes")["valor"]
        .sum()
        .reset_index(name="Gastos")
        )

    rendas = (
        rendas_df[rendas_df["ano"] == ano]
        .groupby("mes")["valor"]
        .sum()
        .reset_index(name="Renda")
        )

    df = gastos.merge(rendas, on="mes", how="outer").fillna(0)
    df["Saldo"] = df["Renda"] - df["Gastos"]

    df["mes_nome"] = df["mes"].apply(
        lambda x: [
            "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
            "Jul", "Ago", "Set", "Out", "Nov", "Dez"
        ][x - 1]
        )

    return df