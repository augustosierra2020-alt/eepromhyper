import os
import threading
import shutil
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_DATASET_REPO = os.environ.get("HF_DATASET_REPO", "GrizzlyBear25/HyperTork_DB")

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def sincronizar_nuvem_para_local():
    """
    Executada na inicialização do app. 
    Puxa o eeprom_master.db, a Fp.xlsx e as Logos da nuvem.
    """
    if not HF_TOKEN:
        print("[HF Sync] Inicialização: HF_TOKEN não configurado. Trabalhando em modo local.")
        return

    print(f"[HF Sync] Conectando ao Dataset: {HF_DATASET_REPO}...")
    repo_id = HF_DATASET_REPO
    
    try:
        # 1. Resgata e copia o eeprom_master.db
        try:
            caminho_tmp_db = hf_hub_download(repo_id=repo_id, filename="eeprom_master.db", repo_type="dataset", token=HF_TOKEN)
            
            # Copia para /core/eeprom_master.db
            pasta_core = os.path.join(BASE_DIR, "core")
            os.makedirs(pasta_core, exist_ok=True)
            shutil.copy2(caminho_tmp_db, os.path.join(pasta_core, "eeprom_master.db"))
            
            # Copia também para a Raiz (fallback)
            shutil.copy2(caminho_tmp_db, os.path.join(BASE_DIR, "eeprom_master.db"))
            
            print("[HF Sync] ✅ eeprom_master.db baixado e aplicado com sucesso!")
        except Exception as e:
            print(f"[HF Sync] ⚠️ Aviso: eeprom_master.db não encontrado no Dataset ou erro: {e}")

        # 2. Resgata a Planilha Fp.xlsx
        try:
            caminho_tmp_fp = hf_hub_download(repo_id=repo_id, filename="Fp.xlsx", repo_type="dataset", token=HF_TOKEN)
            shutil.copy2(caminho_tmp_fp, os.path.join(BASE_DIR, "Fp.xlsx"))
            print("[HF Sync] ✅ Fp.xlsx sincronizado com sucesso!")
        except Exception as e:
            print(f"[HF Sync] ⚠️ Aviso: Fp.xlsx não encontrado no Dataset ou erro: {e}")
            
        # 3. Resgata a pasta de Logos
        try:
            caminho_tmp_logos = snapshot_download(repo_id=repo_id, repo_type="dataset", allow_patterns="Logos/*", token=HF_TOKEN)
            pasta_logos_tmp = os.path.join(caminho_tmp_logos, "Logos")
            pasta_logos_local = os.path.join(BASE_DIR, "Logos")
            os.makedirs(pasta_logos_local, exist_ok=True)
            
            if os.path.exists(pasta_logos_tmp):
                for arquivo in os.listdir(pasta_logos_tmp):
                    shutil.copy2(os.path.join(pasta_logos_tmp, arquivo), os.path.join(pasta_logos_local, arquivo))
            print("[HF Sync] ✅ Logos sincronizadas com sucesso!")
        except Exception as e:
            print(f"[HF Sync] ⚠️ Aviso: Logos não encontradas no Dataset ou erro: {e}")

    except Exception as e:
        print(f"[HF Sync] ❌ Falha crítica na sincronização inicial: {e}")


def executar_backup_sincrono():
    """
    Executa o backup completo dos arquivos locais para o Dataset do Hugging Face.
    """
    if not HF_TOKEN:
        return False, "Token HF_TOKEN ausente."

    try:
        api = HfApi(token=HF_TOKEN)
        repo_id = HF_DATASET_REPO

        # Busca o banco eeprom_master.db
        caminho_db = os.path.join(BASE_DIR, "core", "eeprom_master.db")
        if not os.path.exists(caminho_db):
            caminho_db = os.path.join(BASE_DIR, "eeprom_master.db")
            
        if os.path.exists(caminho_db):
            api.upload_file(path_or_fileobj=caminho_db, path_in_repo="eeprom_master.db", repo_id=repo_id, repo_type="dataset")

        caminho_fp = os.path.join(BASE_DIR, "Fp.xlsx")
        if os.path.exists(caminho_fp):
            api.upload_file(path_or_fileobj=caminho_fp, path_in_repo="Fp.xlsx", repo_id=repo_id, repo_type="dataset")

        caminho_logos = os.path.join(BASE_DIR, "Logos")
        if os.path.exists(caminho_logos) and len(os.listdir(caminho_logos)) > 0:
            api.upload_folder(folder_path=caminho_logos, path_in_repo="Logos", repo_id=repo_id, repo_type="dataset")

        return True, "Backup total para o Dataset concluído com sucesso!"

    except Exception as e:
        return False, str(e)


def backup_local_para_nuvem_async():
    thread = threading.Thread(target=executar_backup_sincrono, daemon=True)
    thread.start()