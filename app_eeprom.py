import streamlit as st
import os
import json
import base64
import sqlite3
import re
import shutil
import unicodedata
from PIL import Image
from huggingface_hub import HfApi, hf_hub_download

# --- CONFIGURAÇÕES DE NUVEM E ANCORAGEM ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "eeprom_master.db")

HF_TOKEN = os.environ.get("HF_TOKEN")
DATASET_REPO_ID = "GrizzlyBear25/HyperTork_DB" 

# --- IA GESTORA DA BIBLIOTECA DA NUVEM ---
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

sincronizar_nuvem_para_local()

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
            
            dados_json = {"posicao_inicio": ini, "intervalo": inter, "valores_invertidos": val_inv, "escala": esc, "detalhes": det}
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
    cursor.execute("CREATE TABLE IF NOT EXISTS chip_memoria (id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT UNIQUE NOT NULL, valor TEXT NOT NULL)")
    conn.commit()
    conn.close()

init_db()

# --- VARIÁVEIS DE SESSÃO ---
if 'montadora_selecionada' not in st.session_state:
    st.session_state.montadora_selecionada = ""
if 'chat_historico' not in st.session_state:
    st.session_state.chat_historico = [{"role": "assistant", "content": "Olá! Eu sou o **Chip**. Fui promovido a Operador! Você pode me pedir para cadastrar, renomear ou excluir veículos direto por aqui."}]

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
        
        dados_json = {"posicao_inicio": inicio, "intervalo": intervalo, "valores_invertidos": valores_invertidos, "escala": escala, "detalhes": info_extra}
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
        backup_local_para_nuvem() 
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
    backup_local_para_nuvem() 

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
    backup_local_para_nuvem() 

# --- 🧠 LÓGICA DE APRENDIZADO E NLP DO CHIP ---
def normalizar_texto(texto):
    """Remove acentos, caracteres especiais básicos e padroniza para minúsculo"""
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return texto.lower().strip()

def salvar_memoria_chip(chave, valor):
    ch = normalizar_texto(chave)
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO chip_memoria (chave, valor) VALUES (?, ?)", (ch, valor.strip()))
    conn.commit()
    conn.close()
    backup_local_para_nuvem()

def buscar_memoria_chip(texto):
    tx = normalizar_texto(texto)
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT chave, valor FROM chip_memoria")
    linhas = cursor.fetchall()
    conn.close()
    for chave, valor in linhas:
        if chave in tx or tx in chave: 
            return f"🧠 **O que eu lembro sobre '{chave.upper()}':**\n\n{valor}"
    return None

