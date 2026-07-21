import os
import shutil
import logging
import threading
import streamlit as st
from huggingface_hub import hf_hub_download, HfApi
from core.db import DB_PATH, init_db

HF_TOKEN = os.environ.get("HF_TOKEN")
DATASET_REPO_ID = "GrizzlyBear25/HyperTork_DB"
DB_BAK_PATH = DB_PATH + ".bak"

def sincronizar_nuvem_para_local():
    """Baixa o banco mestre da nuvem se o local não existir ou for muito pequeno."""
    if HF_TOKEN:
        if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 512000:
            logging.info("Banco local detectado e compatível. Download pulado para proteger dados locais.")
            return True
            
        try:
            logging.info("Baixando banco mestre da nuvem...")
            db_nuvem = hf_hub_download(
                repo_id=DATASET_REPO_ID, 
                filename="eeprom_master.db", 
                repo_type="dataset", 
                token=HF_TOKEN
            )
            shutil.copy(db_nuvem, DB_PATH)
            init_db() 
            return True
        except Exception as e:
            logging.warning(f"Download da nuvem ignorado (Primeiro uso ou erro): {e}")
    return False

def _upload_background():
    """Trabalhador assíncrono que faz o upload sem travar o Streamlit."""
    try:
        if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 512000:
            shutil.copy(DB_PATH, DB_BAK_PATH) # Cria o espelho de segurança local
            api = HfApi()
            api.upload_file(
                path_or_fileobj=DB_PATH, 
                path_in_repo="eeprom_master.db", 
                repo_id=DATASET_REPO_ID, 
                repo_type="dataset", 
                token=HF_TOKEN
            )
            logging.info("Backup na nuvem concluído com sucesso.")
    except Exception as e:
        logging.error(f"Falha na Thread de Backup: {e}")

def backup_local_para_nuvem_async():
    """Dispara a thread de backup e avisa o usuário visualmente."""
    if HF_TOKEN:
        try:
            st.toast("☁️ Sincronização de segurança iniciada...", icon="⏳")
        except:
            pass 
        t = threading.Thread(target=_upload_background)
        t.start()