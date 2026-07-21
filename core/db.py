import sqlite3
import streamlit as st
import os
import logging
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "eeprom_master.db")

@st.cache_resource
def get_db_connection():
    """Pool de Conexão Persistente: Abre apenas uma vez por sessão"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;") # Write-Ahead Logging para concorrência
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS montadoras (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS veiculos (id INTEGER PRIMARY KEY AUTOINCREMENT, montadora_nome TEXT NOT NULL, modelo TEXT NOT NULL, posicao_inicio TEXT, intervalo TEXT, valores_invertidos TEXT, escala TEXT, detalhes TEXT, UNIQUE(montadora_nome, modelo))")
        cursor.execute("CREATE TABLE IF NOT EXISTS graficos (id INTEGER PRIMARY KEY AUTOINCREMENT, veiculo_id INTEGER NOT NULL, foto BLOB NOT NULL, ordem INTEGER NOT NULL, FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE CASCADE)")
        cursor.execute("CREATE TABLE IF NOT EXISTS obd2_history (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, segmento TEXT, montadora TEXT, modelo TEXT, ano TEXT, descricao TEXT, data TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        # Hex history otimizado para Lazy Loading (bytes separados)
        cursor.execute("CREATE TABLE IF NOT EXISTS hex_history (id INTEGER PRIMARY KEY AUTOINCREMENT, veiculo TEXT, data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, file_ori BLOB, file_mod BLOB, laudo TEXT, cv_estimado INTEGER DEFAULT 0)")
        cursor.execute("CREATE TABLE IF NOT EXISTS clientes_fp (fp_codigo TEXT PRIMARY KEY, cidade TEXT, contato TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS os_salvas (id INTEGER PRIMARY KEY AUTOINCREMENT, fp_codigo TEXT, mes_ano TEXT, nome_arquivo TEXT, dados_bytes BLOB, valor_total REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS planilhas_mensais (mes_ano TEXT PRIMARY KEY, dados_json TEXT, total_faturado REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS logos_custom (nome TEXT PRIMARY KEY, foto BLOB)")
        conn.commit()
    except Exception as e:
        logging.error(f"Erro Init SQLite: {e}")