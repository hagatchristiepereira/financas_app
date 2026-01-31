import string
import streamlit as st
import secrets
#from email_utils import send_temporary_password
from db import (
    autenticar_usuario,
    record_login_attempt,
    count_failed_attempts_recent,
    log_audit,
    atualizar_senha,
    set_must_change_password,
    criar_usuario as db_criar_usuario,
)

MAX_FAILED = 5
LOCKOUT_MINUTES = 15

def tela_login():
    st.title("Login")

    login, cadastro = st.tabs(["Entrar", "Cadastrar"])

    with login:
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            failures = count_failed_attempts_recent(email, minutes=LOCKOUT_MINUTES)
            if failures >= MAX_FAILED:
                st.error("Muitas tentativas falhas. Tente novamente mais tarde.")
            else:
                user = autenticar_usuario(email, senha)
                record_login_attempt(email, success=bool(user))
                if user:
                    st.session_state.usuario = {
                        "id": user[0],
                        "nome": user[1],
                        "is_admin": bool(user[2]),
                        "must_change_password": bool(user[3])
                    }
                    log_audit("login_success", user[0], user[0], f"Login bem-sucedido para {email}")
                    st.rerun()
                else:
                    log_audit("login_failed", None, None, f"Falha de login para {email}")
                    st.error("Credenciais inválidas.")

    with cadastro:
        st.info("Cadastro cria usuário padrão (sem permissões de admin).")
        nome = st.text_input("Nome")
        email = st.text_input("Email", key="c_email")
        senha = st.text_input("Senha", type="password", key="c_senha")

        estado_civil = st.selectbox(
            "Estado civil",
            ["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)"]
        )

        if st.button("Cadastrar"):
            if not nome or not email or not senha:
                st.warning("Preencha todos os campos.")
            else:
                try:
                    senha_temp = ''.join(
                    secrets.choice(string.ascii_letters + string.digits)
                    for _ in range(8)
                    )
                    db_criar_usuario(
                        nome, email, senha,
                        estado_civil=estado_civil,
                        is_admin=False,
                        must_change_password=False
                    )
                    log_audit(
                    "user_created_self",
                    None,
                    None,
                    f"Usuário criado via auto-cadastro: {email}"
                    )

                    st.success("Usuário criado com sucesso!")
                    st.rerun()

                except Exception as e:
                    if "UNIQUE constraint failed" in str(e):
                        st.error("Este e-mail já está cadastrado.")
                    else:
                        st.error(f"Erro ao criar usuário: {e}")

def tela_mudar_senha():
    """
    Tela que força o usuário a trocar a senha se must_change_password=True.
    """
    st.header("Trocar senha obrigatória")
    st.write("Por segurança, você precisa trocar a senha antes de continuar.")
    nova = st.text_input("Nova senha", type="password", key="nova_senha_forcada")
    confirma = st.text_input("Confirme a nova senha", type="password", key="conf_nova_senha")
    if st.button("Alterar senha"):
        if not nova or nova != confirma:
            st.warning("Senhas não conferem.")
        else:
            user_id = st.session_state.usuario["id"]
            atualizar_senha(user_id, nova)
            set_must_change_password(user_id, False)
            log_audit("password_changed", user_id, user_id, "Troca de senha obrigatória concluída")
            st.success("Senha alterada com sucesso.")
            st.session_state.usuario["must_change_password"] = False
            st.rerun()

def admin_create_user_flow(nome: str, email: str, is_admin: bool, actor_id: int):
    """
    Cria usuário gerando senha temporária, marca must_change_password e envia e-mail.
    Retorna senha temporária.
    """
    temp_pw = secrets.token_urlsafe(10)
    db_criar_usuario(nome, email, temp_pw, is_admin=is_admin, must_change_password=True)
    #send_temporary_password(email, temp_pw, nome)
    log_audit("user_created_by_admin", actor_id, None, f"Usuário {email} criado por admin {actor_id}")
    return temp_pw