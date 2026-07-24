import streamlit as st
import numpy as np
import plotly.graph_objects as go
import zlib
import pandas as pd
import re
import hashlib
from typing import Tuple, List, Dict, Any
from datetime import datetime

from core.db import get_db_connection
from services.hf_sync import backup_local_para_nuvem_async

try:
    import hypertork_cpp
    HAS_CPP = True
except ImportError:
    HAS_CPP = False

MAX_DIFFS = 3000
GAP_THRESHOLD = 48

# ==========================================
# 1. FUNÇÕES CORE: EXTRAÇÃO DIRETA DO BINÁRIO & RACE
# ==========================================
def extrair_metadados_binario(bytes_binario: bytes) -> dict:
    """
    Realiza varredura analítica no binário (.ORI/.MOD) para extrair 
    chassis (VIN), Part Numbers, família de ECU, Checksum MD5, Magic Bytes
    e faz consulta de modelo no Banco de Dados.
    """
    if not bytes_binario:
        return {}
    
    metadados = {}
    tam = len(bytes_binario)
    metadados["Tamanho Eprom"] = f"0x{tam:08X} ({tam / (1024*1024):.1f} MB)"
    metadados["Tamanho arquivo parcial"] = f"0x{tam:08X}"
    metadados["Endereço inicial do arquivo parcial"] = "0x00000000"
    
    # 1. Checksum MD5
    metadados["Checksum MD5"] = hashlib.md5(bytes_binario).hexdigest().upper()
    
    # 2. Magic Bytes
    header_bytes = bytes_binario[:16]
    metadados["Magic Bytes (Hex)"] = header_bytes[:4].hex().upper()
    
    if bytes_binario.startswith(b"\x01\xA3\xB5"):
        metadados["Fabricante"] = "BOSCH"
    elif bytes_binario.startswith(b"\xFF\x10\x20"):
        metadados["Fabricante"] = "MAGNETI MARELLI"
    elif b"DELCO" in header_bytes or b"GM" in header_bytes:
        metadados["Fabricante"] = "CHEVROLET / DELCO"

    strings_ascii = [s.decode('ascii', errors='ignore') for s in re.findall(b'[\x20-\x7E]{4,}', bytes_binario)]
    texto_completo = " ".join(strings_ascii)
    
    # 3. VIN / Chassis
    vins = re.findall(r'\b[1-9A-HJ-NPR-Z0-9]{17}\b', texto_completo)
    if vins:
        metadados["Chassis"] = vins[0]
        wmi = vins[0][:3]
        if wmi.startswith(("9BG", "3G", "1G")): metadados["Fabricante"] = "CHEVROLET US/EU/SAM"
        elif wmi.startswith(("9BD", "ZFA")): metadados["Fabricante"] = "FIAT"
        elif wmi.startswith(("9BW", "WV")): metadados["Fabricante"] = "VOLKSWAGEN"
        elif wmi.startswith(("9BF", "1FA")): metadados["Fabricante"] = "FORD"
        elif wmi.startswith(("93H", "JHM")): metadados["Fabricante"] = "HONDA"
        elif wmi.startswith(("9BR", "JT")): metadados["Fabricante"] = "TOYOTA"
        elif wmi.startswith(("93Y", "VF3", "VF7")): metadados["Fabricante"] = "PEUGEOT / CITROEN"
        elif wmi.startswith(("98R", "KN")): metadados["Fabricante"] = "HYUNDAI / KIA"
        elif wmi.startswith(("WBA", "WBS")): metadados["Fabricante"] = "BMW"
        elif wmi.startswith(("WDD", "WDB")): metadados["Fabricante"] = "MERCEDES-BENZ"
        elif wmi.startswith(("1C4", "1J4")): metadados["Fabricante"] = "JEEP / CHRYSLER"

    # 4. Part Numbers GM Delco
    pns_gm = list(dict.fromkeys(re.findall(r'\b(?:12|24|55|13|28|84|92)\d{6}\b', texto_completo)))
    if pns_gm:
        if len(pns_gm) >= 1: metadados["Software Nr."] = pns_gm[0]
        if len(pns_gm) >= 2: metadados["Hardware Nr."] = pns_gm[1]
        if len(pns_gm) >= 3: metadados["Software Upgrade Nr."] = pns_gm[2]
        if "Fabricante" not in metadados: metadados["Fabricante"] = "CHEVROLET US/EU/SAM"

    # 5. Números Bosch
    pns_bosch_sw = re.findall(r'\b1037\d{6}\b', texto_completo)
    pns_bosch_hw = re.findall(r'\b0281\d{6}\b|\b0261\d{6}\b', texto_completo)
    if pns_bosch_sw and "Software Nr." not in metadados:
        metadados["Software Nr."] = pns_bosch_sw[0]
        if "Fabricante" not in metadados: metadados["Fabricante"] = "BOSCH"
    if pns_bosch_hw and "Hardware Nr." not in metadados:
        metadados["Hardware Nr."] = pns_bosch_hw[0]

    # 6. Offsets Físicos Fixos
    if "Hardware Nr." not in metadados and len(bytes_binario) > 0x400:
        if metadados.get("Fabricante") == "BOSCH":
            hw_str = bytes_binario[0x200:0x20A].decode("ascii", errors="ignore").strip()
            sw_str = bytes_binario[0x300:0x30A].decode("ascii", errors="ignore").strip()
            if hw_str: metadados["Hardware Nr."] = hw_str
            if sw_str: metadados["Software Nr."] = sw_str
        elif metadados.get("Fabricante") == "MAGNETI MARELLI":
            hw_str = bytes_binario[0x150:0x158].decode("ascii", errors="ignore").strip()
            sw_str = bytes_binario[0x250:0x258].decode("ascii", errors="ignore").strip()
            if hw_str: metadados["Hardware Nr."] = hw_str
            if sw_str: metadados["Software Nr."] = sw_str

    # 7. Família da Central / Planta
    familias = re.findall(r'\b(E80|E39|E78|E38|E92|E83|EDC17\w*|MD1\w*|MG1\w*|SIMOS\d*|ME7\w*|IAW\w*)\b', texto_completo, re.IGNORECASE)
    if familias:
        planta = familias[0].upper()
        metadados["Tipo planta"] = planta
        if "E80" in planta or "E39" in planta or "E78" in planta:
            metadados["Protocolo"] = f"DELCO {planta} GEN2"
            if "Fabricante" not in metadados: metadados["Fabricante"] = "CHEVROLET US/EU/SAM"

    hw_vers = re.findall(r'\bR117\w+|\b[A-Z]\d{12,16}[Z0-9]\b', texto_completo)
    if hw_vers:
        metadados["Versão Hardware"] = hw_vers[0]

    metadados["Número de identificação único"] = f"{sum(bytes_binario[:1000]):04X}{len(bytes_binario):08X}"
    
    sw_id = metadados.get("Software Nr.")
    if sw_id and sw_id != "N/A":
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT veiculo FROM hex_history WHERE laudo LIKE ? LIMIT 1", (f"%{sw_id}%",))
            row = cursor.fetchone()
            if row and row[0]:
                metadados["Modelo"] = row[0]
        except Exception:
            pass

    return metadados

