import streamlit as st
import pandas as pd
from typing import Optional
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

# =============================
# CONFIGURAÇÃO DE ARQUIVOS CSV
# =============================

# CSV com atividades (ANEXO I) já limpo, incluindo colunas *_MIN / *_MAX
ATIVIDADES_CSV_PATH = "ANEXO_I_cleaned_with_portes.csv"

# CSV único com todas as taxas em UFAR (TLP/TLI/TLO)
# colunas esperadas:
#   ANEXO, DESCRICAO, PORTE, POTENCIAL_POLUIDOR, TLP, TLI, TLO
TAXAS_CSV_PATH = "taxas_ambientais_ufar.csv"

# CSV com CNAEs (subclasse, denominacao)
CNAE_CSV_PATH = "IBGE_CNAE_Subclass2.3.csv"


# =============================
# CÁLCULO DE PORTE A PARTIR DE PORTE_*_MIN/MAX
# =============================

def classificar_porte_por_linha_valor(valor: float, linha: pd.Series) -> Optional[str]:
    """
    Classifica o porte com lógica inclusiva para evitar 'buracos' entre faixas.
    """
    spans = [
        ("Mínimo",       "PORTE_MINIMO_MIN",       "PORTE_MINIMO_MAX"),
        ("Pequeno",      "PORTE_PEQUENO_MIN",      "PORTE_PEQUENO_MAX"),
        ("Médio",        "PORTE_MEDIO_MIN",        "PORTE_MEDIO_MAX"),
        ("Grande",       "PORTE_GRANDE_MIN",       "PORTE_GRANDE_MAX"),
        ("Excepcional",  "PORTE_EXCEPCIONAL_MIN",  "PORTE_EXCEPCIONAL_MAX"),
    ]

    for nome, col_min, col_max in spans:
        lo = linha.get(col_min)
        hi = linha.get(col_max)

        # Se ambos são NaN, não há definição para este porte
        if pd.isna(lo) and pd.isna(hi):
            continue

        # Normaliza limites
        limit_lo = 0.0 if pd.isna(lo) else lo
        limit_hi = float('inf') if pd.isna(hi) else hi

        # Lógica de comparação
        if limit_lo == 0.0:
            # Faixa inicial (ex: Até 2): 0 <= valor <= 2
            if valor <= limit_hi:
                return nome
        else:
            # Faixas intermediárias (ex: De 2 até 10)
            # AQUI ESTAVA O ERRO: Mudamos de > para >=
            # Isso garante que se o intervalo começa em 2.0, o valor 2.0 seja aceito.
            if valor >= limit_lo and valor <= limit_hi:
                return nome

    return None


# =============================
# CARREGAMENTO DE TABELAS
# =============================

