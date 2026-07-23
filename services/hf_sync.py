import os
import threading
import shutil
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

HF_TOKEN = os.environ.get("HF_TOKEN")
# Repositório do Dataset no Hugging Face (Ajuste caso o nome do seu repositório seja diferente)
HF_DATASET_REPO = os.environ.get("HF_DATASET_REPO", "GrizzlyBear25/HyperTork_Data")

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def sincronizar_nuvem_para_local():
    """
    Executada na inicialização do app (app_eeprom.py). 
    Puxa o banco de dados, a planilha Fp.xlsx e as Logos da nuvem para o servidor atual.
    """
    if not HF_TOKEN:
        print("[HF Sync] Inicialização: HF_TOKEN não configurado. Trabalhando apenas com dados locais.")
        return

    print("[HF Sync] Iniciando download dos dados salvos no Dataset...")
    repo_id = HF_DATASET_REPO
    
    try:
        # 1. Resgata o Banco de Dados
        try:
            caminho_tmp_db = hf_hub_download(repo_id=repo_id, filename="hypertork.db", repo_type="dataset", token=HF_TOKEN)
            pasta_core = os.path.join(BASE_DIR, "core")
            os.makedirs(pasta_core, exist_ok=True)
            shutil.copy2(caminho_tmp_db, os.path.join(pasta_core, "hypertork.db"))
            print("[HF Sync] Banco de dados sincronizado com sucesso.")
        except Exception as e:
            print(f"[HF Sync] Aviso: hypertork.db não encontrado na nuvem ou erro - {e}")

        # 2. Resgata a Planilha Fp.xlsx
        try:
            caminho_tmp_fp = hf_hub_download(repo_id=repo_id, filename="Fp.xlsx", repo_type="dataset", token=HF_TOKEN)
            shutil.copy2(caminho_tmp_fp, os.path.join(BASE_DIR, "Fp.xlsx"))
            print("[HF Sync] Fp.xlsx sincronizado com sucesso.")
        except Exception as e:
            print(f"[HF Sync] Aviso: Fp.xlsx não encontrado na nuvem ou erro - {e}")
            
        # 3. Resgata a pasta de Logos
        try:
            caminho_tmp_logos = snapshot_download(repo_id=repo_id, repo_type="dataset", allow_patterns="Logos/*", token=HF_TOKEN)
            pasta_logos_tmp = os.path.join(caminho_tmp_logos, "Logos")
            pasta_logos_local = os.path.join(BASE_DIR, "Logos")
            os.makedirs(pasta_logos_local, exist_ok=True)
            
            if os.path.exists(pasta_logos_tmp):
                for arquivo in os.listdir(pasta_logos_tmp):
                    shutil.copy2(os.path.join(pasta_logos_tmp, arquivo), os.path.join(pasta_logos_local, arquivo))
            print("[HF Sync] Logos sincronizadas com sucesso.")
        except Exception as e:
            print(f"[HF Sync] Aviso: Logos não encontradas na nuvem ou erro - {e}")

    except Exception as e:
        print(f"[HF Sync] Falha crítica na sincronização inicial: {e}")


def executar_backup_sincrono():
    """
    Executa o backup completo dos arquivos locais para o Dataset do Hugging Face.
    Acionado pelo botão de Sincronização de Emergência.
    """
    if not HF_TOKEN:
        return False, "Token HF_TOKEN ausente nos Secrets do Hugging Face."

    try:
        api = HfApi(token=HF_TOKEN)
        repo_id = HF_DATASET_REPO

        # 1. Envia DB
        caminho_db = os.path.join(BASE_DIR, "core", "hypertork.db")
        if not os.path.exists(caminho_db):
            caminho_db = os.path.join(BASE_DIR, "hypertork.db") # Fallback
            
        if os.path.exists(caminho_db):
            api.upload_file(path_or_fileobj=caminho_db, path_in_repo="hypertork.db", repo_id=repo_id, repo_type="dataset")

        # 2. Envia Fp.xlsx
        caminho_fp = os.path.join(BASE_DIR, "Fp.xlsx")
        if os.path.exists(caminho_fp):
            api.upload_file(path_or_fileobj=caminho_fp, path_in_repo="Fp.xlsx", repo_id=repo_id, repo_type="dataset")

        # 3. Envia Logos
        caminho_logos = os.path.join(BASE_DIR, "Logos")
        if os.path.exists(caminho_logos) and len(os.listdir(caminho_logos)) > 0:
            api.upload_folder(folder_path=caminho_logos, path_in_repo="Logos", repo_id=repo_id, repo_type="dataset")

        return True, "Backup total para o Dataset concluído com sucesso!"

    except Exception as e:
        return False, str(e)


def backup_local_para_nuvem_async():
    """
    Dispara o backup em segundo plano (assíncrono) para não travar a interface.
    """
    thread = threading.Thread(target=executar_backup_sincrono, daemon=True)
    thread.start()