import streamlit as st
import os
import json
from PIL import Image

# --- FORÇAR DIRETÓRIO RAIZ CORRETO ---
# Isso garante que o Python use a pasta exata onde o app.py está salvo, evitando erros de terminal
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def mapear_pasta_logos(base):
    # Procura por qualquer variação de nome de pasta
    for d in os.listdir(base):
        if d.lower() in ['logos', 'logo'] and os.path.isdir(os.path.join(base, d)):
            return os.path.join(base, d)
    return os.path.join(base, "Logos")

LOGOS_DIR = mapear_pasta_logos(BASE_DIR)

# Garante a criação caso não exista
if not os.path.exists(LOGOS_DIR):
    os.makedirs(LOGOS_DIR)

st.set_page_config(page_title="EEPROM Master System", layout="wide")

# --- ESTADO DE NAVEGAÇÃO ---
if 'montadora_selecionada' not in st.session_state:
    st.session_state.montadora_selecionada = ""

# --- FUNÇÕES ---

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

def buscar_logo_montadora_automatica(montadora):
    """
    BUSCA AUTOMÁTICA EM TEMPO REAL:
    Vasculha a pasta Logos e traz qualquer imagem que contenha o nome da montadora.
    """
    if os.path.exists(LOGOS_DIR):
        arquivos = os.listdir(LOGOS_DIR)
        mont_alvo = montadora.strip().upper()
        
        for arquivo in arquivos:
            arq_upper = arquivo.upper()
            # Se o nome da montadora estiver na imagem, ele valida automaticamente
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

