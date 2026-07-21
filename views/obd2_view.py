import streamlit as st
import pandas as pd
import os
from huggingface_hub import InferenceClient
from duckduckgo_search import DDGS
from core.db import get_db_connection
from services.hf_sync import backup_local_para_nuvem_async

HF_TOKEN = os.environ.get("HF_TOKEN")
API_TIMEOUT_SECONDS = 15

@st.cache_resource
def get_hf_client():
    if HF_TOKEN:
        try: return InferenceClient(token=HF_TOKEN, timeout=API_TIMEOUT_SECONDS)
        except: pass
    return None

def diagnostico_avancado_obd2(codigo, segmento="", montadora="", modelo="", ano=""):
    query = f"DTC fault code {codigo} {montadora} {modelo} symptoms causes repair"
    search_results = ""
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(query, max_results=3))
            for r in resultados: search_results += f"- {r['body']}\n"
    except Exception as e: 
        search_results = f"(Busca web temporariamente indisponível. Detalhe: {e})"
        
    if not HF_TOKEN:
        return f"⚠️ **IA Offline:** A variável `HF_TOKEN` não foi configurada nos Secrets do Hugging Face Spaces. Configure-a para ativar os laudos automáticos do Chip.\n\n**Dados brutos da internet:**\n{search_results}"

    system_prompt = "Você é 'Chip', um Mecânico Chefe Especialista em Diagnóstico Avançado. Retorne APENAS o laudo técnico estruturado OBRIGATORIAMENTE em: Significado, Descrição, Sintomas, Causas e Solução."
    user_prompt = f"Falha: {codigo}. Contexto: {segmento}|{montadora}|{modelo}|{ano}. Dados cruzados web:\n{search_results}"
    
    client = get_hf_client()
    if client:
        try:
            mensagens = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
            completude = client.chat_completion(model="Qwen/Qwen2.5-7B-Instruct", messages=mensagens, max_tokens=850, temperature=0.2)
            return completude.choices[0].message.content.strip()
        except Exception as e:
            return f"⚠️ **IA Offline (Erro na API):** Falha ao conectar ao modelo Qwen. Detalhe: {e}\n\n**Dados brutos da internet:**\n{search_results}"
    
    return f"⚠️ **IA Offline:** Cliente de inferência indisponível.\n\n**Dados brutos da internet:**\n{search_results}"

def salvar_pesquisa_obd2(codigo, segmento, montadora, modelo, ano, descricao):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO obd2_history (codigo, segmento, montadora, modelo, ano, descricao) VALUES (?, ?, ?, ?, ?, ?)", (codigo, segmento, montadora, modelo, ano, descricao))
        conn.commit()
        backup_local_para_nuvem_async()
    except Exception as e:
        st.toast(f"Erro ao salvar histórico OBD2: {e}", icon="⚠️")

def carregar_historico_obd2():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT codigo, segmento, montadora, modelo, ano, data, descricao FROM obd2_history ORDER BY id DESC LIMIT 30")
        return pd.DataFrame(cursor.fetchall(), columns=["Código", "Segmento", "Montadora", "Modelo", "Ano", "Data de Busca", "Laudo Técnico"])
    except: return pd.DataFrame()

def render_obd2():
    st.title("🛠️ Universal Diagnostic Hub (DTC)")
    
    with st.container(border=True):
        st.subheader("🔍 Nova Consulta de Scanner Avançada")
        col_obd1, col_obd2 = st.columns(2)
        codigo_input = col_obd1.text_input("Código de Falha OBD2 / DTC:", placeholder="Ex: P0420").strip().upper()
        segmento_input = col_obd2.selectbox("Segmento Veicular:", ["Leve (Carros)", "Pesado (Caminhões)", "Agrícola (Tratores)", "Motos"])
        
        col_obd3, col_obd4, col_obd5 = st.columns(3)
        montadora_input = col_obd3.text_input("Montadora (Fabricante):", placeholder="Ex: Volkswagen")
        modelo_input = col_obd4.text_input("Modelo do Veículo:", placeholder="Ex: Amarok V6")
        ano_input = col_obd5.text_input("Ano / Motorização:", placeholder="Ex: 2021 / 3.0 TDI")
        
        if st.button("🚀 Iniciar Diagnóstico Baseado em Inteligência Artificial", use_container_width=True, type="primary"):
            if codigo_input:
                with st.spinner(f"Analisando DTC {codigo_input} nos bancos de dados corporativos e internet..."):
                    desc = diagnostico_avancado_obd2(codigo_input, segmento_input, montadora_input, modelo_input, ano_input)
                    st.subheader(f"📋 Laudo Técnico Emitido: {codigo_input}")
                    st.info(desc)
                    salvar_pesquisa_obd2(codigo_input, segmento_input, montadora_input, modelo_input, ano_input, desc)
            else: 
                st.warning("Por favor, digite um código de falha válido para prosseguir.")
            
    st.markdown("---")
    st.subheader("📚 Histórico e Filtros Ativos de Falhas Consultadas")
    df_hist = carregar_historico_obd2()
    if not df_hist.empty:
        st.dataframe(df_hist, use_container_width=True)
    else: 
        st.info("Nenhuma pesquisa registrada no histórico local ou na nuvem até o momento.")