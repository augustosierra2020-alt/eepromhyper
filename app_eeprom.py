import streamlit as st
import os
import json
import base64
import sqlite3
import re
import shutil
from PIL import Image

# --- ANCORAGEM DEFINITIVA DA BIBLIOTECA ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "eeprom_master.db")

# --- IA GESTORA DA BIBLIOTECA (SMART MANAGER) ---
def higienizar_nome(nome):
    if not nome: return ""
    nome_limpo = " ".join(nome.strip().upper().split())
    return re.sub(r'[\\/*?:"<>|]', "", nome_limpo)

def sincronizar_banco_com_pastas():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT montadora_nome, modelo, posicao_inicio, intervalo, valores_invertidos, escala, detalhes, id FROM veiculos")
    veiculos = cursor.fetchall()
    
    pastas_criadas = 0
    for v in veiculos:
        mont, mod, ini, inter, val_inv, esc, det, v_id = v
        pasta_alvo = os.path.join(BASE_DIR, mont, mod)
        
        if not os.path.exists(pasta_alvo):
            os.makedirs(pasta_alvo)
            pastas_criadas += 1
            
            dados_json = {
                "posicao_inicio": ini, "intervalo": inter, 
                "valores_invertidos": val_inv, "escala": esc, "detalhes": det
            }
            with open(os.path.join(pasta_alvo, "dados.json"), "w", encoding="utf-8") as f:
                json.dump(dados_json, f, indent=4, ensure_ascii=False)
                
            cursor.execute("SELECT foto, ordem FROM graficos WHERE veiculo_id = ?", (v_id,))
            for foto_blob, ordem in cursor.fetchall():
                with open(os.path.join(pasta_alvo, f"grafico_{ordem}.png"), "wb") as img_f:
                    img_f.write(foto_blob)
    conn.close()
    return pastas_criadas

# --- SETUP INICIAL ---
def mapear_pasta_logos(base):
    for d in os.listdir(base):
        if d.lower() in ['logos', 'logo'] and os.path.isdir(os.path.join(base, d)):
            return os.path.join(base, d)
    return os.path.join(base, "Logos")

LOGOS_DIR = mapear_pasta_logos(BASE_DIR)
if not os.path.exists(LOGOS_DIR):
    os.makedirs(LOGOS_DIR)

st.set_page_config(page_title="HyperTork EEPROM System", layout="wide")

def conectar_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS montadoras (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE NOT NULL)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS veiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, montadora_nome TEXT NOT NULL, modelo TEXT NOT NULL,
            posicao_inicio TEXT, intervalo TEXT, valores_invertidos TEXT, escala TEXT, detalhes TEXT,
            UNIQUE(montadora_nome, modelo)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graficos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, veiculo_id INTEGER NOT NULL, foto BLOB NOT NULL, ordem INTEGER NOT NULL,
            FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE CASCADE
        )
    """)
    # Nova tabela para a Memória Ativa de Aprendizado do Chip
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chip_memoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT UNIQUE NOT NULL, valor TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- VARIÁVEIS DE SESSÃO ---
if 'montadora_selecionada' not in st.session_state:
    st.session_state.montadora_selecionada = ""
if 'chat_historico' not in st.session_state:
    st.session_state.chat_historico = [{"role": "assistant", "content": "Olá! Eu sou o **Chip**. Agora eu consigo aprender coisas novas! Digite **/ajuda** para ver meus comandos e superpoderes de texto."}]

# --- FUNÇÕES DE GERENCIAMENTO ---
def listar_montadoras():
    montadoras = set()
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT nome FROM montadoras")
        for row in cursor.fetchall():
            montadoras.add(higienizar_nome(row[0]))
        conn.close()
    except: pass
    return sorted(list(montadoras))

def listar_modelos(montadora):
    if not montadora: return []
    modelos = set()
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT modelo FROM veiculos WHERE montadora_nome = ?", (higienizar_nome(montadora),))
        for row in cursor.fetchall():
            modelos.add(higienizar_nome(row[0]))
        conn.close()
    except: pass
    return sorted(list(modelos))

def buscar_dados_veiculo_unificado(montadora, modelo):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, posicao_inicio, intervalo, valores_invertidos, escala, detalhes 
            FROM veiculos WHERE montadora_nome = ? AND modelo = ?
        """, (higienizar_nome(montadora), higienizar_nome(modelo)))
        row = cursor.fetchone()
        
        if row:
            v_id = row[0]
            cursor.execute("SELECT foto FROM graficos WHERE veiculo_id = ? ORDER BY ordem", (v_id,))
            fotos = [f[0] for f in cursor.fetchall()]
            conn.close()
            return {
                "id": v_id, "posicao_inicio": row[1], "intervalo": row[2], "valores_invertidos": row[3],
                "escala": row[4], "detalhes": row[5], "graficos": fotos
            }
        conn.close()
    except: pass
    return None

