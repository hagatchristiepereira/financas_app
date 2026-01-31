import streamlit as st
import secrets
from auth import admin_create_user_flow
#from email_utils import send_temporary_password
from db import (
    listar_usuarios,
    excluir_usuario,
    atualizar_senha,
    log_audit,
    listar_audit_logs,
    can_delete_user,
    set_must_change_password
)


def tela_admin():
    st.header("🔧 Painel Admin — Gestão de usuários e auditoria")
    st.write("Atenção: apenas administradores podem acessar esta área. Tome cuidado ao excluir usuários.")

    # Comentado por estar em desenvolvimento. Mostra configuração SMTP aviso (se não configurado, aviso)
    #import os
    #if not os.environ.get("SMTP_HOST"):
        #st.warning("SMTP não configurado. Emails serão impressos no console (dev). Configure env vars para envio real.")

    # LISTAGEM e ações por usuário
    users = listar_usuarios()
    st.subheader("Usuários")
    if users.empty:
        st.info("Nenhum usuário cadastrado.")
    else:
        for _, u in users.iterrows():
            cols = st.columns([3, 3, 1, 1, 1])
            cols[0].markdown(f"**{u['nome']}**")
            cols[1].markdown(f"{u['email']}")
            cols[2].markdown("Admin" if u["is_admin"] else "Usuário")
            if cols[3].button("Resetar senha", key=f"reset_{u['id_usuario']}"):
                temp_pw = secrets.token_urlsafe(10)

                atualizar_senha(u["id_usuario"], temp_pw)
                set_must_change_password(u["id_usuario"], True)

                log_audit(
                    "password_reset_by_admin",
                    st.session_state.usuario["id"],
                    u["id_usuario"],
                    "Reset de senha por admin"
                    )
                st.success("Senha resetada com sucesso!")
                st.info(f"🔑 Nova senha temporária: {temp_pw}")
                st.warning("Informe essa senha ao usuário. Ele será obrigado a trocá-la no login.")

            if cols[4].button("Excluir", key=f"del_{u['id_usuario']}"):
                st.session_state[f"confirm_delete_{u['id_usuario']}"] = True

            if st.session_state.get(f"confirm_delete_{u['id_usuario']}", False):
                confirm = st.text_input(
                    f"Digite o email de {u['nome']} para confirmar exclusão",
                    key=f"conf_input_{u['id_usuario']}"
                    )

                if st.button("Confirmar exclusão", key=f"confirm_button_{u['id_usuario']}"):
                    if confirm != u["email"]:
                        st.error("Email não confere. Exclusão cancelada.")
                    else:
                        if not can_delete_user(u['id_usuario']):
                            st.error("Não é possível excluir o último administrador.")
                        else:
                            excluir_usuario(u['id_usuario'])
                            log_audit(
                                "user_deleted",
                                st.session_state.usuario['id'],
                                u['id_usuario'],
                                "Exclusão de usuário"
                            )
                            del st.session_state[f"confirm_delete_{u['id_usuario']}"]
                            st.session_state.pop(f"conf_input_{u['id_usuario']}", None)
                            st.success("Usuário excluído.")
                            st.rerun()

    st.divider()
    st.subheader("Criar novo usuário (gera senha temporária)")
    with st.form("form_novo_usuario"):
        nome = st.text_input("Nome", key="novo_nome")
        email = st.text_input("Email", key="novo_email")
        is_admin = st.checkbox("É administrador?", value=False, key="novo_is_admin")
        salvar = st.form_submit_button("Criar usuário")

        if salvar:
            if not nome or not email:
                st.warning("Preencha todos os campos")
            else:
                try:
                    temp_pw = admin_create_user_flow(
                        nome, email, is_admin, st.session_state.usuario["id"]
                    )

                    st.success("Usuário criado com sucesso!")
                    st.info(f"🔑 Senha temporária: {temp_pw}")
                    st.warning("Anote essa senha. O usuário será obrigado a trocá-la no primeiro login.")

                    # NÃO DAR rerun aqui
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e):
                        st.error("Este e-mail já está cadastrado.")
                    else:
                        st.error(f"Erro ao criar usuário: {e}")

    st.divider()
    st.subheader("Logs de auditoria (recentes)")
    logs = listar_audit_logs(limit=100)
    if logs.empty:
        st.info("Sem eventos registrados.")
    else:
        # filtros simples
        tipos = sorted(logs['event_type'].unique().tolist())
        filtro = st.selectbox("Filtrar por tipo (opcional)", ["Todos"] + tipos)
        if filtro != "Todos":
            logs = logs[logs['event_type'] == filtro]
        st.dataframe(logs)
        csv = logs.to_csv(index=False).encode('utf-8')
        st.download_button("Baixar logs (CSV)", csv, file_name="audit_logs.csv", mime="text/csv")