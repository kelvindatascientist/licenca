import streamlit as st
import pandas as pd
from typing import Optional
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import re
import unicodedata
from difflib import SequenceMatcher

# =============================
# CONFIGURAÇÃO DE ARQUIVOS CSV
# =============================

# CSV com atividades (ANEXO I) já limpo, incluindo colunas *_MIN / *_MAX
ATIVIDADES_CSV_PATH = "ANEXO_I_cleaned_with_portes.csv"

# CSV único com todas as taxas em UFAR (TLP/TLI/TLO)
# colunas esperadas:
#   ANEXO, DESCRICAO, PORTE, POTENCIAL_POLUIDOR, TLP, TLI, TLO
TAXAS_CSV_PATH = "taxas_ambientais_ufar.csv"
TAXAS_SEDAM_CSV_PATH = "taxas_sedam_upfs_ground_truth_clean.csv"

# CSV com CNAEs (subclasse, denominacao)
CNAE_CSV_PATH = "IBGE_CNAE_Subclass2.3.csv"

# Planilha com atividades LAS e CNAEs
LAS_XLSX_PATH = "Lista de atividades LAS E CNAES.xlsx"

# Segurança do mapeamento automático CNAE -> Atividade.
# Quanto maior, menor risco de falso positivo.
SCORE_MINIMO_MAPEAMENTO_CNAE = 0.75

# Exceções manuais: CNAE normalizado -> atividade exata no Anexo I.
# Use quando o matcher de similaridade não encontra a correspondência correta.
EXCECOES_MAPEAMENTO_CNAE = {
    # 4543-9/00 (motocicletas/motonetas) mapeia para oficina mecânica de veículos automotores
    "4543900": "Manutenção e reparação de veículos automotores (oficina mecânica)",
}


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

        # Compatibilidade com arquivos legados em minúsculas/nomes alternativos
        renomear = {
            "DESCRICAO_TABELA": "DESCRICAO",
            "TLP_UPFS": "TLP",
            "TLI_UPFS": "TLI",
            "TLO_UPFS": "TLO",
        }
        df = df.rename(columns={k: v for k, v in renomear.items() if k in df.columns})

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


def carregar_tabela_las(caminho_xlsx: str = LAS_XLSX_PATH) -> pd.DataFrame:
    """Carrega a planilha LAS com colunas de CNAE e descrição da tabela LAS."""
    try:
        df = pd.read_excel(caminho_xlsx, dtype=str)
        df.columns = [c.strip() for c in df.columns]
        return df.fillna("")
    except Exception as e:
        st.error(f"Erro ao carregar a planilha LAS ({caminho_xlsx}): {e}")
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


def classe_potencial_poluidor(valor: str) -> str:
    """Converte o potencial para sufixo CSS sem acentos: baixo|medio|alto."""
    v = normalizar_texto(valor)
    if "baixo" in v:
        return "baixo"
    if "alto" in v:
        return "alto"
    if "medio" in v:
        return "medio"
    return ""


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


def normalizar_texto(texto: str) -> str:
    """Remove acentos e caracteres não alfanuméricos para comparação textual."""
    if texto is None:
        return ""
    s = str(texto).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalizar_cnae_codigo(codigo: str) -> str:
    """
    Normaliza CNAE para comparação.
    Trata variações como 1099-6/4 e 1099-6/04 como equivalentes.
    """
    s = str(codigo or "").strip()

    # Tenta extrair no formato canônico XXXX-X/XX
    m = re.search(r"(\d{4})\D*(\d)\D*(\d{1,2})", s)
    if m:
        base, dv, sub = m.groups()
        return f"{base}{dv}{sub.zfill(2)}"

    # Fallback por dígitos
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 6:
        return digits[:5] + digits[5:].zfill(2)
    return digits


def extrair_codigo_cnae_display(display: str) -> str:
    """Extrai o código CNAE do formato '0000-0/00 - descrição'."""
    if not display:
        return ""
    return str(display).split(" - ", 1)[0].strip()


def sanitizar_cnpj_cpf_input():
    """Permite apenas números e separadores válidos para CNPJ/CPF."""
    valor = st.session_state.get("cnpj_cpf_input", "")
    valor_limpo = re.sub(r"[^0-9./-]", "", str(valor))
    if valor_limpo != valor:
        st.session_state["cnpj_cpf_input"] = valor_limpo


def preparar_atividades(df_atividades: pd.DataFrame) -> pd.DataFrame:
    """Prepara dataframe do Anexo I com flags de grupo/subatividade."""
    df = df_atividades.copy()
    df["ITEM_STR"] = df["ITEM"].astype(str).str.strip()
    df["ITEM_BASE"] = df["ITEM_STR"].str.split(".").str[0]
    df["IS_GRUPO"] = ~df["ITEM_STR"].str.contains(".", regex=False, na=False)
    return df


