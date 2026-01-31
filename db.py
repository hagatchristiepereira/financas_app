import sqlite3
import pandas as pd
import numpy as np
import bcrypt
import hashlib
import string
import os
from typing import Optional, Tuple


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "financas.db")

def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


# ---------------- SCHEMA / TABELAS ----------------

def criar_tabela_usuarios():
    with conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha BLOB NOT NULL,
                estado_civil TEXT,
                is_admin INTEGER DEFAULT 0,
                must_change_password INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success INTEGER,
                ip TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                actor_id INTEGER,
                target_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bootstrap dev admin only if no users
        cur = conn.execute("SELECT COUNT(1) FROM usuarios")
        count = cur.fetchone()[0]
        if count == 0:
            default_email = os.environ.get("DEV_ADMIN_EMAIL", "admin@example.com")
            default_name = os.environ.get("DEV_ADMIN_NAME", "Admin")
            default_password = os.environ.get("DEV_ADMIN_PW", "admin")
            hashed = bcrypt.hashpw(default_password.encode("utf-8"), bcrypt.gensalt())
            conn.execute(
                "INSERT INTO usuarios (nome, email, senha, is_admin, must_change_password) VALUES (?,?,?,?,1)",
                (default_name, default_email, hashed, 1)
            )
            print(f"[BOOTSTRAP] Usuário admin criado: {default_email} / senha: {default_password} (troque imediatamente)")

