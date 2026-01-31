import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from logger_config import logger

# ================= CONFIG =================
st.set_page_config(page_title="Minha Renda", layout="wide")

# ================= ENV =================
load_dotenv()

from auth import tela_login, tela_mudar_senha
from db import (
    criar_tabela_usuarios,
    criar_tabelas,
    carregar_gastos,
    carregar_rendas,
    inserir_gasto,
    inserir_renda,
    atualizar_gasto,
    atualizar_renda,
    dump_db_bytes,
)
from logic import (
    classificacao_base_df,
    gerar_resumo,
    gerar_evolucao_mensal
)
from admin import tela_admin

# ================= BANCO =================
criar_tabela_usuarios()
criar_tabelas()

# ================= AUTH =================
if "usuario" not in st.session_state:
    tela_login()
    st.stop()

if st.session_state.usuario.get("must_change_password", False):
    tela_mudar_senha()
    st.stop()

id_usuario = st.session_state.usuario["id"]
is_admin = st.session_state.usuario.get("is_admin", False)

# ================= CACHE =================
@st.cache_data(ttl=30)
def _carregar_gastos(id_u):
    return carregar_gastos(id_u)

@st.cache_data(ttl=30)
def _carregar_rendas(id_u):
    return carregar_rendas(id_u)

if "gastos" not in st.session_state:
    st.session_state.gastos = _carregar_gastos(id_usuario)

if "rendas" not in st.session_state:
    st.session_state.rendas = _carregar_rendas(id_usuario)

# ================= SIDEBAR =================
st.sidebar.markdown(f"👤 **Usuário:** {st.session_state.usuario['nome']}")

if is_admin:
    if "show_admin" not in st.session_state:
        st.session_state.show_admin = False
    if st.sidebar.button("Painel Admin"):
        st.session_state.show_admin = not st.session_state.show_admin
        st.rerun()

if st.sidebar.button("Sair"):
    st.session_state.clear()
    st.rerun()

if is_admin and st.session_state.get("show_admin", False):
    tela_admin()
    st.stop()

# ================= UI =================
st.title("💰 Minha Renda")

aba_renda, aba_gasto, aba_dashboard, aba_registros = st.tabs(
    ["💵 Nova Renda", "➕ Novo Gasto", "📊 Dashboard", "📋 Registros"]
)

# ================= FILTROS =================
with st.sidebar.expander("📅 Período / Filtros", expanded=True):
    mes = st.selectbox(
        "Mês",
        list(range(1, 13)),
        format_func=lambda x: [
            "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
            "Jul", "Ago", "Set", "Out", "Nov", "Dez"
        ][x - 1]
    )

    anos_disponiveis = (
        sorted(st.session_state.rendas["ano"].dropna().astype(int).unique())
        if not st.session_state.rendas.empty
        else [pd.Timestamp.now().year]
    )

    ano = st.selectbox("Ano", anos_disponiveis)
    visao = st.radio("Tipo de visão", ["Mensal", "Anual"])

    if st.button("Aplicar filtros"):
        st.session_state.mes = mes
        st.session_state.ano = ano
        st.session_state.visao = visao
        _carregar_gastos.clear()
        _carregar_rendas.clear()
        st.session_state.gastos = _carregar_gastos(id_usuario)
        st.session_state.rendas = _carregar_rendas(id_usuario)
        st.rerun()

mes = st.session_state.get("mes", 1)
ano = st.session_state.get("ano", anos_disponiveis[0])
visao = st.session_state.get("visao", "Mensal")

# ================= ABA RENDA =================
with aba_renda:
    st.subheader("💵 Nova renda")

    with st.form("form_renda"):
        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor (R$)", min_value=0.0, step=50.0)
        salvar = st.form_submit_button("Salvar")

        if salvar:
            if not descricao or valor <= 0:
                st.warning("Preencha todos os campos")
            else:
                inserir_renda(id_usuario, descricao, valor, mes, ano)
                _carregar_rendas.clear()
                st.session_state.rendas = _carregar_rendas(id_usuario)
                st.success("Renda adicionada!")
                st.rerun()

