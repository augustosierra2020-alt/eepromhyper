import re

def parse_ecu_firmware(file_bytes: bytes) -> dict:
    """Faz a leitura bruta dos magic bytes e strings do firmware igual ao Race EVO"""
    data_str = file_bytes.decode('ascii', errors='ignore')
    
    # Heurísticas de identificação Bosch, Siemens, etc.
    hw_match = re.search(r'(0281\d{6}|0261\d{6})', data_str)
    sw_match = re.search(r'(1037\d{6})', data_str)
    edc_match = re.search(r'(EDC1[567][A-Z0-9]+|MD1[A-Z0-9]+|MG1[A-Z0-9]+)', data_str)
    
    tamanho_mb = len(file_bytes) / (1024 * 1024)
    tipo_mem = "EEPROM (Pequena)" if tamanho_mb < 0.1 else "Flash (Mapa Completo)"
    
    return {
        "Tamanho": f"{tamanho_mb:.2f} MB",
        "Tipo": tipo_mem,
        "Familia_ECU": edc_match.group(1) if edc_match else "Desconhecida/Genérica",
        "HW_Number": hw_match.group(1) if hw_match else "Não Detectado",
        "SW_Number": sw_match.group(1) if sw_match else "Não Detectado",
        "Integridade": "OK (Tamanho Padrão)" if tamanho_mb in [2.0, 4.0, 8.0] else "Aviso: Tamanho atípico"
    }