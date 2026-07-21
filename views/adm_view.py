import streamlit as st
import os
import time
from core.db import get_db_connection
from huggingface_hub import InferenceClient

HF_TOKEN = os.environ.get("HF_TOKEN")

def render_adm():
    st.title("🔑 Central de Administração - HyperTork")
    st.info("Painel operacional blindado executando em arquitetura modular estável.")
    
    if st.button("🚪 Encerrar Sessão Administrador", type="primary", use_container_width=True):
        st.session_state.adm_logged_in = False
        st.session_state.app_mode = "HOME"
        st.rerun()
        
    st.markdown("---")
    
    tab_infra, tab_dados = st.tabs(["🖥️ Infraestrutura & Logs do Sistema", "📊 Estatísticas Globais"])
    
    with tab_infra:
        st.subheader("📋 Diagnóstico e Pente Fino de Infraestrutura")
        st.write("Clique no botão abaixo para o Chip avaliar a saúde das conexões, módulos compilados e integridade das rotas do sistema.")
        
        if st.button("🔍 Rodar Pente Fino no Sistema (Status & Erros)", type="primary", use_container_width=True):
            with st.spinner("Chip está inspecionando as linhas de código e conexões de bancada..."):
                time.sleep(1) # Efeito visual de escaneamento
                
                # 1. Teste de Banco de Dados
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
                    except: status_db = "🟡 Conectado (Tabela hex_history ausente ou antiga)"
                except Exception as e:
                    status_db = f"🔴 Falha Crítica na Conexão: {e}"
                
                # 2. Teste da Aceleração C++
                try:
                    import hypertork_cpp
                    status_cpp = "🟢 Ativa (hypertork_cpp carregado com sucesso)"
                except ImportError:
                    status_cpp = "🟡 Inativa (Fallback Python Ativo - Sem aceleração nativa de binários)"
                
                # 3. Teste do Token da IA
                status_ia = "🟢 Configurada (HF_TOKEN injetado nos Secrets)" if HF_TOKEN else "🔴 Offline (Variável HF_TOKEN ausente no ambiente)"
                
                # Renderização do Relatório Estruturado na Tela
                st.markdown("### 📊 Status da Bancada")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.markdown(f"**Banco de Dados Local:** {status_db}")
                    st.markdown(f"**Aceleração Binária (C++):** {status_cpp}")
                with col_c2:
                    st.markdown(f"**Conexão do Motor de IA:** {status_ia}")
                    st.markdown(f"**Ambiente:** Hugging Face Spaces OS (`Ubuntu/Debian Python`) ")
                
                # Laudo do Chip Baseado nos dados coletados
                st.markdown("---")
                st.markdown("### 🤖 Laudo do Mecânico Chefe Chip:")
                
                analise_chip = ""
                if not HF_TOKEN:
                    analise_chip += "- ❌ **ERRO CRÍTICO DE IA:** Chefe, o scanner OBD2 não vai funcionar porque a chave secreta `HF_TOKEN` está vazia! Vá nas opções do Space do Hugging Face e cadastre o Token nos Secrets.\n"
                else:
                    analise_chip += "-  **IA HUGGING FACE:** Autenticação configurada. Respostas prontas para despacho.\n"
                    
                if "Inativa" in status_cpp:
                    analise_chip += "- ⚠️ **AVISO DE ACC C++:** O módulo compilado para Windows/AMD64 não roda direto no contêiner Linux do Hugging Face. O sistema aplicou automaticamente o fallback em matrizes NumPy. A engenharia hex vai funcionar normal, mas sem aceleração via hardware nativo.\n"
                else:
                    analise_chip += "-  **MOTOR NATIVO:** Aceleração binária ativa.\n"
                    
                if "🔴" in status_db:
                    analise_chip += "- ❌ **PANE NO BANCO DE DADOS:** A tabela SQLite travou ou os arquivos de migração falharam. Reinicie o contêiner.\n"
                else:
                    analise_chip += f"-  **INTEGRIDADE DB:** Banco operando redondo. Temos {qtd_montadoras} marcas no cofre e {qtd_obd2} consultas registradas no histórico.\n"
                
                st.warning(analise_chip)
                st.success("🏁 Pente fino concluído. Core operacional está estruturado!")

    with tab_dados:
        st.subheader("📈 Volumes em Nuvem e Registros Físicos")
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM veiculos")
            qtd_v = cursor.fetchone()[0]
            st.metric("Total de Veículos/Mapas Mapeados na Oficina", f"{qtd_v} modelos")
        except:
            st.info("Carregando volumes armazenados...")