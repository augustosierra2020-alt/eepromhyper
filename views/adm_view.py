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

def higienizar_nome(nome: str) -> str:
    if not nome: return ""
    return re.sub(r'[\\/*?:"<>|]', "", " ".join(nome.strip().upper().split()))

def limpar_para_comparacao(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^A-Z0-9]', '', texto.upper())

def renderizar_logo_harmonizada(caminho):
    if not caminho or not os.path.exists(caminho): return False
    try:
        with open(caminho, "rb") as image_file: 
            encoded_string = base64.b64encode(image_file.read()).decode()
        st.markdown(f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 100px; width: 100%; background-color: #FFFFFF; border-radius: 12px; padding: 10px; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.05); margin-bottom: 10px;">
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
    
    # ==========================================
    # ABA 1: INFRAESTRUTURA, PENTE FINO & BACKUP
    # ==========================================
    with tab_infra:
        st.subheader("📋 Diagnóstico Técnico & Sincronização de Emergência")
        st.write("Invoque a auditoria interna do Chip ou force a sincronização total com o Dataset do Hugging Face.")
        
        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("🔍 Rodar Pente Fino no Sistema (Status & Erros)", type="primary", use_container_width=True):
            with st.spinner("Chip inspecionando portas lógicas e tabelas dinâmicas..."):
                time.sleep(1)
                
                status_db = "🟢 Conectado (Pool SQLite Ativo)"
                qtd_montadoras, qtd_obd2, qtd_hex = 0, 0, 0
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM montadoras")
                    qtd_montadoras = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM obd2_history")
                    qtd_obd2 = cursor.fetchone()[0]
                    try:
                        cursor.execute("SELECT COUNT(*) FROM hex_history")
                        qtd_hex = cursor.fetchone()[0]
                    except Exception: 
                        status_db = "🟡 Conectado (Tabela hex_history antiga)"
                except Exception as e:
                    status_db = f"🔴 Falha Crítica na Conexão: {e}"
                
                try:
                    import hypertork_cpp
                    status_cpp = "🟢 Ativa (hypertork_cpp carregado com sucesso)"
                except ImportError:
                    status_cpp = "🟡 Inativa (Contêiner Linux operando em Fallback NumPy sem perdas)"
                
                status_ia = "🟢 Configurada (HF_TOKEN injetado nos Secrets)" if HF_TOKEN else "🔴 Offline (Variável HF_TOKEN ausente no ambiente)"
                
                st.markdown("### 📊 Status da Bancada")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.markdown(f"**Banco de Dados Local:** {status_db}")
                    st.markdown(f"**Aceleração Binária (C++):** {status_cpp}")
                with col_c2:
                    st.markdown(f"**Conexão do Motor de IA:** {status_ia}")
                    st.markdown(f"**Ambiente:** Hugging Face Spaces OS (`Ubuntu/Debian Python`) ")
                
                st.markdown("---")
                st.markdown("### 🤖 Laudo do Mecânico Chefe Chip:")
                
                analise_chip = ""
                if not HF_TOKEN:
                    analise_chip += "- ❌ **ERRO CRÍTICO DE IA:** Chefe, o scanner OBD2 não vai conseguir gerar laudos porque a chave secreta `HF_TOKEN` está vazia! Cadastre o token nos Secrets do Hugging Face.\n"
                else:
                    analise_chip += "- ✅ **IA HUGGING FACE:** Autenticação ativa. Pronta para laudos DTC.\n"
                    
                if "Inativa" in status_cpp:
                    analise_chip += "- ⚠️ **AVISO DE ACC C++:** O contêiner Linux do Hugging Face aplicou o fallback em matrizes NumPy. O estúdio HEX vai rodar perfeito, mas usando o interpretador nativo do Python.\n"
                else:
                    analise_chip += "- ✅ **MOTOR NATIVO:** Aceleração C++ ativa em hardware local.\n"
                    
                if "🔴" in status_db:
                    analise_chip += "- ❌ **PANE NO BANCO DE DADOS:** Falha crítica na leitura das tabelas locais.\n"
                else:
                    analise_chip += f"- ✅ **INTEGRIDADE DB:** Banco operando redondo. Temos {qtd_montadoras} marcas no cofre e {qtd_obd2} consultas OBD2 gravadas.\n"
                
                st.warning(analise_chip)
                st.success("🏁 Pente fino concluído. Core operacional estruturado!")

        if col_btn2.button("☁️ Forçar Backup Total (Hugging Face)", type="primary", use_container_width=True):
            with st.spinner("Empacotando e enviando banco de dados, logos e planilha Fp.xlsx para a nuvem..."):
                sucesso, msg = executar_backup_sincrono()
                time.sleep(1)
                if sucesso:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ Falha no Backup: {msg}")

    # ==========================================
    # ABA 2: REPOSITÓRIO FÍSICO DE LOGOS
    # ==========================================
    with tab_logos:
        st.subheader("🖼️ Repositório de Logos de Montadoras (Upload em Lote)")
        st.write("Selecione uma ou várias fotos de logos simultaneamente. O sistema manterá em espera até que a montadora com nome correspondente seja criada.")
        
        with st.container(border=True):
            arquivos_logos = st.file_uploader("Arraste ou Selecione as Imagens (Múltiplos arquivos permitidos):", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
            
            if st.button("💾 Gravar Mídias no Repositório", type="primary", use_container_width=True):
                if arquivos_logos:
                    os.makedirs(LOGOS_DIR, exist_ok=True)
                    salvos = 0
                    for arquivo in arquivos_logos:
                        caminho_final = os.path.join(LOGOS_DIR, arquivo.name)
                        try:
                            with open(caminho_final, "wb") as f:
                                f.write(arquivo.read())
                            salvos += 1
                        except Exception as e:
                            st.error(f"Erro ao salvar '{arquivo.name}': {e}")
                            
                    st.success(f"✅ Sucesso! {salvos} arquivo(s) de imagem foram alocados no diretório físico.")
                    backup_local_para_nuvem_async()
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("Selecione ao menos um arquivo de imagem.")
        
        st.markdown("#### 📁 Mídias em Custódia Física")
        if not os.path.exists(LOGOS_DIR) or not os.listdir(LOGOS_DIR):
            st.info("Diretório de logos vazio.")
        else:
            arquivos_existentes = sorted([f for f in os.listdir(LOGOS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))])
            
            for idx in range(0, len(arquivos_existentes), 4):
                cols = st.columns(4)
                for j in range(4):
                    if idx + j < len(arquivos_existentes):
                        nome_arq = arquivos_existentes[idx + j]
                        caminho_completo = os.path.join(LOGOS_DIR, nome_arq)
                        
                        with cols[j]:
                            with st.container(border=True):
                                renderizar_logo_harmonizada(caminho_completo)
                                st.markdown(f"<p style='font-size:0.75rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'><b>Arquivo:</b> {nome_arq}</p>", unsafe_allow_html=True)
                                if st.button("🗑️ Eliminar", key=f"del_logo_adm_{idx+j}", use_container_width=True):
                                    try:
                                        if os.path.exists(caminho_completo):
                                            os.remove(caminho_completo)
                                            st.success("Removido")
                                            backup_local_para_nuvem_async()
                                            time.sleep(0.5)
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")

    # ==========================================
    # ABA 3: ESTATÍSTICAS E VOLUMES
    # ==========================================
    with tab_dados:
        st.subheader("📈 Volumes Cadastrados na Oficina")
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM veiculos")
            qtd_v = cursor.fetchone()[0]
            st.metric("Total de Veículos/Mapas Mapeados", f"{qtd_v} modelos")
        except Exception:
            st.info("Carregando volumes armazenados...")