def processar_linguagem_chip(prompt_cru):
    msg = normalizar_texto(prompt_cru)
    
    # 1. INTENÇÃO: Renomear Montadora
    if "renomear montadora" in msg:
        try:
            partes = msg.split("renomear montadora ")[1].split(" para ")
            antiga = higienizar_nome(partes[0])
            nova = higienizar_nome(partes[1])
            
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("SELECT nome FROM montadoras WHERE nome = ?", (antiga,))
            if not cursor.fetchone():
                conn.close()
                return f"⚠️ Não encontrei a montadora '{antiga}' para renomear."
                
            cursor.execute("UPDATE montadoras SET nome = ? WHERE nome = ?", (nova, antiga))
            cursor.execute("UPDATE veiculos SET montadora_nome = ? WHERE montadora_nome = ?", (nova, antiga))
            conn.commit(); conn.close()
            
            old_path = os.path.join(BASE_DIR, antiga)
            new_path = os.path.join(BASE_DIR, nova)
            if os.path.exists(old_path): os.rename(old_path, new_path)
            
            backup_local_para_nuvem()
            return f"🔄 **Operação Feita!** A montadora `{antiga}` agora se chama `{nova}` em todo o sistema e na Nuvem!"
        except:
            return "⚠️ Para eu entender, use exatamente o formato: `Chip, renomear montadora [NOME ANTIGO] para [NOME NOVO]`"

    # 2. INTENÇÃO: Cadastrar Veículo
    if "cadastrar veiculo" in msg or "criar veiculo" in msg:
        try:
            txt = msg.replace("criar veiculo", "cadastrar veiculo")
            partes = txt.split("cadastrar veiculo ")[1].split(" na montadora ")
            mod = higienizar_nome(partes[0])
            mont = higienizar_nome(partes[1])
            
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("SELECT nome FROM montadoras WHERE nome = ?", (mont,))
            if not cursor.fetchone():
                conn.close()
                return f"⚠️ A montadora '{mont}' não existe. Peça para eu criá-la primeiro!"
            conn.close()
            
            # Cria o veículo com dados base
            salvar_novo_veiculo_hibrido(mont, mod, "Não Definido", "Não Definido", "Criado pelo Chip via Chat", "Desativado", "8 bits", None)
            return f"🚗 **Ficha Criada!** Adicionei o veículo `{mod}` na montadora `{mont}` e salvei no Cofre.\n\n💡 *Dica:* Como sou um bot de texto, vá até a aba **⚙️ GERENCIAR** depois para inserir os Hexadecimais reais e fazer o upload das fotos!"
        except:
            return "⚠️ Para eu cadastrar o carro, use o formato: `Chip, cadastrar veiculo [CARRO] na montadora [MARCA]`"

    # 3. INTENÇÃO: Excluir Veículo
    if "excluir veiculo" in msg or "apagar veiculo" in msg:
        try:
            txt = msg.replace("apagar veiculo", "excluir veiculo")
            partes = txt.split("excluir veiculo ")[1].split(" da montadora ")
            mod = higienizar_nome(partes[0])
            mont = higienizar_nome(partes[1])
            
            excluir_veiculo_db(mont, mod)
            return f"🗑️ **Excluído!** O veículo `{mod}` foi deletado permanentemente da montadora `{mont}`."
        except:
            return "⚠️ Para eu apagar, use o formato: `Chip, excluir veiculo [CARRO] da montadora [MARCA]`"

    # 4. INTENÇÃO: Excluir Montadora
    if "excluir montadora" in msg or "apagar montadora" in msg:
        try:
            txt = msg.replace("apagar montadora", "excluir montadora")
            mont = higienizar_nome(txt.split("excluir montadora ")[1])
            excluir_montadora_db(mont)
            return f"💥 **Destruição Concluída!** A montadora `{mont}` e todos os seus veículos foram apagados da existência."
        except:
            return "⚠️ Para eu apagar a marca inteira, use: `Chip, excluir montadora [NOME]`"

    # 5. INTENÇÃO: Editar Veículo (Guia para UI)
    if "editar informacoes" in msg or "editar veiculo" in msg or "editar carro" in msg:
        return "🛠️ **Edição de Ficha Técnica:** Eu consigo criar e apagar arquivos, mas para alterar endereços Hexadecimais e **adicionar fotos**, por favor use a aba de botões **⚙️ GERENCIAR** logo abaixo do painel principal. Meu terminal de texto ainda não consegue fazer upload de fotos do seu HD!"

    # 6. INTENÇÃO: Criar Montadora
    padroes_criar = ["cria a montadora", "crie a montadora", "criar montadora", "adicione a montadora", "nova montadora", "/montadora"]
    if any(p in msg for p in padroes_criar):
        nome_m = ""
        if "/montadora" in msg:
            nome_m = prompt_cru.split("/montadora", 1)[1].strip()
        else:
            partes = msg.split("montadora")
            if len(partes) > 1:
                nome_m = partes[1].replace("chamada", "").replace("a ", "").replace("uma ", "").replace("o nome", "").strip()

        nome_m = higienizar_nome(nome_m)
        if not nome_m: 
            return "Entendi que quer criar uma montadora, mas qual o nome? Exemplo: `Crie a montadora AUDI`"

        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT nome FROM montadoras WHERE nome = ?", (nome_m,))
        if cursor.fetchone():
            conn.close()
            return f"⚠️ Ops! A montadora **{nome_m}** já existe e está segura na nuvem!"

        cursor.execute("INSERT INTO montadoras (nome) VALUES (?)", (nome_m,))
        conn.commit()
        conn.close()
        os.makedirs(os.path.join(BASE_DIR, nome_m), exist_ok=True)
        backup_local_para_nuvem()
        return f"🏭 **Entendido! Criei a montadora {nome_m} e já sincronizei com a Nuvem!** \n\n🎨 Para a logo, basta colocar um arquivo `{nome_m}.png` na pasta local `Logos/`."

    # 7. INTENÇÃO: Aprender / Memória
    if "/aprender" in msg:
        corpo = prompt_cru.split("/aprender", 1)[1].strip()
        if ":" in corpo:
            chave, valor = corpo.split(":", 1)
            salvar_memoria_chip(chave, valor)
            return f"✅ Entendido! Fixei **'{chave.strip().upper()}'** na minha memória permanente."
        return "⚠️ Formato incorreto. Use: `/aprender termo: significado`"
        
    if "memoria" in msg or "o que voce aprendeu" in msg:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT chave FROM chip_memoria")
        chaves = [c[0].upper() for c in cursor.fetchall()]
        conn.close()
        if chaves: return "🧠 **Termos que eu absorvi:**\n\n" + "\n".join([f"* {c}" for c in chaves])
        return "Minha memória de termos está em branco. Me ensine algo usando `/aprender termo: explicacao`!"

    # 8. INTENÇÃO: Busca em Memória
    memoria_receptiva = buscar_memoria_chip(prompt_cru)
    if memoria_receptiva: return memoria_receptiva

    # 9. INTENÇÃO: Status e Sincronização
    if any(s in msg for s in ["status", "quantos", "estatistica", "resumo"]):
        conn = conectar_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM montadoras"); q_m = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM veiculos"); q_v = c.fetchone()[0]
        conn.close()
        return f"📊 **Estatísticas Atuais:** Temos **{q_m} montadoras** e **{q_v} modelos** gravados no banco de dados."

    if any(s in msg for s in ["sincronizar", "recuperar pastas", "sync"]):
        qtd = sincronizar_banco_com_pastas()
        return f"🔄 **Manutenção Concluída:** Diagnostiquei a árvore e reconstruí **{qtd} pastas** físicas locais ausentes."

    if any(b in msg for b in ["backup", "salvar", "nuvem"]):
        return f"🛡️ **Proteção Ativa:** Meu backup automático no Dataset `HyperTork_DB` está online e protegendo tudo!"

    # 10. INTENÇÃO: Ajuda
    if any(a in msg for a in ["ajuda", "comandos", "o que voce faz", "help"]):
        return (
            "🤖 **Sou o Chip e recebi poderes Administrativos!**\n\n"
            "Escreva para mim usando estes padrões para eu operar o sistema:\n"
            "* `Crie a montadora [MARCA]`\n"
            "* `Renomear montadora [ANTIGA] para [NOVA]`\n"
            "* `Cadastrar veiculo [CARRO] na montadora [MARCA]`\n"
            "* `Excluir veiculo [CARRO] da montadora [MARCA]`\n"
            "* `Excluir montadora [MARCA]`\n\n"
            "Lembrando que para subir fotos, você ainda precisa usar a aba 'Gerenciar' ao lado!"
        )

    # 11. INTENÇÃO: Cumprimentos
    if any(c == msg for c in ["oi", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "chip"]):
        return "🤖 Olá! Processamento de Linguagem Natural online. Qual instrução de banco de dados quer que eu execute hoje?"
        
    return "🤔 Recebi seu comando, mas não identifiquei a estrutura. Digite **ajuda** para ver o formato que eu consigo ler para cadastrar/editar tabelas!"