def mapear_cnaes_para_atividades(
    cnaes_selecionados: list[str], df_cnaes: pd.DataFrame, atividades_df: pd.DataFrame
) -> list[dict]:
    """Mapeia cada CNAE selecionado para uma atividade do Anexo I por similaridade textual."""
    if not cnaes_selecionados or df_cnaes.empty or atividades_df.empty:
        return []

    atividades_sub = atividades_df[~atividades_df["IS_GRUPO"]].copy()
    grupos_df = atividades_df[atividades_df["IS_GRUPO"]].copy()
    atividades_sub["ATIVIDADE_NORM"] = atividades_sub["Atividade"].astype(str).map(normalizar_texto)

    cnae_map = {}
    if {"subclasse", "denominacao"}.issubset(df_cnaes.columns):
        for _, row in df_cnaes.iterrows():
            cnae_map[normalizar_cnae_codigo(row["subclasse"])] = str(row["denominacao"])

    resultados = []
    for display in cnaes_selecionados:
        codigo = extrair_codigo_cnae_display(display)
        codigo_norm = normalizar_cnae_codigo(codigo)
        denominacao = cnae_map.get(codigo_norm, "")
        den_norm = normalizar_texto(denominacao)

        # Verificar exceções manuais antes de recorrer à similaridade
        excecao_atividade = EXCECOES_MAPEAMENTO_CNAE.get(codigo_norm)
        if excecao_atividade:
            match = atividades_sub[atividades_sub["Atividade"] == excecao_atividade]
            if not match.empty:
                melhor_idx = match.index[0]
                melhor_score = 1.0
            else:
                melhor_idx = None
                melhor_score = 0.0
        else:
            melhor_idx = None
            melhor_score = 0.0
            for idx, row in atividades_sub.iterrows():
                atividade_norm = row["ATIVIDADE_NORM"]
                if not den_norm or not atividade_norm:
                    score = 0.0
                elif den_norm in atividade_norm or atividade_norm in den_norm:
                    score = 1.0
                else:
                    score = SequenceMatcher(None, den_norm, atividade_norm).ratio()

                if score > melhor_score:
                    melhor_score = score
                    melhor_idx = idx

        mapeado = melhor_idx is not None and melhor_score >= SCORE_MINIMO_MAPEAMENTO_CNAE
        atividade = ""
        grupo = ""
        item_base = ""
        potencial = ""
        anexo = ""
        unidade = ""

        if mapeado:
            linha = atividades_sub.loc[melhor_idx]
            item_base = str(linha["ITEM_BASE"])
            atividade = str(linha["Atividade"])
            potencial = normalizar_potencial_poluidor(str(linha.get("POTENCIAL_POLUIDOR", "") or ""))
            anexo = str(linha.get("ANEXO_OU_TAXA", "") or "").strip() or "ANEXO II"
            unidade = str(linha.get("UNIDADE_DE_MEDIDA", "") or "").strip()
            grupo_row = grupos_df[grupos_df["ITEM_BASE"] == item_base]
            if not grupo_row.empty:
                grupo = f"{item_base} - {grupo_row.iloc[0]['Atividade']}"

        resultados.append(
            {
                "cnae_display": display,
                "cnae_codigo": codigo,
                "cnae_denominacao": denominacao,
                "mapeado": mapeado,
                "score": round(melhor_score, 3),
                "grupo": grupo,
                "item_base": item_base,
                "atividade": atividade,
                "potencial": potencial,
                "anexo": anexo,
                "unidade": unidade,
            }
        )

    return resultados


def verificar_cnaes_em_las(cnaes_selecionados: list[str], df_las: pd.DataFrame) -> tuple[bool, list[dict]]:
    """Retorna se algum CNAE está na lista LAS e os matches encontrados."""
    if not cnaes_selecionados or df_las.empty:
        return False, []

    colunas = list(df_las.columns)
    col_cnae = next((c for c in colunas if normalizar_texto(c) == "codigo cnae"), None)
    if not col_cnae and colunas:
        col_cnae = colunas[0]  # coluna A
    if not col_cnae:
        return False, []

    col_item = next((c for c in colunas if normalizar_texto(c) == "item"), None)
    if not col_item and len(colunas) >= 3:
        col_item = colunas[2]  # coluna C

    col_tabela = next((c for c in colunas if "tabela las" in normalizar_texto(c)), None)
    if not col_tabela and len(colunas) >= 4:
        col_tabela = colunas[3]  # coluna D

    cnaes_las_map = {}
    for _, row in df_las.iterrows():
        codigo_norm = normalizar_cnae_codigo(row[col_cnae])
        item_val = str(row[col_item]).strip() if col_item else ""
        tabela_val = str(row[col_tabela]).strip() if col_tabela else ""
        if item_val.lower() == "nan":
            item_val = ""
        if tabela_val.lower() == "nan":
            tabela_val = ""
        # Regra: só considera LAS quando houver item associado (coluna C) e tabela LAS (coluna D).
        if codigo_norm and item_val and tabela_val:
            cnaes_las_map[codigo_norm] = {"item": item_val, "atividade_las": tabela_val}

    matches = []
    for display in cnaes_selecionados:
        codigo = extrair_codigo_cnae_display(display)
        codigo_norm = normalizar_cnae_codigo(codigo)
        if codigo_norm in cnaes_las_map:
            matches.append(
                {
                    "cnae_display": display,
                    "cnae_codigo": codigo,
                    "item_las": cnaes_las_map[codigo_norm]["item"],
                    "atividade_las": cnaes_las_map[codigo_norm]["atividade_las"],
                }
            )

    return len(matches) > 0, matches


