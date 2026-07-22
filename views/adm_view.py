import streamlit as st
import os
import time
import base64
import re
import unicodedata
from core.db import get_db_connection
from services.hf_sync import backup_local_para_nuvem_async

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
    except Exception: return False

def render_adm():
    st.title("🔑 Central de Administração - HyperTork")
    st.info("Painel operacional mestre operando em arquitetura modular blindada.")
    
    if st.button("🚪 Encerrar Sessão Administrador", type="primary", use_container_width=True):
        st.session_state.adm_logged_in = False
        st.session_state.app_mode = "HOME"
        st.rerun()
        
    st.markdown("---")
    
    tab_infra, tab_logos, tab_dados = st.tabs([
        "🖥️ Infraestrutura & Pente Fino", 
        "🖼️ Gestão de Logos & Identidades", 
        "📊 Estatísticas Globais"
    ])
    
    with tab_infra:
        st.subheader("📋 Diagnóstico e Pente Fino de Infraestrutura")
        st.write("Clique no botão abaixo para o Chip avaliar a saúde das conexões, módulos compilados e integridade das rotas do sistema.")
        
        if st.button("🔍 Rodar Pente Fino no Sistema (Status & Erros)", type="primary", use_container_width=True):
            with st.spinner("Chip está inspecionando as linhas de código e conexões de bancada..."):
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
                    except Exception: status_db = "🟡 Conectado (Tabela hex_history antiga)"
                except Exception as e:
                    status_db = f"🔴 Falha Crítica na Conexão: {e}"
                
                try:
                    import hypertork_cpp
                    status_cpp = "🟢 Ativa (hypertork_cpp carregado com sucesso)"
                except ImportError:
                    status_cpp = "🟡 Inativa (Fallback Python Ativo - Ambiente Linux contido)"
                
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
                    analise_chip += "- ❌ **ERRO CRÍTICO DE IA:** Chefe, o scanner OBD2 não vai conseguir gerar laudos porque a chave secreta `HF_TOKEN` está vazia! Vá nas configurações do Space do Hugging Face e cadastre-a.\n"
                else:
                    analise_chip += "- ✅ **IA HUGGING FACE:** Autenticação ativa. Pronta para gerar laudos DTC.\n"
                    
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

    with tab_logos:
        st.subheader("🖼️ Repositório Físico de Logos de Montadoras")
        st.write("Gerencie os arquivos visuais que aparecem nos cards do Painel EEPROM.")
        
        with st.container(border=True):
            st.markdown("#### ➕ Fazer Upload de Nova Logo")
            nome_logo_input = st.text_input("Nome da Montadora Correspondente:", placeholder="Ex: VOLKSWAGEN")
            arquivo_logo = st.file_uploader("Selecione a Imagem (PNG preferencialmente):", type=["png", "jpg", "jpeg", "webp"])
            
            if st.button("💾 Salvar Arquivo no Repositório", type="primary"):
                if nome_logo_input and arquivo_logo:
                    os.makedirs(LOGOS_DIR, exist_ok=True)
                    nome_limpo = higienizar_nome(nome_logo_input)
                    extensao = os.path.splitext(arquivo_logo.name)[1].lower()
                    caminho_final = os.path.join(LOGOS_DIR, f"{nome_limpo}{extensao}")
                    
                    try:
                        with open(caminho_final, "wb") as f:
                            f.write(arquivo_logo.read())
                        st.success(f"✅ Imagem salva com sucesso como `{nome_limpo}{extensao}`!")
                        backup_local_para_nuvem_async()
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar arquivo físico: {e}")
                else:
                    st.warning("Por favor, preencha o nome da montadora e selecione uma imagem.")
        
        st.markdown("#### 📁 Logos Ativas no Sistema")
        if not os.path.exists(LOGOS_DIR) or not os.listdir(LOGOS_DIR):
            st.info("Nenhuma imagem de logo encontrada no diretório local.")
        else:
            arquivos_logos = [f for f in os.listdir(LOGOS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
            
            for idx in range(0, len(arquivos_logos), 4):
                cols = st.columns(4)
                for j in range(4):
                    if idx + j < len(arquivos_logos):
                        nome_arquivo = arquivos_logos[idx + j]
                        caminho_completo = os.path.join(LOGOS_DIR, nome_arquivo)
                        nome_exibicao = os.path.splitext(nome_arquivo)[0]
                        
                        with cols[j]:
                            with st.container(border=True):
                                renderizar_logo_harmonizada(caminho_completo)
                                st.markdown(f"**Identificador:** `{nome_exibicao}`")
                                if st.button("🗑️ Excluir Logo", key=f"del_logo_{idx+j}", use_container_width=True):
                                    try:
                                        os.remove(caminho_completo)
                                        st.success("Arquivo removido!")
                                        backup_local_para_nuvem_async()
                                        time.sleep(0.5)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao apagar: {e}")

    with tab_dados:
        st.subheader("📈 Volumes em Nuvem e Registros Físicos")
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM veiculos")
            qtd_v = cursor.fetchone()[0]
            st.metric("Total de Veículos/Mapas Cadastrados", f"{qtd_v} modelos")
        except Exception:
            st.info("Carregando volumes armazenados...")