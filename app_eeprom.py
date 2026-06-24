import streamlit as st
import os
import json
from PIL import Image

# --- CONFIGURAÇÃO E CONSTANTES ---
BASE_DIR = "dados_eeprom" # Pasta raiz onde tudo será salvo
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

st.set_page_config(page_title="EEPROM Master System", layout="wide")

# --- FUNÇÕES DE UTILIDADE (LÓGICA INTELIGENTE) ---

def listar_montadoras():
    """Retorna lista de pastas na raiz de dados."""
    return [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]

def listar_modelos(montadora):
    """Retorna lista de modelos dentro de uma montadora específica."""
    path = os.path.join(BASE_DIR, montadora)
    if os.path.exists(path):
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    return []

def salvar_novo_veiculo(montadora, modelo, inicio, intervalo, info_extra, imagem_upload):
    """Cria a estrutura de pastas e salva os arquivos."""
    # Caminho: dados_eeprom/VOLVO/Volvo FH 460/
    pasta_modelo = os.path.join(BASE_DIR, montadora.upper(), modelo.strip())
    
    if not os.path.exists(pasta_modelo):
        os.makedirs(pasta_modelo)
    
    # Salvar Dados de Texto (JSON)
    dados = {
        "posicao_inicio": inicio,
        "intervalo": intervalo,
        "detalhes": info_extra
    }
    with open(os.path.join(pasta_modelo, "dados.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)
    
    # Salvar Imagem
    if imagem_upload:
        img = Image.open(imagem_upload)
        img.save(os.path.join(pasta_modelo, "grafico.png"))
        return True
    return False

# --- INTERFACE (DESIGN AESTHETIC) ---

st.title("🛡️ EEPROM Data Management System")
st.markdown("---")

# Barra Lateral - Navegação e Filtros
st.sidebar.header("🔍 Navegação por Baias")
montadoras_existentes = listar_montadoras()

if not montadoras_existentes:
    st.sidebar.warning("Nenhuma montadora cadastrada.")
    escolha_montadora = None
else:
    escolha_montadora = st.sidebar.selectbox("Selecionar Montadora", [""] + montadoras_existentes)

modelos_existentes = listar_modelos(escolha_montadora) if escolha_montadora else []
escolha_modelo = st.sidebar.selectbox("Selecionar Modelo", [""] + modelos_existentes) if escolha_montadora else None

# --- CONTEÚDO PRINCIPAL (VISUALIZAÇÃO) ---

if escolha_montadora and escolha_modelo:
    path_final = os.path.join(BASE_DIR, escolha_montadora, escolha_modelo)
    
    st.header(f"📍 {escolha_montadora} - {escolha_modelo}")
    
    col_img, col_info = st.columns([2, 1])
    
    with col_img:
        img_path = os.path.join(path_final, "grafico.png")
        if os.path.exists(img_path):
            st.image(img_path, use_container_width=True, caption=f"Gráfico de Referência: {escolha_modelo}")
        else:
            st.error("⚠️ Imagem do gráfico não encontrada nesta pasta.")
            
    with col_info:
        st.subheader("Informações do Mapa")
        json_path = os.path.join(path_final, "dados.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            st.write("**Início do Gráfico:**")
            st.code(data["posicao_inicio"], language="text")
            
            st.write("**Intervalo:**")
            st.code(data["intervalo"], language="text")
            
            st.write("**Veículo / Módulo:**")
            st.info(data["detalhes"])
        else:
            st.warning("Dados técnicos não encontrados.")

else:
    st.info("👋 Selecione uma montadora e modelo na lateral para visualizar os dados.")

# --- SEÇÃO ADMINISTRATIVA (ADICIONAR NOVOS) ---
st.markdown("---")
with st.expander("➕ ÁREA ADMINISTRATIVA: Adicionar Montadoras e Veículos"):
    
    adm_col1, adm_col2 = st.columns(2)
    
    with adm_col1:
        st.subheader("Nova Montadora")
        nova_m = st.text_input("Nome da Montadora (ex: VOLKSWAGEN, SCANIA)").upper()
        if st.button("Criar Baia da Montadora"):
            if nova_m:
                path_m = os.path.join(BASE_DIR, nova_m)
                if not os.path.exists(path_m):
                    os.makedirs(path_m)
                    st.success(f"Montadora {nova_m} criada!")
                    st.rerun()
                else:
                    st.warning("Essa montadora já existe.")
            else:
                st.error("Digite um nome válido.")

    with adm_col2:
        st.subheader("Novo Veículo (Redirecionamento Inteligente)")
        if not montadoras_existentes:
            st.warning("Crie uma montadora primeiro.")
        else:
            m_selecionada = st.selectbox("Para qual Montadora?", montadoras_existentes)
            v_nome = st.text_input("Nome do Modelo (ex: Volvo FH 460)")
            
            c1, c2 = st.columns(2)
            v_inicio = c1.text_input("Endereço Inicial (ex: 0x7F000)")
            v_intervalo = c2.text_input("Intervalo (ex: 0x7F000 - 0x7F5FF)")
            
            v_info = st.text_area("Dados do Veículo / Motor")
            v_img = st.file_uploader("Upload do Gráfico de Referência", type=["png", "jpg", "jpeg"])
            
            if st.button("Salvar Veículo na Pasta"):
                if m_selecionada and v_nome and v_img:
                    sucesso = salvar_novo_veiculo(m_selecionada, v_nome, v_inicio, v_intervalo, v_info, v_img)
                    if sucesso:
                        st.success(f"Veículo {v_nome} salvo com sucesso em {m_selecionada}!")
                        st.rerun()
                else:
                    st.error("Preencha todos os campos e suba a imagem.")