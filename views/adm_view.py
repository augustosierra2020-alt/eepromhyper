import streamlit as st
import os
import time
import base64
import re
import unicodedata
from core.db import get_db_connection
from services.hf_sync import backup_local_para_nuvem_async, executar_backup_sincrono

HF_TOKEN = os.environ.get("HF_TOKEN")
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
LOGOS_DIR = os.path.join(BASE_DIR, "Logos")

def renderizar_logo_harmonizada(caminho):
    if not caminho or not os.path.exists(caminho): return False
    try:
        if os.path.getsize(caminho) < 500: return False
        with open(caminho, "rb") as image_file: 
            encoded_string = base64.b64encode(image_file.read()).decode()
        st.markdown(f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 100px; width: 100%; background-color: #FFFFFF; border-radius: 12px; padding: 10px; margin-bottom: 10px;">
                <img src="data:image/png;base64,{encoded_string}" style="max-height: 80px; max-width: 100%; object-fit: contain;">
            </div>
        """, unsafe_allow_html=True)
        return True
    except Exception: 
        return False

def render_adm():
    st.title("🔑 Central de Administração - HyperTork")
    st.info("Painel mestre de infraestrutura rodando em pool persistente de dados.")
    
    if st.button("🚪 Encerrar Sessão Administrador", type="primary", use_container_width=True):
        st.session_state.adm_logged_in = False
        st.session_state.app_mode = "HOME"
        st.rerun()
        
    st.markdown("---")
    
    tab_infra, tab_logos, tab_dados = st.tabs([
        "🖥️ Infraestrutura & Sincronização", 
        "🖼️ Repositório Físico de Logos", 
        "📊 Estatísticas Globais"
    ])
    
    with tab_infra:
        st.subheader("📋 Diagnóstico Técnico & Sincronização de Emergência")
        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("🔍 Rodar Pente Fino no Sistema", type="primary", use_container_width=True):
            with st.spinner("Chip inspecionando tabelas dinâmicas..."):
                status_db = "🟢 Conectado (Pool SQLite Ativo)"
                qtd_montadoras, qtd_obd2, qtd_hex = 0, 0, 0
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM montadoras"); qtd_montadoras = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM obd2_history"); qtd_obd2 = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM hex_history"); qtd_hex = cursor.fetchone()[0]
                except Exception as e:
                    status_db = f"🔴 Erro DB: {e}"
                finally:
                    conn.close()
                
                status_ia = "🟢 Configurada" if HF_TOKEN else "🔴 Offline (HF_TOKEN ausente)"
                
                st.markdown("### 📊 Status da Bancada")
                st.write(f"**Banco de Dados:** {status_db}")
                st.write(f"**IA Motor:** {status_ia}")
                st.success(f"✅ Diagnóstico finalizado: {qtd_montadoras} montadoras | {qtd_obd2} consultas OBD2 | {qtd_hex} comparações HEX.")

        if col_btn2.button("☁️ Forçar Backup Total (Hugging Face)", type="primary", use_container_width=True):
            with st.spinner("Enviando banco de dados e arquivos para o repositório em nuvem..."):
                sucesso, msg = executar_backup_sincrono()
                if sucesso: st.success(f"✅ {msg}")
                else: st.error(f"❌ Falha no Backup: {msg}")

    with tab_logos:
        st.subheader("🖼️ Repositório de Logos (Upload em Lote)")
        arquivos_logos = st.file_uploader("Selecione Imagens de Logos:", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
        if st.button("💾 Gravar Logos", type="primary", use_container_width=True):
            if arquivos_logos:
                os.makedirs(LOGOS_DIR, exist_ok=True)
                for arquivo in arquivos_logos:
                    with open(os.path.join(LOGOS_DIR, arquivo.name), "wb") as f:
                        f.write(arquivo.read())
                backup_local_para_nuvem_async()
                st.success("✅ Logos gravadas e salvas na nuvem!")
                st.rerun()

    with tab_dados:
        st.subheader("📈 Volumes Cadastrados na Oficina")
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM veiculos")
            qtd_v = cursor.fetchone()[0]
            st.metric("Total de Veículos/Mapas Mapeados", f"{qtd_v} modelos")
        except Exception:
            st.info("Carregando volumes...")
        finally:
            conn.close()