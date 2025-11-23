# Mapeamento de Potencial Poluidor baseado na Lei 2.349/2019 de Ariquemes
# Este arquivo contém o mapeamento oficial do potencial poluidor para cada atividade

# Mapeamento de tipo de medição apropriada para cada atividade
TIPO_MEDICAO_MAP = {
    # 01.00 - AGRICULTURA E PECUÁRIA
    "01.01 - Agricultura de culturas permanentes": "area",
    "01.02 - Agricultura de culturas temporárias": "area",
    "01.03 - Criação de bovinos": "area",
    "01.04 - Criação de suínos": "area",
    "01.05 - Avicultura": "area",
    
    # 02.00 - INDÚSTRIA DE PRODUTOS MINERAIS
    "02.01 - Extração de areia, cascalho e pedras": "area",
    "02.02 - Beneficiamento de minerais não-metálicos": "area",
    "02.03 - Fabricação de cimento e cal": "area",
    
    # 03.00 - INDÚSTRIA MADEIREIRA
    "03.01 - Serrarias": "area",
    "03.02 - Fabricação de compensados": "area",
    "03.03 - Fabricação de móveis de madeira": "area",
    
    # 04.00 - INDÚSTRIA DE ALIMENTOS E BEBIDAS
    "04.01 - Beneficiamento de produtos de origem vegetal": "area",
    "04.02 - Abate de animais": "area",
    "04.03 - Fabricação de laticínios": "area",
    "04.04 - Fabricação de bebidas": "area",
    
    # 05.00 - INDÚSTRIA QUÍMICA
    "05.01 - Fabricação de produtos químicos": "area",
    "05.02 - Fabricação de produtos farmacêuticos": "area",
    "05.03 - Fabricação de fertilizantes": "area",
    
    # 06.00 - COMÉRCIO E SERVIÇOS
    "06.01 - Postos de combustíveis": "area",
    "06.02 - Oficinas mecânicas": "area",
    "06.03 - Lava-jatos": "area",
    "06.04 - Comércio atacadista": "area",
    
    # 07.00 - CONSTRUÇÃO CIVIL
    "07.01 - Edificações residenciais": "area",
    "07.02 - Edificações comerciais": "area",
    "07.03 - Edificações industriais": "area",
    "07.04 - Loteamentos": "area",
    "07.05 - Condomínios": "area",
    "07.06 - Hospitais e clínicas": "area",
    "07.07 - Escolas e universidades": "area",
    "07.08 - Shopping centers": "area",
    "07.09 - Clínicas e congêneres": "area",
    
    # 08.00 - INFRAESTRUTURA
    "08.01 - Rodovias": "area",
    "08.02 - Ferrovias": "area",
    "08.03 - Linhas de transmissão": "potencia",
    "08.04 - Sistemas de abastecimento de água": "area",
    "08.05 - Sistemas de esgotamento sanitário": "area",
}

# Tipo de medição padrão por grupo (usado como fallback)
TIPO_MEDICAO_POR_GRUPO = {
    "01.00 - AGRICULTURA E PECUÁRIA": "area",
    "02.00 - INDÚSTRIA DE PRODUTOS MINERAIS": "area",
    "03.00 - INDÚSTRIA MADEIREIRA": "area",
    "04.00 - INDÚSTRIA DE ALIMENTOS E BEBIDAS": "area",
    "05.00 - INDÚSTRIA QUÍMICA": "area",
    "06.00 - COMÉRCIO E SERVIÇOS": "area",
    "07.00 - CONSTRUÇÃO CIVIL": "area",
    "08.00 - INFRAESTRUTURA": "area",
}

def obter_tipo_medicao(atividade: str, grupo: str = None) -> str:
    """
    Retorna o tipo de medição apropriado para uma atividade.
    
    Args:
        atividade: Nome da atividade específica
        grupo: Grupo da atividade (usado como fallback)
    
    Returns:
        Tipo de medição: "area", "potencia" ou "funcionarios"
    """
    # Primeiro tenta encontrar a atividade específica
    if atividade in TIPO_MEDICAO_MAP:
        return TIPO_MEDICAO_MAP[atividade]
    
    # Se não encontrar, usa o grupo como fallback
    if grupo and grupo in TIPO_MEDICAO_POR_GRUPO:
        return TIPO_MEDICAO_POR_GRUPO[grupo]
    
    # Valor padrão
    return "area"

