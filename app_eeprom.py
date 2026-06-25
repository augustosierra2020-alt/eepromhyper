import streamlit as st
import os
import json
from PIL import Image

# --- ANCORAGEM DEFINITIVA DA BIBLIOTECA 'Graficoseeprom' ---
# Garante que o ponto central do sistema seja sempre a pasta onde o app.py está executando
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def mapear_pasta_logos(base):
    for d in os.listdir(base):
        if d.lower() in ['logos', 'logo'] and os.path.isdir(os.path.join(base, d)):
            return os.path.join(base, d)
    return os.path.join(base, "Logos")

LOGOS_DIR = mapear_pasta_logos(BASE_DIR)

if not os.path.exists(LOGOS_DIR):
    os.makedirs(LOGOS_DIR)

st.set_page_config(page_title="EEPROM Master System", layout="wide")

# --- ESTADO DE NAVEGAÇÃO ---
if 'montadora_selecionada' not in st.session_state:
    st.session_state.montadora_selecionada = ""

# --- FUNÇÕES DE GERENCIAMENTO DA BIBLIOTECA ---

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
    if os.path.exists(LOGOS_DIR):
        arquivos = os.listdir(LOGOS_DIR)
        mont_alvo = montadora.strip().upper()
        
        # Prioridade máxima para os novos arquivos PNG transparentes pretos
        for arquivo in arquivos:
            arq_upper = arquivo.upper()
            if mont_alvo in arq_upper and arq_upper.endswith(('.PNG', '.WEBP')):
                return os.path.join(LOGOS_DIR, arquivo)
                
        # Segunda opção caso só exista o JPG antigo
        for arquivo in arquivos:
            arq_upper = arquivo.upper()
            if mont_alvo in arq_upper and arq_upper.endswith(('.JPG', '.JPEG')):
                return os.path.join(LOGOS_DIR, arquivo)
    return None

def salvar_novo_veiculo(montadora, modelo, inicio, intervalo, info_extra, valores_invertidos, escala, imagens_upload):
    # Força a criação da pasta do veículo estritamente dentro de Graficoseeprom / MONTADORA / MODELO
    pasta_modelo = os.path.join(BASE_DIR, montadora.upper(), modelo.strip())
    if not os.path.exists(pasta_modelo):
        os.makedirs(pasta_modelo)
    
    dados = {
        "posicao_inicio": inicio, 
        "intervalo": intervalo, 
        "detalhes": info_extra,
        "valores_invertidos": valores_invertidos,
        "escala": escala
    }
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

# Indicador visual para você ter certeza de onde os dados estão salvando fisicamente
st.sidebar.info(f"📂 **Biblioteca Ativa:**\n`Graficoseeprom`")

if st.sidebar.button("🏠 Voltar para Tela Inicial", use_container_width=True):
    st.session_state.montadora_selecionada = ""
    st.rerun()

st.sidebar.markdown("---")
montadoras_existentes = listar_montadoras()

# --- TELA INICIAL: DASHBOARD COM GRID ALINHADO ---
if st.session_state.montadora_selecionada == "":
    st.title("🚜 Painel de Controle - Baias EEPROM")
    st.markdown("### Escolha a Montadora desejada para abrir os modelos")
    st.write("")

    if not montadoras_existentes:
        st.info("Nenhuma montadora cadastrada nas pastas. Use a área administrativa abaixo para iniciar sua biblioteca.")
    else:
        cols = st.columns(4)
        for i, m in enumerate(montadoras_existentes):
            with cols[i % 4]:
                with st.container(border=True):
                    caminho_logo = buscar_logo_montadora_automatica(m)
                    
                    if caminho_logo:
                        try:
                            imagem_objeto = Image.open(caminho_logo)
                            st.image(imagem_objeto, width=140)
                        except:
                            st.error("Erro ao carregar")
                    else:
                        st.markdown(f"<p style='text-align:center; margin:20px 0; font-weight:bold;'>🏭 {m}</p>", unsafe_allow_html=True)
                    
                    if st.button(f"Abrir {m}", key=f"home_{m}", use_container_width=True):
                        st.session_state.montadora_selecionada = m
                        st.rerun()

    # DIAGNÓSTICO DAS LOGOS
    with st.sidebar.expander("🔍 Ver Arquivos da Pasta Logos"):
        if os.path.exists(LOGOS_DIR):
            st.write(os.listdir(LOGOS_DIR))
        else:
            st.write("Pasta vazia")