def buscar_logo_montadora_automatica(montadora):
    if os.path.exists(LOGOS_DIR):
        arquivos = os.listdir(LOGOS_DIR)
        mont_alvo = higienizar_nome(montadora)
        for arquivo in arquivos:
            arq_upper = arquivo.upper()
            if mont_alvo in arq_upper and arq_upper.endswith(('.PNG', '.WEBP')): return os.path.join(LOGOS_DIR, arquivo)
        for arquivo in arquivos:
            arq_upper = arquivo.upper()
            if mont_alvo in arq_upper and arq_upper.endswith(('.JPG', '.JPEG')): return os.path.join(LOGOS_DIR, arquivo)
    return None

def obter_image_base64_html(caminho):
    try:
        extensao = caminho.split('.')[-1].lower()
        mime = "image/jpeg" if extensao in ['jpg', 'jpeg'] else f"image/{extensao}"
        with open(caminho, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode()
            return f"data:{mime};base64,{encoded}"
    except: return ""

def salvar_novo_veiculo_hibrido(montadora, modelo, inicio, intervalo, info_extra, valores_invertidos, escala, imagens_upload=None):
    montadora = higienizar_nome(montadora)
    modelo = higienizar_nome(modelo)
    
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO montadoras (nome) VALUES (?)", (montadora,))
        cursor.execute("""
            INSERT OR REPLACE INTO veiculos 
            (montadora_nome, modelo, posicao_inicio, intervalo, valores_invertidos, escala, detalhes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (montadora, modelo, inicio, intervalo, valores_invertidos, escala, info_extra))
        
        cursor.execute("SELECT id FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (montadora, modelo))
        veiculo_id = cursor.fetchone()[0]
        
        pasta_modelo = os.path.join(BASE_DIR, montadora, modelo)
        os.makedirs(pasta_modelo, exist_ok=True)
        
        dados_json = {
            "posicao_inicio": inicio, "intervalo": intervalo, 
            "valores_invertidos": valores_invertidos, "escala": escala, "detalhes": info_extra
        }
        with open(os.path.join(pasta_modelo, "dados.json"), "w", encoding="utf-8") as f:
            json.dump(dados_json, f, indent=4, ensure_ascii=False)
        
        if imagens_upload:
            cursor.execute("DELETE FROM graficos WHERE veiculo_id = ?", (veiculo_id,))
            for idx, img_file in enumerate(imagens_upload[:6]):
                img_bytes = img_file.read()
                cursor.execute("INSERT INTO graficos (veiculo_id, foto, ordem) VALUES (?, ?, ?)", (veiculo_id, img_bytes, idx+1))
                with open(os.path.join(pasta_modelo, f"grafico_{idx+1}.png"), "wb") as f_img:
                    f_img.write(img_bytes)
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def excluir_veiculo_db(montadora, modelo):
    mont = higienizar_nome(montadora)
    mod = higienizar_nome(modelo)
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (mont, mod))
    conn.commit()
    conn.close()
    
    pasta_modelo = os.path.join(BASE_DIR, mont, mod)
    if os.path.exists(pasta_modelo): shutil.rmtree(pasta_modelo)

def excluir_montadora_db(montadora):
    mont = higienizar_nome(montadora)
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM veiculos WHERE montadora_nome = ?", (mont,))
    cursor.execute("DELETE FROM montadoras WHERE nome = ?", (mont,))
    conn.commit()
    conn.close()
    
    pasta_montadora = os.path.join(BASE_DIR, mont)
    if os.path.exists(pasta_montadora): shutil.rmtree(pasta_montadora)

# --- 🧠 LÓGICA DE APRENDIZADO DO CHIP ---
def salvar_memoria_chip(chave, valor):
    ch = chave.strip().lower()
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO chip_memoria (chave, valor) VALUES (?, ?)", (ch, valor.strip()))
    conn.commit()
    conn.close()

def buscar_memoria_chip(texto):
    tx = texto.strip().lower()
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT chave, valor FROM chip_memoria")
    linhas = cursor.fetchall()
    conn.close()
    for chave, valor in linhas:
        if chave in tx:
            return f"🧠 **O que eu lembro sobre '{chave.upper()}':**\n\n{valor}"
    return None

def processar_linguagem_chip(prompt_cru):
    msg = prompt_cru.strip().lower()
    
    # Comando de Aprendizado Manual via Chat
    if msg.startswith("/aprender"):
        corpo = prompt_cru[9:].strip()
        if ":" in corpo:
            chave, valor = corpo.split(":", 1)
            salvar_memoria_chip(chave, valor)
            return f"✅ Entendido! Guardei na minha memória de silício tudo sobre **'{chave.strip().upper()}'**. Pode me perguntar sobre isso quando quiser!"
        return "⚠️ Formato incorreto. Use: `/aprender termo: significado do termo`"
        
    if msg == "/memoria":
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT chave FROM chip_memoria")
        chaves = [c[0].upper() for c in cursor.fetchall()]
        conn.close()
        if chaves: return "🧠 **Termos que eu aprendi até agora:**\n\n" + "\n".join([f"* {c}" for c in chaves])
        return "Ainda não aprendi nenhum termo customizado. Me ensine algo usando `/aprender termo: explicacao`!"

    # Verifica se há memórias salvas correspondentes no texto
    memoria_receptiva = buscar_memoria_chip(prompt_cru)
    if memoria_receptiva:
        return memoria_receptiva

    # Intenções Contextuais nativas
    if any(p in msg for p in ["apagar", "excluir", "deletar", "remover"]) and any(v in msg for v in ["veiculo", "modelo", "pasta", "não consigo", "erro"]):
        return (
            "🤖 **Diagnóstico do Chip:** Identifiquei que travas de exclusão aconteciam porque os arquivos físicos ficavam abertos no cache do Streamlit "
            "ou as imagens BLOB geravam quebras de chaves estrangeiras.\n\n"
            "⚙️ **Ajuste Aplicado:** Apliquei a biblioteca `shutil.rmtree` combinada com o comando `PRAGMA foreign_keys = ON;`. "
            "Agora, ao excluir um veículo na aba Gerenciar, as imagens e pastas somem instantaneamente sem deixar rastros!"
        )
        
    elif any(s in msg for s in ["sintaxe", "digitação", "erro de digitação", "caractere", "proibido"]):
        return (
            "🧠 **Análise de Sintaxe por Chip:** Eu monitoro e limpo ativamente todos os inputs textuais de nomes de marcas e modelos usando filtros Regex. "
            "Removo caracteres proibidos pelo Windows como `\\ / * ? : \" < > |` automaticamente para blindar sua biblioteca contra quebras de diretório!"
        )
    
    elif msg == "/status" or any(s in msg for s in ["status", "quantos", "biblioteca"]):
        conn = conectar_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM montadoras"); q_m = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM veiculos"); q_v = c.fetchone()[0]
        conn.close()
        return f"📊 **Status da Ficha Técnica:** Atualmente existem **{q_m} montadoras** e **{q_v} modelos** gravados no banco de dados. Tudo verificado!"

    elif msg == "/sync" or any(s in msg for s in ["sincronizar", "sync", "recuperar"]):
        qtd = sincronizar_banco_com_pastas()
        return f"🔄 **Ação Efetuada:** Rodes o diagnóstico do sistema e reconstruí com sucesso **{qtd} pastas** físicas locais a partir dos metadados do banco!"

    elif msg == "/backup" or any(b in msg for b in ["backup", "salvar", "segurança"]):
        return f"🛡️ **Dica de Proteção:** O arquivo definitivo que contém toda a inteligência e os mapas salvos é o **`eeprom_master.db`** localizado em `{BASE_DIR}`. Copie ele e seus dados estarão 100% salvos."

    elif msg == "/ajuda":
        return (
            "🤖 **Guia de Treinamento do Chip:**\n\n"
            "**Comandos Rápidos:**\n"
            "* `/status` -> Exibe as estatísticas do banco de dados.\n"
            "* `/sync` -> Varre e regenera pastas físicas deletadas por engano.\n"
            "* `/backup` -> Mostra onde está o arquivo de segurança.\n"
            "* `/memoria` -> Lista tudo o que você me ensinou.\n"
            "* `/limpar` -> Limpa o terminal.\n\n"
            "**Como me ensinar coisas:**\n"
            "Digite no chat: `/aprender SeuTermo: Sua Explicação Completa`"
        )

    elif any(c in msg for c in ["oi", "olá", "bom dia", "boa tarde"]):
        return "🤖 Olá! Sou o **Chip**, assistente oficial do HyperTork. Estou pronto para gerenciar as memórias EEPROM e aprender novos comandos!"
        
    else:
        return "🤔 Não consegui pescar a intenção dessa frase. Digite **/ajuda** para ver os comandos ou me ensine este termo usando o padrão `/aprender`!"

# --- 🎨 ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        max-width: 200px !important; margin: 0 auto !important; padding: 12px !important;
        border-radius: 12px !important; box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
    }
    div.stButton > button { margin-top: 4px !important; border-radius: 8px !important; }
    </style>
""", unsafe_allow_html=True)

# --- BARRA LATERAL (MENU + INTERACTION COM CHIP) ---
st.sidebar.title("🛡️ HyperTork System")
if st.sidebar.button("🏠 Voltar para Tela Inicial", use_container_width=True):
    st.session_state.montadora_selecionada = ""
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("🤖 **Chip - Inteligência Ativa**")

for mensagem in st.session_state.chat_historico:
    with st.sidebar.chat_message(mensagem["role"]):
        st.markdown(mensagem["content"])

if prompt := st.sidebar.chat_input("Fale com o Chip ou ensine um comando..."):
    st.session_state.chat_historico.append({"role": "user", "content": prompt})
    
    if prompt.strip().lower() == "/limpar":
        st.session_state.chat_historico = [{"role": "assistant", "content": "Histórico redefinido! Como o Chip pode te ajudar agora?"}]
        st.rerun()
    else:
        resposta = processar_linguagem_chip(prompt)
        st.session_state.chat_historico.append({"role": "assistant", "content": resposta})
        st.rerun()

st.sidebar.markdown("---")
montadoras_existentes = listar_montadoras()

# --- TELA INICIAL: DASHBOARD COM GRID ---
if st.session_state.montadora_selecionada == "":
    st.title("🚜 Painel de Controle - Baias EEPROM")
    st.markdown("### Escolha a Montadora desejada para abrir os modelos")
    st.write("")

    if not montadoras_existentes:
        st.info("Nenhuma montadora cadastrada. Use a área administrativa abaixo para iniciar seu Banco de Dados.")
    else:
        cols = st.columns(4)
        for i, m in enumerate(montadoras_existentes):
            with cols[i % 4]:
                with st.container(border=True):
                    caminho_logo = buscar_logo_montadora_automatica(m)
                    if caminho_logo:
                        logo_html_src = obter_image_base64_html(caminho_logo)
                        if logo_html_src:
                            st.markdown(f"""
                                <div style="display: flex; justify-content: center; align-items: center; 
                                            background-color: #FFFFFF; padding: 10px; border-radius: 8px; 
                                            height: 110px; width: 100%; box-sizing: border-box; margin-bottom: 6px;">
                                    <img src="{logo_html_src}" style="max-height: 90px; max-width: 100%; object-fit: contain;">
                                </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                            <div style="display: flex; justify-content: center; align-items: center; height: 110px; width: 100%; margin-bottom: 6px;">
                                <p style='text-align:center; font-weight:bold; color:#1E88E5; margin:0;'>🏭 {m}</p>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    if st.button(f"Abrir {m}", key=f"home_{m}", use_container_width=True):
                        st.session_state.montadora_selecionada = m
                        st.rerun()

# --- TELA INTERNA: EXIBIÇÃO DE MODELOS ---
else:
    col_logo, col_nome = st.columns([1, 8])
    caminho_da_logo = buscar_logo_montadora_automatica(st.session_state.montadora_selecionada)
    
    with col_logo:
        if caminho_da_logo:
            logo_html_src = obter_image_base64_html(caminho_da_logo)
            if logo_html_src:
                st.markdown(f"""
                    <div style="display: flex; justify-content: center; align-items: center; 
                                background-color: #FFFFFF; padding: 6px; border-radius: 8px; height: 75px; width: 75px; box-sizing: border-box;">
                        <img src="{logo_html_src}" style="max-height: 60px; max-width: 100%; object-fit: contain;">
                    </div>
                """, unsafe_allow_html=True)
            else: st.subheader("🏭")
        else: st.subheader("🏭")
            
    with col_nome:
        st.markdown(f"<h1 style='margin-top: 5px; color: #1E88E5;'>{st.session_state.montadora_selecionada}</h1>", unsafe_allow_html=True)
    st.markdown("---")

    modelos_existentes = listar_modelos(st.session_state.montadora_selecionada)
    
    if not modelos_existentes:
        st.warning(f"Nenhum veículo cadastrado para a montadora {st.session_state.montadora_selecionada}.")
    else:
        escolha_modelo = st.selectbox("📂 Selecione o Veículo para carregar os gráficos imediatamente:", [""] + modelos_existentes)
        st.write("")
        
        if escolha_modelo:
            st.markdown(f"#### 📍 Mapa: {st.session_state.montadora_selecionada} {escolha_modelo}")
            dados_mapa = buscar_dados_veiculo_unificado(st.session_state.montadora_selecionada, escolha_modelo)

            col_img, col_info = st.columns([2, 1])
            with col_img:
                if not dados_mapa or not dados_mapa["graficos"]:
                    st.error("⚠️ Nenhuma imagem de mapa encontrada para este veículo.")
                else:
                    # ATUALIZADO: Ferramenta de Zoom Dinâmico por Lente de Controle Deslizante
                    st.caption("💡 *Dica:* Passe o mouse por cima do mapa para abrir o botão de **Tela Cheia** nativo no canto superior direito da foto.")
                    tamanho_zoom = st.slider("🔍 Controle de Zoom da Imagem (Largura em Pixels)", 300, 1600, 750, step=50)
                    
                    lista_fotos = dados_mapa["graficos"]
                    for idx in range(0, len(lista_fotos), 2):
                        sub_cols = st.columns(2)
                        with sub_cols[0]:
                            if idx < len(lista_fotos):
                                st.image(lista_fotos[idx], width=tamanho_zoom, caption=f"Gráfico Principal ({idx+1})")
                        with sub_cols[1]:
                            if idx + 1 < len(lista_fotos):
                                st.image(lista_fotos[idx+1], width=tamanho_zoom, caption=f"Gráfico Complementar ({idx+2})")
                
                with st.container(border=True):
                    st.markdown("⚙️ **Configuração de Mapa**")
                    if dados_mapa:
                        cm1, cm2 = st.columns(2)
                        cm1.write(f"**Valores invertidos:** {dados_mapa.get('valores_invertidos', 'Desativado')}")
                        cm2.write(f"**Escala:** {dados_mapa.get('escala', '8 bits')}")
                    
            with col_info:
                with st.container(border=True):
                    st.subheader("📋 Informações Gerais")
                    if dados_mapa:
                        st.write("**Início do Gráfico:**")
                        st.code(dados_mapa["posicao_inicio"], language="text")
                        st.write("**Intervalo de Endereços:**")
                        st.code(dados_mapa["intervalo"], language="text")
                        st.write("**Detalhes do Veículo:**")
                        st.info(dados_mapa["detalhes"])

# --- SEÇÃO ADMINISTRATIVA INTEGRALMENTE SEPARADA ---
st.markdown("<br><br>", unsafe_allow_html=True)

# PROCESSOS DE SALVAMENTO COMPLETAMENTE INDEPENDENTES
with st.expander("➕ CADASTRAR: Adicionar Estruturas Independentes"):
    cad_tab1, cad_tab2 = st.tabs(["🏭 Cadastrar Montadora", "🚗 Cadastrar Veículo"])
    
    with cad_tab1:
        st.subheader("Nova Montadora")
        nova_m = st.text_input("Digite o Nome da Montadora", key="input_nova_m").strip()
        if st.button("Efetivar Montadora", type="primary"):
            if not nova_m:
                st.error("❌ Erro: O campo de nome da montadora não pode ficar em branco!")
            else:
                m_hig = higienizar_nome(nova_m)
                if m_hig in montadoras_existentes:
                    st.warning(f"⚠️ Atenção: A montadora '{m_hig}' já encontra-se cadastrada no sistema!")
                else:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO montadoras (nome) VALUES (?)", (m_hig,))
                    conn.commit(); conn.close()
                    os.makedirs(os.path.join(BASE_DIR, m_hig), exist_ok=True)
                    st.success(f"✅ Sucesso: Montadora '{m_hig}' cadastrada com êxito!")
                    st.rerun()
                    
    with cad_tab2:
        st.subheader("Novo Veículo")
        if not montadoras_existentes:
            st.info("Cadastre ao menos uma montadora para liberar o painel de veículos.")
        else:
            m_form = st.selectbox("Selecione a Montadora Alvo", montadoras_existentes, key="sb_m_form")
            v_form = st.text_input("Nome do Modelo / Veículo", key="input_v_form").strip()
            
            vc1, vc2 = st.columns(2)
            v_ini = vc1.text_input("Endereço Inicial (Hex/Dec)", key="ini_v_form")
            v_int = vc2.text_input("Intervalo de Endereço", key="int_v_form")
            
            v_inv = st.selectbox("Valores Invertidos?", ["Desativado", "Ativado"], key="inv_v_form")
            v_esc = st.selectbox("Escala do Mapa", ["8 bits", "16 bits", "32 bits"], key="esc_v_form")
            v_det = st.text_area("Informações e Detalhes Adicionais", key="det_v_form")
            v_files = st.file_uploader("Fotos dos Gráficos do Veículo (Máx 6)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="files_v_form")
            
            if st.button("Efetivar Veículo", type="primary"):
                v_hig = higienizar_nome(v_form)
                if not v_form:
                    st.error("❌ Erro: O nome do modelo é obrigatório!")
                else:
                    modelos_da_marca = listar_modelos(m_form)
                    if v_hig in modelos_da_marca:
                        st.error(f"❌ Erro: Já existe um veículo chamado '{v_hig}' cadastrado na marca {m_form}!")
                    else:
                        status_save = salvar_novo_veiculo_hibrido(m_form, v_form, v_ini, v_int, v_det, v_inv, v_esc, v_files)
                        if status_save:
                            st.success(f"✅ Sucesso: Veículo '{v_hig}' gravado e sincronizado com estabilidade!")
                            st.rerun()
                        else:
                            st.error("❌ Erro Crítico: Falha interna de IO ao tentar gravar os mapas.")

# EDICAO E EXCLUSÃO SEPARADAS EM MONTADORAS E VEÍCULOS
with st.expander("⚙️ GERENCIAR: Painel de Edição e Exclusão Total"):
    ger_tab1, ger_tab2 = st.tabs(["🏭 Gerenciar Montadoras", "🚗 Gerenciar Veículos"])
    
    with ger_tab1:
        st.subheader("Modificação de Marcas")
        if not montadoras_existentes:
            st.warning("Nenhuma montadora localizada.")
        else:
            m_select_edit = st.selectbox("Escolha a Montadora para Alterar", montadoras_existentes, key="sb_m_edit_pane")
            
            st.markdown("#### Opções de Ajuste:")
            novo_nome_m = st.text_input("Alterar Nome da Montadora para:", value=m_select_edit, key="txt_rename_m").strip()
            
            m_ed_col1, m_ed_col2 = st.columns(2)
            if m_ed_col1.button("💾 Salvar Novo Nome da Montadora", key="btn_rename_m"):
                n_m_hig = higienizar_nome(novo_nome_m)
                if not n_m_hig:
                    st.error("❌ Erro: O nome não pode ficar em branco.")
                elif n_m_hig in montadoras_existentes and n_m_hig != m_select_edit:
                    st.error("❌ Erro: Esse nome de montadora já existe!")
                else:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE montadoras SET nome = ? WHERE nome = ?", (n_m_hig, m_select_edit))
                    cursor.execute("UPDATE veiculos SET montadora_nome = ? WHERE montadora_nome = ?", (n_m_hig, m_select_edit))
                    conn.commit(); conn.close()
                    
                    old_path = os.path.join(BASE_DIR, m_select_edit)
                    new_path = os.path.join(BASE_DIR, n_m_hig)
                    if os.path.exists(old_path): os.rename(old_path, new_path)
                    
                    st.success("✅ Sucesso: Marca alterada globalmente!")
                    st.session_state.montadora_selecionada = ""
                    st.rerun()
                    
            if m_ed_col2.button("🗑️ Excluir Montadora (Apaga Tudo)", key="btn_del_m_pane"):
                excluir_montadora_db(m_select_edit)
                st.success(f"✅ Limpeza concluída: Montadora {m_select_edit} eliminada.")
                st.session_state.montadora_selecionada = ""
                st.rerun()

    with ger_tab2:
        st.subheader("Edição Completa de Veículos")
        if not montadoras_existentes:
            st.warning("Sem dados cadastrados.")
        else:
            m_sel_v = st.selectbox("Filtrar por Montadora", montadoras_existentes, key="sb_m_sel_v")
            v_existentes = listar_modelos(m_sel_v)
            
            if not v_existentes:
                st.info("Nenhum veículo localizado nesta marca.")
            else:
                v_sel_edit = st.selectbox("Selecione o Veículo para Alteração Total", v_existentes, key="sb_v_sel_edit")
                dados_v = buscar_dados_veiculo_unificado(m_sel_v, v_sel_edit)
                
                if dados_v:
                    st.markdown("---")
                    st.markdown(f"### ✏️ Editando Ficha Técnica: {v_sel_edit}")
                    
                    v_novo_nome = st.text_input("Alterar Nome do Veículo / Modelo", value=v_sel_edit, key="txt_v_name_edit").strip()
                    
                    ve_c1, ve_c2 = st.columns(2)
                    v_novo_ini = ve_c1.text_input("Alterar Endereço Inicial", value=dados_v["posicao_inicio"], key="txt_v_ini_edit")
                    v_novo_int = ve_c2.text_input("Alterar Intervalo", value=dados_v["intervalo"], key="txt_v_int_edit")
                    
                    ve_c3, ve_c4 = st.columns(2)
                    inv_idx = 0 if dados_v["valores_invertidos"] == "Desativado" else 1
                    v_novo_inv = ve_c3.selectbox("Valores Invertidos?", ["Desativado", "Ativado"], index=inv_idx, key="sb_v_inv_edit")
                    
                    esc_opcoes = ["8 bits", "16 bits", "32 bits"]
                    esc_idx = esc_opcoes.index(dados_v["escala"]) if dados_v["escala"] in esc_opcoes else 0
                    v_novo_esc = ve_c4.selectbox("Escala do Mapa", esc_opcoes, index=esc_idx, key="sb_v_esc_edit")
                    
                    v_novo_det = st.text_area("Alterar Detalhes do Veículo", value=dados_v["detalhes"], key="txt_v_det_edit")
                    
                    st.warning("⚠️ Enviar novas fotos substituirá completamente as imagens salvas deste veículo!")
                    v_novas_fotos = st.file_uploader("Substituir Imagens de Mapas (Máx 6)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="files_v_edit")
                    
                    v_manage_col1, v_manage_col2 = st.columns(2)
                    
                    if v_manage_col1.button("💾 Salvar Todas as Alterações do Veículo", type="primary", key="btn_save_v_edit"):
                        n_v_hig = higienizar_nome(v_novo_nome)
                        if not n_v_hig:
                            st.error("❌ Erro: O nome do modelo não pode ser nulo.")
                        else:
                            # Se mudou o nome, verifica duplicata
                            if n_v_hig != v_sel_edit and n_v_hig in v_existentes:
                                st.error("❌ Erro: Já existe outro modelo com esse nome nesta montadora!")
                            else:
                                # Se houve mudança de nome, limpa a pasta anterior física
                                if n_v_hig != v_sel_edit:
                                    velha_pasta = os.path.join(BASE_DIR, m_sel_v, v_sel_edit)
                                    if os.path.exists(velha_pasta): shutil.rmtree(velha_pasta)
                                    
                                    conn = conectar_db()
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE veiculos SET modelo = ? WHERE id = ?", (n_v_hig, dados_v["id"]))
                                    conn.commit(); conn.close()
                                
                                # Salva o restante das configurações atualizadas
                                fotos_para_salvar = v_novas_fotos if v_novas_fotos else None
                                
                                # Se não enviou novas fotos, precisamos resgatar os bytes do banco para repopular a nova pasta física se o nome mudou
                                if n_v_hig != v_sel_edit and not v_novas_fotos:
                                    salvar_novo_veiculo_hibrido(m_sel_v, n_v_hig, v_novo_ini, v_novo_int, v_novo_det, v_novo_inv, v_novo_esc, None)
                                    # Força sincronia de fotos antigas para a nova pasta
                                    sincronizar_banco_com_pastas()
                                else:
                                    salvar_novo_veiculo_hibrido(m_sel_v, n_v_hig, v_novo_ini, v_novo_int, v_novo_det, v_novo_inv, v_novo_esc, v_novas_fotos)
                                    
                                st.success(f"✅ Sucesso: Modelo '{n_v_hig}' atualizado em toda a árvore de arquivos!")
                                st.rerun()
                                
                    if v_manage_col2.button("🗑️ Excluir Este Veículo do Sistema", key="btn_del_v_edit"):
                        excluir_veiculo_db(m_sel_v, v_sel_edit)
                        st.success(f"✅ Remoção Concluída: Veículo {v_sel_edit} excluído.")
                        st.rerun()