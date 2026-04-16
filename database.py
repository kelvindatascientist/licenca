import sqlite3
import pandas as pd
from datetime import datetime
import os

DB_NAME = "historico_calculos.db"

def init_db():
    """Inicializa o banco de dados e cria as tabelas se não existirem."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            municipio TEXT,
            grupo TEXT,
            atividade TEXT,
            medida TEXT,
            porte TEXT,
            potencial_poluidor TEXT,
            valor_total REAL,
            cnpj_cpf TEXT,
            cnaes TEXT,
            email TEXT,
            telefone TEXT,
            usuario_login TEXT,
            usuario_nome TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            calculo_id INTEGER,
            motivo TEXT,
            usuario_login TEXT,
            usuario_nome TEXT,
            FOREIGN KEY (calculo_id) REFERENCES calculos(id)
        )
    ''')
    
    # Migração: verifica se a coluna cnpj_cpf existe, se não, adiciona
    cursor.execute("PRAGMA table_info(calculos)")
    columns = [info[1] for info in cursor.fetchall()]
    if "cnpj_cpf" not in columns:
        cursor.execute("ALTER TABLE calculos ADD COLUMN cnpj_cpf TEXT")
    if "cnaes" not in columns:
        cursor.execute("ALTER TABLE calculos ADD COLUMN cnaes TEXT")
    if "email" not in columns:
        cursor.execute("ALTER TABLE calculos ADD COLUMN email TEXT")
    if "telefone" not in columns:
        cursor.execute("ALTER TABLE calculos ADD COLUMN telefone TEXT")
    if "usuario_login" not in columns:
        cursor.execute("ALTER TABLE calculos ADD COLUMN usuario_login TEXT")
    if "usuario_nome" not in columns:
        cursor.execute("ALTER TABLE calculos ADD COLUMN usuario_nome TEXT")
    
    conn.commit()
    conn.close()


def salvar_feedback(calculo_id, motivo, usuario_login="", usuario_nome=""):
    """Salva um feedback de discordância no banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        '''INSERT INTO feedbacks (data_hora, calculo_id, motivo, usuario_login, usuario_nome)
           VALUES (?, ?, ?, ?, ?)''',
        (data_hora, calculo_id, motivo, usuario_login, usuario_nome),
    )
    conn.commit()
    conn.close()


def listar_feedbacks():
    """Retorna todos os feedbacks salvos como um DataFrame."""
    conn = sqlite3.connect(DB_NAME)
    try:
        df = pd.read_sql_query("SELECT * FROM feedbacks ORDER BY id DESC", conn)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def salvar_calculo(
    municipio,
    grupo,
    atividade,
    medida,
    porte,
    potencial,
    valor_total,
    cnpj_cpf="",
    cnaes="",
    email="",
    telefone="",
    usuario_login="",
    usuario_nome="",
):
    """Salva um novo registro de cálculo no banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute('''
        INSERT INTO calculos (
            data_hora,
            municipio,
            grupo,
            atividade,
            medida,
            porte,
            potencial_poluidor,
            valor_total,
            cnpj_cpf,
            cnaes,
            email,
            telefone,
            usuario_login,
            usuario_nome
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data_hora, municipio, grupo, atividade, medida, porte, potencial, valor_total, cnpj_cpf, cnaes, email, telefone, usuario_login, usuario_nome))
    
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def listar_calculos():
    """Retorna todos os cálculos salvos como um DataFrame."""
    conn = sqlite3.connect(DB_NAME)
    try:
        df = pd.read_sql_query("SELECT * FROM calculos ORDER BY id DESC", conn)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
