import streamlit as st
import os
import json
import base64
import sqlite3
import re
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

st.set_page_config(page_title="EEPROM Master System", layout="wide")

def conectar_db():
    return sqlite3.connect(DB_PATH)

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
    conn.commit()
    conn.close()

init_db()

# --- VARIÁVEIS DE SESSÃO E IDENTIDADE DO CHIP ---
if 'montadora_selecionada' not in st.session_state:
    st.session_state.montadora_selecionada = ""
if 'chat_historico' not in st.session_state:
    # O Chip agora se apresenta formalmente!
    st.session_state.chat_historico = [{"role": "assistant", "content": "Olá! Eu sou o **Chip**, seu assistente de sistema. Digite **/ajuda** para ver os comandos disponíveis."}]

# --- FUNÇÕES DE GERENCIAMENTO (CRUD HÍBRIDO) ---
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
                "posicao_inicio": row[1], "intervalo": row[2], "valores_invertidos": row[3],
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
    except Exception as e:
        st.error(f"Erro na gestão: {e}")
        return False
    finally:
        conn.close()

def excluir_veiculo_db(montadora, modelo):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (higienizar_nome(montadora), higienizar_nome(modelo)))
    conn.commit()
    conn.close()

def excluir_montadora_db(montadora):
    mont = higienizar_nome(montadora)
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM veiculos WHERE montadora_nome = ?", (mont,))
    cursor.execute("DELETE FROM montadoras WHERE nome = ?", (mont,))
    conn.commit()
    conn.close()

# --- 🎨 CONTROLE VISUAL ---
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

# --- BARRA LATERAL (MENU + BOT CHIP) ---
st.sidebar.title("🛡️ EEPROM System")
if st.sidebar.button("🏠 Voltar para Tela Inicial", use_container_width=True):
    st.session_state.montadora_selecionada = ""
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("🤖 **Chip - Assistente do Sistema**")

# Loop para exibir o histórico de mensagens do Chip na barra lateral
for mensagem in st.session_state.chat_historico:
    with st.sidebar.chat_message(mensagem["role"]):
        st.markdown(mensagem["content"])

# Caixa de texto do chat do Chip
if prompt := st.sidebar.chat_input("Fale com o Chip (ex: /status)"):
    st.session_state.chat_historico.append({"role": "user", "content": prompt})
    
    comando = prompt.strip().lower()
    resposta = ""
    
    if comando == "/ajuda":
        resposta = "**O que o Chip sabe fazer:**\n* `/status`: Vê os números do sistema.\n* `/sync`: Reconstrói pastas físicas.\n* `/backup`: Dica de segurança.\n* `/limpar`: Limpa o chat."
    
    elif comando == "/status":
        conn = conectar_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM montadoras")
        qtd_m = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM veiculos")
        qtd_v = c.fetchone()[0]
        conn.close()
        resposta = f"📊 **Status da Biblioteca:**\nVocê tem **{qtd_m} montadoras** cadastradas e um total de **{qtd_v} veículos**. O Chip está de olho em tudo!"
    
    elif comando == "/sync":
        qtd = sincronizar_banco_com_pastas()
        resposta = f"✅ **Sincronização concluída!** O Chip verificou o banco e garantiu que **{qtd} pastas** físicas estivessem perfeitas no seu computador."
    
    elif comando == "/backup":
        resposta = f"🛡️ **Dica de Backup do Chip:** Para não perder nada, basta fazer uma cópia de segurança do arquivo chamado `eeprom_master.db` que está na pasta `{BASE_DIR}`."
        
    elif comando == "/limpar":
        st.session_state.chat_historico = [{"role": "assistant", "content": "Chat limpo! Como o Chip pode te ajudar agora?"}]
        st.rerun()
        
    else:
        resposta = "⚠️ Comando não reconhecido. Digite **/ajuda** para ver o que o Chip sabe fazer."
    
    if resposta:
        st.session_state.chat_historico.append({"role": "assistant", "content": resposta})
        st.rerun()

st.sidebar.markdown("---")
montadoras_existentes = listar_montadoras()

# --- TELA INICIAL: DASHBOARD ---
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

# --- TELA INTERNA ---
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
        else:
            st.subheader("🏭")
            
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
                    lista_fotos = dados_mapa["graficos"]
                    for idx in range(0, len(lista_fotos), 2):
                        sub_cols = st.columns(2)
                        with sub_cols[0]:
                            if idx < len(lista_fotos):
                                st.image(lista_fotos[idx], use_container_width=True, caption=f"Gráfico Principal ({idx+1})")
                        with sub_cols[1]:
                            if idx + 1 < len(lista_fotos):
                                st.image(lista_fotos[idx+1], use_container_width=True, caption=f"Gráfico Complementar ({idx+2})")
                
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

# --- SEÇÃO ADMINISTRATIVA (CADASTRAR E GERENCIAR) ---
st.markdown("<br><br>", unsafe_allow_html=True)

