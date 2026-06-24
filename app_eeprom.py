import streamlit as st
import os
import json
from PIL import Image

# --- CONFIGURAÇÃO DE PASTAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Busca inteligente pela pasta de Logos (aceita logo, Logos, logos, LOGOS)
def encontrar_pasta_logos(base):
    for d in os.listdir(base):
        if d.lower() in ['logos', 'logo'] and os.path.isdir(os.path.join(base, d)):
            return os.path.join(base, d)
    # Se não achar nenhuma, define como 'Logos' por padrão
    return os.path.join(base, "Logos")

LOGOS_DIR = encontrar_pasta_logos(BASE_DIR)

if not os.path.exists(LOGOS_DIR):
    os.makedirs(LOGOS_DIR)

st.set_page_config(page_title="EEPROM Master System", layout="wide")

# --- ESTADO DO SISTEMA (Navegação) ---
if 'montadora_selecionada' not in st.session_state:
    st.session_state.montadora_selecionada = ""

# --- FUNÇÕES DE UTILIDADE ---

def listar_montadoras():
    ignorar = ['.git', '.streamlit', '__pycache__', 'dados_eeprom', 'logos', 'logo', 'Logos', 'LOGO']
    montadoras = []
    if os.path.exists(BASE_DIR):
        for d in os.listdir(BASE_DIR):
            caminho_completo = os.path.join(BASE_DIR, d)
            if os.path.isdir(caminho_completo) and d not in ignorar:
                montadoras.append(d)
    return sorted(montadoras)

def listar_modelos(montadora):
    if not montadora: return []
    path = os.path.join(BASE_DIR, montadora)
    if os.path.exists(path):
        return sorted([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])
    return []

def buscar_logo_montadora(montadora):
    """
    Busca super tolerante: se o arquivo de imagem tiver o nome da montadora em qualquer 
    parte do seu nome (ex: DAF, DAF logo, logo_daf), ele será carregado.
    """
    if os.path.exists(LOGOS_DIR):
        arquivos = os.listdir(LOGOS_DIR)
        mont_alvo = montadora.strip().upper()
        
        for arquivo in arquivos:
            arq_upper = arquivo.upper()
            # Verifica se é uma imagem e se o nome da montadora está contido no arquivo
            if mont_alvo in arq_upper and arq_upper.endswith(('.PNG', '.JPG', '.JPEG', '.WEBP')):
                return os.path.join(LOGOS_DIR, arquivo)
    return None

