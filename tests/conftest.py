"""
Shared fixtures for unit and integration tests.

Uses AST parsing to extract pure logic from calculadora_taxas.py without
triggering any Streamlit UI code or authentication flows.
"""
import ast
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent

# ─────────────────────────────────────────────────────────────
# Functions to extract (no Streamlit dependencies)
# ─────────────────────────────────────────────────────────────
_LOGIC_FUNCTIONS = {
    "normalizar_texto",
    "normalizar_cnae_codigo",
    "extrair_codigo_cnae_display",
    "normalizar_potencial_poluidor",
    "inferir_tipo_medicao_por_unidade",
    "classificar_porte_por_linha_valor",
    "definir_enquadramento",
    "calcular_enquadramento_final",
    "verificar_cnaes_em_las",
    "obter_taxa_ufar",
    "calcular_taxa",
    "preparar_atividades",
    "mapear_cnaes_para_atividades",
}

# Module-level constants needed by those functions
_CONSTANTS = {
    "SCORE_MINIMO_MAPEAMENTO_CNAE",
    "EXCECOES_MAPEAMENTO_CNAE",
    "TIPO_LICENCA_COLUNA",
    "MAPEAMENTO_PORTES_TABELA",
    "MAPA_PORTE_TABELA_PARA_APP",
    "SERVICOS",
    "MUNICIPIOS_CONFIG",
    "ATIVIDADES_CSV_PATH",
    "TAXAS_CSV_PATH",
    "TAXAS_SEDAM_CSV_PATH",
}


def load_logic() -> dict:
    """
    Parse calculadora_taxas.py and extract selected functions + constants
    without executing any Streamlit, authentication, or UI code.
    """
    source = (PROJECT_ROOT / "calculadora_taxas.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="calculadora_taxas.py")

    # Modules that are not needed by the extracted functions and will fail to import
    # in test environments (no Streamlit UI, no auth module installed).
    _SKIP_MODULES = {"streamlit", "streamlit_authenticator", "yaml", "fpdf"}

    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
            if any(n in _SKIP_MODULES for n in names):
                continue
            selected.append(node)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _SKIP_MODULES:
                continue
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in _LOGIC_FUNCTIONS:
            selected.append(node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _CONSTANTS:
                    selected.append(node)
                    break

    module = ast.Module(body=selected, type_ignores=[])
    code = compile(module, filename="calculadora_taxas.py", mode="exec")
    ns: dict = {}
    exec(code, ns, ns)  # noqa: S102
    return ns


# ─────────────────────────────────────────────────────────────
# Session-scoped fixtures (expensive loads done once per run)
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def logic() -> dict:
    """Namespace with pure logic functions and constants from calculadora_taxas.py."""
    return load_logic()


@pytest.fixture(scope="session")
def df_las() -> pd.DataFrame:
    """Real LAS spreadsheet."""
    path = PROJECT_ROOT / "Lista de atividades LAS E CNAES.xlsx"
    return pd.read_excel(path, dtype=str).fillna("")


@pytest.fixture(scope="session")
def df_taxas_sema() -> pd.DataFrame:
    """Real SEMA tax table (UFAR)."""
    path = PROJECT_ROOT / "taxas_ambientais_ufar.csv"
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    for col in ["TLP", "TLI", "TLO"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["ANEXO", "PORTE", "POTENCIAL_POLUIDOR"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


@pytest.fixture(scope="session")
def df_taxas_sedam() -> pd.DataFrame:
    """Real SEDAM tax table (UPFS)."""
    path = PROJECT_ROOT / "taxas_sedam_upfs_ground_truth_clean.csv"
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    renomear = {"TLP_UPFS": "TLP", "TLI_UPFS": "TLI", "TLO_UPFS": "TLO"}
    df = df.rename(columns={k: v for k, v in renomear.items() if k in df.columns})
    for col in ["TLP", "TLI", "TLO"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["ANEXO", "PORTE", "POTENCIAL_POLUIDOR"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


@pytest.fixture(scope="session")
def df_cnaes() -> pd.DataFrame:
    """Real IBGE CNAE reference table."""
    path = PROJECT_ROOT / "IBGE_CNAE_Subclass2.3.csv"
    return pd.read_csv(path, dtype=str).fillna("")


@pytest.fixture(scope="session")
def df_atividades() -> pd.DataFrame:
    """Real ANEXO I activity table."""
    path = PROJECT_ROOT / "ANEXO_I_cleaned_with_portes.csv"
    df = pd.read_csv(path, sep=";", dtype=str)
    if df.shape[1] < 2:
        df = pd.read_csv(path, sep=",", dtype=str)
    for col in df.columns:
        if col.endswith("_MIN") or col.endswith("_MAX"):
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
    return df


# ─────────────────────────────────────────────────────────────
# Function-scoped: isolated database per test
# ─────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Redirect database.DB_NAME to a temporary file so each test gets a clean DB."""
    import database

    db_path = str(tmp_path / "test_calculos.db")
    monkeypatch.setattr(database, "DB_NAME", db_path)
    return db_path
