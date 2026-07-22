import os
import base64
import streamlit as st
from core.db import get_db_connection

# Garante o mapeamento direto na raiz absoluta
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
CAMINHO_LOGO_PRINCIPAL = os.path.join(BASE_DIR, "Logos", "logo.png")

def render_home():
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
            st.markdown("<h1 style='text-align: center; color: white;'>🚀 HyperTork Hub</h1>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center; color: white;'>🚀 HyperTork Hub</h1>", unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center; color: #1E88E5; margin-bottom: 20px; font-weight: 700; letter-spacing: 0.5px;'>PAINEL DE CONTROLE OPERACIONAL</h2>", unsafe_allow_html=True)

    # --- DASHBOARD RESTAURADO ---
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM montadoras")
        total_m = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM veiculos")
        total_v = cursor.fetchone()[0]
        
        st.markdown("### 📊 Dashboard: Visão Geral do Sistema")
        m1, m2, m3 = st.columns(3)
        m1.metric("Montadoras no Cofre", total_m)
        m2.metric("Mapas de Veículos Ativos", total_v)
        m3.metric("Status Operacional", "Online 🟢")
        st.markdown("---")
    except Exception:
        pass

    # --- GRID DE BOTÕES ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
            <div class="big-hub-btn btn-blue">
                <div class="emoji-icon">🛠️</div>
                <h2>HEX Studio</h2>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Acessar Estúdio HEX", key="btn_nav_hex", use_container_width=True, type="secondary"):
            st.session_state.app_mode = "HEX_COMPARE"
            st.rerun()
                
    with col2:
        st.markdown("""
            <div class="big-hub-btn btn-purple">
                <div class="emoji-icon">⚙️</div>
                <h2>EEPROM Maps</h2>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Acessar Bancada EEPROM", key="btn_nav_eeprom", use_container_width=True, type="secondary"):
            st.session_state.app_mode = "EEPROM"
            st.rerun()

    with col3:
        st.markdown("""
            <div class="big-hub-btn btn-green">
                <div class="emoji-icon">📊</div>
                <h2>Gestão & OS</h2>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Acessar Gestão Operacional", key="btn_nav_gestao", use_container_width=True, type="secondary"):
            st.session_state.app_mode = "GESTAO_OS"
            st.rerun()
                
    with col4:
        st.markdown("""
            <div class="big-hub-btn btn-red">
                <div class="emoji-icon">🚗</div>
                <h2>Scanner OBD2</h2>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Acessar Diagnóstico DTC", key="btn_nav_obd2", use_container_width=True, type="secondary"):
            st.session_state.app_mode = "OBD2"
            st.rerun()