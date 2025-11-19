# config_ariquemes.py
# Configurações específicas para o município de Ariquemes/RO
# Atualize estes valores de acordo com a legislação municipal vigente

"""
INSTRUÇÕES DE USO:
1. Consulte os decretos e resoluções municipais de Ariquemes/RO
2. Atualize os valores abaixo conforme a legislação
3. O valor da UFIR deve ser atualizado anualmente
4. Os fatores de serviço e porte devem seguir as tabelas oficiais
"""

# =============================================================================
# VALORES MONETÁRIOS
# =============================================================================

# Valor da UFIR (Unidade Fiscal de Referência) para 2025
# Atualizar conforme decreto municipal
VALOR_UFIR = 4.50  # R$

# Taxa base em UFIRs (valor de referência para cálculos)
TAXA_BASE_UFIRS = 100

# Custo de deslocamento por quilômetro
CUSTO_KM = 2.50  # R$ por km

# Percentual adicional para empreendimentos em Unidade de Conservação
ACRESCIMO_UC_PERCENTUAL = 20  # 20% a mais

# =============================================================================
# TIPOS DE SERVIÇOS E FATORES MULTIPLICADORES
# =============================================================================

SERVICOS = {
    "Licença Prévia": {
        "codigo": "LP",
        "fator": 1.0,
        "descricao": "Atesta a viabilidade ambiental do empreendimento"
    },
    "Licença de Instalação": {
        "codigo": "LI",
        "fator": 1.5,
        "descricao": "Autoriza o início da implementação do empreendimento"
    },
    "Licença de Operação": {
        "codigo": "LO",
        "fator": 1.2,
        "descricao": "Autoriza o funcionamento do empreendimento"
    },
    "Licença Simplificada": {
        "codigo": "LS",
        "fator": 0.8,
        "descricao": "Para atividades de menor impacto ambiental"
    },
    "Renovação de Licença": {
        "codigo": "RLO",
        "fator": 0.6,
        "descricao": "Renovação de licenças já concedidas"
    },
    "Autorização Ambiental": {
        "codigo": "AA",
        "fator": 0.5,
        "descricao": "Para atividades específicas de curta duração"
    }
}

# =============================================================================
# CLASSIFICAÇÃO DE PORTES
# =============================================================================

# Critérios baseados em área construída (m²)
PORTE_POR_AREA = {
    "Micro": {
        "fator": 0.5,
        "area_min": 0,
        "area_max": 100
    },
    "Pequeno": {
        "fator": 1.0,
        "area_min": 100.01,
        "area_max": 500
    },
    "Médio": {
        "fator": 2.0,
        "area_min": 500.01,
        "area_max": 2000
    },
    "Grande": {
        "fator": 4.0,
        "area_min": 2000.01,
        "area_max": float('inf')
    }
}

# Critérios baseados em potência instalada (kW)
PORTE_POR_POTENCIA = {
    "Micro": {
        "fator": 0.5,
        "potencia_min": 0,
        "potencia_max": 50
    },
    "Pequeno": {
        "fator": 1.0,
        "potencia_min": 50.01,
        "potencia_max": 200
    },
    "Médio": {
        "fator": 2.0,
        "potencia_min": 200.01,
        "potencia_max": 1000
    },
    "Grande": {
        "fator": 4.0,
        "potencia_min": 1000.01,
        "potencia_max": float('inf')
    }
}

# Critérios baseados em número de funcionários
PORTE_POR_FUNCIONARIOS = {
    "Micro": {
        "fator": 0.5,
        "funcionarios_min": 0,
        "funcionarios_max": 10
    },
    "Pequeno": {
        "fator": 1.0,
        "funcionarios_min": 11,
        "funcionarios_max": 50
    },
    "Médio": {
        "fator": 2.0,
        "funcionarios_min": 51,
        "funcionarios_max": 200
    },
    "Grande": {
        "fator": 4.0,
        "funcionarios_min": 201,
        "funcionarios_max": float('inf')
    }
}

# =============================================================================
# GRUPOS E ATIVIDADES
# =============================================================================

