import os
import sqlite3
import logging
import shutil

# Define a RAIZ do projeto (voltando 1 nível a partir de core/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CAMINHO ÚNICO E DEFINITIVO DO BANCO NA RAIZ DO PROJETO (Resolve o bug do histórico sumir)
DB_PATH = os.path.join(BASE_DIR, "eeprom_master.db")

# =====================================================================
# 🛠️ ROTINA DE AUTO-CURA (Resgate de dados perdidos)
# Se o sistema gerou um banco fantasma na pasta core, resgatamos para a raiz
# =====================================================================
ghost_db_path = os.path.join(BASE_DIR, "core", "eeprom_master.db")
if os.path.exists(ghost_db_path):
    if not os.path.exists(DB_PATH):
        shutil.move(ghost_db_path, DB_PATH)
        logging.info("[DB Engine] Banco resgatado da pasta core para a raiz.")
    else:
        try:
            os.remove(ghost_db_path) # Já temos o da raiz, oblitera o fantasma
        except Exception:
            pass

def get_db_connection():
    """Retorna uma conexão thread-safe apontando EXCLUSIVAMENTE para o banco real."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# Alias para garantir que nenhuma view quebre
conectar_db = get_db_connection

def init_db():
    """Inicializa as tabelas e executa auto-migração de colunas faltantes."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tabelas Core do Sistema
        cursor.execute("CREATE TABLE IF NOT EXISTS montadoras (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS veiculos (id INTEGER PRIMARY KEY AUTOINCREMENT, montadora_nome TEXT NOT NULL, modelo TEXT NOT NULL, posicao_inicio TEXT, intervalo TEXT, valores_invertidos TEXT, escala TEXT, detalhes TEXT, UNIQUE(montadora_nome, modelo))")
        cursor.execute("CREATE TABLE IF NOT EXISTS graficos (id INTEGER PRIMARY KEY AUTOINCREMENT, veiculo_id INTEGER NOT NULL, foto BLOB NOT NULL, ordem INTEGER NOT NULL, FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE CASCADE)")
        cursor.execute("CREATE TABLE IF NOT EXISTS obd2_history (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, montadora TEXT, modelo TEXT, ano TEXT, descricao TEXT, data TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("CREATE TABLE IF NOT EXISTS hex_history (id INTEGER PRIMARY KEY AUTOINCREMENT, veiculo TEXT, data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, file_ori BLOB, file_mod BLOB, laudo TEXT, cv_estimado INTEGER DEFAULT 0)")
        cursor.execute("CREATE TABLE IF NOT EXISTS clientes_fp (fp_codigo TEXT PRIMARY KEY, cidade TEXT, contato TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS os_salvas (id INTEGER PRIMARY KEY AUTOINCREMENT, fp_codigo TEXT, mes_ano TEXT, nome_arquivo TEXT, dados_bytes BLOB, valor_total REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS planilhas_mensais (mes_ano TEXT PRIMARY KEY, dados_json TEXT, total_faturado REAL)")
        
        # Colunas de atualização segura
        colunas_migracao = [
            ("obd2_history", "montadora TEXT"),
            ("obd2_history", "modelo TEXT"),
            ("obd2_history", "ano TEXT"),
            ("obd2_history", "segmento TEXT"),
            ("hex_history", "cv_estimado INTEGER DEFAULT 0")
        ]
        
        for tabela, coluna in colunas_migracao:
            try:
                cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna}")
            except sqlite3.OperationalError:
                pass # Coluna já existente, ignora
                
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"[DB Engine] Erro ao inicializar SQLite: {e}")