@st.cache_data
def carregar_tabelas_taxas(caminho_csv: str = TAXAS_CSV_PATH) -> pd.DataFrame:
    """
    Carrega a tabela única de TLP/TLI/TLO em UFAR.

    Espera colunas:
      - ANEXO
      - DESCRICAO
      - PORTE
      - POTENCIAL_POLUIDOR
      - TLP
      - TLI
      - TLO
    """
    try:
        df = pd.read_csv(caminho_csv, dtype=str)

        # Normaliza nomes de colunas (maiúsculas, sem espaços extras)
        df.columns = [c.strip().upper() for c in df.columns]

        # Normaliza campos de filtro
        for col in ["ANEXO", "PORTE", "POTENCIAL_POLUIDOR"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # Garante que colunas TLP/TLI/TLO sejam numéricas (UFAR)
        for col in ["TLP", "TLI", "TLO"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
    except Exception as e:
        st.error(f"Erro ao carregar a tabela de taxas em UFAR ({caminho_csv}): {e}")
        return pd.DataFrame()


@st.cache_data
def carregar_atividades_anexo_i(caminho_csv: str = ATIVIDADES_CSV_PATH) -> pd.DataFrame:
    """Carrega o ANEXO I limpo, tratando separadores brasileiros (semicolon/comma)."""
    try:
        # Tenta ler assumindo o padrão criado pelo script de limpeza (sep=';' e decimal=',')
        df = pd.read_csv(caminho_csv, sep=';', dtype=str)

        # Verificação de segurança: Se carregou tudo em 1 coluna só, tenta o separador padrão
        if df.shape[1] < 2:
            df = pd.read_csv(caminho_csv, sep=',', dtype=str)

        if "ITEM" in df.columns:
            df["ITEM"] = df["ITEM"].astype(str).str.strip()

        for col in ["Atividade", "UNIDADE_DE_MEDIDA", "POTENCIAL_POLUIDOR", "ANEXO_OU_TAXA"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # Converte colunas *_MIN / *_MAX para numérico com tratamento de vírgula
        for col in df.columns:
            if col.endswith("_MIN") or col.endswith("_MAX"):
                # 1. Troca vírgula por ponto (para o Python entender que é decimal)
                # 2. Converte para número
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(",", ".", regex=False)
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo de atividades (ANEXO I): {e}")
        return pd.DataFrame()


@st.cache_data
def carregar_cnaes(caminho_csv: str = CNAE_CSV_PATH) -> pd.DataFrame:
    """Carrega a lista de CNAEs (subclasse, denominacao)."""
    try:
        df = pd.read_csv(caminho_csv, dtype=str)
        # Cria coluna combinada para exibição
        if "subclasse" in df.columns and "denominacao" in df.columns:
            df["DISPLAY"] = df["subclasse"] + " - " + df["denominacao"]
        return df
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo de CNAEs: {e}")
        return pd.DataFrame()


# =============================
# NORMALIZAÇÕES
# =============================

def normalizar_potencial_poluidor(valor: str) -> str:
    """Normaliza o potencial poluidor vindo do CSV (BAIXO/MÉDIO/ALTO) para Baixo/Médio/Alto."""
    if not valor:
        return "Médio"
    v = valor.strip().upper()
    if "BAIX" in v:
        return "Baixo"
    if "MÉD" in v or "MED" in v:
        return "Médio"
    if "ALTO" in v:
        return "Alto"
    return "Médio"


def inferir_tipo_medicao_por_unidade(unidade: str) -> str:
    """Inferir o tipo de medição (area, potencia, funcionarios) a partir do texto da UNIDADE_DE_MEDIDA."""
    if not unidade:
        return "area"
    u = unidade.lower()
    if any(token in u for token in ["hectare", "ha", "m²", "m2", "área", "area"]):
        return "area"
    if any(token in u for token in ["kw", "potência", "potencia"]):
        return "potencia"
    if any(token in u for token in ["funcion", "empregado", "trabalhador", "pessoa"]):
        return "funcionarios"
    # Padrão
    return "area"


# =============================
# MAPAS DE COLUNAS E PORTES
# =============================

# Mapeia o tipo de serviço para a coluna correspondente na tabela de taxas (TLP/TLI/TLO)
TIPO_LICENCA_COLUNA = {
    "Licença Prévia": "TLP",
    "Licença de Instalação": "TLI",
    "Licença de Operação": "TLO",
}

# Mapeia o porte usado na interface para o porte da tabela
MAPEAMENTO_PORTES_TABELA = {
    "Mínimo": "Mínimo",
    "Pequeno": "Pequeno",
    "Médio": "Médio",
    "Grande": "Grande",
    "Excepcional": "Excepcional",
}

# Mapa inverso: porte da tabela -> porte exibido na UI
MAPA_PORTE_TABELA_PARA_APP = {
    "Mínimo": "Mínimo",
    "Pequeno": "Pequeno",
    "Médio": "Médio",
    "Grande": "Grande",
    "Excepcional": "Excepcional",
}


# =============================
# CONFIG DA PÁGINA
# =============================

st.set_page_config(
    page_title="Licenciamento Ambiental - Atenas Projetos Ambientais",
    page_icon="🌿",
    layout="wide"
)

# =============================
# AUTENTICAÇÃO
# =============================

with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

authenticator.login()

if st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password')
    st.stop()

# Se autenticado, mostra botão de logout na sidebar e continua
# Se autenticado, continua
if st.session_state["authentication_status"]:
    # Logout movido para a área principal (será renderizado junto com o cabeçalho)
    pass

# CSS customizado
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
    
    .license-card {
        background-color: #f8fffe;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 3px solid #2d8b6b;
        margin-bottom: 1rem;
    }
    
    .license-title {
        font-size: 1.1rem;
        color: #1e6b52;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .license-value {
        font-size: 1.5rem;
        color: #2d8b6b;
        font-weight: bold;
    }
    
    .info-box {
        background-color: #fffbe6;
        padding: 0.75rem;
        border-radius: 0.3rem;
        border-left: 3px solid #ffa000;
        margin: 1rem 0;
        font-size: 0.95rem;
    }
    
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

    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* Hide GitHub/Viewer Badge */
    .css-1jc7ptx, .e1ewe7hr3, .viewerBadge_container__1QSob,
    .styles_viewerBadge__1yB5_, .viewerBadge_link__1S137,
    .viewerBadge_text__1JaDK {
        display: none;
    }
    
    h3 {
        color: #1e6b52;
        font-family: 'Roboto', sans-serif;
        font-weight: 500;
    }
    
    .summary-title {
        color: #2d8b6b;
        font-family: 'Cinzel', serif;
        font-size: 1.3rem;
        margin-bottom: 1rem;
    }
    
    .pollution-indicator {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 0.3rem;
        font-weight: 600;
        margin-top: 0.5rem;
    }
    
    .pollution-baixo {
        background-color: #c8e6c9;
        color: #1b5e20;
    }
    
    .pollution-medio {
        background-color: #fff9c4;
        color: #f57c00;
    }
    
    .pollution-alto {
        background-color: #ffcdd2;
        color: #c62828;
    }
    
    .step-container {
        display: flex;
        align-items: center;
        margin-bottom: 15px;
        margin-top: 10px;
    }
    
    .step-number {
        background-color: #2d8b6b;
        color: white;
        border-radius: 50%;
        width: 32px;
        height: 32px;
        display: flex;
        justify-content: center;
        align-items: center;
        font-weight: bold;
        margin-right: 12px;
        font-family: 'Roboto', sans-serif;
        font-size: 1rem;
        flex-shrink: 0;
        box-shadow: 0 2px 4px rgba(45, 139, 107, 0.2);
    }
    
    .step-text {
        font-size: 1.15rem;
        color: #1e6b52;
        font-weight: 500;
        font-family: 'Roboto', sans-serif;
    }
    
    .required-asterisk {
        color: #d32f2f;
        margin-left: 4px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)


# =============================
# DADOS FIXOS
# =============================

SERVICOS = {
    "Licença Prévia": {"codigo": "LP", "descricao": "Fase de planejamento do empreendimento"},
    "Licença de Instalação": {"codigo": "LI", "descricao": "Autoriza a instalação do empreendimento"},
    "Licença de Operação": {"codigo": "LO", "descricao": "Autoriza a operação da atividade"},
    }

MUNICIPIOS_CONFIG = {
    "Ariquemes - RO": {"ufir": 85.15, "lei": "Lei 2.349/2019"},
    "Porto Velho - RO": {"ufir": 81.22, "lei": "Lei Municipal"},
}


# =============================
# LÓGICA DE CÁLCULO
# =============================

def obter_taxa_ufar(df_taxas: pd.DataFrame, anexo: str, porte_app: str,
                    potencial_poluidor: str, servico: str) -> float:
    """
    Busca a taxa (em UFAR) na tabela oficial, dado anexo, porte, potencial e tipo de licença,
    usando o CSV único com colunas ANEXO / PORTE / POTENCIAL_POLUIDOR / TLP / TLI / TLO.
    """
    if df_taxas.empty:
        valores_default = {
            "Licença Prévia": 50,
            "Licença de Instalação": 75,
            "Licença de Operação": 60,
        }
        return valores_default.get(servico, 50)

    if servico not in TIPO_LICENCA_COLUNA:
        raise ValueError(f"Serviço não mapeado: {servico}")

    coluna_valor = TIPO_LICENCA_COLUNA[servico]
    porte_tabela = MAPEAMENTO_PORTES_TABELA.get(porte_app, porte_app)

    # Normaliza ANEXO para comparação (ex.: "ANEXO II" == "ANEXOII")
    anexo_norm = (anexo or "").replace(" ", "").upper().strip()

    df_filtrado = df_taxas[
        df_taxas["ANEXO"]
        .str.replace(" ", "", regex=False)
        .str.upper()
        .str.strip()
        .eq(anexo_norm)
        & df_taxas["PORTE"].str.strip().eq(porte_tabela)
        & df_taxas["POTENCIAL_POLUIDOR"].str.strip().str.upper().eq(potencial_poluidor.upper())
    ]

    if df_filtrado.empty:
        valores_default = {
            "Licença Prévia": 50,
            "Licença de Instalação": 75,
            "Licença de Operação": 60,
        }
        return valores_default.get(servico, 50)

    return float(df_filtrado.iloc[0][coluna_valor])


def calcular_taxa(servico: str, porte_nome: str, anexo: str,
                  potencial_poluidor: str, df_taxas: pd.DataFrame,
                  valor_ufir: float) -> tuple[float, float]:
    """Calcula o valor da taxa ambiental com base nas tabelas oficiais (em UFAR)."""
    try:
        valor_ufar = obter_taxa_ufar(
            df_taxas=df_taxas,
            anexo=anexo,
            porte_app=porte_nome,
            potencial_poluidor=potencial_poluidor,
            servico=servico,
        )
    except Exception:
        valores_default = {
            "Licença Prévia": 50,
            "Licença de Instalação": 75,
            "Licença de Operação": 60,
        }
        valor_ufar = valores_default.get(servico, 50)

    valor_reais = valor_ufar * valor_ufir
    return valor_reais, valor_ufar


def render_step_header(number: str, text: str, required: bool = False):
    """Renders a professional step header with HTML/CSS"""
    asterisk = '<span class="required-asterisk">*</span>' if required else ''
    st.markdown(f"""
        <div class="step-container">
            <div class="step-number">{number}</div>
            <div class="step-text">{text}{asterisk}</div>
        </div>
    """, unsafe_allow_html=True)


# =============================
# INTERFACE PRINCIPAL
# =============================

col_logo, col_title, col_logout = st.columns([2, 4, 2])

with col_logo:
    try:
        st.image("atenas.jpeg", width=200)
    except Exception:
        st.markdown("🌿")

with col_title:
    st.markdown('<h1 class="main-title">LICENCIAMENTO AMBIENTAL</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Atenas Projetos Ambientais - Sistema Inteligente de Cálculo</p>',
                unsafe_allow_html=True)

with col_logout:
    st.write(f'Bem-vindo, *{st.session_state["name"]}*')
    authenticator.logout('Logout', 'main')

# Aviso
st.markdown("""
    <div class="warning-box">
        <strong>⚠️ Atenção!</strong> Este simulador utiliza dados oficiais da Lei 2.349/2019 de Ariquemes/RO. 
        O potencial poluidor é determinado automaticamente conforme a legislação vigente. 
        Consulte sempre o órgão ambiental para valores oficiais atualizados.
    </div>
""", unsafe_allow_html=True)

# Abas
if st.session_state["username"] == "admin":
    tab_calc, tab_admin = st.tabs(["Dados", "🔐 ADMIN"])
else:
    # Se não for admin, cria apenas uma aba e define tab_admin como None
    tab_calc = st.tabs(["Dados"])[0]
    tab_admin = None

with tab_calc:
    # Formulário principal
    col1, col2 = st.columns([2, 1])

    with col1:
        # 1. CNPJ ou CPF do Empreendedor
        render_step_header("1", "Informe o CNPJ ou CPF do Empreendedor", required=True)
        cnpj_cpf = st.text_input(
            "CNPJ/CPF",
            placeholder="00.000.000/0000-00 ou 000.000.000-00",
            label_visibility="collapsed"
        )

        # 2. Seleção de CNAEs
        st.write("")  # Spacer
        render_step_header("2", "Atividades Requeridas - selecione apenas o(s) CNAE(s)", required=True)
        
        df_cnaes = carregar_cnaes()
        opcoes_cnaes = df_cnaes["DISPLAY"].tolist() if not df_cnaes.empty else []
        
        cnaes_selecionados = st.multiselect(
            "CNAEs",
            options=opcoes_cnaes,
            label_visibility="collapsed",
            placeholder="Selecione um ou mais CNAEs..."
        )

        # 3. Seleção do município
        st.write("")  # Spacer
        render_step_header("3", "Em qual município está localizado seu empreendimento?", required=True)
        municipio_selecionado = st.selectbox(
            "Município",
            options=list(MUNICIPIOS_CONFIG.keys()),
            index=0,
            label_visibility="collapsed"
        )

        config_municipio = MUNICIPIOS_CONFIG[municipio_selecionado]
        valor_ufir = config_municipio["ufir"]
        lei_referencia = config_municipio["lei"]

        # 4. Seleção do grupo de atividade a partir do ANEXO I
        st.write("")  # Spacer
        render_step_header("4", "Qual o Grupo de sua Atividade?", required=True)

        atividades_df = carregar_atividades_anexo_i()
        if atividades_df.empty:
            st.error("Não foi possível carregar o ANEXO I. Verifique o arquivo CSV limpo.")
            st.stop()

        atividades_df = atividades_df.copy()
        atividades_df["ITEM_STR"] = atividades_df["ITEM"].astype(str).str.strip()
        atividades_df["ITEM_BASE"] = atividades_df["ITEM_STR"].str.split(".").str[0]
        # Grupos = linhas sem ponto (1, 2, 3, ...)
        atividades_df["IS_GRUPO"] = ~atividades_df["ITEM_STR"].str.contains(".", regex=False, na=False)

        grupos_df = atividades_df[atividades_df["IS_GRUPO"]].copy().sort_values("ITEM_BASE")

        if grupos_df.empty:
            st.error("Nenhum grupo encontrado no ANEXO I (linhas com ITEM = 1, 2, 3, ...).")
            st.stop()

        opcoes_grupo = {
            f"{row['ITEM_BASE']} - {row['Atividade']}": row["ITEM_BASE"]
            for _, row in grupos_df.iterrows()
        }

        labels_grupo = list(opcoes_grupo.keys())

        grupo_selecionado_label = st.selectbox(
            "Grupo",
            options=labels_grupo,
            index=0,
            label_visibility="collapsed",
        )

        if not grupo_selecionado_label:
            st.info("Selecione um grupo para continuar.")
            st.stop()

        grupo_base = opcoes_grupo[grupo_selecionado_label]
        grupo_selecionado = grupo_selecionado_label  # para resumo

        # 5. Sub-atividade
        st.write("")  # Spacer
        render_step_header("5", "Qual é a sua Atividade?", required=True)

        sub_df = atividades_df[
            (atividades_df["ITEM_BASE"] == grupo_base) & (~atividades_df["IS_GRUPO"])
        ].copy()

        if sub_df.empty:
            st.error("Não há subatividades para o grupo selecionado no ANEXO I.")
            st.stop()

        opcoes_atividade = sub_df["Atividade"].dropna().tolist()

        atividade_selecionada = st.selectbox(
            "Atividade",
            options=opcoes_atividade,
            label_visibility="collapsed",
        )

        linha_atividade = sub_df[sub_df["Atividade"] == atividade_selecionada].iloc[0]

        # UNIDADE_DE_MEDIDA, POTENCIAL_POLUIDOR e ANEXO diretamente do CSV
        unidade_medida = str(linha_atividade.get("UNIDADE_DE_MEDIDA", "") or "").strip()
        potencial_raw = str(linha_atividade.get("POTENCIAL_POLUIDOR", "") or "").strip()
        potencial_poluidor = normalizar_potencial_poluidor(potencial_raw)
        anexo_selecionado = str(linha_atividade.get("ANEXO_OU_TAXA", "") or "").strip() or "ANEXO II"

        # Infere tipo de medição
        tipo_medicao = inferir_tipo_medicao_por_unidade(unidade_medida)

        # Exibe potencial poluidor
        if potencial_poluidor == "Baixo":
            pollution_class = "pollution-baixo"
        elif potencial_poluidor == "Alto":
            pollution_class = "pollution-alto"
        else:
            pollution_class = "pollution-medio"

        st.markdown(
            f"""
            <div class="info-box">
                <strong>🔍 Potencial Poluidor Detectado:</strong> 
                <span class="pollution-indicator {pollution_class}">{potencial_poluidor}</span>
                <br><small>Classificação conforme Lei 2.349/2019 - Anexo I (tabela oficial).</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # 6. Medida do empreendimento (campo baseado na UNIDADE_DE_MEDIDA)
        render_step_header("6", "Informe a medida do seu empreendimento:", required=True)

        if tipo_medicao == "area":
            valor_medida = st.number_input(
                unidade_medida or "Informe a área (ex.: hectares): *",
                min_value=0.0,
                value=0.0,
                step=1.0,
                format="%.2f",
                help=f"Unidade de medida: {unidade_medida}" if unidade_medida else None,
            )
        elif tipo_medicao == "potencia":
            valor_medida = st.number_input(
                unidade_medida or "Informe a potência instalada (kW): *",
                min_value=0.0,
                value=0.0,
                step=1.0,
                format="%.2f",
                help=f"Unidade de medida: {unidade_medida}" if unidade_medida else None,
            )
        else:  # funcionarios
            valor_medida = st.number_input(
                unidade_medida or "Informe o número de funcionários: *",
                min_value=0,
                value=0,
                step=1,
                help=f"Unidade de medida: {unidade_medida}" if unidade_medida else None,
            )

        # Classifica o porte usando ANEXO I (PORTE_*_MIN/MAX)
        porte_encontrado = classificar_porte_por_linha_valor(float(valor_medida), linha_atividade)
        
        if porte_encontrado is None:
            porte_texto = "Não Definido"
            st.error(f"⚠️ Não foi possível determinar o porte para a medida {valor_medida}. Verifique se o valor está dentro das faixas do Anexo I.")
        else:
            porte_texto = MAPA_PORTE_TABELA_PARA_APP.get(porte_encontrado, porte_encontrado)

        # Texto amigável para o resumo lateral
        if unidade_medida:
            medida_texto = f"{valor_medida} ({unidade_medida})"
        else:
            medida_texto = f"{valor_medida}"

    with col2:
        st.markdown('<p class="summary-title">📊 Resumo da Solicitação</p>', unsafe_allow_html=True)
        st.markdown(f"**CNPJ/CPF:** {cnpj_cpf if cnpj_cpf else 'Não informado'}")
        
        if cnaes_selecionados:
            cnaes_str = "; ".join(cnaes_selecionados)
            # Trunca se for muito longo para não quebrar o layout
            if len(cnaes_str) > 100:
                cnaes_display = cnaes_str[:100] + "..."
            else:
                cnaes_display = cnaes_str
            st.markdown(f"**CNAEs:** {cnaes_display}")
        else:
            st.markdown("**CNAEs:** Não selecionado")

        st.markdown(f"**Município:** {municipio_selecionado}")
        st.markdown(f"**Grupo:** {grupo_selecionado}")
        st.markdown(f"**Atividade:** {atividade_selecionada}")
        st.markdown(f"**Medida:** {medida_texto}")
        st.markdown(f"**Porte:** {porte_texto}")

        pollution_colors = {
            "Baixo": "#4caf50",
            "Médio": "#ff9800",
            "Alto": "#f44336"
        }
        st.markdown(f"""
            <div style="margin: 1rem 0;">
                <strong>Potencial Poluidor:</strong>
                <div style="background: {pollution_colors.get(potencial_poluidor, '#999')}; 
                            color: white; padding: 0.5rem; border-radius: 0.3rem; 
                            text-align: center; margin-top: 0.5rem; font-weight: bold;">
                    {potencial_poluidor}
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"**Valor UFIR:** R$ {valor_ufir:.2f}")
        st.markdown(f"**Legislação:** {lei_referencia}")

    # =============================
    # CÁLCULO DAS TAXAS
    # =============================

    st.markdown("---")

    if st.button("🧮 CALCULAR TAXAS", type="primary", width="stretch"):
        if not cnpj_cpf:
            st.error("⚠️ Por favor, informe o CNPJ ou CPF do empreendedor.")
            st.stop()

        if not cnaes_selecionados:
            st.error("⚠️ Por favor, selecione pelo menos um CNAE.")
            st.stop()

        if valor_medida <= 0:
            st.error("⚠️ Por favor, informe as medidas do seu empreendimento antes de calcular as taxas.")
            st.stop()
            
        if porte_texto == "Não Definido":
            st.error("⚠️ Impossível calcular: O porte não foi identificado para a medida informada.")
            st.stop()
        
        df_taxas = carregar_tabelas_taxas()

        st.markdown(f"""
            <div class="result-box">
                <h3>💰 Valores das Taxas de Licenciamento Ambiental</h3>
                <p><strong>Empreendedor (CNPJ/CPF):</strong> {cnpj_cpf}</p>
                <p><strong>CNAEs:</strong> {len(cnaes_selecionados)} selecionado(s)</p>
                <p><strong>Empreendimento:</strong> {atividade_selecionada}</p>
                <p><strong>Município:</strong> {municipio_selecionado} | 
                   <strong>Porte:</strong> {porte_texto} | 
                   <strong>Potencial Poluidor:</strong> <span class="pollution-indicator pollution-{potencial_poluidor.lower()}">{potencial_poluidor}</span></p>
                <hr>
            </div>
        """, unsafe_allow_html=True)

        col_lic1, col_lic2 = st.columns(2)
        todos_valores = {}

        for i, (servico, info) in enumerate(SERVICOS.items()):
            valor_total, valor_ufars = calcular_taxa(
                servico=servico,
                porte_nome=porte_texto,
                anexo=anexo_selecionado,
                potencial_poluidor=potencial_poluidor,
                df_taxas=df_taxas,
                valor_ufir=valor_ufir
            )

            todos_valores[servico] = {
                "valor_reais": valor_total,
                "valor_ufar": valor_ufars,
                "codigo": info["codigo"],
                "descricao": info["descricao"]
            }

            card_html = f"""
                <div class="license-card">
                    <div class="license-title">{info['codigo']} - {servico}</div>
                    <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">{info['descricao']}</div>
                    <div class="license-value">R$ {valor_total:,.2f}</div>
                    <div style="font-size: 0.85rem; color: #999;">Taxa base: {valor_ufars:.2f} UFARs</div>
                </div>
            """

            if i < 3:
                with col_lic1:
                    st.markdown(card_html, unsafe_allow_html=True)
            else:
                with col_lic2:
                    st.markdown(card_html, unsafe_allow_html=True)

        st.markdown("---")
        valor_total_todas = sum(v["valor_reais"] for v in todos_valores.values())

        st.markdown(f"""
            <div style="background-color: #e3f2fd; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #2196f3; margin-bottom: 1rem;">
                <h4>ℹ️ Sobre o Potencial Poluidor</h4>
                <p>O potencial poluidor <strong>{potencial_poluidor}</strong> foi determinado automaticamente com base na 
                atividade <em>"{atividade_selecionada}"</em>, conforme estabelecido no <strong>Anexo I da Lei Municipal 2.349/2019</strong>.</p>
                <p style="font-size: 0.9rem; margin-top: 0.5rem;">Esta classificação afeta diretamente o valor das taxas de licenciamento.</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div style="background-color: #fff3e0; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #ff9800;">
                <h4>📌 Resumo Total</h4>
                <p><strong>Valor total se todas as licenças fossem solicitadas:</strong> 
                   <span style="font-size: 1.3rem; color: #ff6f00;">R$ {valor_total_todas:,.2f}</span></p>
                <p style="font-size: 0.9rem; color: #666; margin-top: 1rem;">
                    <strong>Observação:</strong> Normalmente, as licenças são solicitadas em sequência (LP → LI → LO), 
                    não todas de uma vez. Este é um valor aproximado baseado nas tabelas oficiais da lei municipal.
                </p>
                <p style="font-size: 0.9rem; color: #666; margin-top: 0.5rem;">
                    <strong>As taxas ambientais podem ser parceladas em até 6 vezes no boleto.</strong>
                </p>
            </div>
        """, unsafe_allow_html=True)

        # =============================
        # GERAÇÃO DE PDF
        # =============================
        from fpdf import FPDF
        import tempfile

        class PDF(FPDF):
            def header(self):
                # Logo
                try:
                    self.image('atenas.jpeg', 10, 8, 33)
                except:
                    pass
                self.set_font('Arial', 'B', 15)
                self.cell(80)
                self.cell(30, 10, 'Calculadora de Taxas Ambientais', 0, 0, 'C')
                self.ln(20)

            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, 'Atenas Projetos Ambientais - Página ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

        def gerar_pdf(municipio, grupo, atividade, medida, porte, potencial, ufir, valores, cnpj_cpf, cnaes_list):
            pdf = PDF()
            pdf.alias_nb_pages()
            pdf.add_page()
            pdf.ln(10)
            pdf.set_font('Arial', '', 12)

            # Dados do Empreendimento
            pdf.set_fill_color(200, 220, 255)
            pdf.cell(0, 10, 'Dados do Empreendimento', 0, 1, 'L', 1)
            pdf.ln(5)
            
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(40, 10, 'CNPJ/CPF:', 0, 0)
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 10, cnpj_cpf, 0, 1)

            pdf.set_font('Arial', 'B', 10)
            pdf.cell(40, 10, 'CNAEs:', 0, 0)
            pdf.set_font('Arial', '', 10)
            # Multi-cell para CNAEs pois pode ser longo
            cnaes_text = "; ".join(cnaes_list)
            pdf.multi_cell(0, 10, cnaes_text)

            pdf.set_font('Arial', 'B', 10)
            pdf.cell(40, 10, 'Município:', 0, 0)
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 10, municipio, 0, 1)

            pdf.set_font('Arial', 'B', 10)
            pdf.cell(40, 10, 'Grupo:', 0, 0)
            pdf.set_font('Arial', '', 10)
            pdf.multi_cell(0, 10, grupo)

            pdf.set_font('Arial', 'B', 10)
            pdf.cell(40, 10, 'Atividade:', 0, 0)
            pdf.set_font('Arial', '', 10)
            pdf.multi_cell(0, 10, atividade)

            pdf.set_font('Arial', 'B', 10)
            pdf.cell(40, 10, 'Medida:', 0, 0)
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 10, medida, 0, 1)

            pdf.set_font('Arial', 'B', 10)
            pdf.cell(40, 10, 'Porte:', 0, 0)
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 10, porte, 0, 1)

            pdf.set_font('Arial', 'B', 10)
            pdf.cell(40, 10, 'Potencial Poluidor:', 0, 0)
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 10, potencial, 0, 1)
            
            pdf.ln(10)

            # Valores
            pdf.set_font('Arial', '', 12)
            pdf.set_fill_color(200, 220, 255)
            pdf.cell(0, 10, 'Valores Estimados das Taxas', 0, 1, 'L', 1)
            pdf.ln(5)

            pdf.set_font('Arial', 'B', 10)
            pdf.cell(60, 10, 'Licença', 1, 0, 'C')
            pdf.cell(40, 10, 'Valor (UFAR)', 1, 0, 'C')
            pdf.cell(40, 10, 'Valor (R$)', 1, 0, 'C')
            pdf.ln()

            pdf.set_font('Arial', '', 10)
            total = 0
            for servico, dados in valores.items():
                pdf.cell(60, 10, f"{dados['codigo']} - {servico}", 1, 0)
                pdf.cell(40, 10, f"{dados['valor_ufar']:.2f}", 1, 0, 'R')
                pdf.cell(40, 10, f"R$ {dados['valor_reais']:,.2f}", 1, 0, 'R')
                pdf.ln()
                total += dados['valor_reais']

            pdf.ln(5)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(100, 10, 'Total Estimado:', 0, 0, 'R')
            pdf.cell(40, 10, f"R$ {total:,.2f}", 0, 1, 'R')

            pdf.ln(10)
            pdf.set_font('Arial', 'I', 8)
            pdf.multi_cell(0, 5, 'Observação: Os valores são estimativas baseadas na legislação municipal. O valor final pode variar conforme análise técnica do órgão ambiental. As taxas podem ser parceladas em até 6 vezes.')

            return pdf.output(dest='S').encode('latin-1')

        # Botão de Download
        st.write("")
        col_dl1, col_dl2, col_dl3 = st.columns([1, 2, 1])
        with col_dl2:
            pdf_bytes = gerar_pdf(
                municipio_selecionado,
                grupo_selecionado,
                atividade_selecionada,
                medida_texto,
                porte_texto,
                potencial_poluidor,
                valor_ufir,
                todos_valores,
                cnpj_cpf,
                cnaes_selecionados
            )
            
            st.download_button(
                label="📄 BAIXAR RESUMO EM PDF",
                data=pdf_bytes,
                file_name="resumo_taxas_ambiental.pdf",
                mime="application/pdf",
                width="stretch"
            )

        # =============================
        # SALVAR NO BANCO DE DADOS
        # =============================
        import database
        
        # Inicializa o banco se necessário
        database.init_db()
        
        # Salva o cálculo
        database.salvar_calculo(
            municipio=municipio_selecionado,
            grupo=grupo_selecionado,
            atividade=atividade_selecionada,
            medida=medida_texto,
            porte=porte_texto,
            potencial=potencial_poluidor,
            valor_total=valor_total_todas,
            cnpj_cpf=cnpj_cpf,
            cnaes="; ".join(cnaes_selecionados)
        )
        st.success("✅ Cálculo salvo no histórico com sucesso!")

# =============================
# HISTÓRICO / AUDITORIA (ADMIN)
# =============================
if tab_admin:
    with tab_admin:
        st.header("📂 Histórico de Cálculos (Auditoria)")
        
        import database
        database.init_db()
        df_history = database.listar_calculos()
        
        if not df_history.empty:
            st.dataframe(df_history, width="stretch")
            
            csv = df_history.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Baixar Histórico (CSV)",
                data=csv,
                file_name="historico_calculos.csv",
                mime="text/csv",
            )
        else:
            st.info("Nenhum cálculo registrado ainda.")

# Rodapé
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem; padding: 2rem 0;">
        <p><strong>Calculadora de Taxas de Licenciamento Ambiental</strong></p>
        <p>Atenas Projetos Ambientais | Versão 3.2 | 2025</p>
        <p>Sistema com detecção automática de potencial poluidor conforme Lei 2.349/2019</p>
        <p>⚠️ Os valores apresentados são estimativas. Consulte sempre o órgão ambiental competente.</p>
    </div>
""", unsafe_allow_html=True)