def processar_info_race(conteudo_texto: str) -> dict:
    metadados = {}
    linhas = conteudo_texto.splitlines()
    for linha in linhas:
        linha = linha.strip()
        if not linha: continue
        if "Parcial:" in linha and ":" in linha:
            partes = linha.split(":")
            if len(partes) >= 2: metadados["Tipo Leitura"] = partes[-1].strip()
            continue
        if ":" in linha:
            chave, valor = linha.split(":", 1)
            chave = chave.strip()
            valor = valor.strip()
            if valor: metadados[chave] = valor
    return metadados

def renderizar_aba_info_race(metadados: dict, imagem_bytes: bytes = None):
    if not metadados and not imagem_bytes:
        st.info("ℹ️ Carregue um arquivo .ORI, .TXT, .BIN, .HEX ou uma Imagem para visualizar os metadados da ECU.")
        return

    st.markdown("### 📋 Metadados e Informações do Arquivo ECU")
    
    if imagem_bytes:
        st.markdown("#### 🖼️ Imagem / Etiqueta da ECU Anexada")
        st.image(imagem_bytes, caption="Anexo da Leitura da ECU", use_container_width=True)
        st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Fabricante", metadados.get("Fabricante", "N/A"))
    with col2:
        st.metric("Modelo / Veículo", metadados.get("Modelo", metadados.get("Tipo", "N/A")))
    with col3:
        st.metric("Hardware ECU", metadados.get("Tipo planta", metadados.get("Hardware Nr.", "N/A")))

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        with st.container(border=True):
            st.markdown("#### ⚙️ Identificação do Software & Hardware")
            st.write(f"**Motor / Tipo:** `{metadados.get('Tipo', 'N/A')}`")
            st.write(f"**Protocolo:** `{metadados.get('Protocolo', 'N/A')}`")
            st.write(f"**Hardware Nr.:** `{metadados.get('Hardware Nr.', 'N/A')}`")
            st.write(f"**Software Nr.:** `{metadados.get('Software Nr.', 'N/A')}`")
            st.write(f"**Software Upgrade:** `{metadados.get('Software Upgrade Nr.', 'N/A')}`")
            st.write(f"**Versão Hardware:** `{metadados.get('Versão Hardware', 'N/A')}`")

    with col_b:
        with st.container(border=True):
            st.markdown("#### 🚗 Dados do Veículo & Leitura")
            st.write(f"**Chassi (VIN):** `{metadados.get('Chassis', 'N/A')}`")
            st.write(f"**Checksum MD5:** `{metadados.get('Checksum MD5', 'N/A')}`")
            st.write(f"**Magic Bytes:** `{metadados.get('Magic Bytes (Hex)', 'N/A')}`")
            st.write(f"**Data da Leitura:** `{metadados.get('Data arquivo', datetime.now().strftime('%d/%m/%Y'))}`")
            st.write(f"**ID Único:** `{metadados.get('Número de identificação único', 'N/A')}`")

    with st.expander("🔍 Detalhes do Arquivo Parcial / Eprom"):
        st.write(f"**Endereço Inicial:** `{metadados.get('Endereço inicial do arquivo parcial', '0x00000000')}`")
        st.write(f"**Tamanho Parcial:** `{metadados.get('Tamanho arquivo parcial', 'N/A')}`")
        st.write(f"**Tamanho Eprom:** `{metadados.get('Tamanho Eprom', 'N/A')}`")

