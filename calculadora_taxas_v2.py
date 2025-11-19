import streamlit as st
import pandas as pd
from config_ariquemes import *

# Configuração da página
st.set_page_config(
    page_title="Calculadora de Taxas de Licenciamento - Ariquemes/RO",
    page_icon="🌿",
    layout="wide"
)

# CSS customizado para melhorar o visual
st.markdown("""
    <style>
    .main-title {
        font-size: 2.5rem;
        color: #2c5f2d;
        font-weight: 300;
        margin-bottom: 2rem;
    }
    .warning-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
        margin-bottom: 2rem;
    }
    .result-box {
        background-color: #d4edda;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
        margin-top: 2rem;
    }
    .result-value {
        font-size: 2rem;
        color: #155724;
        font-weight: bold;
    }
    .info-box {
        background-color: #d1ecf1;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #17a2b8;
        margin-top: 1rem;
    }
    .summary-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

def calcular_porte_por_area(area):
    """Determina o porte da atividade baseado na área construída"""
    for porte, config in PORTE_POR_AREA.items():
        if config["area_min"] <= area <= config["area_max"]:
            return porte, config["fator"]
    return "Grande", PORTE_POR_AREA["Grande"]["fator"]

def calcular_porte_por_potencia(potencia):
    """Determina o porte da atividade baseado na potência instalada"""
    for porte, config in PORTE_POR_POTENCIA.items():
        if config["potencia_min"] <= potencia <= config["potencia_max"]:
            return porte, config["fator"]
    return "Grande", PORTE_POR_POTENCIA["Grande"]["fator"]

def calcular_porte_por_funcionarios(funcionarios):
    """Determina o porte da atividade baseado no número de funcionários"""
    for porte, config in PORTE_POR_FUNCIONARIOS.items():
        if config["funcionarios_min"] <= funcionarios <= config["funcionarios_max"]:
            return porte, config["fator"]
    return "Grande", PORTE_POR_FUNCIONARIOS["Grande"]["fator"]

def calcular_taxa(servico, porte_fator, grupo_fator, distancia, unidade_conservacao):
    """Calcula o valor da taxa ambiental"""
    # Taxa base em UFIRs
    valor = TAXA_BASE_UFIRS
    
    # Aplicar fator do serviço
    valor *= SERVICOS[servico]["fator"]
    
    # Aplicar fator do porte
    valor *= porte_fator
    
    # Aplicar fator do grupo de atividade
    valor *= grupo_fator
    
    # Adicionar custo de deslocamento
    custo_deslocamento = distancia * CUSTO_KM
    
    # Adicionar taxa adicional se em unidade de conservação
    if unidade_conservacao:
        valor *= (1 + ACRESCIMO_UC_PERCENTUAL / 100)
    
    # Converter UFIRs para Reais
    valor_reais = valor * VALOR_UFIR
    
    # Valor total
    valor_total = valor_reais + custo_deslocamento
    
    return {
        "valor_total": valor_total,
        "valor_ufirs": valor,
        "valor_taxa_reais": valor_reais,
        "custo_deslocamento": custo_deslocamento,
        "fator_servico": SERVICOS[servico]["fator"],
        "fator_porte": porte_fator,
        "fator_grupo": grupo_fator
    }

# Interface principal
st.markdown('<h1 class="main-title">Calculadora: Taxas de Licenciamento Ambiental</h1>', unsafe_allow_html=True)
st.markdown('<p style="color: #666; font-size: 1.1rem;">Município de Ariquemes - Rondônia</p>', unsafe_allow_html=True)

# Aviso
st.markdown(f"""
    <div class="warning-box">
        <strong>⚠️ Atenção!</strong> Este é um simulador de taxas. Informamos que os valores podem mudar de acordo com as opções selecionadas e a legislação vigente. Consulte sempre o órgão ambiental para valores oficiais.
        <br><br>
        <small>Última atualização: {DATA_ATUALIZACAO} | Versão: {VERSAO_CONFIG}</small>
    </div>
""", unsafe_allow_html=True)

# Criar tabs para melhor organização
tab1, tab2, tab3 = st.tabs(["📝 Calculadora", "ℹ️ Informações", "📞 Contato"])

with tab1:
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
        
        # Mostrar descrição do serviço selecionado
        st.markdown(f"<small>ℹ️ {SERVICOS[servico_selecionado]['descricao']}</small>", unsafe_allow_html=True)
        
        st.markdown("---")
        
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
            options=GRUPOS_ATIVIDADES[grupo_selecionado]["atividades"],
            label_visibility="collapsed"
        )
        
        # Obter fator do grupo
        grupo_fator = GRUPOS_ATIVIDADES[grupo_selecionado]["fator_adicional"]
        
        st.markdown("---")
        
        # Grandezas
        st.markdown("### Selecione uma das grandezas abaixo e responda as perguntas referentes à sua atividade:")
        
        tipo_grandeza = st.radio(
            "Tipo de grandeza",
            options=["Área construída (m²)", "Potência instalada (kW)", "Número de funcionários"],
            label_visibility="collapsed",
            horizontal=True
        )
        
        porte_fator = 1.0
        porte_texto = "Pequeno"
        valor_grandeza = 0
        
        # Container para os campos de entrada
        grandeza_container = st.container()
        
        with grandeza_container:
            if tipo_grandeza == "Área construída (m²)":
                area = st.number_input(
                    "Informe a área construída em m²: *",
                    min_value=0.0,
                    value=123.0,
                    step=1.0,
                    format="%.2f"
                )
                porte_texto, porte_fator = calcular_porte_por_area(area)
                valor_grandeza = area
                
            elif tipo_grandeza == "Potência instalada (kW)":
                potencia = st.number_input(
                    "Informe a potência instalada em kW: *",
                    min_value=0.0,
                    value=50.0,
                    step=1.0,
                    format="%.2f"
                )
                porte_texto, porte_fator = calcular_porte_por_potencia(potencia)
                valor_grandeza = potencia
                
            else:
                funcionarios = st.number_input(
                    "Informe o número de funcionários: *",
                    min_value=0,
                    value=10,
                    step=1
                )
                porte_texto, porte_fator = calcular_porte_por_funcionarios(funcionarios)
                valor_grandeza = funcionarios
        
        # Mostrar informação sobre o porte classificado
        st.info(f"🏭 **Porte classificado:** {porte_texto} (Fator: {porte_fator}x)")
        
        st.markdown("---")
        
        # Licença anterior
        st.markdown("### Qual é a sua Licença anterior?")
        st.caption("Opcional - Para renovações ou alterações")
        licenca_anterior = st.text_input(
            "Ex.: 12345678-9 ou 1234567/2013",
            label_visibility="collapsed"
        )
        
        # Distância
        st.markdown("### Distância entre o órgão ambiental e o Empreendimento em quilômetros: *")
        distancia = st.number_input(
            "Distância (km)",
            min_value=0.0,
            value=12.34,
            step=0.01,
            format="%.2f",
            label_visibility="collapsed",
            help=f"Custo de deslocamento: R$ {CUSTO_KM:.2f} por km"
        )
        
        # Unidade de conservação
        st.markdown("### Seu empreendimento se localiza em uma Unidade de Conservação? *")
        st.caption(f"Acréscimo de {ACRESCIMO_UC_PERCENTUAL}% se localizado em UC")
        unidade_conservacao = st.radio(
            "UC",
            options=["Não", "Sim"],
            horizontal=True,
            label_visibility="collapsed"
        ) == "Sim"
    
    with col2:
        st.markdown('<div class="summary-card">', unsafe_allow_html=True)
        st.markdown("### 📊 Resumo da Solicitação")
        st.markdown(f"**Serviço:** {servico_selecionado}")
        st.markdown(f"**Código:** {SERVICOS[servico_selecionado]['codigo']}")
        st.markdown(f"**Porte:** {porte_texto}")
        st.markdown(f"**Grupo:** {grupo_selecionado.split(' - ')[0]}")
        
        if licenca_anterior:
            st.markdown(f"**Licença anterior:** {licenca_anterior}")
        
        st.markdown(f"**Distância:** {distancia:.2f} km")
        st.markdown(f"**Em UC:** {'✅ Sim' if unidade_conservacao else '❌ Não'}")
        st.markdown(f"**{tipo_grandeza.split('(')[0].strip()}:** {valor_grandeza}")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Informações adicionais
        st.markdown('<div class="info-box">', unsafe_allow_html=True)
        st.markdown("### 💡 Informações")
        st.markdown(f"**Valor da UFIR:** R$ {VALOR_UFIR:.2f}")
        st.markdown(f"**Taxa base:** {TAXA_BASE_UFIRS} UFIRs")
        st.markdown(f"**Fator do serviço:** {SERVICOS[servico_selecionado]['fator']}x")
        st.markdown(f"**Fator do porte:** {porte_fator}x")
        st.markdown(f"**Fator do grupo:** {grupo_fator}x")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Botão de cálculo
    st.markdown("---")
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        calcular_btn = st.button("🧮 Calcular Taxa", type="primary", use_container_width=True)
    
    # Cálculo e exibição do resultado
    if calcular_btn:
        resultado = calcular_taxa(
            servico_selecionado,
            porte_fator,
            grupo_fator,
            distancia,
            unidade_conservacao
        )
        
        st.markdown(f"""
            <div class="result-box">
                <h3>💰 Valor Aproximado pelo Serviço</h3>
                <p class="result-value">R$ {resultado['valor_total']:,.2f}</p>
                <hr>
                <h4>📋 Detalhamento do Cálculo:</h4>
                <ul>
                    <li><strong>Taxa Base:</strong> {TAXA_BASE_UFIRS} UFIRs</li>
                    <li><strong>Fator do Serviço ({SERVICOS[servico_selecionado]['codigo']}):</strong> {resultado['fator_servico']}x</li>
                    <li><strong>Fator do Porte ({porte_texto}):</strong> {resultado['fator_porte']}x</li>
                    <li><strong>Fator do Grupo:</strong> {resultado['fator_grupo']}x</li>
                    <li><strong>Acréscimo UC:</strong> {'Sim (+' + str(ACRESCIMO_UC_PERCENTUAL) + '%)' if unidade_conservacao else 'Não'}</li>
                </ul>
                <hr>
                <ul>
                    <li><strong>Total em UFIRs:</strong> {resultado['valor_ufirs']:.2f} UFIRs</li>
                    <li><strong>Valor da UFIR:</strong> R$ {VALOR_UFIR:.2f}</li>
                    <li><strong>Valor da Taxa:</strong> R$ {resultado['valor_taxa_reais']:,.2f}</li>
                    <li><strong>Custo de Deslocamento:</strong> R$ {resultado['custo_deslocamento']:,.2f} ({distancia:.2f} km × R$ {CUSTO_KM:.2f})</li>
                </ul>
                <hr>
                <p style="margin-top: 1rem; font-size: 0.9rem; color: #666;">
                    <strong>⚠️ Importante:</strong> Este é um valor aproximado. Para o valor oficial e detalhes sobre o processo de licenciamento, 
                    consulte a Secretaria Municipal de Meio Ambiente de Ariquemes/RO na aba "Contato".
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        # Botão para gerar relatório (preparado para futura implementação)
        col_rel1, col_rel2, col_rel3 = st.columns([1, 2, 1])
        with col_rel2:
            st.download_button(
                label="📄 Baixar Resumo (TXT)",
                data=f"""
CALCULADORA DE TAXAS DE LICENCIAMENTO AMBIENTAL
MUNICÍPIO DE ARIQUEMES - RONDÔNIA
{'='*60}

DATA DO CÁLCULO: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M:%S')}

DADOS DO EMPREENDIMENTO:
- Serviço Solicitado: {servico_selecionado} ({SERVICOS[servico_selecionado]['codigo']})
- Grupo de Atividade: {grupo_selecionado}
- Atividade Específica: {atividade_selecionada}
- Porte: {porte_texto}
- {tipo_grandeza}: {valor_grandeza}
- Distância do órgão: {distancia:.2f} km
- Em Unidade de Conservação: {'Sim' if unidade_conservacao else 'Não'}
{f'- Licença Anterior: {licenca_anterior}' if licenca_anterior else ''}

CÁLCULO DA TAXA:
- Taxa Base: {TAXA_BASE_UFIRS} UFIRs
- Fator do Serviço: {resultado['fator_servico']}x
- Fator do Porte: {resultado['fator_porte']}x
- Fator do Grupo: {resultado['fator_grupo']}x
- Acréscimo UC: {str(ACRESCIMO_UC_PERCENTUAL) + '%' if unidade_conservacao else 'Não aplicável'}

VALORES:
- Total em UFIRs: {resultado['valor_ufirs']:.2f} UFIRs
- Valor da UFIR: R$ {VALOR_UFIR:.2f}
- Valor da Taxa: R$ {resultado['valor_taxa_reais']:,.2f}
- Custo de Deslocamento: R$ {resultado['custo_deslocamento']:,.2f}

VALOR TOTAL APROXIMADO: R$ {resultado['valor_total']:,.2f}

{'='*60}
OBSERVAÇÃO: Este é um valor aproximado calculado por simulador.
Para valores oficiais, consulte a Secretaria Municipal de Meio 
Ambiente de Ariquemes/RO.

{CONTATO_ORGAO_AMBIENTAL['nome']}
{CONTATO_ORGAO_AMBIENTAL['endereco']}
Telefone: {CONTATO_ORGAO_AMBIENTAL['telefone']}
E-mail: {CONTATO_ORGAO_AMBIENTAL['email']}
Horário: {CONTATO_ORGAO_AMBIENTAL['horario']}
""",
                file_name=f"taxa_licenciamento_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )

with tab2:
    st.markdown("## 📚 Informações sobre o Licenciamento Ambiental")
    
    # Expandable sections
    with st.expander("🔍 O que é o Licenciamento Ambiental?"):
        st.markdown("""
        O licenciamento ambiental é um procedimento administrativo pelo qual o órgão ambiental 
        competente licencia a localização, instalação, ampliação e operação de empreendimentos 
        e atividades utilizadoras de recursos ambientais, consideradas efetiva ou potencialmente 
        poluidoras ou daquelas que, sob qualquer forma, possam causar degradação ambiental.
        """)
    
    with st.expander("📋 Tipos de Licenças"):
        for servico, dados in SERVICOS.items():
            st.markdown(f"**{servico} ({dados['codigo']})**")
            st.markdown(f"- {dados['descricao']}")
            st.markdown(f"- Fator multiplicador: {dados['fator']}x")
            st.markdown("")
    
    with st.expander("🏭 Classificação de Portes"):
        st.markdown("**Por Área Construída:**")
        for porte, config in PORTE_POR_AREA.items():
            if config['area_max'] == float('inf'):
                st.markdown(f"- **{porte}**: Acima de {config['area_min']:.2f} m² (Fator: {config['fator']}x)")
            else:
                st.markdown(f"- **{porte}**: De {config['area_min']:.2f} a {config['area_max']:.2f} m² (Fator: {config['fator']}x)")
        
        st.markdown("\n**Por Potência Instalada:**")
        for porte, config in PORTE_POR_POTENCIA.items():
            if config['potencia_max'] == float('inf'):
                st.markdown(f"- **{porte}**: Acima de {config['potencia_min']:.2f} kW (Fator: {config['fator']}x)")
            else:
                st.markdown(f"- **{porte}**: De {config['potencia_min']:.2f} a {config['potencia_max']:.2f} kW (Fator: {config['fator']}x)")
    
    with st.expander("⚖️ Base Legal"):
        st.markdown(f"""
        {OBSERVACOES_LEGAIS}
        """)

with tab3:
    st.markdown("## 📞 Informações de Contato")
    
    col_cont1, col_cont2 = st.columns(2)
    
    with col_cont1:
        st.markdown(f"""
        ### {CONTATO_ORGAO_AMBIENTAL['nome']}
        
        📍 **Endereço:**  
        {CONTATO_ORGAO_AMBIENTAL['endereco']}
        
        📞 **Telefone:**  
        {CONTATO_ORGAO_AMBIENTAL['telefone']}
        
        📧 **E-mail:**  
        {CONTATO_ORGAO_AMBIENTAL['email']}
        
        🕐 **Horário de Atendimento:**  
        {CONTATO_ORGAO_AMBIENTAL['horario']}
        
        🌐 **Website:**  
        {CONTATO_ORGAO_AMBIENTAL['site']}
        """)
    
    with col_cont2:
        st.markdown("### 📝 Documentação Necessária")
        st.markdown("""
        Para dar início ao processo de licenciamento, geralmente são necessários:
        
        1. Formulário de solicitação preenchido
        2. Cópia do CNPJ ou CPF
        3. Comprovante de propriedade ou posse do imóvel
        4. Planta de localização do empreendimento
        5. Descrição detalhada da atividade
        6. Estudos ambientais (quando aplicável)
        7. Certidões e comprovantes diversos
        
        ⚠️ A documentação pode variar conforme o tipo de atividade e porte do empreendimento.
        Consulte o órgão ambiental para lista completa.
        """)

# Rodapé
st.markdown("---")
st.markdown(f"""
    <div style="text-align: center; color: #666; font-size: 0.9rem; padding: 2rem 0;">
        <p><strong>Calculadora de Taxas de Licenciamento Ambiental - Ariquemes/RO</strong></p>
        <p>Versão {VERSAO_CONFIG} | Última atualização: {DATA_ATUALIZACAO}</p>
        <p>⚠️ Os valores apresentados são estimativas. Consulte sempre o órgão ambiental competente.</p>
    </div>
""", unsafe_allow_html=True)