# ================= ABA GASTO =================
with aba_gasto:
    st.subheader("➕ Novo gasto")

    with st.form("form_gasto"):
        classificacao = st.selectbox(
            "Classificação",
            classificacao_base_df["nome"]
        )

        id_classificacao = int(
            classificacao_base_df.loc[
                classificacao_base_df["nome"] == classificacao,
                "id_classificacao"
            ].iloc[0]
        )

        categorias_existentes = (
            st.session_state.gastos
            .query("id_classificacao == @id_classificacao")["categoria"]
            .dropna()
            .unique()
            .tolist()
            if not st.session_state.gastos.empty
            else []
        )

        categoria_sel = st.selectbox(
            "Categoria",
            ["Nova categoria..."] + categorias_existentes
        )

        if categoria_sel == "Nova categoria...":
            categoria = st.text_input("Nome da nova categoria")
        else:
            categoria = categoria_sel

        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor (R$)", min_value=0.0, step=1.0)

        salvar = st.form_submit_button("Salvar")

        if salvar:
            if not categoria or not descricao or valor <= 0:
                st.warning("Preencha todos os campos")
            else:
                inserir_gasto(
                    id_usuario,
                    id_classificacao,
                    categoria,
                    descricao,
                    valor,
                    mes,
                    ano
                )
                _carregar_gastos.clear()
                st.session_state.gastos = _carregar_gastos(id_usuario)
                st.success("Gasto adicionado!")
                st.rerun()

# ================= DASHBOARD =================
with aba_dashboard:
    st.subheader("📊 Dashboard")

    renda_total, resumo_df = gerar_resumo(
        st.session_state.rendas,
        st.session_state.gastos,
        classificacao_base_df,
        visao,
        mes,
        ano,
        id_usuario
    )

    if resumo_df.empty:
        st.info("Sem dados no período")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("💵 Renda", f"R$ {renda_total:,.2f}")
        col2.metric("📉 Gastos", f"R$ {resumo_df['valor'].sum():,.2f}")
        saldo = renda_total - resumo_df["valor"].sum()
        col3.metric("💰 Saldo", f"R$ {saldo:,.2f}")

        resumo_sorted = resumo_df.sort_values("real_pct", ascending=False)
        fig = px.bar(
            resumo_sorted,
            x="valor",
            y="nome",
            orientation="h",
            color="status",
            color_discrete_map={
                "Abaixo do ideal": "green",
                "Dentro do ideal": "gold",
                "Acima do ideal": "crimson",
            },
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📈 Evolução mensal")
    evolucao = gerar_evolucao_mensal(
        st.session_state.gastos,
        st.session_state.rendas,
        ano
    )
    fig2 = px.line(
        evolucao,
        x="mes_nome",
        y=["Renda", "Gastos", "Saldo"],
        markers=True
    )
    st.plotly_chart(fig2, use_container_width=True)

# ================= REGISTROS =================
with aba_registros:
    st.subheader("📋 Rendas")
    if not st.session_state.rendas.empty:
        edited_rendas = st.data_editor(
            st.session_state.rendas[["id", "descricao", "valor"]],
            num_rows="dynamic",
            use_container_width=True,
        )
        if st.button("Aplicar alterações em rendas"):
            for _, row in edited_rendas.iterrows():
                atualizar_renda(row["id"], row["descricao"], float(row["valor"]))
            _carregar_rendas.clear()
            st.session_state.rendas = _carregar_rendas(id_usuario)
            st.success("Alterações aplicadas.")

    st.divider()

    st.subheader("📋 Gastos")
    if not st.session_state.gastos.empty:
        edited_gastos = st.data_editor(
            st.session_state.gastos[["id", "categoria", "descricao", "valor"]],
            num_rows="dynamic",
            use_container_width=True,
        )
        if st.button("Aplicar alterações em gastos"):
            for _, row in edited_gastos.iterrows():
                atualizar_gasto(row["id"], row["descricao"], float(row["valor"]))
            _carregar_gastos.clear()
            st.session_state.gastos = _carregar_gastos(id_usuario)
            st.success("Alterações aplicadas.")

    st.divider()

    st.subheader("Exportar / Backup")
    if st.button("Baixar backup do DB"):
        db_bytes = dump_db_bytes()
        st.download_button(
            "Download DB",
            db_bytes,
            file_name="database.db",
            mime="application/octet-stream"
        )
