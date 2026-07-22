import streamlit as st
import streamlit.components.v1 as components
import os
import base64
import json
import shutil
import unicodedata
import re
import time
from PIL import Image
import io

from core.db import get_db_connection
from services.hf_sync import backup_local_para_nuvem_async

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
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
            # Remove o padrão 'LOGO' do nome do arquivo para cruzar perfeitamente
            nome_arq = limpar_para_comparacao(os.path.splitext(arquivo)[0]).replace("LOGO", "")
            if mont_alvo == nome_arq or mont_alvo in nome_arq or nome_arq in mont_alvo: 
                return os.path.join(LOGOS_DIR, arquivo)
    return None

def renderizar_logo_harmonizada(caminho, montadora_nome=""):
    if not caminho or not os.path.exists(caminho): return False
    try:
        with open(caminho, "rb") as image_file: 
            encoded_string = base64.b64encode(image_file.read()).decode()
        st.markdown(f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 110px; width: 100%; background-color: #FFFFFF; border-radius: 12px; padding: 10px; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.05); margin-bottom: 10px;">
                <img src="data:image/png;base64,{encoded_string}" style="max-height: 90px; max-width: 100%; object-fit: contain; pointer-events: none; user-select: none; -webkit-user-drag: none;">
            </div>
        """, unsafe_allow_html=True)
        return True
    except: return False

def listar_montadoras():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT nome FROM montadoras")
        return sorted(list(set([higienizar_nome(r[0]) for r in cursor.fetchall()])))
    except Exception: return []
    finally: conn.close()

def listar_modelos(montadora):
    if not montadora: return []
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT modelo FROM veiculos WHERE montadora_nome = ?", (higienizar_nome(montadora),))
        return sorted(list(set([higienizar_nome(r[0]) for r in cursor.fetchall()])))
    except Exception: return []
    finally: conn.close()

def buscar_dados_veiculo_unificado(montadora, modelo):
    result = None
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, posicao_inicio, intervalo, valores_invertidos, escala, detalhes FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (higienizar_nome(montadora), higienizar_nome(modelo)))
        row = cursor.fetchone()
        if row:
            cursor.execute("SELECT foto FROM graficos WHERE veiculo_id = ? ORDER BY ordem", (row[0],))
            result = {"id": row[0], "posicao_inicio": row[1], "intervalo": row[2], "valores_invertidos": row[3], "escala": row[4], "detalhes": row[5], "graficos": [f[0] for f in cursor.fetchall()]}
    except Exception: pass
    finally: conn.close()
    return result

def salvar_novo_veiculo_hibrido(montadora, modelo, inicio, intervalo, info_extra, valores_invertidos, escala, imagens_upload=None):
    montadora = higienizar_nome(montadora); modelo = higienizar_nome(modelo)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO montadoras (nome) VALUES (?)", (montadora,))
        cursor.execute("INSERT OR REPLACE INTO veiculos (montadora_nome, modelo, posicao_inicio, intervalo, valores_invertidos, escala, detalhes) VALUES (?, ?, ?, ?, ?, ?, ?)", (montadora, modelo, inicio, intervalo, valores_invertidos, escala, info_extra))
        cursor.execute("SELECT id FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (montadora, modelo))
        v_id = cursor.fetchone()[0]
        
        pasta = os.path.join(BASE_DIR, montadora, modelo)
        os.makedirs(pasta, exist_ok=True)
        with open(os.path.join(pasta, "dados.json"), "w", encoding="utf-8") as f: 
            json.dump({"posicao_inicio": inicio, "intervalo": intervalo, "valores_invertidos": valores_invertidos, "escala": escala, "detalhes": info_extra}, f)
        
        if imagens_upload:
            cursor.execute("DELETE FROM graficos WHERE veiculo_id = ?", (v_id,))
            for idx, img_file in enumerate(imagens_upload[:6]):
                img_bytes = img_file.read()
                cursor.execute("INSERT INTO graficos (veiculo_id, foto, ordem) VALUES (?, ?, ?)", (v_id, img_bytes, idx+1))
                with open(os.path.join(pasta, f"grafico_{idx+1}.png"), "wb") as f_img: f_img.write(img_bytes)
        conn.commit()
        backup_local_para_nuvem_async()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar veículo: {e}")
        return False
    finally: conn.close()

def excluir_veiculo_db(montadora, modelo):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM veiculos WHERE montadora_nome = ? AND modelo = ?", (higienizar_nome(montadora), higienizar_nome(modelo)))
        conn.commit()
        pasta = os.path.join(BASE_DIR, higienizar_nome(montadora), higienizar_nome(modelo))
        if os.path.exists(pasta): shutil.rmtree(pasta)
        backup_local_para_nuvem_async()
    except Exception: pass
    finally: conn.close()

def excluir_montadora_db(montadora):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(); mont = higienizar_nome(montadora)
        cursor.execute("DELETE FROM veiculos WHERE montadora_nome = ?", (mont,)); 
        cursor.execute("DELETE FROM montadoras WHERE nome = ?", (mont,))
        conn.commit()
        if os.path.exists(os.path.join(BASE_DIR, mont)): shutil.rmtree(os.path.join(BASE_DIR, mont))
        backup_local_para_nuvem_async()
    except Exception: pass
    finally: conn.close()

def render_eeprom():
    if 'montadora_selecionada' not in st.session_state: st.session_state.montadora_selecionada = ""
    if 'escolha_modelo' not in st.session_state: st.session_state.escolha_modelo = ""

    montadoras_existentes = listar_montadoras()

    if st.session_state.montadora_selecionada == "":
        st.title("🚜 Painel de Controle - Mapas EEPROM")
        st.markdown("### Escolha a Montadora desejada para abrir os modelos")
        if not montadoras_existentes: 
            st.info("Nenhuma montadora cadastrada. Use o painel expansível abaixo para cadastrar a primeira!")
        else:
            for i in range(0, len(montadoras_existentes), 4):
                cols = st.columns(4)
                for j in range(4):
                    if i + j < len(montadoras_existentes):
                        m = montadoras_existentes[i + j]
                        with cols[j]:
                            with st.container(border=True):
                                caminho_logo = buscar_logo_montadora_automatica(m)
                                sucesso_imagem = renderizar_logo_harmonizada(caminho_logo, m)
                                if not sucesso_imagem:
                                    st.markdown(f"<div style='display: flex; justify-content: center; align-items: center; height: 110px; width: 100%; margin-bottom: 10px; background: linear-gradient(135deg, #1E88E5 0%, #0D47A1 100%); border-radius: 12px; border: 1px solid rgba(0,0,0,0.05);'><p style='text-align:center; font-weight:bold; color:#FFFFFF; margin:0; padding: 5px; font-size: 0.95rem;'>🏭 {m}</p></div>", unsafe_allow_html=True)
                                if st.button(f"{m}", key=f"home_{m}", use_container_width=True): 
                                    st.session_state.montadora_selecionada = m
                                    st.rerun()
    else:
        col_logo, col_nome = st.columns([1, 8])
        caminho_da_logo = buscar_logo_montadora_automatica(st.session_state.montadora_selecionada)
        with col_logo:
            if not caminho_da_logo or not os.path.exists(caminho_da_logo):
                st.subheader("🏭")
            else:
                try:
                    with open(caminho_da_logo, "rb") as image_file:
                        enc_side = base64.b64encode(image_file.read()).decode()
                    st.markdown(f'<img src="data:image/png;base64,{enc_side}" style="max-height: 50px; max-width: 100%; object-fit: contain; pointer-events: none; user-select: none; -webkit-user-drag: none;">', unsafe_allow_html=True)
                except Exception: st.subheader("🏭")
        with col_nome: 
            st.markdown(f"<h1 style='margin-top: 5px; color: #1E88E5; font-size: 2rem;'>{st.session_state.montadora_selecionada}</h1>", unsafe_allow_html=True)
        st.markdown("---")

        modelos_existentes = listar_modelos(st.session_state.montadora_selecionada)
        if not modelos_existentes: 
            st.warning(f"Nenhum veículo cadastrado para a montadora {st.session_state.montadora_selecionada}.")
        else:
            idx_veiculo = modelos_existentes.index(st.session_state.escolha_modelo) + 1 if st.session_state.escolha_modelo in modelos_existentes else 0
            escolha_modelo = st.selectbox("📂 Selecione o Veículo para carregar os gráficos:", [""] + modelos_existentes, index=idx_veiculo, key="modelo_selectbox_widget")
            
            if escolha_modelo:
                st.session_state.escolha_modelo = escolha_modelo
                st.markdown(f"#### 📍 Mapa: {st.session_state.montadora_selecionada} {escolha_modelo}")
                dados_mapa = buscar_dados_veiculo_unificado(st.session_state.montadora_selecionada, escolha_modelo)

                col_info, col_img = st.columns([1, 2])
                with col_info:
                    with st.container(border=True):
                        st.subheader("📋 Informações Gerais")
                        if dados_mapa:
                            st.write("**Início do Gráfico:**"); st.code(dados_mapa["posicao_inicio"], language="text")
                            st.write("**Intervalo de Endereços:**"); st.code(dados_mapa["intervalo"], language="text")
                            st.write("**Detalhes do Veículo:**"); st.info(dados_mapa["detalhes"])
                    with st.container(border=True):
                        st.markdown("⚙️ **Configuração de Mapa**")
                        if dados_mapa:
                            st.write(f"**Valores invertidos:** {dados_mapa.get('valores_invertidos', 'Desativado')}")
                            st.write(f"**Escala:** {dados_mapa.get('escala', '8 bits')}")
                            
                with col_img:
                    if not dados_mapa or not dados_mapa["graficos"]: 
                        st.error("⚠️ Nenhuma imagem de mapa encontrada.")
                    else:
                        st.caption("💡 *Clique no botão 'Ampliar Mapa' abaixo de cada imagem para explorar os gráficos em Engine Dinâmica!*")
                        lista_fotos = dados_mapa["graficos"]
                        
                        @st.dialog("🔍 Engine Visual de Alta Performance (HUD Ativo)", width="large")
                        def abrir_modal_zoom(foto_bytes, legenda_titulo):
                            st.markdown(f"### {legenda_titulo}")
                            b64_img = base64.b64encode(foto_bytes).decode()
                            html_code = f"""
                            <!DOCTYPE html><html><head><style>
                            body {{ margin: 0; overflow: hidden; background-color: #121212; display: flex; justify-content: center; align-items: center; height: 75vh; border-radius: 12px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
                            #container {{ width: 100%; height: 100%; position: relative; overflow: hidden; cursor: grab; background-image: radial-gradient(#333 1px, transparent 0); background-size: 20px 20px; }}
                            #container:active {{ cursor: grabbing; }}
                            img {{ position: absolute; transform-origin: 0 0; max-width: none; pointer-events: none; will-change: transform; transition: transform 0.05s linear; }}
                            .crosshair-x, .crosshair-y {{ position: absolute; background: rgba(30, 136, 229, 0.6); pointer-events: none; z-index: 10; display: none; }}
                            .crosshair-x {{ width: 100%; height: 1px; left: 0; }}
                            .crosshair-y {{ width: 1px; height: 100%; top: 0; }}
                            .hud {{ position: absolute; bottom: 20px; right: 20px; background: rgba(0, 0, 0, 0.7); padding: 10px 15px; border-radius: 8px; color: white; z-index: 20; border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(4px); display: flex; gap: 10px; align-items: center; }}
                            .hud-btn {{ background: transparent; border: 1px solid rgba(255,255,255,0.3); color: white; cursor: pointer; border-radius: 4px; padding: 5px 10px; font-weight: bold; transition: all 0.2s; }}
                            .hud-btn:hover {{ background: #1E88E5; border-color: #1E88E5; }}
                            .status-text {{ font-size: 12px; opacity: 0.8; margin-right: 10px; }}
                            </style></head><body>
                            <div id="container">
                                <div class="crosshair-x" id="cx"></div>
                                <div class="crosshair-y" id="cy"></div>
                                <img id="mapImage" src="data:image/png;base64,{b64_img}">
                                <div class="hud">
                                    <span class="status-text" id="zoomLevel">Zoom: 100%</span>
                                    <button class="hud-btn" onclick="zoom(1.2)">➕</button>
                                    <button class="hud-btn" onclick="zoom(0.8)">➖</button>
                                    <button class="hud-btn" onclick="centerImage()">🏠 Auto-Fit</button>
                                </div>
                            </div>
                            <script>
                            const container = document.getElementById('container'), img = document.getElementById('mapImage');
                            const cx = document.getElementById('cx'), cy = document.getElementById('cy');
                            const zoomText = document.getElementById('zoomLevel');
                            let scale = 1, pointX = 0, pointY = 0, startX = 0, startY = 0, panning = false;
                            let velocityX = 0, velocityY = 0, lastX = 0, lastY = 0, animationFrame;
                            function centerImage() {{
                                let minScale = Math.min(container.clientWidth / img.naturalWidth, container.clientHeight / img.naturalHeight);
                                scale = minScale < 1 ? minScale * 0.95 : 1;
                                pointX = (container.clientWidth - (img.naturalWidth * scale)) / 2; pointY = (container.clientHeight - (img.naturalHeight * scale)) / 2;
                                updateTransform();
                            }}
                            function updateTransform() {{
                                img.style.transform = `translate(${{pointX}}px, ${{pointY}}px) scale(${{scale}})`;
                                zoomText.innerText = `Zoom: ${{Math.round(scale * 100)}}%`;
                            }}
                            function zoom(factor) {{
                                let oldScale = scale;
                                scale *= factor;
                                if (scale < 0.1) scale = 0.1; if (scale > 30) scale = 30;
                                let centerX = container.clientWidth / 2;
                                let centerY = container.clientHeight / 2;
                                pointX = centerX - (centerX - pointX) * (scale / oldScale);
                                pointY = centerY - (centerY - pointY) * (scale / oldScale);
                                updateTransform();
                            }}
                            if(img.complete) centerImage(); else img.onload = centerImage;
                            container.onmousedown = e => {{ 
                                e.preventDefault(); 
                                startX = e.clientX - pointX; startY = e.clientY - pointY; 
                                lastX = e.clientX; lastY = e.clientY;
                                panning = true; 
                                cancelAnimationFrame(animationFrame);
                            }};
                            container.onmouseup = container.onmouseleave = (e) => {{
                                panning = false;
                                cx.style.display = 'none'; cy.style.display = 'none';
                            }};
                            container.onmousemove = e => {{
                                cx.style.display = 'block'; cy.style.display = 'block';
                                cx.style.top = e.clientY + 'px'; cy.style.left = e.clientX + 'px';
                                if (!panning) return; 
                                e.preventDefault(); 
                                pointX = e.clientX - startX; pointY = e.clientY - startY; 
                                velocityX = e.clientX - lastX; velocityY = e.clientY - lastY;
                                lastX = e.clientX; lastY = e.clientY;
                                updateTransform();
                            }};
                            container.onwheel = e => {{
                                e.preventDefault(); 
                                let xs = (e.clientX - pointX) / scale, ys = (e.clientY - pointY) / scale;
                                let delta = e.wheelDelta ? e.wheelDelta : -e.deltaY;
                                let oldScale = scale;
                                if (delta > 0) scale *= 1.15; else scale /= 1.15;
                                if (scale < 0.1) scale = 0.1; if (scale > 30) scale = 30;
                                pointX = e.clientX - xs * scale; pointY = e.clientY - ys * scale;
                                updateTransform();
                            }};
                            </script></body></html>
                            """
                            components.html(html_code, height=600)
                            if st.button("❌ Fechar Workspace", use_container_width=True, type="primary"):
                                st.rerun()

                        for idx in range(0, len(lista_fotos), 2):
                            sub_cols = st.columns(2)
                            with sub_cols[0]:
                                if idx < len(lista_fotos):
                                    try:
                                        img = Image.open(io.BytesIO(lista_fotos[idx]))
                                        st.image(img, use_container_width=True)
                                    except Exception: st.error("Falha ao abrir imagem.")
                                    if st.button(f"🔍 AMPLIAR MAPA {idx+1}", key=f"btn_zoom_{idx}", use_container_width=True):
                                        abrir_modal_zoom(lista_fotos[idx], f"Mapa {idx+1} | {st.session_state.montadora_selecionada} {escolha_modelo}")
                                        
                            with sub_cols[1]:
                                if idx + 1 < len(lista_fotos):
                                    try:
                                        img2 = Image.open(io.BytesIO(lista_fotos[idx+1]))
                                        st.image(img2, use_container_width=True)
                                    except Exception: st.error("Falha ao abrir imagem.")
                                    if st.button(f"🔍 AMPLIAR MAPA {idx+2}", key=f"btn_zoom_{idx+1}", use_container_width=True):
                                        abrir_modal_zoom(lista_fotos[idx+1], f"Mapa {idx+2} | {st.session_state.montadora_selecionada} {escolha_modelo}")

            st.markdown("---")
            if st.button("⬅️ Mudar de Montadora (Voltar)", type="secondary", use_container_width=True): 
                st.session_state.montadora_selecionada = ""
                st.session_state.escolha_modelo = ""
                st.rerun()

    with st.expander("➕ CADASTRAR: Adicionar Estruturas Independentes"):
        cad_tab1, cad_tab2 = st.tabs(["🏭 Cadastrar Montadora", "🚗 Cadastrar Veículo"])
        with cad_tab1:
            nova_m = st.text_input("Digite o Nome da Montadora", key="input_nova_m").strip()
            if st.button("Efetivar Montadora", type="primary"):
                if not nova_m: 
                    st.error("❌ O campo não pode ficar em branco!")
                else:
                    m_hig = higienizar_nome(nova_m)
                    if m_hig in montadoras_existentes: 
                        st.error("❌ Montadora já cadastrada!")
                    else:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO montadoras (nome) VALUES (?)", (m_hig,))
                        conn.commit()
                        os.makedirs(os.path.join(BASE_DIR, m_hig), exist_ok=True)
                        st.success("✅ Salva no cofre!"); st.rerun()
        with cad_tab2:
            if not montadoras_existentes: 
                st.info("Cadastre ao menos uma montadora primeiro.")
            else:
                m_form = st.selectbox("Selecione a Montadora Alvo", montadoras_existentes, key="sb_m_form")
                v_form = st.text_input("Nome do Modelo / Veículo", key="input_v_form").strip()
                vc1, vc2 = st.columns(2)
                v_ini = vc1.text_input("Endereço Inicial")
                v_int = vc2.text_input("Intervalo de Endereço")
                v_inv = st.selectbox("Valores Invertidos?", ["Desativado", "Ativado"])
                v_esc = st.selectbox("Escala do Mapa", ["8 bits", "16 bits", "32 bits"])
                v_det = st.text_area("Detalhes Adicionais")
                v_files = st.file_uploader("Fotos dos Gráficos (Máx 6)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
                if st.button("Efetivar Veículo", type="primary"):
                    if not v_form: 
                        st.error("❌ O nome é obrigatório!")
                    elif higienizar_nome(v_form) in listar_modelos(m_form): 
                        st.error("❌ Veículo já existe na marca!")
                    elif salvar_novo_veiculo_hibrido(m_form, v_form, v_ini, v_int, v_det, v_inv, v_esc, v_files): 
                        st.success("✅ Sincronizada!"); st.rerun()

    with st.expander("⚙️ GERENCIAR: Painel de Edição e Exclusão Total"):
        ger_tab1, ger_tab2 = st.tabs(["🏭 Gerenciar Montadoras", "🚗 Gerenciar Veículos"])
        with ger_tab1:
            if not montadoras_existentes:
                st.info("Nenhuma montadora cadastrada para gerenciar.")
            else:
                m_select_edit = st.selectbox("Escolha a Montadora para Alterar", montadoras_existentes, key="sb_m_edit_pane")
                novo_nome_m = st.text_input("Alterar Nome da Montadora para:", value=m_select_edit).strip()
                m_ed_col1, m_ed_col2 = st.columns(2)
                if m_ed_col1.button("💾 Salvar Novo Nome"):
                    n_m_hig = higienizar_nome(novo_nome_m)
                    if n_m_hig and (n_m_hig == m_select_edit or n_m_hig not in montadoras_existentes):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE montadoras SET nome = ? WHERE nome = ?", (n_m_hig, m_select_edit))
                        cursor.execute("UPDATE veiculos SET montadora_nome = ? WHERE montadora_nome = ?", (n_m_hig, m_select_edit))
                        conn.commit()
                        try: 
                            os.rename(os.path.join(BASE_DIR, m_select_edit), os.path.join(BASE_DIR, n_m_hig))
                        except Exception: pass
                        backup_local_para_nuvem_async()
                        st.success("✅ Atualizado!"); st.session_state.montadora_selecionada = ""; st.rerun()
                if m_ed_col2.button("🗑️ Excluir Montadora"): 
                    excluir_montadora_db(m_select_edit); st.session_state.montadora_selecionada = ""; st.rerun()
        with ger_tab2:
            if not montadoras_existentes:
                st.info("Nenhuma montadora cadastrada para gerenciar veículos.")
            else:
                m_sel_v = st.selectbox("Filtrar por Montadora", montadoras_existentes, key="sb_m_sel_v")
                v_existentes = listar_modelos(m_sel_v)
                if v_existentes:
                    v_sel_edit = st.selectbox("Selecione o Veículo", v_existentes)
                    dados_v = buscar_dados_veiculo_unificado(m_sel_v, v_sel_edit)
                    if dados_v:
                        v_novo_nome = st.text_input("Alterar Nome do Veículo", value=v_sel_edit).strip()
                        ve_c1, ve_c2 = st.columns(2)
                        v_novo_ini = ve_c1.text_input("Alterar Endereço Inicial", value=dados_v["posicao_inicio"])
                        v_novo_int = ve_c2.text_input("Alterar Intervalo", value=dados_v["intervalo"])
                        v_novo_det = st.text_area("Alterar Detalhes", value=dados_v["detalhes"])
                        v_novas_fotos = st.file_uploader("Substituir Imagens (Máx 6)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="files_v_edit")
                        v_manage_col1, v_manage_col2 = st.columns(2)
                        if v_manage_col1.button("💾 Salvar Alterações Veículo", type="primary"):
                            n_v_hig = higienizar_nome(v_novo_nome)
                            if n_v_hig:
                                if n_v_hig != v_sel_edit:
                                    try: shutil.rmtree(os.path.join(BASE_DIR, m_sel_v, v_sel_edit))
                                    except Exception: pass
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE veiculos SET modelo = ? WHERE id = ?", (n_v_hig, dados_v["id"]))
                                    conn.commit()
                                salvar_novo_veiculo_hibrido(m_sel_v, n_v_hig, v_novo_ini, v_novo_int, v_novo_det, dados_v["valores_invertidos"], dados_v["escala"], v_novas_fotos)
                                st.success("✅ Alterações salvas!"); st.rerun()
                        if v_manage_col2.button("🗑️ Excluir Veículo"): 
                            excluir_veiculo_db(m_sel_v, v_sel_edit); st.rerun()
                else:
                    st.info("Nenhum veículo cadastrado para esta montadora.")