with st.expander("➕ CADASTRAR: Adicionar Montadoras e Veículos"):
    adm1, adm2 = st.columns(2)
    with adm1:
        st.subheader("Nova Montadora")
        nova_m = st.text_input("Nome da Montadora").strip()
        if st.button("Salvar Montadora"): 
            if nova_m:
                mont_higienizada = higienizar_nome(nova_m)
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO montadoras (nome) VALUES (?)", (mont_higienizada,))
                conn.commit(); conn.close()
                os.makedirs(os.path.join(BASE_DIR, mont_higienizada), exist_ok=True)
                st.success("Montadora salva e pasta criada!"); st.rerun()
    with adm2:
        st.subheader("Novo Veículo")
        if montadoras_existentes:
            m_adm = st.selectbox("Escolha a Montadora", montadoras_existentes)
            v_adm = st.text_input("Nome do Modelo")
            c1, c2 = st.columns(2)
            v_ini = c1.text_input("Endereço Inicial")
            v_int = c2.text_input("Intervalo")
            
            c_adm1, c_adm2 = st.columns(2)
            v_inv_input = c_adm1.selectbox("Valores Invertidos?", ["Desativado", "Ativado"])
            v_escala_input = c_adm2.selectbox("Escala do Mapa", ["8 bits", "16 bits", "32 bits"])
            
            v_det = st.text_area("Informações Adicionais")
            v_files = st.file_uploader("Fotos dos Gráficos (Máx 6)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
            if st.button("Salvar Veículo"): 
                if v_adm:
                    salvar_novo_veiculo_hibrido(m_adm, v_adm, v_ini, v_int, v_det, v_inv_input, v_escala_input, v_files)
                    st.success("Veículo guardado no BD e Pasta Local atualizada!"); st.rerun()

with st.expander("⚙️ GERENCIAR: Editar ou Excluir Dados"):
    tab1, tab2, tab3 = st.tabs(["✏️ Editar Veículo", "🗑️ Excluir Veículo", "⚠️ Excluir Montadora"])
    
    with tab1:
        st.markdown("Reescreva os dados do veículo e clique em Salvar para atualizar.")
        if montadoras_existentes:
            edit_mont = st.selectbox("Montadora (Editar)", montadoras_existentes, key="edit_m")
            modelos_edit = listar_modelos(edit_mont)
            if modelos_edit:
                edit_mod = st.selectbox("Veículo (Editar)", modelos_edit, key="edit_v")
                dados_atuais = buscar_dados_veiculo_unificado(edit_mont, edit_mod)
                
                if dados_atuais:
                    ec1, ec2 = st.columns(2)
                    n_ini = ec1.text_input("Novo Endereço", value=dados_atuais["posicao_inicio"], key="n_ini")
                    n_int = ec2.text_input("Novo Intervalo", value=dados_atuais["intervalo"], key="n_int")
                    
                    esc1, esc2 = st.columns(2)
                    inv_index = 0 if dados_atuais["valores_invertidos"] == "Desativado" else 1
                    n_inv = esc1.selectbox("Valores Invertidos?", ["Desativado", "Ativado"], index=inv_index, key="n_inv")
                    
                    escala_opcoes = ["8 bits", "16 bits", "32 bits"]
                    escala_index = escala_opcoes.index(dados_atuais["escala"]) if dados_atuais["escala"] in escala_opcoes else 0
                    n_esc = esc2.selectbox("Escala do Mapa", escala_opcoes, index=escala_index, key="n_esc")
                    
                    n_det = st.text_area("Novas Informações", value=dados_atuais["detalhes"], key="n_det")
                    st.info("⚠️ Para manter as fotos atuais, deixe o campo abaixo vazio.")
                    n_files = st.file_uploader("Substituir Fotos (Máx 6)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="n_file")
                    
                    if st.button("💾 Salvar Alterações", type="primary"):
                        salvar_novo_veiculo_hibrido(edit_mont, edit_mod, n_ini, n_int, n_det, n_inv, n_esc, n_files if n_files else None)
                        st.success("Dados e Pastas atualizados!"); st.rerun()
            else:
                st.warning("Sem veículos nesta montadora.")
                
    with tab2:
        if montadoras_existentes:
            del_mont = st.selectbox("Montadora do Veículo a excluir", montadoras_existentes, key="del_m_v")
            modelos_del = listar_modelos(del_mont)
            if modelos_del:
                del_mod = st.selectbox("Veículo a Excluir", modelos_del, key="del_v")
                if st.button("🗑️ Confirmar Exclusão de Veículo"):
                    excluir_veiculo_db(del_mont, del_mod)
                    st.error("Veículo removido do Sistema!"); st.rerun()
            else:
                st.warning("Sem veículos para excluir.")

    with tab3:
        if montadoras_existentes:
            del_m = st.selectbox("Selecione a Montadora para apagar TUDO", montadoras_existentes, key="del_m")
            st.error(f"Atenção: Isso apagará a montadora {del_m} e TODOS os seus veículos.")
            if st.button("⚠️ Confirmar Exclusão de Montadora"):
                excluir_montadora_db(del_m)
                st.success("Montadora apagada do Sistema!"); st.rerun()