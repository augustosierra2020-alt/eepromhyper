import streamlit as st
import json
import os
from huggingface_hub import InferenceClient
from core.db import get_db_connection

HF_TOKEN = os.environ.get("HF_TOKEN")

def get_hf_client():
    if HF_TOKEN:
        try: return InferenceClient(token=HF_TOKEN, timeout=15)
        except Exception: pass
    return None

def obter_resumo_banco():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM montadoras"); m = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM os_salvas"); o = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM planilhas_mensais"); p = cursor.fetchone()[0]
        conn.close()
        return f"Montadoras: {m} | OS Gravadas: {o} | Fechamentos Mensais: {p}"
    except Exception:
        return "Resumo do banco indisponível."

def processar_linguagem_chip(historico_mensagens: list) -> str:
    client = get_hf_client()
    if not client: 
        return "⚠️ IA Offline (Chave HF_TOKEN não configurada ou instável)."
    
    dados_tela = {
        "Aba_Ativa": st.session_state.get("app_mode", "HOME"),
        "Montadora_Ativa": st.session_state.get("montadora_selecionada", "Nenhuma"),
        "Modelo_Ativo": st.session_state.get("escolha_modelo", "Nenhum"),
        "Mês_Aberto": st.session_state.get("os_mes_selecionado", "Nenhum"),
        "Cliente_Aberto": st.session_state.get("os_cliente_selecionado", "Nenhum"),
    }
    
    alerta_seguranca = ""
    if st.session_state.get("hex_atual") and len(st.session_state.hex_atual.get("diffs", [])) > 0:
        total_diffs = len(st.session_state.hex_atual["diffs"])
        if total_diffs > 1500:
            alerta_seguranca = "⚠️ ALERTA COPILOTO: Modificação massiva no arquivo HEX (+1500 bytes alterados). Verifique limites térmicos da ECU."
        else:
            alerta_seguranca = "✅ COPILOTO: Modificações HEX dentro da margem de segurança."

    contexto = (
        f"--- CONTEXTO VIVO DO SISTEMA ---\n{json.dumps(dados_tela, indent=2)}\n"
        f"--- BANCO DA OFICINA ---\n{obter_resumo_banco()}\n"
        f"--- ANÁLISE DE SEGURANÇA MECÂNICA ---\n{alerta_seguranca}\n"
    )
    
    system_prompt = (
        "Você é o 'Chip', Mecânico Chefe Sênior e Engenheiro de Calibração da HyperTork.\n"
        "Você analisa os dados na tela em tempo real e fornece respostas diretas, técnicas e executivas."
    )
    
    mensagens_api = [{"role": "system", "content": f"{system_prompt}\n\n{contexto}"}]
    for msg in historico_mensagens:
        if msg["role"] != "system":
            mensagens_api.append(msg)
            
    try:
        completude = client.chat_completion(
            model="Qwen/Qwen2.5-7B-Instruct", 
            messages=mensagens_api, 
            max_tokens=700, 
            temperature=0.3
        )
        return completude.choices[0].message.content.strip()
    except Exception as e:
        return f"🤖 Erro ao consultar o Chip: {e}"