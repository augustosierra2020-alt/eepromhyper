import streamlit as st
import os
import json
from PIL import Image

# --- CONFIGURAÇÃO DE PASTAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGOS_DIR = os.path.join(BASE_DIR, "logos")

# Garante que a pasta de logos exista
if not os.path.exists(LOGOS_DIR):
    os.makedirs(LOGOS_DIR)

st.set_page_config(page_title="EEPROM Master System", layout="wide")

# --- FUNÇÕES DE UTILIDADE ---

def listar_montadoras():
    ignorar = ['.git', '.streamlit', '__pycache__', 'dados_eeprom', 'logos']
    montadoras = []
    for d in os.listdir(BASE_DIR):
        caminho_completo = os.path.join(BASE_DIR, d)
        if os.path.isdir(caminho_completo) and d not in ignorar:
            montadoras.append(d)
    return sorted(montadoras)

def listar_modelos(montadora):
    path = os.path.join(BASE_DIR, montadora)
    if os.path.exists(path):
        return sorted([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])
    return []

def buscar_logo_montadora(montadora):
    """
    Busca a logo ignorando se a extensão está em maiúsculo ou minúsculo.
    O nome do arquivo deve ser exatamente: NOMEDAMONTADORA logo.extensao
    """
    # Lista todos os arquivos da pasta logos para fazer uma busca inteligente
    if os.path.exists(LOGOS_DIR):
        arquivos = os.listdir(LOGOS_DIR)
        nome_alvo = f"{montadora.upper()} LOGO"
        
        for arquivo in arquivos:
            nome_sem_ext, _ = os.path.splitext(arquivo)
            # Remove espaços extras e joga para maiúsculo para comparar
            if nome_sem_ext.strip().upper() == nome_alvo:
                return os.path.join(LOGOS_DIR, arquivo)
    return None

