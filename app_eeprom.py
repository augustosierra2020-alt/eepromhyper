import streamlit as st
import json
import re
import time
from core.db import init_db

# Importação dos Módulos/Telas (Views)
from views.home import render_home
from views.hex_compare import render_hex_compare
from views.eeprom_view import render_eeprom
from views.gestao_os import render_gestao_os
from views.obd2_view import render_obd2
from views.adm_view import render_adm

# Importação dos Serviços (Nuvem)
from services.hf_sync import sincronizar_nuvem_para_local

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E CSS VISUAL
# ==========================================
st.set_page_config(page_title="HyperTork System Hub", page_icon="⚙️", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="css"]  { overflow-x: hidden; }
    .block-container { padding-top: 2rem; max-width: 1200px; }
    
    .big-hub-btn-link { text-decoration: none !important; display: block !important; width: 100% !important; }
    .big-hub-btn { display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; height: 160px !important; padding: 20px !important; border-radius: 20px !important; box-shadow: 0 8px 20px rgba(0,0,0,0.2) !important; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important; text-align: center !important; margin-bottom: 25px !important; border: 1px solid rgba(255,255,255,0.05); backdrop-filter: blur(8px); }
    .btn-blue { background: linear-gradient(135deg, #1976D2 0%, #0D47A1 100%) !important; }
    .btn-red { background: linear-gradient(135deg, #D32F2F 0%, #B71C1C 100%) !important; }
    .btn-green { background: linear-gradient(135deg, #388E3C 0%, #1B5E20 100%) !important; }
    .btn-purple { background: linear-gradient(135deg, #8E24AA 0%, #4A148C 100%) !important; }
    .big-hub-btn:hover { transform: translateY(-8px) scale(1.02) !important; box-shadow: 0 15px 30px rgba(0,0,0,0.4) !important; border: 1px solid rgba(255,255,255,0.2); }
    .big-hub-btn .emoji-icon { font-size: 3.5rem !important; line-height: 1 !important; margin-bottom: 12px !important; filter: drop-shadow(0px 4px 4px rgba(0,0,0,0.3)); }
    .big-hub-btn h2 { color: #FFFFFF !important; margin: 0 !important; font-weight: 700 !important; font-size: 1.25rem !important; letter-spacing: 0.5px !important; text-transform: uppercase; text-shadow: 0px 2px 4px rgba(0,0,0,0.5); }
    
    /* Configuração e Posicionamento do Chip Pop-up */
    div[data-testid="stPopover"] { 
        position: fixed !important; 
        bottom: 30px !important; 
        right: 30px !important; 
        z-index: 999999 !important; 
        max-width: 70px !important;
        width: 70px !important;
        height: 70px !important;
    }
    
    /* Botão Laranja Embelezado */
    div[data-testid="stPopover"] > button {
        background: linear-gradient(135deg, #ff8c00 0%, #ff4500 100%) !important;
        color: white !important;
        border-radius: 50% !important;
        width: 70px !important; height: 70px !important;
        border: 2px solid white !important;
        box-shadow: 0 10px 20px rgba(255, 69, 0, 0.4) !important;
        font-size: 30px !important;
        transition: all 0.3s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
    }
    
    div[data-testid="stPopover"] > button:hover {
        transform: scale(1.1) rotate(10deg) !important;
        box-shadow: 0 15px 30px rgba(255, 69, 0, 0.6) !important;
    }
    
    div[data-testid="stPopover"] > button p { 
        font-size: 30px !important; 
        margin: 0 !important; 
        line-height: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INICIALIZAÇÃO DE ESTADOS E PROTEÇÕES
# ==========================================
if "startup_ok" not in st.session_state:
    # Baixa o banco da nuvem para garantir que as tabelas locais estejam atualizadas
    sincronizar_nuvem_para_local()  
    # Inicializa o pool de conexões com segurança
    init_db()                       
    st.session_state.startup_ok = True
    st.session_state.app_mode = "HOME"
    st.session_state.adm_logged_in = False
    st.session_state.chat_historico = [{"role": "assistant", "content": "Olá chefe! Sou o Chip. Como posso ajudar na oficina hoje?"}]

# Captura redirecionamentos via query params (Cliques rápidos)
params = st.query_params
if "page" in params:
    st.session_state.app_mode = params["page"]
    st.query_params.clear()

# ==========================================
# 3. MODAL DE SEGURANÇA ADM ROOM
# ==========================================
@st.dialog("🔓 Restrito - Autenticação Adm Room")
def modal_login_adm():
    st.write("Forneça as credenciais administrativas do HyperTork System:")
    user_input = st.text_input("Usuário", placeholder="adm01")
    pass_input = st.text_input("Senha", type="password", placeholder="•••••")
    if st.button("Autenticar Panel", type="primary", use_container_width=True):
        if user_input == "adm01" and pass_input == "12345":
            st.session_state.adm_logged_in = True
            st.session_state.app_mode = "ADM_ROOM"
            st.success("Acesso autorizado com sucesso!")
            st.rerun()
        else:
            st.error("Credenciais inválidas. Tente novamente.")

# ==========================================
# 4. BARRA LATERAL (MENU DE NAVEGAÇÃO)
# ==========================================
st.sidebar.title("🛡️ HyperTork Hub")

if st.session_state.app_mode != "HOME":
    if st.sidebar.button("🎮 Voltar ao Menu Principal", use_container_width=True, type="primary"):
        st.session_state.app_mode = "HOME"
        st.rerun()
    st.sidebar.markdown("---")
else:
    st.sidebar.info("📌 Escolha uma das ferramentas abaixo ou no painel principal.")

# Botões de Navegação
if st.sidebar.button("🏠 Home / Dashboard", use_container_width=True): st.session_state.app_mode = "HOME"; st.rerun()
if st.sidebar.button("🛠️ HEX Studio", use_container_width=True): st.session_state.app_mode = "HEX_COMPARE"; st.rerun()
if st.sidebar.button("⚙️ EEPROM Maps", use_container_width=True): st.session_state.app_mode = "EEPROM"; st.rerun()
if st.sidebar.button("📊 Gestão & OS Lote", use_container_width=True): st.session_state.app_mode = "GESTAO_OS"; st.rerun()
if st.sidebar.button("🚗 Códigos de Falha OBD2", use_container_width=True): st.session_state.app_mode = "OBD2"; st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🔑 Adm Room", use_container_width=True):
    if st.session_state.adm_logged_in: 
        st.session_state.app_mode = "ADM_ROOM"
        st.rerun()
    else: 
        modal_login_adm()

# ==========================================
# 5. ROTEADOR DE INTERFACES (VIEWS MODULARES)
# ==========================================
modo = st.session_state.app_mode

if modo == "HOME": 
    render_home()
elif modo == "HEX_COMPARE": 
    render_hex_compare()
elif modo == "EEPROM": 
    render_eeprom()
elif modo == "GESTAO_OS": 
    render_gestao_os()
elif modo == "OBD2": 
    render_obd2()
elif modo == "ADM_ROOM":
    if not st.session_state.adm_logged_in:
        st.warning("Você não está autenticado.")
        if st.button("Ir para a Home"): 
            st.session_state.app_mode = "HOME"
            st.rerun()
    else:
        render_adm()
else:
    render_home()

# ==========================================
# 6. CENTRAL ASSISTENTE CHIP (POP-UP FLUTUANTE)
# ==========================================
with st.popover("🤖"):
    st.markdown("#### 💬 Chip Assistant")
    
    # Renderiza mensagens anteriores do chat
    for msg in st.session_state.chat_historico:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]): 
                st.markdown(msg["content"])
                
    # Interface de entrada otimizada
    prompt = st.chat_input("Diga um código DTC ou pergunte algo...")
    if prompt:
        st.session_state.chat_historico.append({"role": "user", "content": prompt})
        
        # Inteligência de Resposta Direta
        if any(c.isdigit() for c in prompt) and "P" in prompt.upper():
            resp = f"🔧 **Análise de Diagnóstico ({prompt.upper()}):** Detectei que este código refere-se a uma anomalia no sistema. Recomendo verificar os sensores de oxigênio e a estanqueidade do escape."
        else:
            resp = "Chefe, recebi sua mensagem. Estou monitorando os sistemas da HyperTork e pronto para processar seus arquivos HEX."
        
        st.session_state.chat_historico.append({"role": "assistant", "content": resp})
        st.rerun()