# --- 🖼️ MODAL DE ZOOM EXPANDIDO EM TELA CHEIA ---
@st.dialog("🔍 Visualizador de Mapa Ampliado", width="large")
def abrir_modal_zoom(foto_bytes, legenda_titulo):
    st.write(f"#### {legenda_titulo}")
    zoom_dinamico = st.slider("Arraste para ajustar o Zoom do Mapa (Pixels)", 400, 2000, 950, step=50)
    st.image(foto_bytes, width=zoom_dinamico)
    st.write("")
    if st.button("❌ Fechar Visualização", use_container_width=True):
        st.rerun()

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

# --- BARRA LATERAL (MENU + CHAT CHIP) ---
st.sidebar.title("🛡️ HyperTork System")
if st.sidebar.button("🏠 Voltar para Tela Inicial", use_container_width=True):
    st.session_state.montadora_selecionada = ""
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("🤖 **Chip - Assistente Operacional**")

for mensagem in st.session_state.chat_historico:
    with st.sidebar.chat_message(mensagem["role"]):
        st.markdown(mensagem["content"])

if prompt := st.sidebar.chat_input("Dê um comando para o Chip..."):
    st.session_state.chat_historico.append({"role": "user", "content": prompt})
    if prompt.strip().lower() in ["/limpar", "limpar chat", "limpar"]:
        st.session_state.chat_historico = [{"role": "assistant", "content": "Visão limpa! Qual é o próximo comando?"}]
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
        st.info("Nenhuma montadora cadastrada. Use a área administrativa ou peça para o Chip 'criar a montadora'!")
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
                    st.caption("💡 *Dica:* Clique em 'Expandir e Dar Zoom' abaixo das fotos para abrir o Visualizador em Tela Cheia!")
                    
                    lista_fotos = dados_mapa["graficos"]
                    for idx in range(0, len(lista_fotos), 2):
                        sub_cols = st.columns(2)
                        with sub_cols[0]:
                            if idx < len(lista_fotos):
                                label_cap = f"Gráfico Principal ({idx+1})"
                                st.image(lista_fotos[idx], use_container_width=True, caption=label_cap)
                                if st.button(f"🔍 Expandir e Dar Zoom ({idx+1})", key=f"btn_zoom_{idx}", use_container_width=True):
                                    abrir_modal_zoom(lista_fotos[idx], label_cap)
                                    
                        with sub_cols[1]:
                            if idx + 1 < len(lista_fotos):
                                label_cap_2 = f"Gráfico Complementar ({idx+2})"
                                st.image(lista_fotos[idx+1], use_container_width=True, caption=label_cap_2)
                                if st.button(f"🔍 Expandir e Dar Zoom ({idx+2})", key=f"btn_zoom_{idx+1}", use_container_width=True):
                                    abrir_modal_zoom(lista_fotos[idx+1], label_cap_2)
                
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