def salvar_novo_veiculo(montadora, modelo, inicio, intervalo, info_extra, imagens_upload):
    pasta_modelo = os.path.join(BASE_DIR, montadora.upper(), modelo.strip())
    
    if not os.path.exists(pasta_modelo):
        os.makedirs(pasta_modelo)
    
    dados = {
        "posicao_inicio": inicio,
        "intervalo": intervalo,
        "detalhes": info_extra
    }
    with open(os.path.join(pasta_modelo, "dados.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)
    
    # Salvar as imagens enviadas (aceita até 2)
    if imagens_upload:
        for idx, img_file in enumerate(imagens_upload[:2]):
            img = Image.open(img_file)
            # Salva como grafico_1.png e grafico_2.png
            img.save(os.path.join(pasta_modelo, f"grafico_{idx+1}.png"))
        return True
    return False

# --- INTERFACE VISUAL ---

st.title("🛡️ EEPROM Data Management System")
st.markdown("---")

st.sidebar.header("🔍 Navegação por Baias")
montadoras_existentes = listar_montadoras()

if not montadoras_existentes:
    st.sidebar.warning("Nenhuma montadora cadastrada.")
    escolha_montadora = None
else:
    escolha_montadora = st.sidebar.selectbox("Selecionar Montadora", [""] + montadoras_existentes)

modelos_existentes = listar_modelos(escolha_montadora) if escolha_montadora else []
escolha_modelo = st.sidebar.selectbox("Selecionar Modelo", [""] + modelos_existentes) if escolha_montadora else None

# --- CONTEÚDO PRINCIPAL ---

if escolha_montadora:
    st.markdown("### Montadora Selecionada")
    col_logo, col_nome = st.columns([1, 4])
    
    caminho_da_logo = buscar_logo_montadora(escolha_montadora)
    
    with col_logo:
        if caminho_da_logo:
            try:
                logo_img = Image.open(caminho_da_logo)
                st.image(logo_img, width=120)
            except:
                st.subheader("⚠️ Erro Img")
        else:
            st.subheader("🏭")
            
    with col_nome:
        st.markdown(f"<h1 style='margin-top: 10px; color: #1E88E5;'>{escolha_montadora}</h1>", unsafe_allow_html=True)
    
    st.markdown("---")

    if escolha_modelo:
        path_final = os.path.join(BASE_DIR, escolha_montadora, escolha_modelo)
        st.header(f"📍 Modelo: {escolha_modelo}")
        
        # Redirecionamento inteligente de layouts para os gráficos
        # Verifica quais imagens existem na pasta (grafico_1.png, grafico_2.png ou o antigo grafico.png)
        graficos_encontrados = []
        for nome_img in ["grafico_1.png", "grafico_2.png", "grafico.png"]:
            p = os.path.join(path_final, nome_img)
            if os.path.exists(p):
                graficos_encontrados.append(p)

        col_img, col_info = st.columns([2, 1])
        
        with col_img:
            if not graficos_encontrados:
                st.error("⚠️ Nenhuma imagem de gráfico encontrada nesta pasta.")
            elif len(graficos_encontrados) == 1:
                # Se só tem 1 imagem, expande ela na tela inteira designada
                st.image(graficos_encontrados[0], use_container_width=True, caption="Gráfico de Referência")
            else:
                # Se tem 2 imagens, divide o espaço em duas subcolunas perfeitamente alinhadas
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    st.image(graficos_encontrados[0], use_container_width=True, caption="Gráfico Principal (1)")
                with sub_col2:
                    st.image(graficos_encontrados[1], use_container_width=True, caption="Gráfico Complementar (2)")
                
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
        st.info(f"Agora selecione um **Modelo** da {escolha_montadora} na barra lateral para ver o gráfico.")
else:
    st.info("👋 Selecione uma montadora e um modelo na barra lateral para começar.")

# --- SEÇÃO ADMINISTRATIVA ---
st.markdown("---")
with st.expander("➕ ÁREA ADMINISTRATIVA: Adicionar Montadoras e Veículos"):
    adm_col1, adm_col2 = st.columns(2)
    
    with adm_col1:
        st.subheader("Nova Montadora")
        nova_m = st.text_input("Nome da Montadora (ex: VOLKSWAGEN, DAF, VOLVO)").upper().strip()
        if st.button("Criar Pasta da Montadora"):
            if nova_m:
                path_m = os.path.join(BASE_DIR, nova_m)
                if not os.path.exists(path_m):
                    os.makedirs(path_m)
                    st.success(f"Pasta '{nova_m}' criada com sucesso!")
                    st.rerun()
                else:
                    st.warning("Esta montadora já existe.")
            else:
                st.error("Digite um nome válido.")

    with adm_col2:
        st.subheader("Novo Veículo")
        if not montadoras_existentes:
            st.warning("Crie uma montadora primeiro.")
        else:
            m_selecionada = st.selectbox("Para qual Montadora?", montadoras_existentes)
            v_nome = st.text_input("Nome do Modelo (ex: Volvo FH 460)")
            
            c1, c2 = st.columns(2)
            v_inicio = c1.text_input("Endereço Inicial (ex: 0x7F000)")
            v_intervalo = c2.text_input("Intervalo (ex: 0x7F000 - 0x7F5FF)")
            
            v_info = st.text_area("Dados do Veículo / Motor")
            
            # ATUALIZADO: accept_multiple_files=True permite arrastar até duas imagens de uma vez
            v_imgs = st.file_uploader("Upload dos Gráficos de Referência (Máx. 2)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
            
            if st.button("Salvar Veículo na Pasta"):
                if m_selecionada and v_nome and v_imgs:
                    sucesso = salvar_novo_veiculo(m_selecionada, v_nome, v_inicio, v_intervalo, v_info, v_imgs)
                    if sucesso:
                        st.success(f"Veículo {v_nome} salvo em {m_selecionada} com seus gráficos!")
                        st.rerun()
                else:
                    st.error("Preencha todos os campos e faça o upload de pelo menos uma imagem.")