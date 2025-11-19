import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(
    page_title="Calculadora de Taxas - Atenas Projetos Ambientais",
    page_icon="🌿",
    layout="wide"
)

# CSS customizado para melhorar o visual - Identidade Atenas Projetos Ambientais
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600&family=Roboto:wght@300;400;500&display=swap');
    
    .main-title {
        font-size: 2.5rem;
        color: #2d8b6b;
        font-weight: 600;
        margin-bottom: 0.5rem;
        font-family: 'Cinzel', serif;
        letter-spacing: 2px;
    }
    
    .subtitle {
        font-size: 1.2rem;
        color: #2d8b6b;
        font-family: 'Roboto', sans-serif;
        font-weight: 300;
        margin-bottom: 2rem;
    }
    
    .warning-box {
        background-color: #f0f8f5;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2d8b6b;
        margin-bottom: 2rem;
    }
    
    .result-box {
        background-color: #e8f5f0;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2d8b6b;
        margin-top: 2rem;
    }
    
    .result-value {
        font-size: 2.5rem;
        color: #1e6b52;
        font-weight: bold;
        font-family: 'Cinzel', serif;
    }
    
    /* Estilização de botões */
    .stButton > button {
        background-color: #2d8b6b;
        color: white;
        font-family: 'Roboto', sans-serif;
        font-weight: 500;
        border: none;
        border-radius: 0.5rem;
        padding: 0.75rem 2rem;
        font-size: 1.1rem;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background-color: #1e6b52;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(45, 139, 107, 0.3);
    }
    
    /* Títulos de seções */
    h3 {
        color: #1e6b52;
        font-family: 'Roboto', sans-serif;
        font-weight: 500;
    }
    
    /* Resumo lateral */
    .summary-title {
        color: #2d8b6b;
        font-family: 'Cinzel', serif;
        font-size: 1.3rem;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Dados de configuração - Taxas de Ariquemes/RO
# Valores em UFIRs (Unidade Fiscal de Referência) - ajustar conforme legislação municipal

SERVICOS = {
    "Licença Prévia": {"codigo": "LP", "fator": 1.0},
    "Licença de Instalação": {"codigo": "LI", "fator": 1.5},
    "Licença de Operação": {"codigo": "LO", "fator": 1.2},
    "Licença Simplificada": {"codigo": "LS", "fator": 0.8},
    "Renovação de Licença": {"codigo": "RLO", "fator": 0.6}
}

GRUPOS_ATIVIDADES = {
    "01.00 - AGRICULTURA E PECUÁRIA": [
        "01.01 - Agricultura de culturas permanentes",
        "01.02 - Agricultura de culturas temporárias",
        "01.03 - Criação de bovinos",
        "01.04 - Criação de suínos",
        "01.05 - Avicultura"
    ],
    "02.00 - INDÚSTRIA DE PRODUTOS MINERAIS": [
        "02.01 - Extração de areia, cascalho e pedras",
        "02.02 - Beneficiamento de minerais não-metálicos",
        "02.03 - Fabricação de cimento e cal"
    ],
    "03.00 - INDÚSTRIA MADEIREIRA": [
        "03.01 - Serrarias",
        "03.02 - Fabricação de compensados",
        "03.03 - Fabricação de móveis de madeira"
    ],
    "04.00 - INDÚSTRIA DE ALIMENTOS E BEBIDAS": [
        "04.01 - Beneficiamento de produtos de origem vegetal",
        "04.02 - Abate de animais",
        "04.03 - Fabricação de laticínios",
        "04.04 - Fabricação de bebidas"
    ],
    "05.00 - INDÚSTRIA QUÍMICA": [
        "05.01 - Fabricação de produtos químicos",
        "05.02 - Fabricação de produtos farmacêuticos",
        "05.03 - Fabricação de fertilizantes"
    ],
    "06.00 - COMÉRCIO E SERVIÇOS": [
        "06.01 - Postos de combustíveis",
        "06.02 - Oficinas mecânicas",
        "06.03 - Lava-jatos",
        "06.04 - Comércio atacadista"
    ],
    "07.00 - CONSTRUÇÃO CIVIL": [
        "07.01 - Edificações residenciais",
        "07.02 - Edificações comerciais",
        "07.03 - Edificações industriais",
        "07.04 - Loteamentos",
        "07.05 - Condomínios",
        "07.06 - Hospitais e clínicas",
        "07.07 - Escolas e universidades",
        "07.08 - Shopping centers",
        "07.09 - Clínicas e congêneres"
    ],
    "08.00 - INFRAESTRUTURA": [
        "08.01 - Rodovias",
        "08.02 - Ferrovias",
        "08.03 - Linhas de transmissão",
        "08.04 - Sistemas de abastecimento de água",
        "08.05 - Sistemas de esgotamento sanitário"
    ]
}

# Portes das atividades baseados em grandezas
PORTES = {
    "Micro": {"fator": 0.5, "area_max": 100, "potencia_max": 50},
    "Pequeno": {"fator": 1.0, "area_max": 500, "potencia_max": 200},
    "Médio": {"fator": 2.0, "area_max": 2000, "potencia_max": 1000},
    "Grande": {"fator": 4.0, "area_max": float('inf'), "potencia_max": float('inf')}
}

# Valor base da UFIR para 2025 (ajustar conforme decreto municipal)
VALOR_UFIR = 4.50  # Valor hipotético - deve ser atualizado

def calcular_porte_por_area(area):
    """Determina o porte da atividade baseado na área construída"""
    for porte, config in PORTES.items():
        if area <= config["area_max"]:
            return porte, config["fator"]
    return "Grande", PORTES["Grande"]["fator"]

def calcular_porte_por_potencia(potencia):
    """Determina o porte da atividade baseado na potência instalada"""
    for porte, config in PORTES.items():
        if potencia <= config["potencia_max"]:
            return porte, config["fator"]
    return "Grande", PORTES["Grande"]["fator"]

def calcular_taxa(servico, porte_fator):
    """Calcula o valor da taxa ambiental"""
    # Taxa base em UFIRs
    taxa_base = 100
    
    # Aplicar fator do serviço
    valor = taxa_base * SERVICOS[servico]["fator"]
    
    # Aplicar fator do porte
    valor *= porte_fator
    
    # Converter UFIRs para Reais
    valor_reais = valor * VALOR_UFIR
    
    return valor_reais, valor

# Interface principal
col_logo, col_title = st.columns([1, 4])

with col_logo:
    # Logo da Atenas Projetos Ambientais
    st.image("atenas.jpeg", width=150)

with col_title:
    st.markdown('<h1 class="main-title">CALCULADORA DE TAXAS</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Atenas Projetos Ambientais</p>', unsafe_allow_html=True)

# Aviso
st.markdown("""
    <div class="warning-box">
        <strong>⚠️ Atenção!</strong> Este é um simulador de taxas. Informamos que os valores podem mudar de acordo com as opções selecionadas e a legislação vigente. Consulte sempre o órgão ambiental para valores oficiais.
    </div>
""", unsafe_allow_html=True)

# Formulário principal
col1, col2 = st.columns([2, 1])

with col1:
    # Seleção do serviço
    st.markdown("### Qual o serviço você deseja? *")
    servico_selecionado = st.selectbox(
        "Tipo de licença",
        options=list(SERVICOS.keys()),
        label_visibility="collapsed"
    )
    
    # Seleção do grupo de atividade
    st.markdown("### Qual o Grupo de sua Atividade? *")
    grupo_selecionado = st.selectbox(
        "Grupo",
        options=list(GRUPOS_ATIVIDADES.keys()),
        label_visibility="collapsed"
    )
    
    # Seleção da atividade específica
    st.markdown("### Qual é a sua Atividade? *")
    atividade_selecionada = st.selectbox(
        "Atividade",
        options=GRUPOS_ATIVIDADES[grupo_selecionado],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Grandezas
    st.markdown("### Selecione uma das grandezas abaixo e responda as perguntas referentes à sua atividade:")
    
    tipo_grandeza = st.radio(
        "Tipo de grandeza",
        options=["Área construída (m²)", "Potência instalada (kW)", "Número de funcionários"],
        label_visibility="collapsed"
    )
    
    porte_fator = 1.0
    porte_texto = "Pequeno"
    
    if tipo_grandeza == "Área construída (m²)":
        area = st.number_input(
            "Informe a área construída em m²: *",
            min_value=0.0,
            value=123.0,
            step=1.0,
            format="%.2f"
        )
        porte_texto, porte_fator = calcular_porte_por_area(area)
        
    elif tipo_grandeza == "Potência instalada (kW)":
        potencia = st.number_input(
            "Informe a potência instalada em kW: *",
            min_value=0.0,
            value=50.0,
            step=1.0,
            format="%.2f"
        )
        porte_texto, porte_fator = calcular_porte_por_potencia(potencia)
        
    else:
        funcionarios = st.number_input(
            "Informe o número de funcionários: *",
            min_value=0,
            value=10,
            step=1
        )
        if funcionarios <= 10:
            porte_texto, porte_fator = "Micro", 0.5
        elif funcionarios <= 50:
            porte_texto, porte_fator = "Pequeno", 1.0
        elif funcionarios <= 200:
            porte_texto, porte_fator = "Médio", 2.0
        else:
            porte_texto, porte_fator = "Grande", 4.0
    
    st.markdown("---")
    
    # Licença anterior
    st.markdown("### Qual é a sua Licença anterior?")
    licenca_anterior = st.text_input(
        "Ex.: 12345678-9 ou 1234567/2013",
        label_visibility="collapsed"
    )

with col2:
    st.markdown('<p class="summary-title">📊 Resumo da Solicitação</p>', unsafe_allow_html=True)
    st.markdown(f"**Serviço:** {servico_selecionado}")
    st.markdown(f"**Porte:** {porte_texto}")
    st.markdown(f"**Grupo:** {grupo_selecionado.split(' - ')[0]}")
    
    if licenca_anterior:
        st.markdown(f"**Licença anterior:** {licenca_anterior}")

# Cálculo e exibição do resultado
st.markdown("---")

if st.button("🧮 Simular", type="primary", use_container_width=True):
    valor_total, valor_ufirs = calcular_taxa(
        servico_selecionado,
        porte_fator
    )
    
    st.markdown(f"""
        <div class="result-box">
            <h3>💰 Valor Aproximado pelo Serviço</h3>
            <p class="result-value">R$ {valor_total:,.2f}</p>
            <hr>
            <p><strong>Detalhamento:</strong></p>
            <ul>
                <li>Taxa base: {valor_ufirs:.2f} UFIRs</li>
                <li>Valor em Reais: R$ {valor_total:,.2f}</li>
                <li>Valor da UFIR: R$ {VALOR_UFIR:.2f}</li>
            </ul>
            <p style="margin-top: 1rem; font-size: 0.9rem; color: #666;">
                <strong>Observação:</strong> Este é um valor aproximado. Para o valor oficial, 
                consulte o órgão ambiental competente.
            </p>
        </div>
    """, unsafe_allow_html=True)

# Rodapé com informações
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem; padding: 2rem 0;">
        <p><strong>Calculadora de Taxas de Licenciamento Ambiental</strong></p>
        <p>Atenas Projetos Ambientais | Versão 1.0 | 2025</p>
        <p>⚠️ Os valores apresentados são estimativas. Consulte sempre o órgão ambiental competente.</p>
    </div>
""", unsafe_allow_html=True)