# --- SEÇÃO ADMINISTRATIVA INDEPENDENTE ---
st.markdown("<br><br>", unsafe_allow_html=True)

with st.expander("➕ CADASTRAR: Adicionar Estruturas Independentes"):
    cad_tab1, cad_tab2 = st.tabs(["🏭 Cadastrar Montadora", "🚗 Cadastrar Veículo"])
    
    with cad_tab1:
        st.subheader("Nova Montadora")
        nova_m = st.text_input("Digite o Nome da Montadora", key="input_nova_m").strip()
        if st.button("Efetivar Montadora", type="primary"):
            if not nova_m:
                st.error("❌ Erro de Cadastro: O campo de nome da montadora não pode ficar em branco!")
            else:
                m_hig = higienizar_nome(nova_m)
                if m_hig in montadoras_existentes:
                    st.error(f"❌ Falha de Duplicidade: A montadora '{m_hig}' já encontra-se cadastrada no banco de dados!")
                else:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO montadoras (nome) VALUES (?)", (m_hig,))
                    conn.commit(); conn.close()
                    os.makedirs(os.path.join(BASE_DIR, m_hig), exist_ok=True)
                    backup_local_para_nuvem()
                    st.success(f"✅ Sucesso Absoluto: Montadora '{m_hig}' foi salva no Dataset em Nuvem!")
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
                    st.error("❌ Erro de Validação: O nome do modelo/veículo é obrigatório!")
                else:
                    modelos_da_marca = listar_modelos(m_form)
                    if v_hig in modelos_da_marca:
                        st.error(f"❌ Falha de Duplicidade: O veículo '{v_hig}' já existe na montadora {m_form}!")
                    else:
                        status_save = salvar_novo_veiculo_hibrido(m_form, v_form, v_ini, v_int, v_det, v_inv, v_esc, v_files)
                        if status_save:
                            st.success(f"✅ Sucesso Absoluto: Ficha técnica do modelo '{v_hig}' sincronizada com a Nuvem!")
                            st.rerun()
                        else:
                            st.error("❌ Erro de Gravação.")