GRUPOS_ATIVIDADES = {
    "01.00 - AGRICULTURA E PECUÁRIA": {
        "atividades": [
            "01.01 - Agricultura de culturas permanentes",
            "01.02 - Agricultura de culturas temporárias",
            "01.03 - Criação de bovinos para corte",
            "01.04 - Criação de bovinos para leite",
            "01.05 - Criação de suínos",
            "01.06 - Avicultura de corte",
            "01.07 - Avicultura de postura",
            "01.08 - Piscicultura",
            "01.09 - Aquicultura"
        ],
        "fator_adicional": 1.0
    },
    
    "02.00 - INDÚSTRIA DE PRODUTOS MINERAIS": {
        "atividades": [
            "02.01 - Extração de areia, cascalho e pedras",
            "02.02 - Extração de argila",
            "02.03 - Beneficiamento de minerais não-metálicos",
            "02.04 - Fabricação de cimento",
            "02.05 - Fabricação de cal",
            "02.06 - Fabricação de cerâmica",
            "02.07 - Britagem de pedras"
        ],
        "fator_adicional": 1.2
    },
    
    "03.00 - INDÚSTRIA MADEIREIRA": {
        "atividades": [
            "03.01 - Serrarias",
            "03.02 - Fabricação de compensados e laminados",
            "03.03 - Fabricação de móveis de madeira",
            "03.04 - Fabricação de estruturas de madeira",
            "03.05 - Preservação de madeira",
            "03.06 - Fabricação de chapas e placas"
        ],
        "fator_adicional": 1.1
    },
    
    "04.00 - INDÚSTRIA DE ALIMENTOS E BEBIDAS": {
        "atividades": [
            "04.01 - Beneficiamento de café",
            "04.02 - Beneficiamento de cacau",
            "04.03 - Abate de bovinos",
            "04.04 - Abate de suínos",
            "04.05 - Abate de aves",
            "04.06 - Fabricação de laticínios",
            "04.07 - Fabricação de óleos vegetais",
            "04.08 - Fabricação de bebidas alcoólicas",
            "04.09 - Fabricação de bebidas não-alcoólicas",
            "04.10 - Fabricação de rações",
            "04.11 - Beneficiamento de pescados"
        ],
        "fator_adicional": 1.3
    },
    
    "05.00 - INDÚSTRIA QUÍMICA": {
        "atividades": [
            "05.01 - Fabricação de produtos químicos inorgânicos",
            "05.02 - Fabricação de produtos químicos orgânicos",
            "05.03 - Fabricação de produtos farmacêuticos",
            "05.04 - Fabricação de fertilizantes",
            "05.05 - Fabricação de defensivos agrícolas",
            "05.06 - Fabricação de produtos de limpeza",
            "05.07 - Fabricação de tintas e vernizes"
        ],
        "fator_adicional": 1.5
    },
    
    "06.00 - COMÉRCIO E SERVIÇOS": {
        "atividades": [
            "06.01 - Postos de combustíveis",
            "06.02 - Oficinas mecânicas",
            "06.03 - Lava-jatos",
            "06.04 - Comércio atacadista de produtos químicos",
            "06.05 - Comércio atacadista de combustíveis",
            "06.06 - Armazenamento de produtos perigosos",
            "06.07 - Serviços de pintura",
            "06.08 - Borracharias"
        ],
        "fator_adicional": 0.9
    },
    
    "07.00 - CONSTRUÇÃO CIVIL": {
        "atividades": [
            "07.01 - Edificações residenciais unifamiliares",
            "07.02 - Edificações residenciais multifamiliares",
            "07.03 - Edificações comerciais",
            "07.04 - Edificações industriais",
            "07.05 - Loteamentos urbanos",
            "07.06 - Loteamentos rurais",
            "07.07 - Condomínios residenciais",
            "07.08 - Hospitais e clínicas",
            "07.09 - Clínicas e congêneres",
            "07.10 - Escolas e universidades",
            "07.11 - Shopping centers",
            "07.12 - Estacionamentos",
            "07.13 - Hotéis e pousadas"
        ],
        "fator_adicional": 1.0
    },
    
    "08.00 - INFRAESTRUTURA": {
        "atividades": [
            "08.01 - Rodovias e estradas",
            "08.02 - Ferrovias",
            "08.03 - Aeroportos",
            "08.04 - Linhas de transmissão de energia",
            "08.05 - Sistemas de abastecimento de água",
            "08.06 - Sistemas de esgotamento sanitário",
            "08.07 - Aterros sanitários",
            "08.08 - Usinas de geração de energia",
            "08.09 - Barragens e reservatórios"
        ],
        "fator_adicional": 1.4
    },
    
    "09.00 - SERVIÇOS DE SAÚDE": {
        "atividades": [
            "09.01 - Hospitais gerais",
            "09.02 - Hospitais especializados",
            "09.03 - Clínicas médicas",
            "09.04 - Clínicas odontológicas",
            "09.05 - Laboratórios de análises clínicas",
            "09.06 - Clínicas veterinárias",
            "09.07 - Farmácias de manipulação"
        ],
        "fator_adicional": 1.1
    },
    
    "10.00 - TURISMO E LAZER": {
        "atividades": [
            "10.01 - Hotéis e pousadas",
            "10.02 - Parques temáticos",
            "10.03 - Clubes recreativos",
            "10.04 - Marinas e atracadouros",
            "10.05 - Pistas de corrida",
            "10.06 - Campos de golfe"
        ],
        "fator_adicional": 1.0
    }
}

# =============================================================================
# INFORMAÇÕES DE CONTATO
# =============================================================================

CONTATO_ORGAO_AMBIENTAL = {
    "nome": "Secretaria Municipal de Meio Ambiente de Ariquemes",
    "endereco": "Avenida [inserir endereço], Ariquemes/RO",
    "telefone": "(69) [inserir telefone]",
    "email": "[inserir e-mail]",
    "horario": "Segunda a Sexta, das 8h às 14h",
    "site": "https://ariquemes.ro.gov.br"
}

# =============================================================================
# OBSERVAÇÕES LEGAIS
# =============================================================================

OBSERVACOES_LEGAIS = """
OBSERVAÇÕES IMPORTANTES:

1. Os valores apresentados neste simulador são aproximados e têm caráter 
   meramente informativo.

2. Para obter o valor oficial e exato da taxa, o interessado deve consultar 
   diretamente a Secretaria Municipal de Meio Ambiente de Ariquemes/RO.

3. Os valores estão sujeitos a alterações conforme decretos e resoluções 
   municipais.

4. O valor da UFIR é atualizado periodicamente pela Prefeitura Municipal.

5. Podem incidir taxas adicionais não contempladas neste simulador, conforme 
   especificidades de cada atividade.

6. O licenciamento ambiental requer análise técnica e pode envolver custos 
   adicionais relacionados a estudos ambientais, compensações e condicionantes.

7. Este simulador não substitui o processo oficial de licenciamento ambiental.
"""

# =============================================================================
# VERSÃO E ATUALIZAÇÃO
# =============================================================================

VERSAO_CONFIG = "1.0.0"
DATA_ATUALIZACAO = "2025-11-18"
RESPONSAVEL_ATUALIZACAO = "Equipe de Desenvolvimento"