def calcular_enquadramento_final(
    municipio: str,
    possui_mapeamento_cnae: bool,
    potencial_poluidor: str,
    possui_cnae_las: bool,
) -> tuple[dict, bool]:
    """
    Ponto único da decisão final de enquadramento.
    Regra LAS: CNAE na planilha LAS (coluna A) com Item (C) e Tabela LAS (D) preenchidos.
    """
    las_aplicavel = possui_cnae_las
    if las_aplicavel:
        return (
            {"enquadramento": "LAS", "orgao": "SEMA", "tipo_licenca": "Licença Simplificada"},
            True,
        )

    # Fora da condição LAS, segue fluxo normal.
    return (
        definir_enquadramento(
            municipio=municipio,
            possui_mapeamento_cnae=possui_mapeamento_cnae,
            potencial_poluidor=potencial_poluidor,
            is_las=False,
        ),
        False,
    )


def definir_enquadramento(
    municipio: str,
    possui_mapeamento_cnae: bool,
    potencial_poluidor: str,
    is_las: bool,
) -> dict:
    """
    Define enquadramento final e órgão.
    Regra adotada para conflito: potencial Médio e Alto seguem SEDAM; Baixo segue SEMA.
    """
    if municipio != "Ariquemes - RO":
        if is_las:
            return {"enquadramento": "LAS", "orgao": "SEMA", "tipo_licenca": "Licença Simplificada"}
        return {"enquadramento": "LP/LI/LO", "orgao": "SEMA", "tipo_licenca": "LP/LI/LO"}

    # LAS tem prioridade sobre as demais regras.
    if is_las:
        return {"enquadramento": "LAS", "orgao": "SEMA", "tipo_licenca": "Licença Simplificada"}

    if not possui_mapeamento_cnae:
        return {"enquadramento": "Dispensa", "orgao": "SEMA", "tipo_licenca": "Dispensa"}

    if potencial_poluidor == "Baixo":
        return {"enquadramento": "LP/LI/LO", "orgao": "SEMA", "tipo_licenca": "LP/LI/LO"}

    return {"enquadramento": "LP/LI/LO", "orgao": "SEDAM", "tipo_licenca": "LP/LI/LO"}


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
# EMAIL DE FEEDBACK
# =============================

def _get_secret(key, default=""):
    """Lê um segredo do st.secrets (Streamlit Cloud) ou os.environ (local)."""
    import os
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)


def enviar_email_feedback(calculo_id, motivo, municipio, atividade, cnpj_cpf, usuario_nome, usuario_login, detalhes_calculo=None):
    """Envia um e-mail de notificação de feedback para kelvinpac@gmail.com.
    Streamlit Cloud: adicione SMTP_USER e SMTP_PASS em Settings > Secrets (formato TOML).
    Local: defina as mesmas variáveis no arquivo .env ou no ambiente.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = _get_secret("SMTP_HOST") or "smtp.gmail.com"
    smtp_port = int(_get_secret("SMTP_PORT") or "587")
    smtp_user = _get_secret("SMTP_USER")
    smtp_pass = _get_secret("SMTP_PASS")

    if not smtp_user or not smtp_pass:
        return False, "SMTP não configurado (defina SMTP_USER e SMTP_PASS)."

    destinatario = "kelvinpac@gmail.com"

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = destinatario
    msg["Subject"] = f"[Feedback] Discordância no Cálculo #{calculo_id} — {municipio}"

    d = detalhes_calculo or {}

    # Build fee lines
    valores_linhas = ""
    todos_valores = d.get("todos_valores", {})
    if todos_valores:
        for servico, dados in todos_valores.items():
            valores_linhas += (
                f"  {servico}: {dados.get('valor_ufar', 0):.2f} UFAR/UPFS"
                f" = R$ {dados.get('valor_reais', 0):.2f}\n"
            )
    else:
        valores_linhas = "  (não disponível)\n"

    corpo = f"""Feedback de Discordância Recebido
===========================================
ID do Cálculo : {calculo_id}
Município     : {municipio}
Atividade     : {atividade}
CNPJ/CPF      : {cnpj_cpf}
Usuário       : {usuario_nome} ({usuario_login})

--- VARIÁVEIS SELECIONADAS ---
Grupo / Setor         : {d.get('grupo', '-')}
CNAEs selecionados    : {d.get('cnaes', '-')}
Medida informada      : {d.get('medida', '-')}

--- VARIÁVEIS CALCULADAS ---
Porte                 : {d.get('porte', '-')}
Potencial Poluidor    : {d.get('potencial', '-')}
Enquadramento         : {d.get('enquadramento', '-')}
Órgão responsável     : {d.get('orgao', '-')}
Tipo de Licença       : {d.get('tipo_licenca', '-')}
Valor UFIR municipal  : R$ {d.get('valor_ufir', 0):.2f}
Valor Total           : R$ {d.get('valor_total', 0):.2f}