# --- GERENCIAMENTO DE ALTERAÇÃO SEPARADO (EDICAO TOTAL) ---
with st.expander("⚙️ GERENCIAR: Painel de Edição e Exclusão Total"):
    ger_tab1, ger_tab2 = st.tabs(["🏭 Gerenciar Montadoras", "🚗 Gerenciar Veículos"])
    
    with ger_tab1:
        st.subheader("Modificação de Marcas")
        if not montadoras_existentes:
            st.warning("Nenhuma montadora localizada.")
        else:
            m_select_edit = st.selectbox("Escolha a Montadora para Alterar", montadoras_existentes, key="sb_m_edit_pane")
            novo_nome_m = st.text_input("Alterar Nome da Montadora para:", value=m_select_edit, key="txt_rename_m").strip()
            
            m_ed_col1, m_ed_col2 = st.columns(2)
            if m_ed_col1.button("💾 Salvar Novo Nome da Montadora", key="btn_rename_m"):
                n_m_hig = higienizar_nome(novo_nome_m)
                if not n_m_hig: st.error("❌ Erro: Nome nulo inválido.")
                elif n_m_hig in montadoras_existentes and n_m_hig != m_select_edit: st.error("❌ Erro: Essa montadora já existe!")
                else:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE montadoras SET nome = ? WHERE nome = ?", (n_m_hig, m_select_edit))
                    cursor.execute("UPDATE veiculos SET montadora_nome = ? WHERE montadora_nome = ?", (n_m_hig, m_select_edit))
                    conn.commit(); conn.close()
                    old_path = os.path.join(BASE_DIR, m_select_edit)
                    new_path = os.path.join(BASE_DIR, n_m_hig)
                    if os.path.exists(old_path): os.rename(old_path, new_path)
                    
                    backup_local_para_nuvem()
                    st.success("✅ Sucesso: Nome da marca atualizado globalmente e na Nuvem!")
                    st.session_state.montadora_selecionada = ""
                    st.rerun()
                    
            if m_ed_col2.button("🗑️ Excluir Montadora (Apaga Tudo)", key="btn_del_m_pane"):
                excluir_montadora_db(m_select_edit)
                st.success(f"✅ Limpeza concluída e Nuvem sincronizada.")
                st.session_state.montadora_selecionada = ""
                st.rerun()

    with ger_tab2:
        st.subheader("Edição Completa de Veículos")
        if not montadoras_existentes:
            st.warning("Sem marcas salvas.")
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
                    
                    st.warning("⚠️ Atenção: Enviar novas fotos substituirá todas as imagens antigas deste veículo!")
                    v_novas_fotos = st.file_uploader("Substituir Imagens de Mapas (Máx 6)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="files_v_edit")
                    
                    v_manage_col1, v_manage_col2 = st.columns(2)
                    
                    if v_manage_col1.button("💾 Salvar Todas as Alterações do Veículo", type="primary", key="btn_save_v_edit"):
                        n_v_hig = higienizar_nome(v_novo_nome)
                        if not n_v_hig: st.error("❌ Erro: O nome do modelo não pode ser vazio.")
                        else:
                            if n_v_hig != v_sel_edit and n_v_hig in v_existentes:
                                st.error("❌ Erro de Duplicidade: Já existe outro modelo com esse nome nesta montadora!")
                            else:
                                if n_v_hig != v_sel_edit:
                                    velha_pasta = os.path.join(BASE_DIR, m_sel_v, v_sel_edit)
                                    if os.path.exists(velha_pasta): shutil.rmtree(velha_pasta)
                                    conn = conectar_db()
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE veiculos SET modelo = ? WHERE id = ?", (n_v_hig, dados_v["id"]))
                                    conn.commit(); conn.close()
                                
                                if n_v_hig != v_sel_edit and not v_novas_fotos:
                                    salvar_novo_veiculo_hibrido(m_sel_v, n_v_hig, v_novo_ini, v_novo_int, v_novo_det, v_novo_inv, v_novo_esc, None)
                                    sincronizar_banco_com_pastas()
                                else:
                                    salvar_novo_veiculo_hibrido(m_sel_v, n_v_hig, v_novo_ini, v_novo_int, v_novo_det, v_novo_inv, v_novo_esc, v_novas_fotos)
                                    
                                st.success(f"✅ Sucesso: O veículo '{n_v_hig}' foi modificado e salvo na Nuvem com estabilidade!")
                                st.rerun()
                                
                    if v_manage_col2.button("🗑️ Excluir Este Veículo do Sistema", key="btn_del_v_edit"):
                        excluir_veiculo_db(m_sel_v, v_sel_edit)
                        st.success(f"✅ Remoção Concluída na Nuvem!")
                        st.rerun()