# --- ESTILIZAÇÃO CSS PARA ALINHAMENTO ---
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; }
    .montadora-card { text-align: center; padding: 10px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- BARRA LATERAL ---
st.sidebar.title("🛡️ EEPROM System")
if st.sidebar.button("🏠 Voltar para Tela Inicial", use_container_width=True):
    st.session_state.montadora_selecionada = ""
    st.rerun()

st.sidebar.markdown("---")
montadoras_existentes = listar_montadoras()

# --- TELA INICIAL: DASHBOARD COM SELEÇÃO DIRETA ---
if st.session_state.montadora_selecionada == "":
    st.title("🚜 Painel de Controle - Baias EEPROM")
    st.markdown("### Escolha a Montadora desejada para abrir os modelos")
    st.write("")

    if not montadoras_existentes:
        st.info("Nenhuma montadora cadastrada nas pastas. Use a área administrativa abaixo.")
    else:
        # Cria o grid alinhado de montadoras
        cols = st.columns(4)
        for i, m in enumerate(montadoras_existentes):
            with cols[i % 4]:
                caminho_logo = buscar_logo_montadora_automatica(m)
                
                # Renderiza a logo ou aviso centralizado e alinhado
                if caminho_logo:
                    try:
                        img_home = Image.open(caminho_logo)
                        st.image(img_home, width=150)
                    except:
                        st.error("Erro ao ler arquivo")
                else:
                    # Se não achar, mostra o nome grande estilizado para não ficar desalinhado
                    st.info(f"🏭 {m} (Sem imagem na pasta Logos)")
                
                # Botão de clique para abrir
                if st.button(f"Abrir {m}", key=f"home_{m}", use_container_width=True):
                    st.session_state.montadora_selecionada = m
                    st.rerun()

    # DIAGNÓSTICO DAS LOGOS (Aparece apenas na tela inicial para te ajudar a corrigir)
    with st.sidebar.expander("🔍 Diagnóstico Técnico de Imagens"):
        st.write(f"**Pasta Atual:** `{BASE_DIR}`")
        st.write(f"**Procurando em:** `{LOGOS_DIR}`")
        if os.path.exists(LOGOS_DIR):
            arquivos_na_pasta = os.listdir(LOGOS_DIR)
            st.write(f"**Arquivos detectados lá dentro:** {arquivos_na_pasta}")
        else:
            st.write("❌ Pasta de Logos não detectada!")

# --- TELA INTERNA: JÁ EXIBE OS MODELOS DISPONÍVEIS IMEDIATAMENTE ---
else:
    # Cabeçalho alinhado: Logo na esquerda, Nome na direita
    col_logo, col_nome = st.columns([1, 5])
    caminho_da_logo = buscar_logo_montadora_automatica(st.session_state.montadora_selecionada)
    
    with col_logo:
        if caminho_da_logo:
            st.image(Image.open(caminho_da_logo), width=100)
        else:
            st.subheader("🏭")
            
    with col_nome:
        st.markdown(f"<h1 style='margin-top: 5px; color: #1E88E5;'>{st.session_state.montadora_selecionada}</h1>", unsafe_allow_html=True)
    
    st.markdown("---")

    # CARREGAMENTO DOS MODELOS DIRETO NA TELA
    modelos_existentes = listar_modelos(st.session_state.montadora_selecionada)
    
    if not modelos_existentes:
        st.warning(f"Nenhum veículo cadastrado para a montadora {st.session_state.montadora_selecionada}. Cadastre um modelo abaixo.")
    else:
        # Seletor de modelos centralizado e em destaque na tela principal
        escolha_modelo = st.selectbox("📂 Escolha o Modelo/Veículo para ver o gráfico:", [""] + modelos_existentes)
        
        if escolha_modelo:
            st.markdown(f"### 📍 Visualizando: {escolha_modelo}")
            path_final = os.path.join(BASE_DIR, st.session_state.montadora_selecionada, escolha_modelo)
            
            graficos_encontrados = []
            for nome_img in ["grafico_1.png", "grafico_2.png", "grafico.png"]:
                p = os.path.join(path_final, nome_img)
                if os.path.exists(p): graficos_encontrados.append(p)

            # Divisão em duas colunas: Gráficos na Esquerda (Grande), Dados na Direita (Painel Fixo)
            col_img, col_info = st.columns([2, 1])
            
            with col_img:
                if not graficos_encontrados:
                    st.error("⚠️ Nenhuma imagem de mapa encontrada nesta pasta.")
                elif len(graficos_encontrados) == 1:
                    st.image(graficos_encontrados[0], use_container_width=True)
                else:
                    sub1, sub2 = st.columns(2)
                    sub1.image(graficos_encontrados[0], use_container_width=True, caption="Gráfico 1")
                    sub2.image(graficos_encontrados[1], use_container_width=True, caption="Gráfico 2")
                    
            with col_info:
                st.subheader("📋 Informações do Mapa")
                json_path = os.path.join(path_final, "dados.json")
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    st.write("**Início do Gráfico:**")
                    st.code(data["posicao_inicio"], language="text")
                    st.write("**Intervalo de Endereços:**")
                    st.code(data["intervalo"], language="text")
                    st.write("**Detalhes do Veículo:**")
                    st.info(data["detalhes"])
                else:
                    st.warning("Arquivo dados.json ausente.")

# --- SEÇÃO ADMINISTRATIVA ---
st.markdown("<br><br>", unsafe_allow_html=True)
with st.expander("➕ ÁREA ADMINISTRATIVA: Adicionar Montadoras e Veículos"):
    adm1, adm2 = st.columns(2)
    with adm1:
        st.subheader("Nova Montadora")
        nova_m = st.text_input("Nome da Montadora").upper().strip()
        if st.button("Criar Pasta"):
            if nova_m:
                os.makedirs(os.path.join(BASE_DIR, nova_m), exist_ok=True)
                st.success("Montadora Criada!"); st.rerun()
    with adm2:
        st.subheader("Novo Veículo")
        if montadoras_existentes:
            m_adm = st.selectbox("Escolha a Montadora", montadoras_existentes)
            v_adm = st.text_input("Nome do Modelo")
            c1, c2 = st.columns(2)
            v_ini = c1.text_input("Endereço Inicial")
            v_int = c2.text_input("Intervalo")
            v_det = st.text_area("Informações Adicionais")
            v_files = st.file_uploader("Fotos dos Gráficos (Máx 2)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
            if st.button("Salvar Tudo"):
                if v_adm and v_files:
                    salvar_novo_veiculo(m_adm, v_adm, v_ini, v_int, v_det, v_files)
                    st.success("Veículo guardado na pasta com sucesso!"); st.rerun()