# --- TELA INTERNA: EXIBE OS MODELOS DISPONÍVEIS IMEDIATAMENTE ---
else:
    col_logo, col_nome = st.columns([1, 5])
    caminho_da_logo = buscar_logo_montadora_automatica(st.session_state.montadora_selecionada)
    
    with col_logo:
        if caminho_da_logo:
            try:
                st.image(Image.open(caminho_da_logo), width=90)
            except:
                st.subheader("🏭")
        else:
            st.subheader("🏭")
            
    with col_nome:
        st.markdown(f"<h1 style='margin-top: 5px; color: #1E88E5;'>{st.session_state.montadora_selecionada}</h1>", unsafe_allow_html=True)
    
    st.markdown("---")

    modelos_existentes = listar_modelos(st.session_state.montadora_selecionada)
    
    if not modelos_existentes:
        st.warning(f"Nenhum veículo cadastrado para a montadora {st.session_state.montadora_selecionada}. Cadastre um modelo abaixo.")
    else:
        st.markdown("### 📂 Selecione o Veículo para carregar os gráficos imediatamente:")
        escolha_modelo = st.selectbox("", [""] + modelos_existentes, label_visibility="collapsed")
        st.write("")
        
        if escolha_modelo:
            st.markdown(f"#### 📍 Mapa: {st.session_state.montadora_selecionada} {escolha_modelo}")
            path_final = os.path.join(BASE_DIR, st.session_state.montadora_selecionada, escolha_modelo)
            
            graficos_encontrados = []
            for nome_img in ["grafico_1.png", "grafico_2.png", "grafico.png"]:
                p = os.path.join(path_final, nome_img)
                if os.path.exists(p): graficos_encontrados.append(p)

            col_img, col_info = st.columns([2, 1])
            
            with col_img:
                if not graficos_encontrados:
                    st.error("⚠️ Nenhuma imagem de mapa encontrada nesta pasta.")
                elif len(graficos_encontrados) == 1:
                    st.image(graficos_encontrados[0], use_container_width=True)
                else:
                    sub1, sub2 = st.columns(2)
                    sub1.image(graficos_encontrados[0], use_container_width=True, caption="Gráfico Principal (1)")
                    sub2.image(graficos_encontrados[1], use_container_width=True, caption="Gráfico Complementar (2)")
                
                # Configuração de mapa adicionada logo abaixo dos gráficos
                st.write("")
                with st.container(border=True):
                    st.markdown("⚙️ **Configuração de Mapa**")
                    json_path = os.path.join(path_final, "dados.json")
                    if os.path.exists(json_path):
                        with open(json_path, "r", encoding="utf-8") as f:
                            cfg_data = json.load(f)
                        
                        v_inv_salvo = cfg_data.get("valores_invertidos", "Não informado")
                        escala_salva = cfg_data.get("escala", "Não informado")
                        
                        cm1, cm2 = st.columns(2)
                        cm1.write(f"**Valores invertidos:** {v_inv_salvo}")
                        cm2.write(f"**Escala:** {escala_salva}")
                    else:
                        st.caption("Configurações técnicas estruturais não localizadas.")
                    
            with col_info:
                with st.container(border=True):
                    st.subheader("📋 Informações Gerais")
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
                # Força a criação da pasta da montadora rigorosamente dentro de Graficoseeprom
                os.makedirs(os.path.join(BASE_DIR, nova_m), exist_ok=True)
                st.success(f"Pasta '{nova_m}' criada com sucesso na biblioteca!"); st.rerun()
    with adm2:
        st.subheader("Novo Veículo")
        if montadoras_existentes:
            m_adm = st.selectbox("Escolha a Montadora", montadoras_existentes)
            v_adm = st.text_input("Nome do Modelo")
            c1, c2 = st.columns(2)
            v_ini = c1.text_input("Endereço Inicial")
            v_int = c2.text_input("Intervalo")
            
            c_adm1, c_adm2 = st.columns(2)
            v_inv_input = c_adm1.selectbox("Valores Invertidos?", ["Não", "Sim"])
            v_escala_input = c_adm2.selectbox("Escala do Mapa", ["8 bits", "16 bits", "32 bits"])
            
            v_det = st.text_area("Informações Adicionais")
            v_files = st.file_uploader("Fotos dos Gráficos (Máx 2)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
            if st.button("Salvar Tudo"):
                if v_adm and v_files:
                    salvar_novo_veiculo(m_adm, v_adm, v_ini, v_int, v_det, v_inv_input, v_escala_input, v_files)
                    st.success("Veículo guardado na pasta com sucesso!"); st.rerun()