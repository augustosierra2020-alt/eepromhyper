import os
import threading
from huggingface_hub import HfApi

HF_TOKEN = os.environ.get("HF_TOKEN")
# Repositório do Dataset no Hugging Face (pode ser ajustado via variável de ambiente ou string padrão)
HF_DATASET_REPO = os.environ.get("HF_DATASET_REPO", "GrizzlyBear25/HyperTork_Data")

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def executar_backup_sincrono():
    """
    Executa o backup completo dos arquivos locais (Banco SQLite, Fp.xlsx e Logos) 
    diretamente para o Dataset do Hugging Face.
    """
    if not HF_TOKEN:
        print("[HF Sync] Abortado: HF_TOKEN não configurado no ambiente.")
        return False, "Token HF_TOKEN ausente nos Secrets do Hugging Face."

    try:
        api = HfApi(token=HF_TOKEN)
        repo_id = HF_DATASET_REPO

        # 1. Backup do Banco de Dados SQLite
        caminho_db = os.path.join(BASE_DIR, "core", "hypertork.db")
        if not os.path.exists(caminho_db):
            caminho_db = os.path.join(BASE_DIR, "hypertork.db")
            
        if os.path.exists(caminho_db):
            api.upload_file(
                path_or_fileobj=caminho_db,
                path_in_repo="hypertork.db",
                repo_id=repo_id,
                repo_type="dataset"
            )
            print("[HF Sync] Banco de dados enviado com sucesso.")

        # 2. Backup da Planilha Fp.xlsx
        caminho_fp = os.path.join(BASE_DIR, "Fp.xlsx")
        if os.path.exists(caminho_fp):
            api.upload_file(
                path_or_fileobj=caminho_fp,
                path_in_repo="Fp.xlsx",
                repo_id=repo_id,
                repo_type="dataset"
            )
            print("[HF Sync] Fp.xlsx enviado com sucesso.")

        # 3. Backup da Pasta Logos
        caminho_logos = os.path.join(BASE_DIR, "Logos")
        if os.path.exists(caminho_logos) and len(os.listdir(caminho_logos)) > 0:
            api.upload_folder(
                folder_path=caminho_logos,
                path_in_repo="Logos",
                repo_id=repo_id,
                repo_type="dataset"
            )
            print("[HF Sync] Pasta Logos enviada com sucesso.")

        return True, "Backup total para o Dataset concluído com sucesso!"

    except Exception as e:
        print(f"[HF Sync] Erro durante o backup: {e}")
        return False, str(e)

def backup_local_para_nuvem_async():
    """
    Dispara o backup em segundo plano (assíncrono) para não travar a interface do Streamlit.
    """
    thread = threading.Thread(target=executar_backup_sincrono, daemon=True)
    thread.start()