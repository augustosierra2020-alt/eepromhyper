import streamlit as st
import numpy as np
import plotly.graph_objects as go
import zlib
import pandas as pd
from typing import Tuple, List, Dict, Any
from datetime import datetime

# Importações da nossa arquitetura modular
from core.db import get_db_connection
from services.hf_sync import backup_local_para_nuvem_async

# Tenta importar o C++ para aceleração, caso exista
try:
    import hypertork_cpp
    HAS_CPP = True
except ImportError:
    HAS_CPP = False

MAX_DIFFS = 3000
GAP_THRESHOLD = 48

# ==========================================
# FUNÇÕES CORE: COMPARADOR HEX UNIFICADO
# ==========================================
def processar_bytes_para_valores(bytes_crus, bits=16, signed=False, endian='big'):
    if not bytes_crus: return np.array([])
    if bits == 8: dt = np.dtype('i1' if signed else 'u1')
    elif bits == 16: dt = np.dtype('>i2' if endian == 'big' and signed else ('>u2' if endian == 'big' else ('<i2' if signed else '<u2')))
    else: dt = np.dtype('>i4' if endian == 'big' and signed else ('>u4' if endian == 'big' else ('<i4' if signed else '<u4')))
    comprimento_valido = (len(bytes_crus) // dt.itemsize) * dt.itemsize
    return np.frombuffer(bytes_crus[:comprimento_valido], dtype=dt).astype(float)

def detectar_dimensao_mapa(valores_ori, valores_mod):
    tamanho_total = min(len(valores_ori), len(valores_mod))
    if tamanho_total < 8: return 1, max(1, tamanho_total)
    melhor_coluna = 16; menor_variancia = float('inf')
    larguras_possiveis = [4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 32]
    for colunas in larguras_possiveis:
        if tamanho_total >= colunas:
            linhas = tamanho_total // colunas
            elementos_validos = linhas * colunas
            if linhas < 2: continue
            matriz_teste = valores_ori[:elementos_validos].reshape((linhas, colunas))
            diff_x = np.diff(matriz_teste, axis=1); diff_y = np.diff(matriz_teste, axis=0)
            variancia_total = (np.sum(np.abs(diff_x)) + np.sum(np.abs(diff_y))) / elementos_validos
            if variancia_total < menor_variancia:
                menor_variancia = variancia_total; melhor_coluna = colunas
    linhas = tamanho_total // melhor_coluna
    if linhas == 0: return 1, tamanho_total
    return linhas, melhor_coluna

def comparar_arquivos_hex(file1_bytes: bytes, file2_bytes: bytes) -> Tuple[List[Dict[str, Any]], int, int]:
    len1, len2 = len(file1_bytes), len(file2_bytes)
    if HAS_CPP:
        try:
            res_cpp = hypertork_cpp.compare_hex_fast(file1_bytes, file2_bytes, MAX_DIFFS)
            diferencas = [{"EnderecoInt": item["EnderecoInt"], "Endereço": f"0x{item['EnderecoInt']:06X}", "Byte Original": f"{item['ByteOriginal']:02X}", "Byte Modificado": f"{item['ByteModificado']:02X}"} for item in res_cpp]
            return diferencas, len1, len2
        except Exception: pass 
    min_len = min(len1, len2)
    arr1 = np.frombuffer(file1_bytes[:min_len], dtype=np.uint8)
    arr2 = np.frombuffer(file2_bytes[:min_len], dtype=np.uint8)
    diff_indices = np.where(arr1 != arr2)[0][:MAX_DIFFS]
    diferencas = [{"EnderecoInt": int(i), "Endereço": f"0x{i:06X}", "Byte Original": f"{arr1[i]:02X}", "Byte Modificado": f"{arr2[i]:02X}"} for i in diff_indices]
    return diferencas, len1, len2

def obter_blocos_diferencas(diferencas):
    if not diferencas: return []
    blocos = []; bloco_atual = {"inicio": diferencas[0]["EnderecoInt"], "fim": diferencas[0]["EnderecoInt"], "qtd": 1}
    for diff in diferencas[1:]:
        addr = diff["EnderecoInt"]
        if (addr - bloco_atual["fim"]) <= GAP_THRESHOLD: 
            bloco_atual["fim"] = addr; bloco_atual["qtd"] += 1
        else:
            blocos.append(bloco_atual); bloco_atual = {"inicio": addr, "fim": addr, "qtd": 1}
    blocos.append(bloco_atual)
    return blocos

def obter_classificacao_heuristica(dados):
    has_mod, has_off = False, False
    for b in dados['blocos']:
        ini, fim = b['inicio'], b['fim']
        b_mod = list(dados['bytes_mod'][ini:fim+1])
        if len(b_mod) > 0:
            if b['qtd'] <= 8 or b_mod.count(0x00)/len(b_mod) >= 0.60 or b_mod.count(0xFF)/len(b_mod) >= 0.85: has_off = True
            else: has_mod = True
    if has_mod and has_off: return "STG 2"
    elif has_mod: return "MOD"
    elif has_off: return "OFF"
    return "Não Identificado"

def formatar_resumo_ia(blocos):
    resumo_ia = ""
    for i, b in enumerate(blocos[:30]): 
        tipo = "SWITCH ISOLADO (Potencial OFF)" if b["qtd"] <= 8 else "BLOCO/TABELA DE DADOS (Potencial Mapa)"
        resumo_ia += f"- Bloco {i+1}: 0x{b['inicio']:06X} até 0x{b['fim']:06X} ({b['qtd']} bytes) -> {tipo}\n"
    if len(blocos) > 30: resumo_ia += f"... e mais {len(blocos) - 30} blocos detectados.\n"
    return resumo_ia

def analisar_remap_com_ia(resumo_blocos, info_veiculo, classificacao):
    # Nota: A IA foi isolada no pop-up global conforme a arquitetura modular, 
    # mas mantemos a simulação local para o laudo rápido.
    return f"🛠️ **Análise Heurística Rápida:**\n\nVeículo: {info_veiculo}\nClassificação detectada: **{classificacao}**\n\nDetalhes de Modificação:\n{resumo_blocos}"

# --- BANCO DE DADOS HEX MODULARIZADO ---
def salvar_comparacao_hex_nuvem(veiculo, file_ori, file_mod, laudo, cv):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        ori_comp = zlib.compress(file_ori); mod_comp = zlib.compress(file_mod)
        data_formatada = datetime.now().strftime("%d/%m/%Y %H:%M")
        try: cursor.execute("ALTER TABLE hex_history ADD COLUMN cv_estimado INTEGER DEFAULT 0")
        except: pass
        cursor.execute("INSERT INTO hex_history (veiculo, data, file_ori, file_mod, laudo, cv_estimado) VALUES (?, ?, ?, ?, ?, ?)", (veiculo, data_formatada, ori_comp, mod_comp, laudo, int(cv)))
        conn.commit()
        backup_local_para_nuvem_async() # Chamada assíncrona modular
    except Exception as e:
        st.error(f"Erro ao persistir histórico hex: {e}")

def carregar_historico_hex_geral():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        try: cursor.execute("ALTER TABLE hex_history ADD COLUMN cv_estimado INTEGER DEFAULT 0")
        except: pass
        cursor.execute("SELECT id, veiculo, data, laudo, cv_estimado FROM hex_history ORDER BY id DESC LIMIT 50")
        return cursor.fetchall()
    except Exception: return []

def carregar_arquivos_hex_por_id(hist_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT file_ori, file_mod, veiculo, laudo, cv_estimado FROM hex_history WHERE id = ?", (hist_id,))
        res = cursor.fetchone()
        if res: return zlib.decompress(res[0]), zlib.decompress(res[1]), res[2], res[3], res[4]
    except Exception: pass
    return None, None, None, None, None


# ==========================================
# VIEW PRINCIPAL (RENDERIZADOR DA TELA)
# ==========================================
def render_hex_compare():
    hud_axis_style = dict(backgroundcolor="#121212", gridcolor="#333333", showbackground=True, zerolinecolor="#333333")
    
    # MODO FOCO 3D TELA CHEIA
    if st.session_state.get('focus_mode') == '3D' and st.session_state.get('hex_atual'):
        dados = st.session_state.hex_atual
        st.subheader("🔍 Modo Expandido Total - Mapa 3D")
        if st.button("❌ Sair do Modo Tela Cheia (Voltar ao Workspace)", type="primary", use_container_width=True):
            st.session_state.focus_mode = None
            st.rerun()
            
        bits_val = int(st.session_state.get('escala_op_saved', '16 bits').split()[0])
        b_step = bits_val // 8
        addr = st.session_state.get('view_addr_atual', 0)
        zoom = st.session_state.get('zoom_janela', 256)
        fator = st.session_state.get('fator_saved', 1.0)
        offset = st.session_state.get('offset_saved', 0.0)
        signed_op = st.session_state.get('signed_saved', False)
        endian_op = st.session_state.get('byteorder_saved', 'big')
        
        janela_bytes_tamanho = zoom * b_step
        addr_fim = min(len(dados['bytes_orig']), addr + janela_bytes_tamanho)

        valores_ori = (processar_bytes_para_valores(dados['bytes_orig'][addr:addr_fim], bits_val, signed_op, endian_op) * fator) + offset
        valores_mod = (processar_bytes_para_valores(dados['bytes_mod'][addr:addr_fim], bits_val, signed_op, endian_op) * fator) + offset
        
        linhas, colunas = detectar_dimensao_mapa(valores_ori, valores_mod)
        elementos_validos = linhas * colunas
        
        fig_3d = go.Figure()
        fig_3d.add_trace(go.Surface(z=valores_ori[:elementos_validos].reshape((linhas, colunas)), name='ORI', colorscale='Blues', opacity=0.5))
        fig_3d.add_trace(go.Surface(z=valores_mod[:elementos_validos].reshape((linhas, colunas)), name='MOD', colorscale='Reds', opacity=1.0))
        fig_3d.update_layout(height=850, margin=dict(l=0, r=0, b=0, t=20), paper_bgcolor='#121212', scene=dict(xaxis=hud_axis_style, yaxis=hud_axis_style, zaxis=hud_axis_style))
        st.plotly_chart(fig_3d, use_container_width=True)
        st.stop()

    st.title("🛠️ Estúdio Avançado de Calibração")
    
    aba_comp, aba_id = st.tabs(["⚖️ Comparação e Gráficos", "🔍 Identificador de Firmware (ECU ID)"])
    
    with aba_id:
        st.subheader("Validador Inteligente de Arquivo Único")
        fw_file = st.file_uploader("Suba o arquivo .bin ou .ori para leitura de Header:", key="fw_upload")
        if fw_file:
            try:
                from services.ecu_parser import parse_ecu_firmware
                info = parse_ecu_firmware(fw_file.read())
                st.json(info)
                st.success("Análise de metadados estruturais concluída.")
            except Exception as e:
                st.error(f"Erro no parser de ECU: {e}")
    
    with aba_comp:
        historico_global = carregar_historico_hex_geral()
        if historico_global:
            with st.expander("📚 Histórico Global de Consultas (Carregar Salvos na Nuvem)", expanded=not st.session_state.get('hex_atual')):
                for hist in historico_global:
                    h_id, h_veiculo, h_data, h_laudo, h_cv = hist
                    col_ha, col_hb = st.columns([4, 1])
                    col_ha.write(f"🕒 **{h_data}** | Veículo/ECU: {h_veiculo or 'N/A'}")
                    if col_hb.button("📂 Abrir Comparação", key=f"btn_load_{h_id}"):
                        with st.spinner("Descarregando da nuvem..."):
                            ori_b, mod_b, veic_b, laudo_b, cv_b = carregar_arquivos_hex_por_id(h_id)
                            if ori_b and mod_b:
                                diffs, len1, len2 = comparar_arquivos_hex(ori_b, mod_b)
                                blocos = obter_blocos_diferencas(diffs)
                                st.session_state.hex_atual = {
                                    "timestamp": h_data, "veiculo": veic_b, "len1": len1, "len2": len2, 
                                    "diffs": diffs, "blocos": blocos, "laudo": laudo_b, "bytes_orig": ori_b, 
                                    "bytes_mod": mod_b, "salvo_no_banco": True, "cv_estimado": cv_b
                                }
                                st.session_state.view_addr_atual = max(0, blocos[0]['inicio'] - 100) if blocos else 0
                                st.rerun()

        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1: arq_original = st.file_uploader("📂 Arquivo Original (.ori, .bin, .hex)", type=["bin", "hex", "ori", "mod", "dat"])
            with col2: arq_modificado = st.file_uploader("📂 Arquivo Modificado (.mod, .bin, .hex)", type=["bin", "hex", "ori", "mod", "dat"])
            info_veiculo = st.text_input("🚙 Qual o veículo/ECU?", placeholder="Ex: Bosch MD1CS001 / Siemens SID208")
            
            if st.button("🚀 Iniciar Engenharia Reversa", use_container_width=True, type="primary"):
                if arq_original and arq_modificado:
                    with st.spinner("Comparando matrizes binárias..."):
                        bytes_orig = arq_original.read()
                        bytes_mod = arq_modificado.read()
                        diffs, len1, len2 = comparar_arquivos_hex(bytes_orig, bytes_mod)
                        
                        if diffs:
                            blocos = obter_blocos_diferencas(diffs)
                            classificacao_exata = obter_classificacao_heuristica({"blocos": blocos, "bytes_mod": bytes_mod})
                            laudo_ia = analisar_remap_com_ia(formatar_resumo_ia(blocos), info_veiculo, classificacao_exata)
                            
                            # Copiloto Anti-Quebra
                            total_diffs = len(diffs)
                            if total_diffs > 1500: 
                                laudo_ia = "⚠️ **CRÍTICO - ALERTA DO CHIP:** Alteração massiva detectada no arquivo hex. Alto risco de corromper o checksum ou estourar limites térmicos da ECU.\n\n" + laudo_ia
                            
                            # Cálculo Dinâmico (Dino Virtual)
                            est_cv = min(75, int(total_diffs * 0.04) + 10) if diffs else 0
                            
                            st.session_state.hex_atual = {
                                "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"), "veiculo": info_veiculo, 
                                "len1": len1, "len2": len2, "diffs": diffs, "blocos": blocos, 
                                "laudo": laudo_ia, "bytes_orig": bytes_orig, "bytes_mod": bytes_mod,
                                "salvo_no_banco": False, "cv_estimado": est_cv
                            }
                            st.session_state.view_addr_atual = max(0, blocos[0]['inicio'] - 100) if blocos else 0
                            st.rerun() 
                else: st.error("Insira ambos os arquivos.")

        if st.session_state.get('hex_atual'):
            dados = st.session_state.hex_atual
            st.write("---")
            st.subheader(f"📊 Workspace de Calibração: {dados['veiculo'] or 'ECU Não Identificada'}")
            
            col_i1, col_i2, col_i3, col_i4 = st.columns(4)
            col_i1.metric("Tamanho Original", f"{dados['len1']} bytes")
            col_i2.metric("Tamanho Modificado", f"{dados['len2']} bytes")
            col_i3.metric("Modificações de Bytes", f"{len(dados['diffs'])}")
            col_i4.metric("Dino Virtual Estimado", f"+{dados.get('cv_estimado', 0)} cv")
            
            if not dados.get('salvo_no_banco', True):
                st.warning("⚠️ Engenharia Reversa concluída. Clique abaixo para registrar a análise no histórico global.")
                if st.button("💾 Gravar Análise permanentemente no Histórico", type="primary", use_container_width=True):
                    salvar_comparacao_hex_nuvem(dados['veiculo'], dados['bytes_orig'], dados['bytes_mod'], dados['laudo'], dados['cv_estimado'])
                    st.session_state.hex_atual['salvo_no_banco'] = True
                    st.success("✅ Salvo permanentemente com sucesso!")
                    st.rerun()
            
            st.info(dados['laudo'])
            
            # Controles Visuais Unificados
            st.markdown("### ⚙️ Painel de Engenharia (Conversão e Visualização Analítica)")
            
            addr_slider = st.slider("🖱️ Navegação Rápida de Endereços", 0, len(dados['bytes_orig']), value=int(st.session_state.get('view_addr_atual', 0)), step=1, format="0x%x")
            zoom_slider = st.slider("🔍 Largura da Janela (Zoom Base)", 64, 4096, value=int(st.session_state.get('zoom_janela', 256)), step=32)
            
            st.session_state.view_addr_atual = addr_slider
            st.session_state.zoom_janela = zoom_slider

            with st.expander("📊 Configurações Avançadas de Interpretação Matrix/Mapa", expanded=True):
                col_c1, col_c2, col_c3 = st.columns(3)
                escala_op = col_c1.selectbox("Formato de Bits:", ["8 bits", "16 bits", "32 bits"], index=1)
                byteorder_op = col_c2.selectbox("Endereçamento (Endian):", ["big", "little"], index=0)
                signed_op = col_c3.checkbox("Valores com Sinal (Signed)", value=False)
                
                col_c4, col_c5, col_c6 = st.columns(3)
                fator_op = col_c4.number_input("Fator de Multiplicação:", value=1.0, step=0.001, format="%.4f")
                offset_op = col_c5.number_input("Offset de Ajuste:", value=0.0, step=1.0)
                tipo_grafico_hex = col_c6.selectbox("Tipo de Visualização Gráfica:", ["Matriz 2D (Heatmap)", "Superfície 3D"])
                
            bits_val = int(escala_op.split()[0])
            b_step = bits_val // 8
            addr = st.session_state.view_addr_atual
            zoom = st.session_state.zoom_janela
            
            janela_bytes_tamanho = zoom * b_step
            addr_fim = min(len(dados['bytes_orig']), addr + janela_bytes_tamanho)

            valores_originais_mapa = (processar_bytes_para_valores(dados['bytes_orig'][addr:addr_fim], bits_val, signed_op, byteorder_op) * fator_op) + offset_op
            valores_modificados_mapa = (processar_bytes_para_valores(dados['bytes_mod'][addr:addr_fim], bits_val, signed_op, byteorder_op) * fator_op) + offset_op
            
            if len(valores_originais_mapa) > 0 and len(valores_modificados_mapa) > 0:
                linhas, colunas = detectar_dimensao_mapa(valores_originais_mapa, valores_modificados_mapa)
                elementos_validos = linhas * colunas
                matriz_ori = valores_originais_mapa[:elementos_validos].reshape((linhas, colunas))
                matriz_mod = valores_modificados_mapa[:elementos_validos].reshape((linhas, colunas))
                
                if tipo_grafico_hex == "Matriz 2D (Heatmap)":
                    fig_map = go.Figure(data=go.Heatmap(z=matriz_mod - matriz_ori, colorscale='RdBu', reversescale=True))
                    fig_map.update_layout(title="Diferencial de Calibração (MOD - ORI)", paper_bgcolor='#121212', plot_bgcolor='#121212', font=dict(color='white'))
                    st.plotly_chart(fig_map, use_container_width=True)
                else:
                    fig_map = go.Figure()
                    fig_map.add_trace(go.Surface(z=matriz_ori, name='Original (ORI)', colorscale='Blues', opacity=0.5, showscale=False))
                    fig_map.add_trace(go.Surface(z=matriz_mod, name='Modificado (MOD)', colorscale='Reds', opacity=0.9, showscale=False))
                    fig_map.update_layout(title="Topologia Tridimensional Comparativa", scene=dict(xaxis=hud_axis_style, yaxis=hud_axis_style, zaxis=hud_axis_style), paper_bgcolor='#121212', font=dict(color='white'), margin=dict(l=0, r=0, b=0, t=30))
                    st.plotly_chart(fig_map, use_container_width=True)
                    
                if st.button("🖥️ Expandir para Tela Cheia (Foco 3D)", use_container_width=True):
                    st.session_state.focus_mode = '3D'
                    st.session_state.escala_op_saved = escala_op
                    st.session_state.byteorder_saved = byteorder_op
                    st.session_state.signed_saved = signed_op
                    st.session_state.fator_saved = fator_op
                    st.session_state.offset_saved = offset_op
                    st.rerun()

            st.markdown("---")
            st.markdown("### 🔍 Detalhamento Técnico Completo (Tabela Hexadecimal)")
            df_diff = pd.DataFrame([{k: v for k, v in d.items() if k != "EnderecoInt"} for d in dados['diffs']])
            st.dataframe(df_diff, use_container_width=True, height=300)