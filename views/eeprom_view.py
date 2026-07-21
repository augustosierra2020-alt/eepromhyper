import streamlit as st
import os
import base64
import json
import shutil
import unicodedata
import re
import time
from core.db import get_db_connection
from services.hf_sync import backup_local_para_nuvem_async

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGOS_DIR = os.path.join(BASE_DIR, "Logos")

def limpar_para_comparacao(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^A-Z0-9]', '', texto.upper())

def higienizar_nome(nome: str) -> str:
    if not nome: return ""
    return re.sub(r'[\\/*?:"<>|]', "", " ".join(nome.strip().upper().split()))

def buscar_logo_montadora_automatica(montadora):
    if os.path.exists(LOGOS_DIR):
        arquivos = sorted(os.listdir(LOGOS_DIR), key=lambda x: (not x.lower().endswith('.png'), x))
        mont_alvo = limpar_para_comparacao(montadora)
        for arquivo in arquivos:
            if not arquivo.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')): continue
            nome_arq = limpar_para_comparacao(os.path.splitext(arquivo)[0])
            if mont_alvo == nome_arq: return os.path.join(LOGOS_DIR, arquivo)
    return None

def renderizar_logo_harmonizada(caminho, montadora_nome=""):
    if not caminho or not os.path.exists(caminho): return False
    try:
        with open(caminho, "rb") as image_file: encoded_string = base64.b64encode(image_file.read()).decode()
        st.markdown(f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 110px; width: 100%; background-color: #FFFFFF; border-radius: 12px; padding: 10px; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.05); margin-bottom: 10px;">
                <img src="data:image/png;base64,{encoded_string}" style="max-height: 90px; max-width: 100%; object-fit: contain; pointer-events: none; user-select: none; -webkit-user-drag: none;">
            </div>
        """, unsafe_allow_html=True)
        return True
    except: return False

def render_eeprom():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if 'montadora_selecionada' not in st.session_state: st.session_state.montadora_selecionada = ""
    if 'escolha_modelo' not in st.session_state: st.session_state.escolha_modelo = ""

    if st.session_state.montadora_selecionada == "":
        st.title("🚜 Painel de Controle - Mapas EEPROM")
        cursor.execute("SELECT nome FROM montadoras")
        montadoras = sorted(list(set([higienizar_nome(r[0]) for r in cursor.fetchall()])))
        
        for i in range(0, len(montadoras), 4):
            cols = st.columns(4)
            for j in range(4):
                if i + j < len(montadoras):
                    m = montadoras[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            caminho_logo = buscar_logo_montadora_automatica(m)
                            if renderizar_logo_harmonizada(caminho_logo, m) or True:
                                if st.button(f"{m}", key=f"ee_{m}", use_container_width=True): 
                                    st.session_state.montadora_selecionada = m
                                    st.session_state.escolha_modelo = ""
                                    st.rerun()
    else:
        montadora_atual = st.session_state.montadora_selecionada
        caminho_logo_m = buscar_logo_montadora_automatica(montadora_atual)
        
        if caminho_logo_m and os.path.exists(caminho_logo_m):
            try:
                with open(caminho_logo_m, "rb") as lf: enc_logo_m = base64.b64encode(lf.read()).decode()
                st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                        <img src="data:image/png;base64,{enc_logo_m}" style="max-height: 45px; max-width: 120px; object-fit: contain;">
                        <h1 style="margin: 0; font-size: 2.2rem;">{montadora_atual}</h1>
                    </div>
                """, unsafe_allow_html=True)
            except: st.title(f"🏭 {montadora_atual}")
        else: st.title(f"🏭 {montadora_atual}")
            
        st.markdown("---")
        
        cursor.execute("SELECT modelo FROM veiculos WHERE montadora_nome = ?", (higienizar_nome(montadora_atual),))
        modelos = sorted(list(set([higienizar_nome(r[0]) for r in cursor.fetchall()])))
        
        col_mod1, col_mod2 = st.columns([1, 2])
        with col_mod1:
            st.subheader("🚗 Modelos Salvos")
            if not modelos: st.info("Nenhum modelo cadastrado nesta categoria.")
            for m_idx, mod in enumerate(modelos):
                if st.button(f"📁 {mod}", key=f"mod_btn_{m_idx}", use_container_width=True):
                    st.session_state.escolha_modelo = mod; st.rerun()
                    
            st.markdown("---")
            st.subheader("➕ Novo Veículo / Mapa")
            with st.form("novo_veiculo_form"):
                novo_mod = st.text_input("Nome do Modelo/Motor:")
                p_ini = st.text_input("Posição Inicial Hex:", value="0x00")
                p_int = st.text_input("Intervalo / Tamanho:")
                p_scale = st.text_input("Fator de Escala:", value="1.0")
                p_inv = st.selectbox("Inverter Valores?", ["Não", "Sim"])
                p_det = st.text_area("Detalhes Técnicos / Pinagem da ECU:")
                uploaded_imgs = st.file_uploader("Imagens/Gráficos da Eeprom:", accept_multiple_files=True, type=["png", "jpg", "jpeg"])
                
                if st.form_submit_button("💾 Salvar Parâmetros", use_container_width=True):
                    if novo_mod and p_ini and p_int:
                        m_clean = higienizar_nome(montadora_atual)
                        mod_clean = higienizar_nome(novo_mod)
                        cursor.execute("INSERT OR IGNORE INTO montadoras (nome) VALUES (?)", (m_clean,))
                        cursor.execute("INSERT OR REPLACE INTO veiculos (montadora_nome, modelo, posicao_inicio, intervalo, valores_invertidos, escala, detalhes) VALUES (?, ?, ?, ?, ?, ?, ?)", (m_clean, mod_clean, p_ini, p_int, p_inv, p_scale, p_det))
                        cursor.execute("SELECT id FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (m_clean, mod_clean))
                        v_id = cursor.fetchone()[0]
                        
                        # Espelho físico em pastas locais
                        pasta = os.path.join(BASE_DIR, m_clean, mod_clean)
                        os.makedirs(pasta, exist_ok=True)
                        with open(os.path.join(pasta, "dados.json"), "w", encoding="utf-8") as f:
                            json.dump({"posicao_inicio": p_ini, "intervalo": p_int, "valores_invertidos": p_inv, "escala": p_scale, "detalhes": p_det}, f)
                        
                        if uploaded_imgs:
                            cursor.execute("DELETE FROM graficos WHERE veiculo_id = ?", (v_id,))
                            for idx, img_file in enumerate(uploaded_imgs[:6]):
                                img_bytes = img_file.read()
                                cursor.execute("INSERT INTO graficos (veiculo_id, foto, ordem) VALUES (?, ?, ?)", (v_id, img_bytes, idx+1))
                                with open(os.path.join(pasta, f"grafico_{idx+1}.png"), "wb") as f_img: f_img.write(img_bytes)
                        conn.commit()
                        backup_local_para_nuvem_async()
                        st.success("Veículo inserido com sucesso!")
                        time.sleep(0.5); st.rerun()
        
        with col_mod2:
            if st.session_state.escolha_modelo:
                st.subheader(f"🔍 Parâmetros Técnicos: {st.session_state.escolha_modelo}")
                cursor.execute("SELECT id, posicao_inicio, intervalo, valores_invertidos, escala, detalhes FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (higienizar_nome(montadora_atual), higienizar_nome(st.session_state.escolha_modelo)))
                row = cursor.fetchone()
                
                if row:
                    dados_v = {"id": row[0], "posicao_inicio": row[1], "intervalo": row[2], "valores_invertidos": row[3], "escala": row[4], "detalhes": row[5]}
                    cursor.execute("SELECT foto FROM graficos WHERE veiculo_id = ? ORDER BY ordem", (row[0],))
                    dados_v['graficos'] = [f[0] for f in cursor.fetchall()]
                    
                    with st.container(border=True):
                        st.markdown(f"📌 **Posição Inicial na Memória:** `{dados_v['posicao_inicio']}`")
                        st.markdown(f"📏 **Intervalo do Bloco (Size):** `{dados_v['intervalo']}`")
                        st.markdown(f"⚖️ **Multiplicador de Escala:** `{dados_v['escala']}`")
                        st.markdown(f"🔄 **Leitura Invertida (Invert):** `{dados_v['valores_invertidos']}`")
                        st.write(f"📝 **Notas e Instruções de Bancada:**\n{dados_v['detalhes']}")
                    
                    if dados_v.get('graficos'):
                        st.markdown("#### 🖼️ Gráficos e Arquivos de Apoio Salvos")
                        g_cols = st.columns(2)
                        for g_idx, g_bytes in enumerate(dados_v['graficos']):
                            with g_cols[g_idx % 2]:
                                st.image(g_bytes, caption=f"Topologia Visual {g_idx+1}", use_container_width=True)
                                
                    if st.button("🗑️ Excluir Este Modelo da Base", type="primary", use_container_width=True):
                        cursor.execute("DELETE FROM veiculos WHERE id = ?", (dados_v['id'],))
                        conn.commit()
                        pasta = os.path.join(BASE_DIR, higienizar_nome(montadora_atual), higienizar_nome(st.session_state.escolha_modelo))
                        if os.path.exists(pasta): shutil.rmtree(pasta)
                        backup_local_para_nuvem_async()
                        st.session_state.escolha_modelo = ""; st.rerun()
                else: st.error("Erro interno ao ler arquivos estruturais deste veículo.")
            else: st.info("💡 Selecione um modelo da lista ao lado para expandir as posições de memória, mapas de injeção e fotos associadas.")

        st.markdown("---")
        if st.button("⬅️ Mudar de Montadora (Voltar)", type="secondary", use_container_width=True): 
            st.session_state.montadora_selecionada = ""
            st.session_state.escolha_modelo = ""
            st.rerun()