def criar_tabelas():
    """Cria tabelas de rendas/gastos caso não existam."""
    with conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rendas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_usuario INTEGER,
                descricao TEXT,
                valor REAL,
                mes INTEGER,
                ano INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_usuario INTEGER,
                id_classificacao INTEGER,
                categoria TEXT,
                descricao TEXT,
                valor REAL,
                mes INTEGER,
                ano INTEGER
            )
        """)

# ---------------- USUÁRIOS / AUTENTICAÇÃO ----------------

def criar_usuario(
    nome: str,
    email: str,
    senha: str,
    estado_civil: Optional[str] = None,
    is_admin: bool = False,
    must_change_password: bool = False
):
    hashed = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO usuarios
            (nome, email, senha, estado_civil, is_admin, must_change_password)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nome, email, hashed, estado_civil, 1 if is_admin else 0, 1 if must_change_password else 0)
        )

def get_user_by_email(email: str) -> Optional[Tuple]:
    with conectar() as conn:
        cur = conn.execute("SELECT id_usuario, nome, email, senha, is_admin, must_change_password FROM usuarios WHERE email=?", (email,))
        row = cur.fetchone()
    return row

def autenticar_usuario(email: str, senha: str) -> Optional[Tuple[int, str, bool, bool]]:
    """
    Autentica usuário e suporta migração automática de hashes SHA256 (hex) antigos para bcrypt.
    Retorna (id_usuario, nome, is_admin, must_change_password) se sucesso, else None.
    """
    row = get_user_by_email(email)
    if not row:
        return None
    id_usuario, nome, _email, stored_hash, is_admin, must_change = row

    # Normalize stored_hash types
    if isinstance(stored_hash, memoryview):
        stored_hash = bytes(stored_hash)

    # Case 1: stored_hash is bytes (likely bcrypt bytes) -> try bcrypt
    if isinstance(stored_hash, (bytes, bytearray)):
        try:
            if bcrypt.checkpw(senha.encode("utf-8"), bytes(stored_hash)):
                return (id_usuario, nome, bool(is_admin), bool(must_change))
        except Exception:
            return None

    # Case 2: stored_hash is str
    if isinstance(stored_hash, str):
        s = stored_hash

        if len(s) == 64 and all(c in string.hexdigits for c in s):
            if hashlib.sha256(senha.encode("utf-8")).hexdigest() == s:
                try:
                    new_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())
                    with conectar() as conn:
                        conn.execute("UPDATE usuarios SET senha = ? WHERE id_usuario = ?", (new_hash, id_usuario))
                except Exception:
                    pass
                return (id_usuario, nome, bool(is_admin), bool(must_change))
            else:
                return None

        if s.startswith("$2"):
            try:
                if bcrypt.checkpw(senha.encode("utf-8"), s.encode("utf-8")):
                    return (id_usuario, nome, bool(is_admin), bool(must_change))
            except Exception:
                return None

        return None

    return None

def atualizar_senha(id_usuario: int, nova_senha: str, must_change: bool = False):
    hashed = bcrypt.hashpw(nova_senha.encode("utf-8"), bcrypt.gensalt())
    with conectar() as conn:
        conn.execute("UPDATE usuarios SET senha = ?, must_change_password = ? WHERE id_usuario = ?", (hashed, 1 if must_change else 0, id_usuario))

def set_must_change_password(id_usuario: int, flag: bool):
    with conectar() as conn:
        conn.execute("UPDATE usuarios SET must_change_password = ? WHERE id_usuario = ?", (1 if flag else 0, id_usuario))

# ---------------- LOGIN ATTEMPTS / LOCKOUT ----------------

def record_login_attempt(email: str, success: bool, ip: Optional[str] = None):
    with conectar() as conn:
        conn.execute("INSERT INTO login_attempts (email, success, ip) VALUES (?,?,?)", (email, 1 if success else 0, ip))

def count_failed_attempts_recent(email: str, minutes: int = 15) -> int:
    with conectar() as conn:
        cur = conn.execute(
            "SELECT COUNT(1) FROM login_attempts WHERE email = ? AND success = 0 AND attempted_at >= datetime('now', ?)",
            (email, f"-{minutes} minutes")
        )
        row = cur.fetchone()
    return row[0] if row else 0

def clear_login_attempts(email: str):
    with conectar() as conn:
        conn.execute("DELETE FROM login_attempts WHERE email = ?", (email,))

# ---------------- AUDIT / LOG ----------------

def log_audit(event_type: str, actor_id: Optional[int], target_id: Optional[int], details: Optional[str] = None):
    with conectar() as conn:
        conn.execute(
            "INSERT INTO audit_logs (event_type, actor_id, target_id, details) VALUES (?,?,?,?)",
            (event_type, actor_id, target_id, details)
        )

def listar_audit_logs(limit: int = 200, event_type: Optional[str] = None) -> pd.DataFrame:
    with conectar() as conn:
        if event_type:
            df = pd.read_sql("SELECT * FROM audit_logs WHERE event_type = ? ORDER BY created_at DESC LIMIT ?", conn, params=(event_type, limit))
        else:
            df = pd.read_sql("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", conn, params=(limit,))
    return df

# ---------------- ADMIN / MANAGEMENT ----------------

def listar_usuarios() -> pd.DataFrame:
    with conectar() as conn:
        df = pd.read_sql("SELECT id_usuario, nome, email, is_admin, must_change_password FROM usuarios", conn)
    if not df.empty:
        df["is_admin"] = df["is_admin"].astype(int).astype(bool)
        df["must_change_password"] = df["must_change_password"].astype(int).astype(bool)
    return df

def get_admin_count() -> int:
    with conectar() as conn:
        cur = conn.execute("SELECT COUNT(1) FROM usuarios WHERE is_admin = 1")
        row = cur.fetchone()
    return row[0] if row else 0

def can_delete_user(target_id: int) -> bool:
    """Impede exclusão do último admin."""
    with conectar() as conn:
        cur = conn.execute("SELECT is_admin FROM usuarios WHERE id_usuario = ?", (target_id,))
        row = cur.fetchone()
        if not row:
            return True
        is_admin = bool(row[0])
    if not is_admin:
        return True
    return get_admin_count() > 1

def atualizar_usuario(id_usuario: int, nome: Optional[str] = None, email: Optional[str] = None, is_admin: Optional[bool] = None):
    updates = []
    params = []
    if nome is not None:
        updates.append("nome = ?"); params.append(nome)
    if email is not None:
        updates.append("email = ?"); params.append(email)
    if is_admin is not None:
        updates.append("is_admin = ?"); params.append(1 if is_admin else 0)
    if not updates:
        return
    params.append(id_usuario)
    with conectar() as conn:
        conn.execute(f"UPDATE usuarios SET {', '.join(updates)} WHERE id_usuario = ?", params)

def excluir_usuario(id_usuario: int):
    if not can_delete_user(id_usuario):
        raise RuntimeError("Impossível excluir o último administrador.")
    with conectar() as conn:
        conn.execute("DELETE FROM usuarios WHERE id_usuario = ?", (id_usuario,))

# ---------------- CRUD RENDAS / GASTOS ----------------

def inserir_renda(id_usuario, descricao, valor, mes, ano):
    with conectar() as conn:
        conn.execute(
            "INSERT INTO rendas VALUES (NULL,?,?,?,?,?)",
            (id_usuario, descricao, valor, mes, ano)
        )

def inserir_gasto(id_usuario, id_classificacao, categoria, descricao, valor, mes, ano):
    with conectar() as conn:
        conn.execute(
            "INSERT INTO gastos VALUES (NULL,?,?,?,?,?,?,?)",
            (id_usuario, id_classificacao, categoria, descricao, valor, mes, ano)
        )

def carregar_rendas(id_usuario):
    with conectar() as conn:
        df = pd.read_sql(
            "SELECT * FROM rendas WHERE id_usuario=?",
            conn,
            params=(id_usuario,))
    df = normalizar_int(df, ["mes", "ano", "id_usuario"])
    return normalizar_df(df)

def carregar_gastos(id_usuario):
    with conectar() as conn:
        df = pd.read_sql(
            "SELECT * FROM gastos WHERE id_usuario=?",
            conn,
            params=(id_usuario,))
    df = normalizar_int(df, ["mes", "ano", "id_usuario"])
    return normalizar_df(df)

def atualizar_gasto(id_, desc, val):
    with conectar() as conn:
        conn.execute(
            "UPDATE gastos SET descricao=?, valor=? WHERE id=?",
            (desc, val, id_)
        )

def atualizar_renda(id_, desc, val):
    with conectar() as conn:
        conn.execute(
            "UPDATE rendas SET descricao=?, valor=? WHERE id=?",
            (desc, val, id_)
        )

def excluir_renda(id_):
    with conectar() as conn:
        conn.execute("DELETE FROM rendas WHERE id=?", (id_,))

def excluir_gasto(id_):
    with conectar() as conn:
        conn.execute("DELETE FROM gastos WHERE id=?", (id_,))

# ---------------- EXPORT / BACKUP ----------------

def dump_db_bytes() -> bytes:
    """Retorna conteúdo do arquivo SQLite (para download)."""
    with open(DB_NAME, "rb") as f:
        return f.read()

# ---------------- NORMALIZAÇÃO ----------------

def converter_ano(valor):
    if pd.isna(valor):
        return pd.NA
    if isinstance(valor, (bytes, bytearray, memoryview)):
        try:
            return int.from_bytes(bytes(valor), byteorder="little", signed=False)
        except Exception:
            pass
    try:
        return int(valor)
    except Exception:
        try:
            return int(float(valor))
        except Exception:
            return pd.NA

def normalizar_df(df):
    if df.empty:
        return df
    if "mes" in df.columns:
        df["mes"] = pd.to_numeric(df["mes"], errors="coerce").astype("Int64")
    if "ano" in df.columns:
        df["ano"] = df["ano"].apply(converter_ano).astype("Int64")
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").astype(float)
    return df


def normalizar_int(df, colunas):
    for col in colunas:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(".0", "", regex=False)
                .replace("nan", pd.NA)
                .astype("Int64")
            )
        return df
    