# ==========================================
# 2. FUNÇÕES CORE: ENGENHARIA REVERSA 
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
    return None

def formatar_resumo_ia(blocos):
    resumo_ia = ""
    for i, b in enumerate(blocos[:30]): 
        tipo = "SWITCH ISOLADO (Potencial OFF)" if b["qtd"] <= 8 else "BLOCO/TABELA DE DADOS (Potencial Mapa)"
        resumo_ia += f"- Bloco {i+1}: 0x{b['inicio']:06X} até 0x{b['fim']:06X} ({b['qtd']} bytes) -> {tipo}\n"
    if len(blocos) > 30: resumo_ia += f"... e mais {len(blocos) - 30} blocos detectados.\n"
    return resumo_ia

def analisar_remap_com_ia(resumo_blocos, info_veiculo, classificacao):
    linha_classif = f"\nAssinatura do Firmware / Classificação: **{classificacao}**" if classificacao in ["MOD", "OFF", "STG 2", "STAGE 2"] else ""
    return f"🛠️ **Laudo Técnico Preliminar de Calibração (Chip Engine):**\n\nIdentificação da ECU: {info_veiculo}{linha_classif}\n\nEstrutura Topológica das Modificações:\n{resumo_blocos}"

def obter_checksum_arquivo(dados_bytes):
    if not dados_bytes: return 0
    return sum(np.frombuffer(dados_bytes, dtype=np.uint8)) & 0xFF

def salvar_comparacao_hex_nuvem(veiculo, file_ori, file_mod, laudo):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        ori_comp = zlib.compress(file_ori); mod_comp = zlib.compress(file_mod)
        data_formatada = datetime.now().strftime("%d/%m/%Y %H:%M")
        cursor.execute("INSERT INTO hex_history (veiculo, data, file_ori, file_mod, laudo) VALUES (?, ?, ?, ?, ?)", (veiculo, data_formatada, ori_comp, mod_comp, laudo))
        conn.commit()
        backup_local_para_nuvem_async()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def carregar_historico_hex_geral():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, veiculo, data, laudo FROM hex_history ORDER BY id DESC LIMIT 50")
        return cursor.fetchall()
    except Exception: return []

