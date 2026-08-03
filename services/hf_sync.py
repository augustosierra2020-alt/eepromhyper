import os
import threading
import shutil
import sqlite3
import logging
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_DATASET_REPO = os.environ.get("HF_DATASET_REPO", "GrizzlyBear25/HyperTork_DB")
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, "eeprom_master.db")

def verificar_integridade_banco(caminho):
    """
    Entra no banco de dados para checar se ele tem dados reais.
    Se for menor que 12KB ou não tiver tabelas, é considerado um 'Banco Fantasma' e deve ser ignorado.
    """
    if not os.path.exists(caminho):
        return False
        
    if os.path.getsize(caminho) < 12000:
        return False
        
    try:
        conn = sqlite3.connect(caminho, timeout=5)
        cursor = conn.cursor()
        
        # Verifica a estrutura mínima
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        if cursor.fetchone()[0] < 3:
            conn.close()
            return False
            
        # Verifica se há dados na oficina
        try:
            cursor.execute("SELECT COUNT(*) FROM montadoras")
            m_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM os_salvas")
            os_count = cursor.fetchone()[0]
        except Exception:
            m_count, os_count = 0, 0
            
        conn.close()
        
        if m_count == 0 and os_count == 0:
            return False # Banco estruturado, mas VAZIO.
            
        return True
    except Exception:
        return False

def sincronizar_nuvem_para_local():
    """
    Puxa dados da nuvem COM TRAVA INTELIGENTE para ignorar bancos fantasmas do Git.
    """
    if not HF_TOKEN:
        print("[HF Sync] Modo local: HF_TOKEN ausente.")
        return

    repo_id = HF_DATASET_REPO
    try:
        # PROTEÇÃO: Se não existir ou for um banco vazio, BAIXA da nuvem a força.
        if not verificar_integridade_banco(DB_PATH):
            print("[HF Sync] ⚠️ Banco local ausente ou VAZIO. Forçando download do cofre principal da nuvem...")
            try:
                caminho_tmp_db = hf_hub_download(repo_id=repo_id, filename="eeprom_master.db", repo_type="dataset", token=HF_TOKEN, force_download=True)
                shutil.copy2(caminho_tmp_db, DB_PATH)
                print("[HF Sync] ✅ eeprom_master.db original resgatado e aplicado com sucesso!")
            except Exception as e:
                print(f"[HF Sync] ❌ Erro ao baixar o banco da nuvem: {e}")
        else:
            print("[HF Sync] 🛡️ Banco local com dados detectado. Download bloqueado para proteger suas edições da sessão atual.")

        # Sincroniza a Planilha Fp.xlsx
        try:
            caminho_tmp_fp = hf_hub_download(repo_id=repo_id, filename="Fp.xlsx", repo_type="dataset", token=HF_TOKEN)
            shutil.copy2(caminho_tmp_fp, os.path.join(BASE_DIR, "Fp.xlsx"))
        except Exception: pass
            
        # Sincroniza a pasta de Logos
        try:
            caminho_tmp_logos = snapshot_download(repo_id=repo_id, repo_type="dataset", allow_patterns="Logos/*", token=HF_TOKEN)
            pasta_logos_tmp = os.path.join(caminho_tmp_logos, "Logos")
            pasta_logos_local = os.path.join(BASE_DIR, "Logos")
            os.makedirs(pasta_logos_local, exist_ok=True)
            
            if os.path.exists(pasta_logos_tmp):
                for arquivo in os.listdir(pasta_logos_tmp):
                    shutil.copy2(os.path.join(pasta_logos_tmp, arquivo), os.path.join(pasta_logos_local, arquivo))
        except Exception: pass

    except Exception as e:
        print(f"[HF Sync] ❌ Falha crítica na inicialização: {e}")

def executar_backup_sincrono():
    """
    Executa o backup completo, MAS TRAVA se o banco local for inválido.
    """
    if not HF_TOKEN:
        return False, "Token HF_TOKEN ausente."

    try:
        # TRAVA DE SEGURANÇA MÁXIMA: NUNCA envia um banco vazio para a nuvem
        if not verificar_integridade_banco(DB_PATH):
            msg = "Upload bloqueado: O sistema evitou o envio de um banco vazio para a nuvem."
            print(f"[HF Sync] 🛡️ {msg}")
            return False, msg

        api = HfApi(token=HF_TOKEN)
        repo_id = HF_DATASET_REPO
        
        api.upload_file(path_or_fileobj=DB_PATH, path_in_repo="eeprom_master.db", repo_id=repo_id, repo_type="dataset")

        caminho_fp = os.path.join(BASE_DIR, "Fp.xlsx")
        if os.path.exists(caminho_fp):
            api.upload_file(path_or_fileobj=caminho_fp, path_in_repo="Fp.xlsx", repo_id=repo_id, repo_type="dataset")

        caminho_logos = os.path.join(BASE_DIR, "Logos")
        if os.path.exists(caminho_logos) and len(os.listdir(caminho_logos)) > 0:
            api.upload_folder(folder_path=caminho_logos, path_in_repo="Logos", repo_id=repo_id, repo_type="dataset")

        return True, "Backup concluído com sucesso!"
    except Exception as e:
        return False, str(e)

def backup_local_para_nuvem_async():
    thread = threading.Thread(target=executar_backup_sincrono, daemon=True)
    thread.start()

# Alias de compatibilidade
backup_local_para_nuvem = backup_local_para_nuvem_async