def salvar_novo_veiculo(montadora, modelo, inicio, intervalo, info_extra, imagens_upload):
    pasta_modelo = os.path.join(BASE_DIR, montadora.upper(), modelo.strip())
    if not os.path.exists(pasta_modelo):
        os.makedirs(pasta_modelo)
    
    dados = {"posicao_inicio": inicio, "intervalo": intervalo, "detalhes": info_extra}
    with open(os.path.join(pasta_modelo, "dados.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)
    
    if imagens_upload:
        for idx, img_file in enumerate(imagens_upload[:2]):
            img = Image.open(img_file)
            img.save(os.path.join(pasta_modelo, f"grafico_{idx+1}.png"))
        return True
    return False

# --- BARRA LATERAL ---
st.sidebar.title("🛡️ EEPROM System")

if st.sidebar.button("🏠 Tela Inicial / Dashboard", use_container_width=True):
    st.session_state.montadora_selecionada = ""
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🔍 Navegação por Baias")

montadoras_existentes = listar_montadoras()

escolha_sidebar = st.sidebar.selectbox(
    "Selecionar Montadora", 
    [""] + montadoras_existentes,
    index=0 if st.session_state.montadora_selecionada == "" else (montadoras_existentes.index(st.session_state.montadora_selecionada) + 1)
)

if escolha_sidebar != st.session_state.montadora_selecionada:
    st.session_state.montadora_selecionada = escolha_sidebar
    st.rerun()

modelos_existentes = listar_modelos(st.session_state.montadora_selecionada)
escolha_modelo = st.sidebar.selectbox("Selecionar Modelo", [""] + modelos_existentes) if st.session_state.montadora_selecionada else None

# --- CONTEÚDO PRINCIPAL ---

# TELA INICIAL (DASHBOARD)
if st.session_state.montadora_selecionada == "":
    st.title("🚜 Bem-vindo ao Sistema de Baias EEPROM")
    st.markdown("### Selecione uma montadora para visualizar os mapas")
    st.write("")

    if not montadoras_existentes:
        st.info("Nenhuma montadora cadastrada ainda. Use a área administrativa abaixo.")
    else:
        cols = st.columns(4)
        for i, m in enumerate(montadoras_existentes):
            with cols[i % 4]:
                caminho_logo = buscar_logo_montadora(m)
                if caminho_logo:
                    try:
                        img_home = Image.open(caminho_logo)
                        st.image(img_home, width=150)
                    except:
                        st.markdown("### ⚠️ Erro")
                else:
                    st.markdown("### 🏭")
                
                if st.button(f"Abrir {m}", key=f"home_{m}", use_container_width=True):
                    st.session_state.montadora_selecionada = m
                    st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)

# TELA DA MONTADORA / MODELO
else:
    col_logo, col_nome = st.columns([1, 4])
    caminho_da_logo = buscar_logo_montadora(st.session_state.montadora_selecionada)
    
    with col_logo:
        if caminho_da_logo:
            try:
                st.image(Image.open(caminho_da_logo), width=120)
            except:
                st.subheader("⚠️")
        else:
            st.subheader("🏭")
            
    with col_nome:
        st.markdown(f"<h1 style='margin-top: 10px; color: #1E88E5;'>{st.session_state.montadora_selecionada}</h1>", unsafe_allow_html=True)
    
    st.markdown("---")

    if escolha_modelo:
        path_final = os.path.join(BASE_DIR, st.session_state.montadora_selecionada, escolha_modelo)
        st.header(f"📍 Modelo: {escolha_modelo}")
        
        graficos_encontrados = []
        for nome_img in ["grafico_1.png", "grafico_2.png", "grafico.png"]:
            p = os.path.join(path_final, nome_img)
            if os.path.exists(p): graficos_encontrados.append(p)

        col_img, col_info = st.columns([2, 1])
        
        with col_img:
            if not graficos_encontrados:
                st.error("⚠️ Nenhuma imagem encontrada.")
            elif len(graficos_encontrados) == 1:
                st.image(graficos_encontrados[0], use_container_width=True)
            else:
                sub1, sub2 = st.columns(2)
                sub1.image(graficos_encontrados[0], use_container_width=True)
                sub2.image(graficos_encontrados[1], use_container_width=True)
                
        with col_info:
            st.subheader("Informações do Mapa")
            json_path = os.path.join(path_final, "dados.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                st.write("**Início:**"); st.code(data["posicao_inicio"], language="text")
                st.write("**Intervalo:**"); st.code(data["intervalo"], language="text")
                st.write("**Detalhes:**"); st.info(data["detalhes"])
    else:
        st.info(f"Selecione um Modelo da **{st.session_state.montadora_selecionada}** na lateral.")

# --- SEÇÃO ADMINISTRATIVA ---
st.markdown("<br><br>", unsafe_allow_html=True)
with st.expander("➕ ÁREA ADMINISTRATIVA"):
    adm1, adm2 = st.columns(2)
    with adm1:
        st.subheader("Nova Montadora")
        nova_m = st.text_input("Nome").upper().strip()
        if st.button("Criar Pasta"):
            if nova_m:
                os.makedirs(os.path.join(BASE_DIR, nova_m), exist_ok=True)
                st.success("Criada!"); st.rerun()
    with adm2:
        st.subheader("Novo Veículo")
        if montadoras_existentes:
            m_adm = st.selectbox("Montadora", montadoras_existentes)
            v_adm = st.text_input("Modelo")
            c1, c2 = st.columns(2)
            v_ini = c1.text_input("Início")
            v_int = c2.text_input("Intervalo")
            v_det = st.text_area("Detalhes")
            v_files = st.file_uploader("Fotos (Máx 2)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
            if st.button("Salvar Veículo"):
                if v_adm and v_files:
                    salvar_novo_veiculo(m_adm, v_adm, v_ini, v_int, v_det, v_files)
                    st.success("Salvo!"); st.rerun()