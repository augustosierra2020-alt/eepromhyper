import os
import base64
import streamlit as st
import pandas as pd

# Mapeamentos de Caminho
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
CAMINHO_LOGO_PRINCIPAL = os.path.join(BASE_DIR, "Logos", "logo.png")
CAMINHO_PLANILHA_FP = os.path.join(BASE_DIR, "Fp.xlsx")

def render_home():
    # Renderização da Logo Principal via Base64
    if os.path.exists(CAMINHO_LOGO_PRINCIPAL):
        try:
            with open(CAMINHO_LOGO_PRINCIPAL, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            st.markdown(
                f'<div style="text-align: center; margin-bottom: 25px;">'
                f'<img src="data:image/png;base64,{encoded_string}" class="locked-main-logo">'
                f'</div>', 
                unsafe_allow_html=True
            )
        except Exception:
            st.markdown("<h1 style='text-align: center; color: white;'>🚀 HyperTork Hub</h1>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center; color: white;'>🚀 HyperTork Hub</h1>", unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center; color: #1E88E5; margin-bottom: 30px; font-weight: 700;'>PAINEL DE CONTROLE OPERACIONAL</h2>", unsafe_allow_html=True)

    # --- DASHBOARD COM AS 3 MÉTRICAS SOLICITADAS DA PLANILHA FP ---
    total_clientes = 0
    total_servicos = 0
    total_montadoras = 0
    status_fp = "Aguardando Sincronização"

    try:
        if os.path.exists(CAMINHO_PLANILHA_FP):
            df_fp = pd.read_excel(CAMINHO_PLANILHA_FP)
            
            # 1. Total de Clientes Identificados (Clientes Únicos)
            col_cliente = "Flash Point" if "Flash Point" in df_fp.columns else df_fp.columns[0]
            total_clientes = df_fp[col_cliente].nunique()
            
            # 2. Total de Serviços realizados (Total de Linhas da Planilha)
            total_servicos = len(df_fp)
            
            # 3. Total de Montadoras identificadas
            col_montadora = None
            for col in ["Fabricante", "Veículo", "Montadora"]:
                if col in df_fp.columns:
                    col_montadora = col
                    break
            
            if col_montadora:
                total_montadoras = df_fp[col_montadora].nunique()
            else:
                total_montadoras = 0
                
            status_fp = "Online 🟢"
    except Exception:
        status_fp = "Erro de Leitura 🔴"
        
    st.markdown("### 📊 Visão Geral: Base de Clientes (Fp)")
    
    # Exibição dos 3 cards de métricas
    m1, m2, m3 = st.columns(3)
    m1.metric("Total de Clientes Identificados", total_clientes)
    m2.metric("Total de Serviços realizados", total_servicos)
    m3.metric("Total de Montadoras identificadas", total_montadoras)
    
    st.caption(f"Status do Arquivo Fp: {status_fp}")
    st.markdown("---")

    # --- GRID DE NAV PREMIUM (DARK GLASSMORPHISM MONOCROMÁTICO) ---
    st.markdown("""
        <style>
            .hub-grid { 
                display: grid; 
                grid-template-columns: repeat(4, 1fr); 
                gap: 20px; 
            }
            .big-hub-btn { 
                text-decoration: none !important; 
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                background: linear-gradient(145deg, #1A1A1A 0%, #0D0D0D 100%);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 35px 15px;
                transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
                box-shadow: 0 6px 15px rgba(0,0,0,0.5);
            }
            .big-hub-btn:hover {
                transform: translateY(-5px);
                border-color: #1E88E5;
                box-shadow: 0 10px 25px rgba(30, 136, 229, 0.2);
                background: linear-gradient(145deg, #222222 0%, #111111 100%);
            }
            .big-hub-btn .emoji-icon { 
                font-size: 2.6rem; 
                margin-bottom: 15px;
                filter: grayscale(10%) drop-shadow(0px 3px 5px rgba(0,0,0,0.7));
                transition: transform 0.3s ease;
            }
            .big-hub-btn:hover .emoji-icon {
                transform: scale(1.12);
            }
            .big-hub-btn h2 { 
                color: #C0C0C0 !important; 
                font-size: 1.05rem !important; 
                font-weight: 600 !important; 
                margin: 0;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                transition: color 0.3s ease;
            }
            .big-hub-btn:hover h2 {
                color: #FFFFFF !important;
            }
        </style>
        <div class="hub-grid">
            <a href="?page=HEX_COMPARE" class="big-hub-btn" target="_self">
                <div class="emoji-icon">🛠️</div>
                <h2>HEX Studio</h2>
            </a>
            <a href="?page=EEPROM" class="big-hub-btn" target="_self">
                <div class="emoji-icon">⚙️</div>
                <h2>EEPROM Maps</h2>
            </a>
            <a href="?page=GESTAO_OS" class="big-hub-btn" target="_self">
                <div class="emoji-icon">📊</div>
                <h2>Gestão & OS</h2>
            </a>
            <a href="?page=OBD2" class="big-hub-btn" target="_self">
                <div class="emoji-icon">🚗</div>
                <h2>Scanner OBD2</h2>
            </a>
        </div>
    """, unsafe_allow_html=True)