def carregar_arquivos_hex_por_id(hist_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT file_ori, file_mod, veiculo, laudo FROM hex_history WHERE id = ?", (hist_id,))
        res = cursor.fetchone()
        if res: return zlib.decompress(res[0]), zlib.decompress(res[1]), res[2], res[3]
    except Exception: pass
    return None, None, None, None

# ==========================================
# 3. RENDERIZAÇÃO DA VIEW PRINCIPAL
# ==========================================
def render_hex_compare():
    if "zoom_janela" not in st.session_state: st.session_state.zoom_janela = 256
    if "view_addr_atual" not in st.session_state: st.session_state.view_addr_atual = 0

    # MODO TELA CHEIA 2D
    if st.session_state.get('focus_mode') == '2D' and st.session_state.get('hex_atual'):
        dados = st.session_state.hex_atual
        st.title("🔍 Modo Expandido Total - Mapa 2D")
        if st.button("❌ Sair do Modo Tela Cheia (Voltar ao Workspace)", type="primary", use_container_width=True):
            st.session_state.focus_mode = None
            st.rerun()
            
        bits_val = int(st.session_state.get('escala_op_saved', '16 bits').split()[0])
        b_step = bits_val // 8
        byteorder_str = st.session_state.get('byteorder_saved', 'big')
        is_signed = st.session_state.get('signed_saved', False)
        inverter_val = st.session_state.get('inverter_saved', False)
        
        tamanho_total_arquivo = len(dados['bytes_orig'])
        janela_pontos = st.session_state.zoom_janela
        janela_bytes_tamanho = janela_pontos * b_step
        addr_inicio = st.session_state.view_addr_atual
        addr_fim = min(tamanho_total_arquivo, addr_inicio + janela_bytes_tamanho)

        bytes_janela_ori = dados['bytes_orig'][addr_inicio:addr_fim]
        bytes_janela_mod = dados['bytes_mod'][addr_inicio:addr_fim]

        ori_y = processar_bytes_para_valores(bytes_janela_ori, bits_val, is_signed, byteorder_str)
        mod_y = processar_bytes_para_valores(bytes_janela_mod, bits_val, is_signed, byteorder_str)
        
        if inverter_val:
            max_v = (2**bits_val) - 1
            ori_y = max_v - ori_y
            mod_y = max_v - mod_y
            
        eixo_x = np.arange(addr_inicio, addr_inicio + len(ori_y) * b_step, b_step)
        
        fig_2d_fs = go.Figure()
        fig_2d_fs.add_trace(go.Scatter(x=eixo_x, y=ori_y[:len(eixo_x)], mode='lines', name='Original (ORI)', line=dict(color='#1E88E5', width=2)))
        fig_2d_fs.add_trace(go.Scatter(x=eixo_x, y=mod_y[:len(eixo_x)], mode='lines', name='Modificado (MOD)', line=dict(color='#FF0000', width=2)))

        fig_2d_fs.update_layout(
            height=800, paper_bgcolor='#121212', plot_bgcolor='#121212', font=dict(color='white'), dragmode='pan', hovermode='closest',
            xaxis=dict(title="Endereço Hexadecimal", tickformat="06X", tickprefix="0x", showspikes=True, spikecolor="#9C27B0", spikesnap="cursor", spikemode="across"),
            yaxis=dict(title="Valor Convertido", fixedrange=False, showspikes=True, spikecolor="#9C27B0", spikesnap="cursor", spikemode="across"),
            margin=dict(l=20, r=20, b=20, t=30), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_2d_fs, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
        st.stop()

    # MODO TELA CHEIA 3D
    if st.session_state.get('focus_mode') == '3D' and st.session_state.get('hex_atual'):
        dados = st.session_state.hex_atual
        st.title("📐 Modo Expandido Total - Mapa 3D")
        if st.button("❌ Sair do Modo Tela Cheia (Voltar ao Workspace)", type="primary", use_container_width=True):
            st.session_state.focus_mode = None
            st.rerun()
            
        bits_val = int(st.session_state.get('escala_op_saved', '16 bits').split()[0])
        b_step = bits_val // 8
        byteorder_str = st.session_state.get('byteorder_saved', 'big')
        is_signed = st.session_state.get('signed_saved', False)
        fator = st.session_state.get('fator_saved', 1.0)
        offset = st.session_state.get('offset_saved', 0.0)
        modo_exibicao = st.session_state.get('modo_exibicao_saved', 'Valores Absolutos Convertidos')
        inverter_val = st.session_state.get('inverter_saved', False)
        
        janela_bytes_tamanho = st.session_state.zoom_janela * b_step
        addr_inicio = st.session_state.view_addr_atual
        addr_fim = min(len(dados['bytes_orig']), addr_inicio + janela_bytes_tamanho)

        bytes_janela_ori = dados['bytes_orig'][addr_inicio:addr_fim]
        bytes_janela_mod = dados['bytes_mod'][addr_inicio:addr_fim]
        valores_ori_brutos = processar_bytes_para_valores(bytes_janela_ori, bits_val, is_signed, byteorder_str)
        valores_mod_brutos = processar_bytes_para_valores(bytes_janela_mod, bits_val, is_signed, byteorder_str)
        linhas, colunas = detectar_dimensao_mapa(valores_ori_brutos, valores_mod_brutos)
        total_elementos = linhas * colunas
        valores_ori_eng = (valores_ori_brutos[:total_elementos] * fator) + offset
        valores_mod_eng = (valores_mod_brutos[:total_elementos] * fator) + offset
        
        with np.errstate(divide='ignore', invalid='ignore'):
            valores_delta_pct = np.where(valores_ori_eng != 0, ((valores_mod_eng - valores_ori_eng) / np.abs(valores_ori_eng)) * 100.0, 0.0)
            valores_delta_pct = np.nan_to_num(valores_delta_pct)

        matriz_ori_eng = valores_ori_eng.reshape((linhas, colunas))
        matriz_mod_eng = valores_mod_eng.reshape((linhas, colunas))
        matriz_delta_pct = valores_delta_pct.reshape((linhas, colunas))
        
        fig_3d = go.Figure()
        z_dir = "reversed" if inverter_val else True
        if "Percentual" in modo_exibicao:
            fig_3d.add_trace(go.Surface(z=matriz_delta_pct, name='Delta %', colorscale='Viridis'))
        else:
            fig_3d.add_trace(go.Surface(z=matriz_ori_eng, name='ORI', colorscale='Blues', opacity=0.5, showscale=False))
            fig_3d.add_trace(go.Surface(z=matriz_mod_eng, name='MOD', colorscale='Reds', opacity=1.0))
        
        fig_3d.update_layout(
            height=850, margin=dict(l=0, r=0, b=0, t=20), paper_bgcolor='#121212', plot_bgcolor='#121212', font=dict(color='white'), 
            scene=dict(zaxis=dict(autorange=z_dir), camera=dict(eye=dict(x=1.6, y=1.6, z=1.3)))
        )
        st.plotly_chart(fig_3d, use_container_width=True, config={'displayModeBar': True, 'scrollZoom': True, 'displaylogo': False})
        st.stop()

    # WORKSPACE PRINCIPAL
    st.title("🛠️ Estúdio Avançado de Calibração")
    st.markdown("Engine unificada de alta performance com análise geométrica 3D, leitura direta de metadados ECU e grade térmica.")

    historico_global = carregar_historico_hex_geral()
    if historico_global:
        with st.expander("📚 Histórico Global de Comparações (Nuvem)", expanded=not st.session_state.get('hex_atual')):
            for hist in historico_global:
                h_id, h_veiculo, h_data, h_laudo = hist
                col_ha, col_hb = st.columns([4, 1])
                col_ha.write(f"🕒 **{h_data}** | Veículo/ECU: {h_veiculo or 'N/A'}")
                if col_hb.button("📂 Abrir Comparação", key=f"btn_load_{h_id}"):
                    with st.spinner("Descarregando..."):
                        ori_b, mod_b, veic_b, laudo_b = carregar_arquivos_hex_por_id(h_id)
                        if ori_b and mod_b:
                            diffs, len1, len2 = comparar_arquivos_hex(ori_b, mod_b)
                            blocos = obter_blocos_diferencas(diffs)
                            metadados_auto = extrair_metadados_binario(ori_b)
                            st.session_state.hex_atual = {"timestamp": h_data, "veiculo": veic_b, "len1": len1, "len2": len2, "diffs": diffs, "blocos": blocos, "laudo": laudo_b, "bytes_orig": ori_b, "bytes_mod": mod_b, "salvo": True, "metadados_race": metadados_auto, "imagem_race": None}
                            st.session_state.view_addr_atual = max(0, blocos[0]['inicio'] - 100) if blocos else 0
                            st.rerun()

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1: arq_original = st.file_uploader("📂 Arquivo Original (.ori, .bin, .hex)", type=["bin", "hex", "ori", "mod", "dat"])
        with col2: arq_modificado = st.file_uploader("📂 Arquivo Modificado (.mod, .bin, .hex)", type=["bin", "hex", "ori", "mod", "dat"])
        
        with col3: arq_race_txt = st.file_uploader("📋 Info Race / Anexo (txt, hex, bin, ori, imagem)", type=["txt", "hex", "bin", "ori", "png", "jpg", "jpeg", "bmp", "webp"], key="arq_race_anexo")
        
        info_veiculo = st.text_input("🚙 Identificação/Modelo da ECU (Opcional)", placeholder="Ex: Chevrolet S10 2.5 Flex Delco E80")
        
        if st.button("🚀 Iniciar Engenharia Reversa", use_container_width=True, type="primary"):
            if arq_original and arq_modificado:
                with st.spinner("Analisando matrizes e extraindo metadados da ECU..."):
                    bytes_orig = arq_original.read()
                    bytes_mod = arq_modificado.read()
                    
                    metadados_finais = extrair_metadados_binario(bytes_orig)
                    
                    imagem_anexo_bytes = None
                    if arq_race_txt:
                        nome_ext = arq_race_txt.name.lower()
                        conteudo_anexo = arq_race_txt.read()
                        
                        if any(nome_ext.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]):
                            imagem_anexo_bytes = conteudo_anexo
                        else:
                            meta_bin_extra = extrair_metadados_binario(conteudo_anexo)
                            metadados_finais.update(meta_bin_extra)
                            
                            try:
                                str_txt = conteudo_anexo.decode("utf-8", errors="ignore")
                                metadados_txt = processar_info_race(str_txt)
                                metadados_finais.update(metadados_txt)
                            except Exception: pass
                        
                    nome_veiculo_final = info_veiculo
                    if not nome_veiculo_final:
                        fab = metadados_finais.get('Fabricante', '')
                        mod = metadados_finais.get('Modelo', metadados_finais.get('Tipo planta', 'ECU'))
                        nome_veiculo_final = f"{fab} {mod}".strip() if fab or mod else "ECU Não Identificada"

                    diffs, len1, len2 = comparar_arquivos_hex(bytes_orig, bytes_mod)
                    if diffs:
                        blocos_encontrados = obter_blocos_diferencas(diffs)
                        temp_dados = {"blocos": blocos_encontrados, "bytes_mod": bytes_mod}
                        classificacao_exata = obter_classificacao_heuristica(temp_dados)
                        laudo_ia = analisar_remap_com_ia(formatar_resumo_ia(blocos_encontrados), nome_veiculo_final, classificacao_exata)
                        
                        st.session_state.hex_atual = {
                            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"), 
                            "veiculo": nome_veiculo_final, 
                            "len1": len1, 
                            "len2": len2, 
                            "diffs": diffs, 
                            "blocos": blocos_encontrados, 
                            "laudo": laudo_ia, 
                            "bytes_orig": bytes_orig, 
                            "bytes_mod": bytes_mod, 
                            "salvo": False,
                            "metadados_race": metadados_finais,
                            "imagem_race": imagem_anexo_bytes
                        }
                        st.session_state.view_addr_atual = max(0, blocos_encontrados[0]['inicio'] - 100) if blocos_encontrados else 0
                        st.rerun() 
            else: st.error("Insira ao menos os arquivos Original e Modificado.")

    if st.session_state.get('hex_atual'):
        dados = st.session_state.hex_atual
        st.write("---")
        
        expandir_graficos = st.toggle("🔲 Ativar Modo Ampliado no Painel (Gráficos Longos)", value=False)
        altura_dinamica = 800 if expandir_graficos else 450
        
        st.subheader(f"📊 Workspace de Calibração: {dados['veiculo']}")
        
        col_i1, col_i2, col_i3, col_i4 = st.columns(4)
        col_i1.metric("Tamanho Original", f"{dados['len1']} bytes")
        col_i2.metric("Tamanho Modificado", f"{dados['len2']} bytes")
        col_i3.metric("Modificações de Bytes", f"{len(dados['diffs'])}")
        csum_mod = obter_checksum_arquivo(dados['bytes_mod'])
        col_i4.metric("Checksum Modificado", f"0x{csum_mod:02X}")
        st.info(dados['laudo'])

        if not dados.get('salvo', True):
            if st.button("💾 Gravar Análise permanentemente no Histórico", type="primary", use_container_width=True):
                salvar_comparacao_hex_nuvem(dados['veiculo'], dados['bytes_orig'], dados['bytes_mod'], dados['laudo'])
                st.session_state.hex_atual['salvo'] = True
                st.success("✅ Salvo permanentemente com sucesso!"); st.rerun()
        
        st.markdown("### ⚙️ Painel de Engenharia (Conversão e Visualização Analítica)")
        
        c_conf1, c_conf2, c_conf3, c_conf4 = st.columns(4)
        escala_op = c_conf1.selectbox("📏 Resolução da ECU", ["8 bits", "16 bits", "32 bits"], index=1)
        st.session_state.escala_op_saved = escala_op
        
        bits_val = int(escala_op.split()[0]); b_step = bits_val // 8
        byteorder_str = 'big' if "Big" in c_conf2.selectbox("🔄 Endianness", ["Big Endian (Motorola)", "Little Endian (Intel)"]) else 'little'
        st.session_state.byteorder_saved = byteorder_str
        
        is_signed = "Signed" in c_conf3.selectbox("📉 Arquitetura Numérica", ["Unsigned (Sem Sinal)", "Signed (Com Sinal)"])
        st.session_state.signed_saved = is_signed
        
        inverter_val = c_conf4.toggle("Inverter Z-Axis (3D)", value=False)
        st.session_state.inverter_saved = inverter_val

        c_an1, c_an2, c_an3 = st.columns([1, 1, 2])
        fator = c_an1.number_input("✖️ Fator de Conversão", value=1.0, step=0.001, format="%.4f")
        st.session_state.fator_saved = fator
        offset = c_an2.number_input("➕ Offset Base", value=0.0, step=1.0)
        st.session_state.offset_saved = offset
        modo_exibicao = c_an3.radio("📊 Modo de Leitura", ["Valores Absolutos Convertidos", "Diferença Percentual Absoluta (%)"], horizontal=True)
        st.session_state.modo_exibicao_saved = modo_exibicao

        opcoes_blocos = ["--- Selecione um Bloco para Saltar ---"]
        for i, b in enumerate(dados['blocos']):
            ini, fim, qtd = b['inicio'], b['fim'], b['qtd']
            b_mod = dados['bytes_mod'][ini:fim+1]
            t_real = len(b_mod)
            if t_real > 0:
                zero_ratio = b_mod.count(0x00) / t_real
                ff_ratio = b_mod.count(0xFF) / t_real
                tipo_label = "OFF (DPF/EGR/DTC)" if (b['qtd'] <= 8 or zero_ratio >= 0.60 or ff_ratio >= 0.85) else "MOD (Remap)"
            else: tipo_label = "Dados Desconhecidos"
            opcoes_blocos.append(f"Bloco {i+1}: 0x{ini:06X} até 0x{fim:06X} ({qtd}b) -> {tipo_label}")

        def atualizar_por_bloco():
            sel = st.session_state.select_block_busca
            if "Bloco" in sel:
                match = re.search(r'0x([0-9A-Fa-f]+)', sel)
                if match: st.session_state.view_addr_atual = max(0, int(match.group(1), 16) - (20 * b_step)) 

        def ir_para_endereco():
            val = st.session_state.goto_input
            if val:
                try: st.session_state.view_addr_atual = int(val, 16)
                except ValueError: pass

        col_nav1, col_nav2 = st.columns([2, 1])
        with col_nav1: st.selectbox("⚡ Saltos Estratégicos (Indexador de Mapas)", opcoes_blocos, key="select_block_busca", on_change=atualizar_por_bloco)
        with col_nav2: st.text_input("🔍 Ir para Endereço (Hex GOTO)", placeholder="Ex: 1C4A00", key="goto_input", on_change=ir_para_endereco)

        st.markdown("---")
        
        tamanho_total_arquivo = len(dados['bytes_orig'])
        janela_pontos = st.session_state.zoom_janela
        max_addr_possivel = max(1, tamanho_total_arquivo - (janela_pontos * b_step))
        if st.session_state.view_addr_atual > max_addr_possivel: st.session_state.view_addr_atual = max_addr_possivel

        janela_bytes_tamanho = janela_pontos * b_step
        addr_inicio = st.session_state.view_addr_atual
        addr_fim = min(tamanho_total_arquivo, addr_inicio + janela_bytes_tamanho)

        bytes_janela_ori = dados['bytes_orig'][addr_inicio:addr_fim]
        bytes_janela_mod = dados['bytes_mod'][addr_inicio:addr_fim]

        valores_ori_brutos = processar_bytes_para_valores(bytes_janela_ori, bits_val, is_signed, byteorder_str)
        valores_mod_brutos = processar_bytes_para_valores(bytes_janela_mod, bits_val, is_signed, byteorder_str)

        linhas, colunas = detectar_dimensao_mapa(valores_ori_brutos, valores_mod_brutos)
        total_elementos = linhas * colunas

        valores_ori_brutos = valores_ori_brutos[:total_elementos]
        valores_mod_brutos = valores_mod_brutos[:total_elementos]

        valores_ori_eng = (valores_ori_brutos * fator) + offset
        valores_mod_eng = (valores_mod_brutos * fator) + offset
        
        with np.errstate(divide='ignore', invalid='ignore'):
            valores_delta_pct = np.where(valores_ori_eng != 0, ((valores_mod_eng - valores_ori_eng) / np.abs(valores_ori_eng)) * 100.0, 0.0)
            valores_delta_pct = np.nan_to_num(valores_delta_pct)

        matriz_ori_eng = valores_ori_eng.reshape((linhas, colunas))
        matriz_mod_eng = valores_mod_eng.reshape((linhas, colunas))
        matriz_delta_pct = valores_delta_pct.reshape((linhas, colunas))

        tab_2d, tab_3d, tab_grid, tab_race_info = st.tabs([
            "📈 Gráfico 2D (Contínuo com Minimapa)", 
            "📐 Superfície 3D (Topografia)", 
            "🧮 Grade Térmica (Hex Dump)",
            "ℹ️ Metadados ECU (Leitura Direta)"
        ])

        with tab_2d:
            st.slider("🖱️ Navegação Rápida (Barra de Rolagem de Endereços)", 0, max_addr_possivel, key="view_addr_atual", step=1, format="0x%x")
            st.slider("🔍 Largura da Janela (Zoom Base)", min_value=64, max_value=4096, step=32, key="zoom_janela")

            MACRO_WINDOW_POINTS = 16384 
            macro_start = max(0, st.session_state.view_addr_atual - (MACRO_WINDOW_POINTS // 4) * b_step)
            macro_end = min(tamanho_total_arquivo, macro_start + MACRO_WINDOW_POINTS * b_step)
            
            bytes_macro_ori = dados['bytes_orig'][macro_start:macro_end]
            bytes_macro_mod = dados['bytes_mod'][macro_start:macro_end]
            
            ori_y_macro = processar_bytes_para_valores(bytes_macro_ori, bits_val, is_signed, byteorder_str)
            mod_y_macro = processar_bytes_para_valores(bytes_macro_mod, bits_val, is_signed, byteorder_str)
            
            valid_len_ori = (len(bytes_macro_ori) // b_step) * b_step
            valid_len_mod = (len(bytes_macro_mod) // b_step) * b_step
            min_valid_len = min(valid_len_ori, valid_len_mod)
            
            if inverter_val:
                max_v = (2**bits_val) - 1
                ori_y_macro = max_v - ori_y_macro
                mod_y_macro = max_v - mod_y_macro
                
            eixo_x_macro = np.arange(macro_start, macro_start + min_valid_len, b_step)
            ori_y_macro = ori_y_macro[:len(eixo_x_macro)]
            mod_y_macro = mod_y_macro[:len(eixo_x_macro)]
            
            fig_2d = go.Figure()
            fig_2d.add_trace(go.Scatter(x=eixo_x_macro, y=ori_y_macro, mode='lines', name='Original (ORI)', line=dict(color='#1E88E5', width=1.5, simplify=True)))
            fig_2d.add_trace(go.Scatter(x=eixo_x_macro, y=mod_y_macro, mode='lines', name='Modificado (MOD)', line=dict(color='#FF0000', width=1.5, simplify=True)))

            x_zoom_start = st.session_state.view_addr_atual
            x_zoom_end = st.session_state.view_addr_atual + (janela_pontos * b_step)

            fig_2d.update_layout(
                height=altura_dinamica, paper_bgcolor='#1E1E1E', plot_bgcolor='#1E1E1E', font=dict(color='white'), dragmode='pan', hovermode='closest',   
                xaxis=dict(
                    title="Endereço Hexadecimal", tickformat="06X", tickprefix="0x", range=[x_zoom_start, x_zoom_end], 
                    showspikes=True, spikecolor="#9C27B0", spikesnap="cursor", spikemode="across", spikethickness=1, spikedash="dot", 
                    rangeslider=dict(visible=True, bgcolor='rgba(156, 39, 176, 0.15)', bordercolor='#9C27B0', borderwidth=2)
                ),
                yaxis=dict(title="Valor", fixedrange=False, showspikes=True, spikecolor="#9C27B0", spikesnap="cursor", spikemode="across", spikethickness=1, spikedash="dot"),
                margin=dict(l=10, r=10, b=10, t=30), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_2d, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
            
            if st.button("🔍 Expandir Gráfico 2D em Tela Cheia", key="btn_fs_2d", use_container_width=True):
                st.session_state.focus_mode = '2D'
                st.rerun()

        with tab_3d:
            st.caption(f"📐 Geometria do mapa detectada: Matriz de **{linhas} linhas** x **{colunas} colunas**")
            fig_3d_aba = go.Figure()
            z_dir = "reversed" if inverter_val else True
            if "Percentual" in modo_exibicao:
                fig_3d_aba.add_trace(go.Surface(z=matriz_delta_pct, name='Delta %', colorscale='Viridis', showscale=True))
            else:
                fig_3d_aba.add_trace(go.Surface(z=matriz_ori_eng, name='ORI Base', colorscale='Blues', opacity=0.5, showscale=False))
                fig_3d_aba.add_trace(go.Surface(z=matriz_mod_eng, name='MOD Remap', colorscale='Reds', opacity=1.0, showscale=True))

            fig_3d_aba.update_layout(height=altura_dinamica, paper_bgcolor='#1E1E1E', margin=dict(l=0, r=0, b=0, t=20), font=dict(color='white'), scene=dict(zaxis=dict(autorange=z_dir), camera=dict(eye=dict(x=1.6, y=1.6, z=1.3))))
            st.plotly_chart(fig_3d_aba, use_container_width=True, config={'displayModeBar': True, 'scrollZoom': True, 'displaylogo': False})
            
            if st.button("🔲 Expandir Gráfico 3D em Tela Cheia", key="btn_fs_3d", use_container_width=True):
                st.session_state.focus_mode = '3D'
                st.rerun()

        with tab_grid:
            st.markdown("##### 🧮 Grade Térmica de Engenharia (Hex Dump)")
            matriz_ativa = matriz_delta_pct if "Percentual" in modo_exibicao else matriz_mod_eng
            colunas_labels = [f"Col {j+1}" for j in range(colunas)]
            linhas_labels = [f"0x{addr_inicio + (i * colunas * b_step):06X}" for i in range(linhas)]
            df_matriz = pd.DataFrame(matriz_ativa, index=linhas_labels, columns=colunas_labels)
            
            if "Percentual" in modo_exibicao:
                df_styled = df_matriz.style.format("{:+.2f}%").background_gradient(
                    cmap="vlag", vmin=-20.0, vmax=20.0
                )
                st.dataframe(df_styled, use_container_width=True, height=altura_dinamica)
            else:
                fmt_str = "{:.0f}" if bits_val <= 16 and fator == 1.0 else "{:.2f}"
                df_styled = df_matriz.style.format(fmt_str).background_gradient(
                    cmap="YlOrRd"
                )
                st.dataframe(df_styled, use_container_width=True, height=altura_dinamica)

        with tab_race_info:
            renderizar_aba_info_race(dados.get('metadados_race', {}), dados.get('imagem_race', None))

        st.markdown("---")
        st.markdown("### 🔍 Detalhamento Técnico Completo (Tabela Hexadecimal)")
        df_diff = pd.DataFrame([{k: v for k, v in d.items() if k != "EnderecoInt"} for d in dados['diffs']])
        st.dataframe(df_diff, use_container_width=True, height=350 if expandir_graficos else 250)

# Alias para compatibilidade caso outro módulo tente importar como render_eeprom
render_eeprom = render_hex_compare