POTENCIAL_POLUIDOR_MAP = {
    # 01.00 - AGRICULTURA E PECUÁRIA
    "01.01 - Agricultura de culturas permanentes": "Baixo",
    "01.02 - Agricultura de culturas temporárias": "Baixo",
    "01.03 - Criação de bovinos": "Médio",
    "01.04 - Criação de suínos": "Médio",
    "01.05 - Avicultura": "Baixo",
    
    # 02.00 - INDÚSTRIA DE PRODUTOS MINERAIS
    "02.01 - Extração de areia, cascalho e pedras": "Alto",
    "02.02 - Beneficiamento de minerais não-metálicos": "Alto",
    "02.03 - Fabricação de cimento e cal": "Alto",
    
    # 03.00 - INDÚSTRIA MADEIREIRA
    "03.01 - Serrarias": "Alto",
    "03.02 - Fabricação de compensados": "Alto",
    "03.03 - Fabricação de móveis de madeira": "Médio",
    
    # 04.00 - INDÚSTRIA DE ALIMENTOS E BEBIDAS
    "04.01 - Beneficiamento de produtos de origem vegetal": "Baixo",
    "04.02 - Abate de animais": "Alto",
    "04.03 - Fabricação de laticínios": "Alto",
    "04.04 - Fabricação de bebidas": "Alto",
    
    # 05.00 - INDÚSTRIA QUÍMICA
    "05.01 - Fabricação de produtos químicos": "Alto",
    "05.02 - Fabricação de produtos farmacêuticos": "Alto",
    "05.03 - Fabricação de fertilizantes": "Alto",
    
    # 06.00 - COMÉRCIO E SERVIÇOS
    "06.01 - Postos de combustíveis": "Médio",
    "06.02 - Oficinas mecânicas": "Médio",
    "06.03 - Lava-jatos": "Médio",
    "06.04 - Comércio atacadista": "Baixo",
    
    # 07.00 - CONSTRUÇÃO CIVIL
    "07.01 - Edificações residenciais": "Baixo",
    "07.02 - Edificações comerciais": "Baixo",
    "07.03 - Edificações industriais": "Médio",
    "07.04 - Loteamentos": "Médio",
    "07.05 - Condomínios": "Médio",
    "07.06 - Hospitais e clínicas": "Médio",
    "07.07 - Escolas e universidades": "Baixo",
    "07.08 - Shopping centers": "Baixo",
    "07.09 - Clínicas e congêneres": "Médio",
    
    # 08.00 - INFRAESTRUTURA
    "08.01 - Rodovias": "Alto",
    "08.02 - Ferrovias": "Alto",
    "08.03 - Linhas de transmissão": "Alto",
    "08.04 - Sistemas de abastecimento de água": "Médio",
    "08.05 - Sistemas de esgotamento sanitário": "Médio",
}

# Mapeamento por grupo de atividade (para casos não especificados)
POTENCIAL_POLUIDOR_POR_GRUPO = {
    "01.00 - AGRICULTURA E PECUÁRIA": "Baixo",
    "02.00 - INDÚSTRIA DE PRODUTOS MINERAIS": "Alto",
    "03.00 - INDÚSTRIA MADEIREIRA": "Alto",
    "04.00 - INDÚSTRIA DE ALIMENTOS E BEBIDAS": "Médio",
    "05.00 - INDÚSTRIA QUÍMICA": "Alto",
    "06.00 - COMÉRCIO E SERVIÇOS": "Médio",
    "07.00 - CONSTRUÇÃO CIVIL": "Baixo",
    "08.00 - INFRAESTRUTURA": "Alto",
}

def obter_potencial_poluidor(atividade: str, grupo: str = None) -> str:
    """
    Retorna o potencial poluidor de uma atividade específica.
    
    Args:
        atividade: Nome da atividade específica
        grupo: Grupo da atividade (usado como fallback)
    
    Returns:
        Potencial poluidor: "Baixo", "Médio" ou "Alto"
    """
    # Primeiro tenta encontrar a atividade específica
    if atividade in POTENCIAL_POLUIDOR_MAP:
        return POTENCIAL_POLUIDOR_MAP[atividade]
    
    # Se não encontrar, usa o grupo como fallback
    if grupo and grupo in POTENCIAL_POLUIDOR_POR_GRUPO:
        return POTENCIAL_POLUIDOR_POR_GRUPO[grupo]
    
    # Valor padrão se não encontrar
    return "Médio"
