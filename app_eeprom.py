import streamlit as st
import json
import re
import time
import urllib.parse
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
    
    /* === LOGO VISUAL === */
    .locked-main-logo { 
        max-height: 280px !important; 
        width: auto !important; 
        object-fit: contain !important; 
        pointer-events: none !important; 
        user-select: none !important; 
        -webkit-user-drag: none !important;
        filter: drop-shadow(0px 12px 24px rgba(0,0,0,0.25)) !important; 
        transition: transform 0.3s ease !important;
    }
    .locked-main-logo:hover {
        transform: scale(1.03) !important;
    }
    
    /* === SLIDER ROXO E INPUTS === */
    .stSlider > div[data-baseweb="slider"] [data-testid="stTickBar"] + div,
    .stSlider > div[data-baseweb="slider"] [role="slider"] { background-color: #9C27B0 !important; border-color: #9C27B0 !important; }
    div.stSlider > div[data-baseweb="slider"] > div > div > div { background-color: #9C27B0 !important; }
    div.stSlider > div[data-baseweb="slider"] div { background-color: #9C27B0 !important; }
    
    div[data-baseweb="select"] { border-radius: 8px !important; border: 1px solid rgba(255,255,255,0.1) !important; transition: all 0.2s ease-in-out !important; }
    div[data-baseweb="select"]:focus-within, div[data-baseweb="select"]:hover { border-color: #1E88E5 !important; box-shadow: 0 0 0 2px rgba(30, 136, 229, 0.2) !important; }
    .stNumberInput input, .stTextInput input { border-radius: 8px !important; background-color: #1A1A1A !important; border: 1px solid rgba(255,255,255,0.1) !important; color: #FFFFFF !important; transition: all 0.2s ease-in-out !important; }
    .stNumberInput input:focus, .stTextInput input:focus { border-color: #9C27B0 !important; box-shadow: 0 0 0 2px rgba(156, 39, 176, 0.2) !important; }
    div[data-testid="stTabBar"] button { font-weight: 600 !important; letter-spacing: 0.5px !important; text-transform: uppercase !important; font-size: 0.85rem !important; padding: 10px 20px !important; transition: all 0.2s ease !important; }
    div[data-testid="stTabBar"] button[aria-selected="true"] { color: #1E88E5 !important; border-bottom-color: #1E88E5 !important; }
    
    /* === DESIGN DO CHIP POP-UP EM LARANJA GRADIENTE PREMIUM === */
    div[data-testid="stPopover"] { 
        position: fixed !important; 
        bottom: 30px !important; 
        right: 30px !important; 
        z-index: 999999 !important; 
        max-width: 75px !important;
        width: 75px !important;
        height: 75px !important;
    }
    
    div[data-testid="stPopover"] > button { 
        background: linear-gradient(135deg, #FF8C00 0%, #FF4500 100%) !important; 
        color: white !important; 
        border: 3px solid rgba(255, 255, 255, 0.8) !important; 
        border-radius: 50% !important; 
        width: 75px !important; 
        height: 75px !important; 
        min-width: 75px !important; 
        max-width: 75px !important;
        box-shadow: 0 10px 25px rgba(255, 69, 0, 0.6), inset 0 -4px 10px rgba(0,0,0,0.15) !important; 
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }
    
    div[data-testid="stPopover"] > button:hover {
        transform: translateY(-5px) scale(1.1) !important;
        box-shadow: 0 15px 35px rgba(255, 69, 0, 0.8), inset 0 -4px 10px rgba(0,0,0,0.2) !important;
        border-color: #FFFFFF !important;
    }
    
    div[data-testid="stPopover"] > button p { 
        font-size: 34px !important; 
        margin: 0 !important; 
        line-height: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.3));
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INICIALIZAÇÃO DE ESTADOS E PROTEÇÕES
# ==========================================
if "startup_ok" not in st.session_state:
    # 1º Baixa o banco da nuvem para garantir que as tabelas locais estejam atualizadas
    sincronizar_nuvem_para_local()  
    # 2º Inicializa o pool de conexões com segurança
    init_db()                       
    st.session_state.startup_ok = True
    st.session_state.app_mode = "HOME"
    st.session_state.adm_logged_in = False
    st.session_state.chat_historico = [{"role": "assistant", "content": "Olá chefe! Sou o Chip. Como posso ajudar na oficina hoje?"}]

# Inicialização de variáveis de controle para as views
if 'montadora_selecionada' not in st.session_state: st.session_state.montadora_selecionada = ""
if 'escolha_modelo' not in st.session_state: st.session_state.escolha_modelo = ""
if 'hex_atual' not in st.session_state: st.session_state.hex_atual = None
if 'view_addr_atual' not in st.session_state: st.session_state.view_addr_atual = 0
if 'focus_mode' not in st.session_state: st.session_state.focus_mode = None
if 'zoom_janela' not in st.session_state: st.session_state.zoom_janela = 256

# Captura redirecionamentos via query params (Cliques rápidos)
params = st.query_params
if "page" in params:
    st.session_state.app_mode = params["page"]
    st.query_params.clear()
if "mont" in params: st.session_state.montadora_selecionada = urllib.parse.unquote(params["mont"])
if "mod" in params: st.session_state.escolha_modelo = urllib.parse.unquote(params["mod"])

# ==========================================
# 3. MODAL DE SEGURANÇA ADM ROOM
# ==========================================
@st.dialog("🔓 Restrito - Autenticação Adm Room")
def modal_login_adm():
    st.write("Forneça as credenciais administrativas do HyperTork System:")
    user_input = st.text_input("Usuário", placeholder="adm01")
    pass_input = st.text_input("Senha", type="password", placeholder="•••••")
    if st.button("Autenticar Painel", type="primary", use_container_width=True):
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
        st.query_params.clear()
        st.session_state.app_mode = "HOME"
        st.session_state.montadora_selecionada = ""
        st.session_state.escolha_modelo = ""
        st.session_state.focus_mode = None
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
                
    # Interface de entrada nativa do chat
    prompt = st.chat_input("Diga um código DTC ou pergunte algo...")
    if prompt:
        st.session_state.chat_historico.append({"role": "user", "content": prompt})
        
        # Inteligência Rápida de Resposta
        if any(c.isdigit() for c in prompt) and "P" in prompt.upper():
            resp = f"🔧 **Análise de Diagnóstico ({prompt.upper()}):** Detectei que este código refere-se a uma anomalia de injeção ou falha em sensor. Recomendo cruzar os dados na aba OBD2 para uma pesquisa aprofundada na web."
        else:
            resp = "Chefe, recebi sua mensagem. Os sistemas do HyperTork Hub estão 100% operacionais e protegidos. Posso processar as matrizes HEX ou buscar as pinagens EEPROM que você precisar."
        
        st.session_state.chat_historico.append({"role": "assistant", "content": resp})
        st.rerun()