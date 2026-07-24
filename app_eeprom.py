import streamlit as st
import json
import re
import time
import urllib.parse

# 1. Configuração da Página (Deve ser o primeiro comando Streamlit)
st.set_page_config(
    page_title="HyperTork System Hub",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Importação do Banco de Dados e Serviços
from core.db import init_db
from services.hf_sync import sincronizar_nuvem_para_local

# Importação dos Módulos / Telas (Views)
from views.home import render_home
from views.hex_compare import render_hex_compare
from views.eeprom_view import render_eeprom
from views.gestao_os import render_gestao_os
from views.obd2_view import render_obd2
from views.adm_view import render_adm

# ==========================================
# 1. INJEÇÃO CSS GLOBAL (BOTÕES E CHIP ASSISTANT)
# ==========================================
st.markdown("""
    <style>
    /* Estilização Geral da Aplicação */
    html, body, [class*="css"] { overflow-x: hidden; }
    .block-container { padding-top: 2rem; max-width: 1200px; }
    
    /* =========================================================
       TODOS OS BOTÕES DO SISTEMA (Sidebar, Hub e Telas) 
       ========================================================= */
    div[data-testid="stButton"] button {
        background: linear-gradient(135deg, #FF8C00 0%, #E65100 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 50px !important;
        padding: 10px 25px !important;
        font-weight: bold !important;
        font-size: 16px !important;
        box-shadow: 0 8px 20px rgba(230, 81, 0, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    div[data-testid="stButton"] button:hover {
        transform: translateY(-3px) scale(1.02) !important;
        box-shadow: 0 12px 25px rgba(230, 81, 0, 0.6) !important;
        color: white !important;
    }

    /* Cartões Grandes do Hub Visual */
    .big-hub-btn-link { text-decoration: none !important; display: block !important; width: 100% !important; }
    .big-hub-btn { 
        display: flex !important; 
        flex-direction: column !important; 
        align-items: center !important; 
        justify-content: center !important; 
        height: 160px !important; 
        padding: 20px !important; 
        border-radius: 20px !important; 
        box-shadow: 0 8px 20px rgba(0,0,0,0.2) !important; 
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important; 
        text-align: center !important; 
        margin-bottom: 25px !important; 
        border: 1px solid rgba(255,255,255,0.05); 
        backdrop-filter: blur(8px); 
    }
    .btn-blue { background: linear-gradient(135deg, #1976D2 0%, #0D47A1 100%) !important; }
    .btn-red { background: linear-gradient(135deg, #D32F2F 0%, #B71C1C 100%) !important; }
    .btn-green { background: linear-gradient(135deg, #388E3C 0%, #1B5E20 100%) !important; }
    .btn-purple { background: linear-gradient(135deg, #8E24AA 0%, #4A148C 100%) !important; }
    .big-hub-btn:hover { 
        transform: translateY(-8px) scale(1.02) !important; 
        box-shadow: 0 15px 30px rgba(0,0,0,0.4) !important; 
        border: 1px solid rgba(255,255,255,0.2); 
    }
    .big-hub-btn .emoji-icon { font-size: 3.5rem !important; line-height: 1 !important; margin-bottom: 12px !important; filter: drop-shadow(0px 4px 4px rgba(0,0,0,0.3)); }
    .big-hub-btn h2 { color: #FFFFFF !important; margin: 0 !important; font-weight: 700 !important; font-size: 1.25rem !important; letter-spacing: 0.5px !important; text-transform: uppercase; text-shadow: 0px 2px 4px rgba(0,0,0,0.5); }
    
    /* Logo e Sliders Customizados */
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
    .locked-main-logo:hover { transform: scale(1.03) !important; }
    
    .stSlider > div[data-baseweb="slider"] [data-testid="stTickBar"] + div,
    .stSlider > div[data-baseweb="slider"] [role="slider"] { background-color: #FF8C00 !important; border-color: #FF8C00 !important; }
    div.stSlider > div[data-baseweb="slider"] > div > div > div { background-color: #FF8C00 !important; }
    
    div[data-baseweb="select"] { border-radius: 8px !important; border: 1px solid rgba(255,255,255,0.1) !important; transition: all 0.2s ease-in-out !important; }
    div[data-baseweb="select"]:focus-within, div[data-baseweb="select"]:hover { border-color: #FF8C00 !important; box-shadow: 0 0 0 2px rgba(255, 140, 0, 0.2) !important; }
    .stNumberInput input, .stTextInput input { border-radius: 8px !important; background-color: #1A1A1A !important; border: 1px solid rgba(255,255,255,0.1) !important; color: #FFFFFF !important; }
    .stNumberInput input:focus, .stTextInput input:focus { border-color: #FF8C00 !important; box-shadow: 0 0 0 2px rgba(255, 140, 0, 0.2) !important; }
    
    /* =========================================================
       BOTÃO FLUTUANTE DO ASSISTENTE CHIP (POPOVER)
       ========================================================= */
    div[data-testid="stPopover"] {
        position: fixed !important;
        bottom: 25px !important;
        right: 25px !important;
        z-index: 999999 !important;
        width: 60px !important;
        height: 60px !important;
    }
    div[data-testid="stPopover"] > button {
        background: linear-gradient(135deg, #FF8C00 0%, #E65100 100%) !important;
        color: #FFFFFF !important;
        border: 2px solid #FFFFFF !important;
        border-radius: 50% !important;
        width: 60px !important;
        height: 60px !important;
        min-width: 60px !important;
        max-width: 60px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 8px 25px rgba(230, 81, 0, 0.7) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }
    div[data-testid="stPopover"] > button p,
    div[data-testid="stPopover"] > button span {
        font-size: 28px !important;
        margin: 0 !important;
        line-height: 1 !important;
        color: #FFFFFF !important;
    }
    div[data-testid="stPopover"] > button:hover {
        transform: scale(1.12) translateY(-3px) !important;
        box-shadow: 0 12px 30px rgba(230, 81, 0, 0.9) !important;
    }
    div[data-testid="stPopoverBody"] {
        max-width: 380px !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        box-shadow: 0 15px 35px rgba(0,0,0,0.5) !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INICIALIZAÇÃO DE ESTADOS E PROTEÇÕES
# ==========================================
if "startup_ok" not in st.session_state:
    sincronizar_nuvem_para_local()  # Baixa banco da nuvem
    init_db()                       # Inicializa banco SQLite
    st.session_state.startup_ok = True
    st.session_state.app_mode = "HOME"
    st.session_state.adm_logged_in = False
    st.session_state.chat_historico = [
        {"role": "assistant", "content": "Oi, eu sou o Chip! Como posso ajudar na oficina hoje?"}
    ]

# Variáveis Globais de Controle de Sessão
if 'montadora_selecionada' not in st.session_state: st.session_state.montadora_selecionada = ""
if 'escolha_modelo' not in st.session_state: st.session_state.escolha_modelo = ""
if 'hex_atual' not in st.session_state: st.session_state.hex_atual = None
if 'view_addr_atual' not in st.session_state: st.session_state.view_addr_atual = 0
if 'focus_mode' not in st.session_state: st.session_state.focus_mode = None
if 'zoom_janela' not in st.session_state: st.session_state.zoom_janela = 256

# Captura redirecionamentos via URL query parameters
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

# Botões de Navegação Direta
if st.sidebar.button("🏠 Home / Dashboard", use_container_width=True): 
    st.session_state.app_mode = "HOME"; st.rerun()
if st.sidebar.button("🛠️ HEX Studio", use_container_width=True): 
    st.session_state.app_mode = "HEX_COMPARE"; st.rerun()
if st.sidebar.button("⚙️ EEPROM Maps", use_container_width=True): 
    st.session_state.app_mode = "EEPROM"; st.rerun()
if st.sidebar.button("📊 Gestão & OS Lote", use_container_width=True): 
    st.session_state.app_mode = "GESTAO_OS"; st.rerun()
if st.sidebar.button("🚗 Códigos de Falha OBD2", use_container_width=True): 
    st.session_state.app_mode = "OBD2"; st.rerun()

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
    
    # Histórico de Conversas
    for msg in st.session_state.chat_historico:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]): 
                st.markdown(msg["content"])
                
    # Entrada de Chat
    prompt = st.chat_input("Diga um código DTC ou pergunte algo...")
    if prompt:
        st.session_state.chat_historico.append({"role": "user", "content": prompt})
        
        # Resposta rápida do Chip
        if any(c.isdigit() for c in prompt) and "P" in prompt.upper():
            resp = f"🔧 **Análise de Diagnóstico ({prompt.upper()}):** Detectei que este código refere-se a uma anomalia de injeção ou falha em sensor. Recomendo cruzar os dados na aba OBD2 para uma pesquisa aprofundada na web."
        else:
            resp = "Oi, eu sou o Chip! Como posso ajudar?"
        
        st.session_state.chat_historico.append({"role": "assistant", "content": resp})
        st.rerun()

# Bloco de execução principal (Opcional no Streamlit, mas garante consistência caso executado via python direto)
if __name__ == "__main__":
    pass