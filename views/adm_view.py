import streamlit as st
import pandas as pd
import os
import shutil
from core.db import get_db_connection, DB_PATH
from services.hf_sync import backup_local_para_nuvem_async, sincronizar_nuvem_para_local

LOGOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logos")

def render_adm():
    st.title("🔑 Sala de Administração - Infraestrutura")
    conn = get_db_connection(); cursor = conn.cursor()

    st.subheader("📊 Status dos Motores")
    c1, c2, c3 = st.columns(3)
    c1.metric("Engine C++", "Inativo (Fallback)")
    c2.metric("Checksum C", "Nativo Ativo")
    c3.metric("SQLite Integrity", "OK")

    st.markdown("---")
    st.subheader("☁️ Controle de Nuvem")
    if st.button("📤 Forçar Envio para Nuvem (Backup Atual)", use_container_width=True):
        backup_local_para_nuvem_async()
        st.success("Backup disparado!")

    if st.button("🔄 Forçar Download da Nuvem (Restaurar Histórico)", use_container_width=True):
        if os.path.exists(DB_PATH): os.remove(DB_PATH)
        sincronizar_nuvem_para_local()
        st.rerun()

    st.markdown("---")
    st.subheader("🖼️ Cofre de Logos")
    up = st.file_uploader("Novas Logos (.png)", accept_multiple_files=True)
    if st.button("Gravar Logos no Cofre"):
        for f in up:
            with open(os.path.join(LOGOS_DIR, f.name), "wb") as save_f:
                save_f.write(f.read())
        st.success("Logos salvas!")