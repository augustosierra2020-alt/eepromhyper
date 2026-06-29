import streamlit as st
import os
import json
import base64
import sqlite3
import re
import shutil
import unicodedata
import pandas as pd
from PIL import Image
from duckduckgo_search import DDGS
from huggingface_hub import HfApi, hf_hub_download, InferenceClient

# ==========================================
# 1. CONFIGURAÇÕES DE NUVEM E ANCORAGEM
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "eeprom_master.db")

HF_TOKEN = os.environ.get("HF_TOKEN")
DATASET_REPO_ID = "GrizzlyBear25/HyperTork_DB" 

def sincronizar_nuvem_para_local():
    if HF_TOKEN:
        try:
            db_nuvem = hf_hub_download(repo_id=DATASET_REPO_ID, filename="eeprom_master.db", repo_type="dataset", token=HF_TOKEN)
            shutil.copy(db_nuvem, DB_PATH)
            return True
        except Exception:
            pass
    return False

def backup_local_para_nuvem():
    if HF_TOKEN and os.path.exists(DB_PATH):
        try:
            api = HfApi()
            api.upload_file(
                path_or_fileobj=DB_PATH,
                path_in_repo="eeprom_master.db",
                repo_id=DATASET_REPO_ID,
                repo_type="dataset",
                token=HF_TOKEN
            )
            return True
        except Exception:
            pass
    return False

def higienizar_nome(nome):
    if not nome: return ""
    nome_limpo = " ".join(nome.strip().upper().split())
    return re.sub(r'[\\/*?:"<>|]', "", nome_limpo)

def sincronizar_banco_com_pastas():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT nome FROM montadoras")
    montadoras = cursor.fetchall()
    for m in montadoras:
        os.makedirs(os.path.join(BASE_DIR, m[0]), exist_ok=True)
    
    cursor.execute("SELECT montadora_nome, modelo, posicao_inicio, intervalo, valores_invertidos, escala, detalhes, id FROM veiculos")
    veiculos = cursor.fetchall()
    
    pastas_criadas = 0
    for v in veiculos:
        mont, mod, ini, inter, val_inv, esc, det, v_id = v
        pasta_alvo = os.path.join(BASE_DIR, mont, mod)
        if not os.path.exists(pasta_alvo):
            os.makedirs(pasta_alvo)
            pastas_criadas += 1
            dados_json = {"posicao_inicio": ini, "intervalo": inter, "valores_invertidos": val_inv, "escala": esc, "detalhes": det}
            with open(os.path.join(pasta_alvo, "dados.json"), "w", encoding="utf-8") as f:
                json.dump(dados_json, f, indent=4, ensure_ascii=False)
            cursor.execute("SELECT foto, ordem FROM graficos WHERE veiculo_id = ?", (v_id,))
            for foto_blob, ordem in cursor.fetchall():
                with open(os.path.join(pasta_alvo, f"grafico_{ordem}.png"), "wb") as img_f:
                    img_f.write(foto_blob)
    conn.close()
    return pastas_criadas