Detalhamento das Taxas:
{valores_linhas}
--- MOTIVO DA DISCORDÂNCIA ---
{motivo}
"""
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, destinatario, msg.as_string())
        return True, ""
    except Exception as exc:
        return False, str(exc)


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
    st.error('Nome de usuário ou senha incorretos.')
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.warning('Por favor, insira seu nome de usuário e senha.')
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
    .stDeployButton {display:none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    button[kind="headerNoPadding"] {display: none !important;}
    /* Streamlit Cloud: viewer badge (profile photo) and manage-app crown button */
    [data-testid="stViewerBadge"] {display: none !important;}
    [data-testid="manage-app-button"] {display: none !important;}
    .stCloudBadge {display: none !important;}
    #stDecoration {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    div[class*="managedApp"] {display: none !important;}

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

    .enq-badge {
        display: inline-block;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.92rem;
        letter-spacing: 0.3px;
        border: 1px solid transparent;
        vertical-align: middle;
    }

    .enq-las {
        background: linear-gradient(135deg, #eafaf3 0%, #d6f5e7 100%);
        color: #0f6d49;
        border-color: #2d8b6b;
        box-shadow: 0 1px 4px rgba(45, 139, 107, 0.2);
    }

    .enq-default {
        background-color: #edf2f7;
        color: #2d3748;
        border-color: #cbd5e0;
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
        # Alguns anexos especiais usam PORTE "-" (valor único por potencial).
        df_filtrado = df_taxas[
            df_taxas["ANEXO"]
            .str.replace(" ", "", regex=False)
            .str.upper()
            .str.strip()
            .eq(anexo_norm)
            & df_taxas["PORTE"].str.strip().eq("-")
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
    tab_calc, tab_admin = st.tabs(["🌿 Cálculo de Taxas", "🔐 ADMIN"])
else:
    # Se não for admin, cria apenas uma aba e define tab_admin como None
    tab_calc = st.tabs(["🌿 Cálculo de Taxas"])[0]
    tab_admin = None

with tab_calc:
    # Formulário principal (full width)
    col1 = st.container()

    with col1:
        # 1. CNPJ ou CPF do Empreendedor
        render_step_header("1", "Informe o CNPJ ou CPF do Empreendedor", required=True)
        cnpj_cpf = st.text_input(
            "CNPJ/CPF",
            placeholder="00.000.000/0000-00 ou 000.000.000-00",
            label_visibility="collapsed",
            key="cnpj_cpf_input",
            on_change=sanitizar_cnpj_cpf_input
        )

        # 1.1 Dados opcionais de contato
        st.write("")  # Spacer
        render_step_header("1.1", "Qual seu email? (opcional)", required=False)
        email_contato = st.text_input(
            "Email",
            placeholder="nome@empresa.com",
            label_visibility="collapsed"
        )

        st.write("")  # Spacer
        render_step_header("1.2", "Qual seu telefone? (opcional)", required=False)
        telefone_contato = st.text_input(
            "Telefone",
            placeholder="(69) 99999-9999",
            label_visibility="collapsed"
        )

        # 2. Seleção de CNAEs
        st.write("")  # Spacer
        render_step_header("2", "Atividades Requeridas - selecione o CNAE", required=True)
        
        df_cnaes = carregar_cnaes()
        opcoes_cnaes = df_cnaes["DISPLAY"].tolist() if not df_cnaes.empty else []
        
        cnae_selecionado = st.selectbox(
            "CNAEs",
            options=opcoes_cnaes,
            index=None,
            label_visibility="collapsed",
            placeholder="Digite para buscar e selecione um CNAE..."
        )
        cnaes_selecionados = [cnae_selecionado] if cnae_selecionado else []

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

        # Grupo/atividade seguem automáticos (não exibidos no formulário principal)

        atividades_df = carregar_atividades_anexo_i()
        if atividades_df.empty:
            st.error("Não foi possível carregar o ANEXO I. Verifique o arquivo CSV limpo.")
            st.stop()

        atividades_df = preparar_atividades(atividades_df)

        grupos_df = atividades_df[atividades_df["IS_GRUPO"]].copy().sort_values("ITEM_BASE")

        if grupos_df.empty:
            st.error("Nenhum grupo encontrado no ANEXO I (linhas com ITEM = 1, 2, 3, ...).")
            st.stop()

        # Mapeamento automático de CNAE -> Atividade/Grupo (foco Ariquemes)
        mapeamentos_cnae = mapear_cnaes_para_atividades(cnaes_selecionados, df_cnaes, atividades_df)
        mapeados_validos = [m for m in mapeamentos_cnae if m["mapeado"]]
        melhor_mapeamento = max(mapeados_validos, key=lambda m: m["score"], default=None)

        subatividades_df = atividades_df[~atividades_df["IS_GRUPO"]].copy()
        if subatividades_df.empty:
            st.error("Não há subatividades cadastradas no ANEXO I.")
            st.stop()

        linha_atividade = None
        if melhor_mapeamento:
            linha_candidata = subatividades_df[
                (subatividades_df["ITEM_BASE"] == melhor_mapeamento["item_base"])
                & (subatividades_df["Atividade"] == melhor_mapeamento["atividade"])
            ]
            if not linha_candidata.empty:
                linha_atividade = linha_candidata.iloc[0]

        # Fallback técnico apenas para manter o formulário funcional enquanto não há CNAE.
        if linha_atividade is None:
            linha_atividade = subatividades_df.iloc[0]

        grupo_base = str(linha_atividade["ITEM_BASE"])
        grupo_row = grupos_df[grupos_df["ITEM_BASE"] == grupo_base]
        grupo_nome = str(grupo_row.iloc[0]["Atividade"]) if not grupo_row.empty else "Grupo não identificado"
        grupo_selecionado = f"{grupo_base} - {grupo_nome}"
        atividade_selecionada = str(linha_atividade["Atividade"])

        # UNIDADE_DE_MEDIDA, POTENCIAL_POLUIDOR e ANEXO diretamente do CSV
        unidade_medida = str(linha_atividade.get("UNIDADE_DE_MEDIDA", "") or "").strip()
        potencial_raw = str(linha_atividade.get("POTENCIAL_POLUIDOR", "") or "").strip()
        potencial_poluidor = normalizar_potencial_poluidor(potencial_raw)
        anexo_selecionado = str(linha_atividade.get("ANEXO_OU_TAXA", "") or "").strip() or "ANEXO II"

        # Infere tipo de medição
        tipo_medicao = inferir_tipo_medicao_por_unidade(unidade_medida)

        # Enquadramento final é calculado apenas no clique do botão.
        possui_mapeamento_cnae = len(mapeados_validos) > 0
        enquadramento_info = {"enquadramento": "Pendente", "orgao": "-", "tipo_licenca": "-"}

        # 4. Medida do empreendimento (campo baseado na UNIDADE_DE_MEDIDA)
        render_step_header("4", "Informe a medida do seu empreendimento:", required=True)

        if tipo_medicao == "area":
            label_medida = unidade_medida or "Informe a área (ex.: hectares): *"
            placeholder_medida = "Ex.: 12,5"
        elif tipo_medicao == "potencia":
            label_medida = unidade_medida or "Informe a potência instalada (kW): *"
            placeholder_medida = "Ex.: 150"
        else:  # funcionarios
            label_medida = unidade_medida or "Informe o número de funcionários: *"
            placeholder_medida = "Ex.: 10"

        valor_medida_raw = st.text_input(
            label_medida,
            value="",
            placeholder=placeholder_medida,
            help=f"Unidade de medida: {unidade_medida}" if unidade_medida else None,
        )

        medida_invalida = False
        valor_medida = 0.0
        if str(valor_medida_raw).strip():
            valor_normalizado = str(valor_medida_raw).strip().replace(",", ".")
            try:
                valor_convertido = float(valor_normalizado)
                if tipo_medicao == "funcionarios" and not valor_convertido.is_integer():
                    medida_invalida = True
                else:
                    valor_medida = int(valor_convertido) if tipo_medicao == "funcionarios" else valor_convertido
            except ValueError:
                medida_invalida = True

        # Classifica o porte usando ANEXO I (PORTE_*_MIN/MAX)
        porte_encontrado = classificar_porte_por_linha_valor(float(valor_medida), linha_atividade)
        
        if porte_encontrado is None:
            porte_texto = "Não Definido"
        else:
            porte_texto = MAPA_PORTE_TABELA_PARA_APP.get(porte_encontrado, porte_encontrado)

        # Texto amigável para o resumo lateral
        if unidade_medida:
            medida_texto = f"{valor_medida} ({unidade_medida})"
        else:
            medida_texto = f"{valor_medida}"

    # =============================
    # CÁLCULO DAS TAXAS
    # =============================

    st.markdown("---")

    if st.button("🧮 ENQUADRAMENTO AMBIENTAL E TAXAS", type="primary", width="stretch"):
        if not cnpj_cpf:
            st.error("⚠️ Por favor, informe o CNPJ ou CPF do empreendedor.")
            st.stop()

        if not cnaes_selecionados:
            st.error("⚠️ Por favor, selecione pelo menos um CNAE.")
            st.stop()

        if medida_invalida:
            st.error("⚠️ A medida informada é inválida. Corrija o valor para continuar.")
            st.stop()

        if valor_medida <= 0:
            st.error("⚠️ Por favor, informe as medidas do seu empreendimento antes de calcular as taxas.")
            st.stop()

        if porte_texto == "Não Definido":
            st.error("⚠️ Impossível calcular: O porte não foi identificado para a medida informada.")
            st.stop()

        # Decisão final de enquadramento em um único ponto.
        # Recalcula LAS no clique para evitar estado intermediário/stale.
        tabela_las_click_df = carregar_tabela_las()
        is_las_click, las_matches_click = verificar_cnaes_em_las(cnaes_selecionados, tabela_las_click_df)
        enquadramento_info, las_aplicavel = calcular_enquadramento_final(
            municipio=municipio_selecionado,
            possui_mapeamento_cnae=possui_mapeamento_cnae,
            potencial_poluidor=potencial_poluidor,
            possui_cnae_las=is_las_click,
        )
        las_matches_aplicaveis = las_matches_click if las_aplicavel else []

        enquadramento_badge = (
            f"<span class='enq-badge enq-las'>{enquadramento_info['enquadramento']}</span>"
            if enquadramento_info["enquadramento"] == "LAS"
            else f"<span class='enq-badge enq-default'>{enquadramento_info['enquadramento']}</span>"
        )

        cnaes_resumo = "; ".join(cnaes_selecionados)
        cnaes_resumo = cnaes_resumo if len(cnaes_resumo) <= 120 else cnaes_resumo[:120] + "..."
        potencial_resumo = potencial_poluidor if melhor_mapeamento else "Não informado"
        classe_potencial_resumo = classe_potencial_poluidor(potencial_resumo)
        potencial_resumo_html = (
            f"<span class='pollution-indicator pollution-{classe_potencial_resumo}'>{potencial_resumo}</span>"
            if classe_potencial_resumo
            else potencial_resumo
        )

        st.markdown(
            f"""
            <div class="result-box">
                <h3>📊 Resumo da Solicitação</h3>
                <p><strong>CNPJ/CPF:</strong> {cnpj_cpf}</p>
                <p><strong>Email:</strong> {email_contato or 'Não informado'}</p>
                <p><strong>Telefone:</strong> {telefone_contato or 'Não informado'}</p>
                <p><strong>CNAEs:</strong> {cnaes_resumo}</p>
                <p><strong>Município:</strong> {municipio_selecionado}</p>
                <p><strong>Medida:</strong> {medida_texto if valor_medida > 0 else 'Não informado'}</p>
                <p><strong>Porte:</strong> {porte_texto if porte_texto != 'Não Definido' else 'Não informado'}</p>
                <p><strong>Potencial Poluidor:</strong> {potencial_resumo_html}</p>
                <p><strong>Enquadramento:</strong> {enquadramento_badge} | <strong>Órgão:</strong> {enquadramento_info['orgao']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        todos_valores = {}
        valor_total_todas = 0.0
        atividade_para_salvar = atividade_selecionada
        grupo_para_salvar = grupo_selecionado

        if enquadramento_info["enquadramento"] == "LAS":
            cnaes_las = ", ".join(m["cnae_codigo"] for m in las_matches_aplicaveis) if las_matches_aplicaveis else "Não detalhado"
            valor_las_ufar = 10.0
            valor_las_reais = valor_las_ufar * valor_ufir
            descricoes_las = [str(m.get("atividade_las", "")).strip() for m in las_matches_aplicaveis]
            descricoes_las = [d for d in descricoes_las if d]
            descricao_las_db = " | ".join(dict.fromkeys(descricoes_las)) if descricoes_las else "LAS"

            st.success("✅ Enquadramento: LAS (Licença Ambiental Simplificada).")
            st.info(f"CNAE(s) enquadrados em LAS: {cnaes_las}. Órgão responsável: {enquadramento_info['orgao']}.")
            st.markdown(
                f"""
                <div class="result-box">
                    <h3>💰 Taxa LAS</h3>
                    <p><strong>Taxa fixa:</strong> {valor_las_ufar:.2f} UFAR</p>
                    <p><strong>Valor estimado:</strong> R$ {valor_las_reais:.2f}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            todos_valores = {
                "Licença Simplificada": {
                    "valor_reais": valor_las_reais,
                    "valor_ufar": valor_las_ufar,
                    "codigo": "LAS",
                    "descricao": "Licença Ambiental Simplificada",
                }
            }
            valor_total_todas = valor_las_reais
            # Para LAS, grupo e atividade no histórico devem refletir a coluna D da planilha LAS.
            grupo_para_salvar = descricao_las_db
            atividade_para_salvar = descricao_las_db

        # Regra: sem mapeamento CNAE/SEMA (Ariquemes) -> Dispensa
        elif enquadramento_info["enquadramento"] == "Dispensa":
            st.success(
                "✅ Enquadramento: DISPENSA. Nenhum CNAE selecionado teve mapeamento confiável para atividade SEMA."
            )
            st.info(
                "Regra aplicada: se não houver CNAE mapeado para atividade/grupo, o empreendimento entra como dispensa."
            )
            todos_valores = {
                "Dispensa": {
                    "valor_reais": 0.0,
                    "valor_ufar": 0.0,
                    "codigo": "DISP",
                    "descricao": "Dispensa de licenciamento",
                }
            }
            valor_total_todas = 0.0
            atividade_para_salvar = "Dispensa por ausência de mapeamento CNAE"

        else:
            caminho_taxas = TAXAS_SEDAM_CSV_PATH if enquadramento_info["orgao"] == "SEDAM" else TAXAS_CSV_PATH
            df_taxas = carregar_tabelas_taxas(caminho_taxas)
            classe_potencial_card = classe_potencial_poluidor(potencial_poluidor)
            potencial_card_html = (
                f"<span class='pollution-indicator pollution-{classe_potencial_card}'>{potencial_poluidor}</span>"
                if classe_potencial_card
                else potencial_poluidor
            )

            st.markdown(f"""
                <div class="result-box">
                    <h3>💰 Valores das Taxas de Licenciamento Ambiental</h3>
                    <p><strong>Empreendedor (CNPJ/CPF):</strong> {cnpj_cpf}</p>
                    <p><strong>CNAEs:</strong> {len(cnaes_selecionados)} selecionado(s)</p>
                    <p><strong>Grupo:</strong> {grupo_selecionado}</p>
                    <p><strong>Empreendimento:</strong> {atividade_selecionada}</p>
                    <p><strong>Município:</strong> {municipio_selecionado} | 
                       <strong>Órgão:</strong> {enquadramento_info['orgao']} |
                       <strong>Porte:</strong> {porte_texto} | 
                       <strong>Potencial Poluidor:</strong> {potencial_card_html}</p>
                    <hr>
                </div>
            """, unsafe_allow_html=True)

            if enquadramento_info["orgao"] == "SEDAM":
                st.info("Tabela aplicada: SEDAM (Lei 3.941/2016) - valores base em UPFs.")

            col_lic1, col_lic2, col_lic3 = st.columns(3)
            lic_cols = [col_lic1, col_lic2, col_lic3]

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
                        <div class="license-value">R$ {valor_total:.2f}</div>
                        <div style="font-size: 0.85rem; color: #999;">Taxa base: {valor_ufars:.2f} UFARs</div>
                    </div>
                """

                with lic_cols[i % 3]:
                    st.markdown(card_html, unsafe_allow_html=True)

            st.markdown("---")
            valor_total_todas = sum(v["valor_reais"] for v in todos_valores.values())

            st.markdown(f"""
                <div style="background-color: #e8f5f0; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #2d8b6b; margin-bottom: 1rem;">
                    <h4>🌿 Sobre o Potencial Poluidor</h4>
                    <p>O potencial poluidor <strong>{potencial_poluidor}</strong> foi determinado automaticamente com base na
                    atividade <em>"{atividade_selecionada}"</em>, conforme estabelecido no <strong>Anexo I da Lei Municipal 2.349/2019</strong>.</p>
                    <p style="font-size: 0.9rem; margin-top: 0.5rem;">Esta classificação afeta diretamente o valor das taxas de licenciamento.</p>
                </div>
            """, unsafe_allow_html=True)

            if enquadramento_info["orgao"] == "SEMA":
                st.markdown(f"""
                    <div style="background-color: #fff3e0; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #ff9800;">
                        <h4>📌 Resumo Total</h4>
                        <p><strong>Valor total se todas as licenças fossem solicitadas:</strong> 
                           <span style="font-size: 1.3rem; color: #ff6f00;">R$ {valor_total_todas:.2f}</span></p>
                        <p style="font-size: 0.9rem; color: #666; margin-top: 1rem;">
                            <strong>Observação:</strong> Normalmente, as licenças são solicitadas em sequência (LP → LI → LO), 
                            não todas de uma vez. Este é um valor aproximado baseado nas tabelas oficiais da lei municipal.
                        </p>
                        <p style="font-size: 0.9rem; color: #666; margin-top: 0.5rem;">
                            <strong>As taxas ambientais podem ser parceladas em até 6 vezes no boleto.</strong>
                        </p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="background-color: #fff3e0; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #ff9800;">
                        <h4>📌 Resumo Total</h4>
                        <p><strong>Valor total se todas as licenças fossem solicitadas:</strong> 
                           <span style="font-size: 1.3rem; color: #ff6f00;">R$ {valor_total_todas:.2f}</span></p>
                        <p style="font-size: 0.9rem; color: #666; margin-top: 1rem;">
                            <strong>Observação:</strong> Valores estimados conforme tabela oficial do órgão ambiental competente.
                        </p>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown(
                f"""
                <div class="info-box">
                    <strong>Regra de órgão aplicada:</strong> Potencial <strong>Baixo</strong> = SEMA; potencial
                    <strong>Médio/Alto</strong> = SEDAM (quando não for LAS/Dispensa).
                </div>
                """,
                unsafe_allow_html=True,
            )

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
                self.cell(30, 10, 'Enquadramento de Licenciamento Ambiental', 0, 0, 'C')
                self.ln(20)

            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, 'Atenas Projetos Ambientais - Página ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

        def gerar_pdf(municipio, grupo, atividade, medida, porte, potencial, ufir, valores, cnpj_cpf, cnaes_list, orgao):
            pdf = PDF()
            pdf.alias_nb_pages()
            pdf.add_page()
            pdf.ln(10)
            pdf.set_font('Arial', '', 12)

            # Dados do Empreendimento
            pdf.set_fill_color(178, 223, 205)
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
            pdf.set_fill_color(178, 223, 205)
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
                pdf.cell(40, 10, f"R$ {dados['valor_reais']:.2f}", 1, 0, 'R')
                pdf.ln()
                total += dados['valor_reais']

            pdf.ln(5)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(100, 10, 'Total Estimado:', 0, 0, 'R')
            pdf.cell(40, 10, f"R$ {total:.2f}", 0, 1, 'R')

            if orgao == "SEMA":
                pdf.ln(10)
                pdf.set_font('Arial', 'I', 8)
                pdf.multi_cell(0, 5, 'Observação: Os valores são estimativas baseadas na legislação municipal. O valor final pode variar conforme análise técnica do órgão ambiental. As taxas podem ser parceladas em até 6 vezes.')
            else:
                pdf.ln(10)
                pdf.set_font('Arial', 'I', 8)
                pdf.multi_cell(0, 5, 'Observação: Valores estimados conforme tabela oficial do órgão ambiental competente.')

            return pdf.output(dest='S').encode('latin-1')

        # Botão de Download
        st.write("")
        col_dl1, col_dl2, col_dl3 = st.columns([1, 2, 1])
        with col_dl2:
            pdf_bytes = gerar_pdf(
                municipio_selecionado,
                grupo_para_salvar,
                atividade_para_salvar,
                medida_texto,
                porte_texto,
                potencial_poluidor,
                valor_ufir,
                todos_valores,
                cnpj_cpf,
                cnaes_selecionados,
                enquadramento_info["orgao"]
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
        
        # Salva o cálculo e guarda o ID para o formulário de feedback
        calculo_id = database.salvar_calculo(
            municipio=municipio_selecionado,
            grupo=grupo_para_salvar,
            atividade=atividade_para_salvar,
            medida=medida_texto,
            porte=porte_texto,
            potencial=potencial_poluidor,
            valor_total=valor_total_todas,
            cnpj_cpf=cnpj_cpf,
            cnaes="; ".join(cnaes_selecionados),
            email=email_contato,
            telefone=telefone_contato,
            usuario_login=st.session_state.get("username", ""),
            usuario_nome=st.session_state.get("name", "")
        )
        st.session_state["feedback_calculo_id"] = calculo_id
        st.session_state["feedback_municipio"] = municipio_selecionado
        st.session_state["feedback_atividade"] = atividade_para_salvar
        st.session_state["feedback_cnpj_cpf"] = cnpj_cpf
        st.session_state["feedback_enviado"] = False
        st.session_state["feedback_mostrar_form"] = False
        st.session_state["feedback_detalhes"] = {
            "grupo": grupo_para_salvar,
            "cnaes": "; ".join(cnaes_selecionados),
            "medida": medida_texto,
            "porte": porte_texto,
            "potencial": potencial_poluidor,
            "enquadramento": enquadramento_info.get("enquadramento", "-"),
            "orgao": enquadramento_info.get("orgao", "-"),
            "tipo_licenca": enquadramento_info.get("tipo_licenca", "-"),
            "valor_ufir": valor_ufir,
            "valor_total": valor_total_todas,
            "todos_valores": todos_valores,
        }

    # =============================
    # SEÇÃO DE FEEDBACK
    # =============================
    if st.session_state.get("feedback_calculo_id"):
        st.markdown("---")
        if st.session_state.get("feedback_enviado"):
            st.success("Feedback registrado. Obrigado pela sua contribuição!")
        else:
            st.markdown("**Você concorda com o resultado do cálculo?**")
            if not st.session_state.get("feedback_mostrar_form", False):
                col_discordo, _ = st.columns([1, 3])
                with col_discordo:
                    if st.button("Não concordo com o resultado", key="btn_discordo", use_container_width=True):
                        st.session_state["feedback_mostrar_form"] = True
                        st.rerun()
            else:
                motivo_input = st.text_area(
                    "Descreva o motivo da discordância:",
                    key="feedback_motivo_text",
                    height=130,
                    placeholder="Ex.: O porte calculado parece incorreto para o meu caso...",
                )
                col_ok, col_cancel = st.columns([1, 1])
                with col_ok:
                    if st.button("Enviar Feedback", key="btn_enviar_feedback", type="primary"):
                        if motivo_input.strip():
                            import database as _db
                            _db.init_db()
                            _db.salvar_feedback(
                                calculo_id=st.session_state["feedback_calculo_id"],
                                motivo=motivo_input.strip(),
                                usuario_login=st.session_state.get("username", ""),
                                usuario_nome=st.session_state.get("name", ""),
                            )
                            ok, err = enviar_email_feedback(
                                calculo_id=st.session_state["feedback_calculo_id"],
                                motivo=motivo_input.strip(),
                                municipio=st.session_state.get("feedback_municipio", ""),
                                atividade=st.session_state.get("feedback_atividade", ""),
                                cnpj_cpf=st.session_state.get("feedback_cnpj_cpf", ""),
                                usuario_nome=st.session_state.get("name", ""),
                                usuario_login=st.session_state.get("username", ""),
                                detalhes_calculo=st.session_state.get("feedback_detalhes"),
                            )
                            st.session_state["feedback_enviado"] = True
                            st.session_state["feedback_mostrar_form"] = False
                            if not ok:
                                st.warning(f"Feedback salvo, mas não foi possível enviar o e-mail: {err}")
                            st.rerun()
                        else:
                            st.warning("Por favor, descreva o motivo antes de enviar.")
                with col_cancel:
                    if st.button("Cancelar", key="btn_cancelar_feedback"):
                        st.session_state["feedback_mostrar_form"] = False
                        st.rerun()

# =============================
# HISTÓRICO / AUDITORIA (ADMIN)
# =============================
if tab_admin:
    with tab_admin:
        st.header("📂 Histórico de Consultas")
        
        import database
        database.init_db()
        df_history = database.listar_calculos()
        
        if not df_history.empty:
            colunas_prioritarias = ["usuario_login", "usuario_nome"]
            colunas_existentes = [c for c in colunas_prioritarias if c in df_history.columns]
            if colunas_existentes:
                demais_colunas = [c for c in df_history.columns if c not in colunas_existentes]
                df_history = df_history[colunas_existentes + demais_colunas]

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

        st.markdown("---")
        st.subheader("💬 Feedbacks de Discordância")
        df_feedbacks = database.listar_feedbacks()
        if not df_feedbacks.empty:
            st.dataframe(df_feedbacks, width="stretch")
            csv_fb = df_feedbacks.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Baixar Feedbacks (CSV)",
                data=csv_fb,
                file_name="feedbacks.csv",
                mime="text/csv",
            )
        else:
            st.info("Nenhum feedback registrado ainda.")

# Rodapé
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem; padding: 2rem 0;">
        <p style="color: #2d8b6b; font-weight: 600;">🌿 Atenas Projetos Ambientais</p>
        <p>Enquadramento de Licenciamento Ambiental | Rondônia · 2026</p>
        <p>Detecção automática de potencial poluidor conforme Lei 2.349/2019</p>
        <p style="font-size: 0.8rem; margin-top: 0.5rem;">Os valores apresentados são estimativas. Consulte sempre o órgão ambiental competente.</p>
    </div>
""", unsafe_allow_html=True)
