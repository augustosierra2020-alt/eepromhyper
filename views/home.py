import streamlit as st
import json
from core.db import get_db_connection

def render_home():
    st.markdown("<h1 style='text-align: center;'>📊 Dashboard HyperTork</h1>", unsafe_allow_html=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Métrica 1: Clientes cadastrados (da tabela clientes_fp)
    cursor.execute("SELECT COUNT(*) FROM clientes_fp")
    total_clientes = cursor.fetchone()[0] or 0
    
    # Métrica 2: Veículos feitos (Soma da quantidade de registros em cada JSON de planilha)
    cursor.execute("SELECT dados_json FROM planilhas_mensais")
    linhas_planilhas = cursor.fetchall()
    total_veiculos = 0
    for linha in linhas_planilhas:
        try:
            dados = json.loads(linha[0])
            total_veiculos += len(dados)
        except: pass
    
    # Métrica 3: Ordens de Serviço (da tabela os_salvas)
    cursor.execute("SELECT COUNT(*) FROM os_salvas")
    total_os = cursor.fetchone()[0] or 0

    c1, c2, c3 = st.columns(3)
    c1.metric("👥 Clientes cadastrados", f"{total_clientes}")
    c2.metric("🚀 Veículos feitos", f"{total_veiculos}")
    c3.metric("📄 Ordens de Serviço Emitidas", f"{total_os}")

    st.markdown("---")
    st.subheader("Ferramentas de Calibração")
    r1, r2 = st.columns(2)
    if r1.button("🛠️ Comparador HEX & Firmwares", use_container_width=True): st.session_state.app_mode = "HEX_COMPARE"; st.rerun()
    if r2.button("⚙️ Mapas EEPROM Avançado", use_container_width=True): st.session_state.app_mode = "EEPROM"; st.rerun()
    
    r3, r4 = st.columns(2)
    if r3.button("📊 Gestão & Batch OS", use_container_width=True): st.session_state.app_mode = "GESTAO_OS"; st.rerun()
    if r4.button("🚗 Universal OBD2 Scanner", use_container_width=True): st.session_state.app_mode = "OBD2"; st.rerun()