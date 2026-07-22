import os
import base64
import streamlit as st

# Garante o mapeamento direto na raiz absoluta, ignorando a subpasta views
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
CAMINHO_LOGO_PRINCIPAL = os.path.join(BASE_DIR, "Logos", "logo.png")

def render_home():
    # Renderização da Logo Principal via Conversão Base64 Blindada
    if os.path.exists(CAMINHO_LOGO_PRINCIPAL):
        try:
            with open(CAMINHO_LOGO_PRINCIPAL, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            st.markdown(
                f'<div style="text-align: center; margin-bottom: 25px;">'
                f'<img src="data:image/png;base64,{encoded_string}" class="locked-main-logo">'
                f'</div>', 
                unsafe_allow_html=True
            )
        except Exception:
            st.title("🚀 HyperTork Hub")
    else:
        st.title("🚀 HyperTork Hub")

    st.markdown("<h2 style='text-align: center; color: #1E88E5; margin-bottom: 30px;'>Painel de Controle Operacional</h2>", unsafe_allow_html=True)

    # Grid Técnico de Atalhos Rápidos para Acesso (Agora com as 4 colunas originais!)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        with st.container(border=True):
            st.markdown("### 🛠️ HEX Studio")
            st.write("Estúdio avançado de calibração bidimensional e topologia tridimensional.")
            if st.button("Abrir HEX Studio", key="hub_go_hex", use_container_width=True):
                st.session_state.app_mode = "HEX_COMPARE"
                st.rerun()
                
    with col2:
        with st.container(border=True):
            st.markdown("### ⚙️ EEPROM Maps")
            st.write("Bancada digital de pinagens de ECU, esquemas técnicos e clonagem de memórias.")
            if st.button("Abrir EEPROM Maps", key="hub_go_eeprom", use_container_width=True):
                st.session_state.app_mode = "EEPROM"
                st.rerun()

    with col3:
        with st.container(border=True):
            st.markdown("### 📊 Gestão & OS")
            st.write("Gerenciamento financeiro, ordens de serviço em lote e emissão de laudos em PDF.")
            if st.button("Abrir Gestão & OS", key="hub_go_gestao", use_container_width=True):
                st.session_state.app_mode = "GESTAO_OS"
                st.rerun()
                
    with col4:
        with st.container(border=True):
            st.markdown("### 🚗 Scanner OBD2")
            st.write("Diagnóstico guiado por Inteligência Artificial ativa e cruzamento de falhas DTC.")
            if st.button("Abrir Scanner OBD2", key="hub_go_obd2", use_container_width=True):
                st.session_state.app_mode = "OBD2"
                st.rerun()