# ==========================================
# 2. SETUP DO BANCO DE DADOS UNIFICADO
# ==========================================
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
    cursor.execute("CREATE TABLE IF NOT EXISTS chip_memoria (id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT UNIQUE NOT NULL, valor TEXT NOT NULL)")
    
    # Tabela OBD-II (agora com colunas extras para filtros)
    cursor.execute('''CREATE TABLE IF NOT EXISTS obd2_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  codigo TEXT, montadora TEXT, modelo TEXT, ano TEXT,
                  descricao TEXT, data TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
                  
    # Garante que as colunas novas existam caso o banco seja antigo
    try: cursor.execute("ALTER TABLE obd2_history ADD COLUMN montadora TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE obd2_history ADD COLUMN modelo TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE obd2_history ADD COLUMN ano TEXT")
    except: pass
    
    conn.commit()
    conn.close()

sincronizar_nuvem_para_local()
init_db()
sincronizar_banco_com_pastas()

def mapear_pasta_logos(base):
    for d in os.listdir(base):
        if d.lower() in ['logos', 'logo'] and os.path.isdir(os.path.join(base, d)):
            return os.path.join(base, d)
    return os.path.join(base, "Logos")

LOGOS_DIR = mapear_pasta_logos(BASE_DIR)
if not os.path.exists(LOGOS_DIR):
    os.makedirs(LOGOS_DIR)

st.set_page_config(page_title="HyperTork System Hub", page_icon="⚙️", layout="wide")

# ==========================================
# 3. ROTINAS OBD-II DE ALTA PERFORMANCE (RAG)
# ==========================================
def salvar_pesquisa_obd2(codigo, montadora, modelo, ano, descricao):
    conn = conectar_db()
    c = conn.cursor()
    c.execute("INSERT INTO obd2_history (codigo, montadora, modelo, ano, descricao) VALUES (?, ?, ?, ?, ?)", 
              (codigo, montadora, modelo, ano, descricao))
    conn.commit(); conn.close()
    backup_local_para_nuvem()

def carregar_historico_obd2():
    conn = conectar_db()
    df = pd.read_sql_query("SELECT codigo, montadora, modelo, ano, data FROM obd2_history ORDER BY id DESC", conn)
    conn.close()
    return df

def diagnostico_avancado_obd2(codigo, montadora="", modelo="", ano=""):
    """Busca na web e usa a IA do HF para gerar um laudo comparativo e profundo."""
    query = f"OBD2 code {codigo}"
    if montadora: query += f" {montadora}"
    if modelo: query += f" {modelo}"
    query += " symptoms causes repair manual"
    
    # 1. Captura contexto bruto da internet
    search_results = ""
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(query, max_results=4))
            for r in resultados: search_results += f"- {r['body']}\n"
    except Exception:
        search_results = "(Busca na web indisponível no momento. Use apenas sua base de conhecimento interna.)"
        
    # 2. Pede para a IA processar a internet + cérebro dela
    prompt_ia = f"""
    Você é um Engenheiro de Diagnóstico Automotivo Avançado.
    O usuário precisa saber TUDO sobre o código de falha OBD-II: **{codigo}**.
    Contexto do veículo informado: Montadora: {montadora or 'Qualquer'} | Modelo: {modelo or 'Qualquer'} | Ano: {ano or 'Qualquer'}.
    
    Resultados encontrados na web agora:
    {search_results}
    
    Gere um relatório técnico contendo:
    1. Significado e Descrição Técnica da Falha.
    2. Se for um código específico de montadora (ex: começados com P1, C1, B1), verifique na sua base de dados se esse mesmo código tem significados DIFERENTES em outras marcas (ex: Scania vs Volvo vs Mercedes) e liste-os!
    3. Sintomas no veículo.
    4. Causas mais prováveis.
    5. Passos para solução.
    
    Responda em Markdown, sendo claro, direto e em Português do Brasil.
    """
    
    if HF_TOKEN:
        try:
            client = InferenceClient(token=HF_TOKEN)
            completude = client.chat_completion(
                model="Qwen/Qwen2.5-7B-Instruct",
                messages=[{"role": "user", "content": prompt_ia}],
                max_tokens=800, temperature=0.3
            )
            return completude.choices[0].message.content.strip()
        except Exception as e:
            return f"⚠️ Falha na IA: {e}\n\n**Dados crus encontrados:**\n{search_results}"
    else:
        return f"**Dados crus encontrados:**\n{search_results}"

# ==========================================
# 4. ROTINAS EEPROM
# ==========================================
def listar_montadoras():
    montadoras = set()
    try:
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT nome FROM montadoras")
        for row in cursor.fetchall(): montadoras.add(higienizar_nome(row[0]))
        conn.close()
    except: pass
    return sorted(list(montadoras))

def listar_modelos(montadora):
    if not montadora: return []
    modelos = set()
    try:
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT modelo FROM veiculos WHERE montadora_nome = ?", (higienizar_nome(montadora),))
        for row in cursor.fetchall(): modelos.add(higienizar_nome(row[0]))
        conn.close()
    except: pass
    return sorted(list(modelos))

def buscar_dados_veiculo_unificado(montadora, modelo):
    try:
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT id, posicao_inicio, intervalo, valores_invertidos, escala, detalhes FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (higienizar_nome(montadora), higienizar_nome(modelo)))
        row = cursor.fetchone()
        if row:
            v_id = row[0]
            cursor.execute("SELECT foto FROM graficos WHERE veiculo_id = ? ORDER BY ordem", (v_id,))
            fotos = [f[0] for f in cursor.fetchall()]
            conn.close()
            return {"id": v_id, "posicao_inicio": row[1], "intervalo": row[2], "valores_invertidos": row[3], "escala": row[4], "detalhes": row[5], "graficos": fotos}
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
    montadora = higienizar_nome(montadora); modelo = higienizar_nome(modelo)
    conn = conectar_db(); cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO montadoras (nome) VALUES (?)", (montadora,))
        cursor.execute("INSERT OR REPLACE INTO veiculos (montadora_nome, modelo, posicao_inicio, intervalo, valores_invertidos, escala, detalhes) VALUES (?, ?, ?, ?, ?, ?, ?)", (montadora, modelo, inicio, intervalo, valores_invertidos, escala, info_extra))
        cursor.execute("SELECT id FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (montadora, modelo))
        veiculo_id = cursor.fetchone()[0]
        pasta_modelo = os.path.join(BASE_DIR, montadora, modelo)
        os.makedirs(pasta_modelo, exist_ok=True)
        with open(os.path.join(pasta_modelo, "dados.json"), "w", encoding="utf-8") as f:
            json.dump({"posicao_inicio": inicio, "intervalo": intervalo, "valores_invertidos": valores_invertidos, "escala": escala, "detalhes": info_extra}, f, indent=4, ensure_ascii=False)
        if imagens_upload:
            cursor.execute("DELETE FROM graficos WHERE veiculo_id = ?", (veiculo_id,))
            for idx, img_file in enumerate(imagens_upload[:6]):
                img_bytes = img_file.read()
                cursor.execute("INSERT INTO graficos (veiculo_id, foto, ordem) VALUES (?, ?, ?)", (veiculo_id, img_bytes, idx+1))
                with open(os.path.join(pasta_modelo, f"grafico_{idx+1}.png"), "wb") as f_img: f_img.write(img_bytes)
        conn.commit(); backup_local_para_nuvem() 
        return True
    except: return False
    finally: conn.close()

def excluir_veiculo_db(montadora, modelo):
    mont = higienizar_nome(montadora); mod = higienizar_nome(modelo)
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("DELETE FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (mont, mod))
    conn.commit(); conn.close()
    pasta_modelo = os.path.join(BASE_DIR, mont, mod)
    if os.path.exists(pasta_modelo): shutil.rmtree(pasta_modelo)
    backup_local_para_nuvem() 

def excluir_montadora_db(montadora):
    mont = higienizar_nome(montadora)
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("DELETE FROM veiculos WHERE montadora_nome = ?", (mont,))
    cursor.execute("DELETE FROM montadoras WHERE nome = ?", (mont,))
    conn.commit(); conn.close()
    pasta_montadora = os.path.join(BASE_DIR, mont)
    if os.path.exists(pasta_montadora): shutil.rmtree(pasta_montadora)
    backup_local_para_nuvem() 

def obter_resumo_banco_para_ia():
    try:
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT nome FROM montadoras")
        monts = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT COUNT(*) FROM obd2_history")
        hist_obd = cursor.fetchone()[0]
        conn.close()
        return f"Montadoras: {', '.join(monts)}\nTotal de Pesquisas OBD-II no Histórico: {hist_obd}"
    except: return "Erro ao carregar dados locais."

# ==========================================
# 5. CORE DE INTELIGÊNCIA ARTIFICIAL (CHIP)
# ==========================================
def processar_linguagem_chip(prompt_cru):
    DADOS_DO_SISTEMA = obter_resumo_banco_para_ia()
    CONTEUDO_DO_SISTEMA = (
        "Você é o Chip, a IA do HyperTork System. "
        "Você analisa DADOS OBD-II ou gerencia EEPROM.\n"
        f"Dados locais: {DADOS_DO_SISTEMA}\n\n"
        "Se o usuário pedir diagnóstico de um código (ex: P0001 na Volvo), escolha a ação DIAGNOSTICAR_FALHA.\n"
        "Formato JSON EXATO:\n"
        "{\n"
        '  "acao": "CRIAR_MONTADORA" | "CADASTRAR_VEICULO" | "DIAGNOSTICAR_FALHA" | "ANALISAR_RESPONDER",\n'
        '  "parametros": { "codigo": "P0001", "montadora": "NOME", "modelo": "NOME", "ano": "2014" },\n'
        '  "resposta": "Sua resposta curta (Apenas para comandos EEPROM. Se for DIAGNOSTICAR_FALHA, deixe em branco pois outra função fará o laudo)."\n'
        "}\n"
    )
    
    if HF_TOKEN:
        try:
            client = InferenceClient(token=HF_TOKEN)
            completude = client.chat_completion(
                model="Qwen/Qwen2.5-7B-Instruct",
                messages=[{"role": "system", "content": CONTEUDO_DO_SISTEMA}, {"role": "user", "content": prompt_cru}],
                max_tokens=400, temperature=0.2
            )
            resposta_ia = completude.choices[0].message.content.strip()
            resposta_ia = re.sub(r'```json\s*|```', '', resposta_ia)
            dados = json.loads(resposta_ia)
            
            acao = dados.get("acao", "ANALISAR_RESPONDER")
            params = dados.get("parametros", {})
            texto_base = dados.get("resposta", "Análise concluída!")
            
            if acao == "DIAGNOSTICAR_FALHA" and params.get("codigo"):
                cod = params.get("codigo")
                mont = params.get("montadora", "")
                mod = params.get("modelo", "")
                ano = params.get("ano", "")
                laudo = diagnostico_avancado_obd2(cod, mont, mod, ano)
                salvar_pesquisa_obd2(cod, mont, mod, ano, laudo)
                return f"🔍 **Laudo de Falha Solicitado via Chip:**\n\n{laudo}"
                
            elif acao == "CRIAR_MONTADORA" and params.get("montadora"):
                m = higienizar_nome(params["montadora"])
                conn = conectar_db(); cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO montadoras (nome) VALUES (?)", (m,))
                conn.commit(); conn.close(); os.makedirs(os.path.join(BASE_DIR, m), exist_ok=True)
                backup_local_para_nuvem()
                return texto_base
                
            return texto_base
        except Exception:
            pass 

    return "🤖 Olá! Estou com minha rede principal ocupada, mas pode explorar o sistema usando os painéis."

@st.dialog("🔍 Visualizador de Mapa Ampliado", width="large")
def abrir_modal_zoom(foto_bytes, legenda_titulo):
    st.write(f"#### {legenda_titulo}")
    zoom_dinamico = st.slider("Arraste para ajustar o Zoom do Mapa", 400, 2000, 950, step=50)
    st.image(foto_bytes, width=zoom_dinamico)
    if st.button("❌ Fechar Visualização", use_container_width=True): st.rerun()

# ==========================================
# 6. ESTILIZAÇÃO CSS AVANÇADA E ESTADO
# ==========================================
st.markdown("""
    <style>
    /* Trava a tela para não tremer */
    html { overflow-y: scroll !important; }
    .block-container { padding-top: 2rem; }
    
    /* Botões Gigantes da Tela Inicial usando CSS nos st.button nativos */
    div[data-testid="stButton"] button.hub-btn-eeprom {
        height: 250px !important;
        background: linear-gradient(145deg, #1E88E5, #1565C0) !important;
        color: white !important;
        font-size: 1.5rem !important;
        border-radius: 20px !important;
        border: none !important;
        transition: transform 0.2s, box-shadow 0.2s !important;
    }
    div[data-testid="stButton"] button.hub-btn-eeprom:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 24px rgba(0,0,0,0.4) !important;
    }
    
    div[data-testid="stButton"] button.hub-btn-obd {
        height: 250px !important;
        background: linear-gradient(145deg, #E53935, #C62828) !important;
        color: white !important;
        font-size: 1.5rem !important;
        border-radius: 20px !important;
        border: none !important;
        transition: transform 0.2s, box-shadow 0.2s !important;
    }
    div[data-testid="stButton"] button.hub-btn-obd:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 24px rgba(0,0,0,0.4) !important;
    }
    </style>
""", unsafe_allow_html=True)

if 'app_mode' not in st.session_state:
    st.session_state.app_mode = "HOME"
if 'montadora_selecionada' not in st.session_state:
    st.session_state.montadora_selecionada = ""
if 'chat_historico' not in st.session_state:
    st.session_state.chat_historico = [{"role": "assistant", "content": "🤖 Bem-vindo ao Hub! Posso gerenciar mapas EEPROM ou gerar laudos OBD-II detalhados. Como posso ajudar?"}]

# ==========================================
# 7. BARRA LATERAL GERAL
# ==========================================
st.sidebar.title("🛡️ HyperTork Hub")
if st.session_state.app_mode != "HOME":
    if st.sidebar.button("🎮 Voltar ao Menu Principal", use_container_width=True, type="primary"):
        st.session_state.app_mode = "HOME"
        st.session_state.montadora_selecionada = ""
        st.rerun()
    st.sidebar.markdown("---")

st.sidebar.markdown("🤖 **Chip - Assistente Integrado**")
for mensagem in st.session_state.chat_historico:
    with st.sidebar.chat_message(mensagem["role"]): st.markdown(mensagem["content"])

if prompt := st.sidebar.chat_input("Diga um comando ou peça laudo de falha..."):
    st.session_state.chat_historico.append({"role": "user", "content": prompt})
    if prompt.strip().lower() in ["/limpar", "limpar chat"]:
        st.session_state.chat_historico = [{"role": "assistant", "content": "Visão redefinida!"}]
        st.rerun()
    else:
        with st.spinner("Analisando..."):
            resposta = processar_linguagem_chip(prompt)
        st.session_state.chat_historico.append({"role": "assistant", "content": resposta})
        st.rerun()

montadoras_existentes = listar_montadoras()

# ==========================================
# 8. RENDERIZAÇÃO DAS TELAS
# ==========================================
if st.session_state.app_mode == "HOME":
    st.markdown("<h1 style='text-align: center; margin-bottom: 50px;'>HyperTork System Hub</h1>", unsafe_allow_html=True)
    
    # Injetando classes CSS via marcação no HTML renderizado pelo Streamlit
    st.markdown('<div class="hub-container">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<style>div:nth-child(1) > div > div > div > button { @extend .hub-btn-eeprom; }</style>', unsafe_allow_html=True)
        if st.button("⚙️ GRÁFICOS EEPROM\n\nGerenciamento de banco de dados, mapas hexadecimais e escalas.", key="btn_eeprom", use_container_width=True):
            st.session_state.app_mode = "EEPROM"
            st.rerun()
            
    with col2:
        st.markdown('<style>div:nth-child(2) > div > div > div > button { @extend .hub-btn-obd; }</style>', unsafe_allow_html=True)
        if st.button("🚗 CÓDIGOS DE FALHA\n\nDiagnóstico IA, Busca de falhas cruzadas e Histórico.", key="btn_obd", use_container_width=True):
            st.session_state.app_mode = "OBD2"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Gambiarra de CSS para forçar a cor e o tamanho baseando na chave (key) do botão
    st.markdown("""
        <style>
        button[kind="secondary"]:has(div:contains("GRÁFICOS EEPROM")) {
            height: 250px !important; background: linear-gradient(145deg, #1E88E5, #1565C0) !important; color: white !important; font-size: 1.5rem !important; border-radius: 20px !important; border: none !important;
        }
        button[kind="secondary"]:has(div:contains("GRÁFICOS EEPROM")):hover { transform: translateY(-5px); box-shadow: 0 12px 24px rgba(0,0,0,0.4) !important; color: white !important; }
        
        button[kind="secondary"]:has(div:contains("CÓDIGOS DE FALHA")) {
            height: 250px !important; background: linear-gradient(145deg, #E53935, #C62828) !important; color: white !important; font-size: 1.5rem !important; border-radius: 20px !important; border: none !important;
        }
        button[kind="secondary"]:has(div:contains("CÓDIGOS DE FALHA")):hover { transform: translateY(-5px); box-shadow: 0 12px 24px rgba(0,0,0,0.4) !important; color: white !important;}
        </style>
    """, unsafe_allow_html=True)

# ------------------------------------------
# TELA 1: OBD-II AI SCANNER (AVANÇADO)
# ------------------------------------------
elif st.session_state.app_mode == "OBD2":
    st.title("🚗 Diagnóstico de Falhas OBD-II")
    st.markdown("Identifique problemas no seu veículo com uma análise RAG profunda cruzando informações da web.")
    
    with st.container(border=True):
        col_cod, col_mont, col_mod, col_ano = st.columns([2, 2, 2, 1])
        with col_cod:
            codigo_input = st.text_input("Código (Ex: P0001, C0035)", placeholder="Obrigatório").strip().upper()
        with col_mont:
            mont_input = st.text_input("Montadora (Opcional)", placeholder="Ex: Volvo, Scania").strip()
        with col_mod:
            mod_input = st.text_input("Modelo (Opcional)", placeholder="Ex: VM 330").strip()
        with col_ano:
            ano_input = st.text_input("Ano (Opcional)", placeholder="Ex: 2014").strip()
            
        btn_buscar = st.button("🔍 Iniciar Diagnóstico de IA", use_container_width=True, type="primary")
            
    if btn_buscar:
        if codigo_input:
            with st.spinner(f"Cruzando bancos de dados globais e manuais para {codigo_input}..."):
                descricao_encontrada = diagnostico_avancado_obd2(codigo_input, mont_input, mod_input, ano_input)
                st.subheader(f"Laudo Técnico: {codigo_input} {mont_input}")
                st.info(descricao_encontrada)
                salvar_pesquisa_obd2(codigo_input, mont_input, mod_input, ano_input, descricao_encontrada)
                st.success("✅ Diagnóstico salvo no histórico da nuvem!")
        else:
            st.warning("O código da falha é obrigatório para iniciar a busca.")
            
    st.divider()
    st.subheader("📚 Histórico de Pesquisas")
    df_historico = carregar_historico_obd2()
    if not df_historico.empty:
        st.dataframe(df_historico, use_container_width=True, hide_index=True)
    else:
        st.write("Nenhum código foi pesquisado ainda.")

# ------------------------------------------
# TELA 2: GESTÃO EEPROM (Layout Corrigido)
# ------------------------------------------
elif st.session_state.app_mode == "EEPROM":
    if st.session_state.montadora_selecionada == "":
        st.title("🚜 Painel de Controle - Baias EEPROM")
        st.markdown("### Escolha a Montadora desejada para abrir os modelos")
        st.write("")
        if not montadoras_existentes:
            st.info("Nenhuma montadora cadastrada. Converse com o Chip no painel lateral para criar uma!")
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
            escolha_modelo = st.selectbox("📂 Selecione o Veículo para carregar os gráficos:", [""] + modelos_existentes)
            st.write("")
            if escolha_modelo:
                st.markdown(f"#### 📍 Mapa: {st.session_state.montadora_selecionada} {escolha_modelo}")
                dados_mapa = buscar_dados_veiculo_unificado(st.session_state.montadora_selecionada, escolha_modelo)

                # Layout refeito para corrigir o vazamento de coluna
                col_info, col_img = st.columns([1, 2])
                
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
                    
                    with st.container(border=True):
                        st.markdown("⚙️ **Configuração de Mapa**")
                        if dados_mapa:
                            st.write(f"**Valores invertidos:** {dados_mapa.get('valores_invertidos', 'Desativado')}")
                            st.write(f"**Escala:** {dados_mapa.get('escala', '8 bits')}")

                with col_img:
                    if not dados_mapa or not dados_mapa["graficos"]:
                        st.error("⚠️ Nenhuma imagem de mapa encontrada para este veículo.")
                    else:
                        st.caption("💡 *Dica:* Clique nos botões de Expandir para ver os mapas detalhados em Tela Cheia!")
                        lista_fotos = dados_mapa["graficos"]
                        for idx in range(0, len(lista_fotos), 2):
                            sub_cols = st.columns(2)
                            with sub_cols[0]:
                                if idx < len(lista_fotos):
                                    label_cap = f"Gráfico Principal ({idx+1})"
                                    st.image(lista_fotos[idx], use_container_width=True, caption=label_cap)
                                    if st.button(f"🔍 Expandir ({idx+1})", key=f"btn_zoom_{idx}", use_container_width=True):
                                        abrir_modal_zoom(lista_fotos[idx], label_cap)
                            with sub_cols[1]:
                                if idx + 1 < len(lista_fotos):
                                    label_cap_2 = f"Gráfico Complementar ({idx+2})"
                                    st.image(lista_fotos[idx+1], use_container_width=True, caption=label_cap_2)
                                    if st.button(f"🔍 Expandir ({idx+2})", key=f"btn_zoom_{idx+1}", use_container_width=True):
                                        abrir_modal_zoom(lista_fotos[idx+1], label_cap_2)
                    
    st.markdown("<br><br>", unsafe_allow_html=True)

    with st.expander("➕ CADASTRAR: Adicionar Estruturas Independentes"):
        cad_tab1, cad_tab2 = st.tabs(["🏭 Cadastrar Montadora", "🚗 Cadastrar Veículo"])
        with cad_tab1:
            st.subheader("Nova Montadora")
            nova_m = st.text_input("Digite o Nome da Montadora", key="input_nova_m").strip()
            if st.button("Efetivar Montadora", type="primary"):
                if not nova_m: st.error("❌ O campo não pode ficar em branco!")
                else:
                    m_hig = higienizar_nome(nova_m)
                    if m_hig in montadoras_existentes: st.error(f"❌ Montadora '{m_hig}' já cadastrada!")
                    else:
                        conn = conectar_db(); cursor = conn.cursor()
                        cursor.execute("INSERT INTO montadoras (nome) VALUES (?)", (m_hig,))
                        conn.commit(); conn.close()
                        os.makedirs(os.path.join(BASE_DIR, m_hig), exist_ok=True)
                        backup_local_para_nuvem()
                        st.success(f"✅ Montadora '{m_hig}' salva no cofre!")
                        st.rerun()
                        
        with cad_tab2:
            st.subheader("Novo Veículo")
            if not montadoras_existentes: st.info("Cadastre ao menos uma montadora para liberar.")
            else:
                m_form = st.selectbox("Selecione a Montadora Alvo", montadoras_existentes, key="sb_m_form")
                v_form = st.text_input("Nome do Modelo / Veículo", key="input_v_form").strip()
                vc1, vc2 = st.columns(2)
                v_ini = vc1.text_input("Endereço Inicial", key="ini_v_form")
                v_int = vc2.text_input("Intervalo de Endereço", key="int_v_form")
                v_inv = st.selectbox("Valores Invertidos?", ["Desativado", "Ativado"], key="inv_v_form")
                v_esc = st.selectbox("Escala do Mapa", ["8 bits", "16 bits", "32 bits"], key="esc_v_form")
                v_det = st.text_area("Detalhes Adicionais", key="det_v_form")
                v_files = st.file_uploader("Fotos dos Gráficos (Máx 6)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="files_v_form")
                if st.button("Efetivar Veículo", type="primary"):
                    v_hig = higienizar_nome(v_form)
                    if not v_form: st.error("❌ O nome do veículo é obrigatório!")
                    else:
                        modelos_da_marca = listar_modelos(m_form)
                        if v_hig in modelos_da_marca: st.error(f"❌ Veículo '{v_hig}' já existe na {m_form}!")
                        else:
                            status_save = salvar_novo_veiculo_hibrido(m_form, v_form, v_ini, v_int, v_det, v_inv, v_esc, v_files)
                            if status_save:
                                st.success(f"✅ Ficha técnica '{v_hig}' sincronizada!")
                                st.rerun()

    with st.expander("⚙️ GERENCIAR: Painel de Edição e Exclusão Total"):
        ger_tab1, ger_tab2 = st.tabs(["🏭 Gerenciar Montadoras", "🚗 Gerenciar Veículos"])
        with ger_tab1:
            st.subheader("Modificação de Marcas")
            if not montadoras_existentes: st.warning("Nenhuma montadora localizada.")
            else:
                m_select_edit = st.selectbox("Escolha a Montadora para Alterar", montadoras_existentes, key="sb_m_edit_pane")
                novo_nome_m = st.text_input("Alterar Nome da Montadora para:", value=m_select_edit, key="txt_rename_m").strip()
                m_ed_col1, m_ed_col2 = st.columns(2)
                if m_ed_col1.button("💾 Salvar Novo Nome", key="btn_rename_m"):
                    n_m_hig = higienizar_nome(novo_nome_m)
                    if not n_m_hig: st.error("❌ Nome inválido.")
                    elif n_m_hig in montadoras_existentes and n_m_hig != m_select_edit: st.error("❌ Já existe!")
                    else:
                        conn = conectar_db(); cursor = conn.cursor()
                        cursor.execute("UPDATE montadoras SET nome = ? WHERE nome = ?", (n_m_hig, m_select_edit))
                        cursor.execute("UPDATE veiculos SET montadora_nome = ? WHERE montadora_nome = ?", (n_m_hig, m_select_edit))
                        conn.commit(); conn.close()
                        old_path = os.path.join(BASE_DIR, m_select_edit)
                        new_path = os.path.join(BASE_DIR, n_m_hig)
                        if os.path.exists(old_path): os.rename(old_path, new_path)
                        backup_local_para_nuvem()
                        st.success("✅ Nome atualizado globalmente!")
                        st.session_state.montadora_selecionada = ""
                        st.rerun()
                if m_ed_col2.button("🗑️ Excluir Montadora", key="btn_del_m_pane"):
                    excluir_montadora_db(m_select_edit)
                    st.success(f"✅ Limpeza concluída e Nuvem sincronizada.")
                    st.session_state.montadora_selecionada = ""
                    st.rerun()

        with ger_tab2:
            st.subheader("Edição Completa de Veículos")
            if not montadoras_existentes: st.warning("Sem marcas salvas.")
            else:
                m_sel_v = st.selectbox("Filtrar por Montadora", montadoras_existentes, key="sb_m_sel_v")
                v_existentes = listar_modelos(m_sel_v)
                if not v_existentes: st.info("Nenhum veículo localizado nesta marca.")
                else:
                    v_sel_edit = st.selectbox("Selecione o Veículo", v_existentes, key="sb_v_sel_edit")
                    dados_v = buscar_dados_veiculo_unificado(m_sel_v, v_sel_edit)
                    if dados_v:
                        st.markdown("---")
                        v_novo_nome = st.text_input("Alterar Nome do Veículo", value=v_sel_edit, key="txt_v_name_edit").strip()
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
                        st.warning("⚠️ Novas fotos substituirão todas as imagens antigas!")
                        v_novas_fotos = st.file_uploader("Substituir Imagens (Máx 6)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="files_v_edit")
                        v_manage_col1, v_manage_col2 = st.columns(2)
                        if v_manage_col1.button("💾 Salvar Alterações", type="primary", key="btn_save_v_edit"):
                            n_v_hig = higienizar_nome(v_novo_nome)
                            if not n_v_hig: st.error("❌ O nome não pode ser vazio.")
                            else:
                                if n_v_hig != v_sel_edit and n_v_hig in v_existentes: st.error("❌ Já existe outro modelo com esse nome!")
                                else:
                                    if n_v_hig != v_sel_edit:
                                        velha_pasta = os.path.join(BASE_DIR, m_sel_v, v_sel_edit)
                                        if os.path.exists(velha_pasta): shutil.rmtree(velha_pasta)
                                        conn = conectar_db(); cursor = conn.cursor()
                                        cursor.execute("UPDATE veiculos SET modelo = ? WHERE id = ?", (n_v_hig, dados_v["id"]))
                                        conn.commit(); conn.close()
                                    if n_v_hig != v_sel_edit and not v_novas_fotos:
                                        salvar_novo_veiculo_hibrido(m_sel_v, n_v_hig, v_novo_ini, v_novo_int, v_novo_det, v_novo_inv, v_novo_esc, None)
                                        sincronizar_banco_com_pastas()
                                    else:
                                        salvar_novo_veiculo_hibrido(m_sel_v, n_v_hig, v_novo_ini, v_novo_int, v_novo_det, v_novo_inv, v_novo_esc, v_novas_fotos)
                                    st.success(f"✅ Sucesso: Sincronizado com estabilidade!")
                                    st.rerun()
                        if v_manage_col2.button("🗑️ Excluir Veículo", key="btn_del_v_edit"):
                            excluir_veiculo_db(m_sel_v, v_sel_edit)
                            st.success(f"✅ Remoção Concluída!")
                            st.rerun()