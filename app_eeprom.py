import streamlit as st
from PIL import Image
import os

# Configuração da página (deve ser a primeira função do Streamlit)
st.set_page_config(page_title="Catálogo EEPROM", layout="centered")

st.title("Catálogo EEPROM - Pós Tratamento")

# --- DADOS MOCK (Exemplo) ---
dados_exemplo = {
    "imagem": "grafico_referencia.png",
    "posicao_inicio": "0x7F000",
    "intervalo": "0x7F000 - 0x7F5FF",
    "dados_veiculo": "Caminhão Volvo FH 460 - Motor D13C - Módulo TRW EMS2.2"
}

# --- ÁREA DA IMAGEM ---
st.subheader("Gráfico de Referência")

if os.path.exists(dados_exemplo["imagem"]):
    image = Image.open(dados_exemplo["imagem"])
    # O Streamlit ajusta a imagem automaticamente para a largura da tela
    st.image(image, caption="Gráfico do Sistema", use_container_width=True)
else:
    st.warning("⚠️ Imagem não encontrada. Certifique-se de que o arquivo 'grafico_referencia.png' está na mesma pasta.")

# --- ÁREA DE INFORMAÇÕES ---
st.subheader("Informações do Mapa")

# Usando colunas para organizar os dados
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Início do Gráfico:**")
    st.info(dados_exemplo["posicao_inicio"])
    
    st.markdown("**Intervalo:**")
    st.info(dados_exemplo["intervalo"])

with col2:
    st.markdown("**Veículo / Módulo:**")
    st.success(dados_exemplo["dados_veiculo"])