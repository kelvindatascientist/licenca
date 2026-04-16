# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Environmental licensing fee calculator (Calculadora de Taxas - Licenciamento Ambiental) for Brazilian municipalities in Rondônia state. Calculates LP/LI/LO (Licença Prévia, de Instalação, de Operação) fees based on activity CNAE codes, enterprise size, and municipal tax tables (UFAR/UPFS).

## Commands

```bash
# Run the app
streamlit run calculadora_taxas.py

# Run tests
python test_examples.py

# Clean activity size classifications from SEMA_ANEXO_I_full.csv
python limpar_portes.py

# Clean duplicate rows from SEDAM tax table
python clean_sedam_ground_truth.py --input taxas_sedam_upfs_ground_truth.csv --output taxas_sedam_upfs_ground_truth_clean.csv

# Validate SEDAM CSV against official PDF
python validate_sedam_csv.py

# Install dependencies
pip install -r requirements.txt
```

## Architecture

### Core Application (`calculadora_taxas.py`)
Single-file Streamlit app (~1500 lines) with multi-step wizard UI, authentication, and all business logic. Authentication uses `streamlit-authenticator` with bcrypt hashes in `config.yaml`.

### Calculation Pipeline
1. User selects CNAE → system maps to activity using `SequenceMatcher` similarity (threshold: 0.75) against `ANEXO_I_cleaned_with_portes.csv`
2. Activity lookup retrieves Potencial Poluidor (Baixo/Médio/Alto) and measurement type (area/potencia/funcionarios)
3. User input measurement → size classification via PORTE_*_MIN/MAX range columns
4. CNAE checked against `Lista de atividades LAS E CNAES.xlsx` for simplified licensing (LAS) — takes highest priority
5. Enquadramento (LAS / LP-LI-LO / Dispensa) depends on: LAS status, Potencial Poluidor (Baixo → SEMA tables, Médio/Alto → SEDAM tables), and mapping confidence
6. Tax looked up from `taxas_ambientais_ufar.csv` (SEMA) or `taxas_sedam_upfs_ground_truth_clean.csv` (SEDAM) and converted to Reais via municipal UFIR
7. PDF generated via `fpdf`, calculation saved to SQLite (`historico_calculos.db`)

### Key Data Files
| File | Role |
|------|------|
| `ANEXO_I_cleaned_with_portes.csv` | Activities + parsed size ranges (output of `limpar_portes.py`) |
| `taxas_ambientais_ufar.csv` | SEMA tax table (TLP/TLI/TLO in UFAR units) |
| `taxas_sedam_upfs_ground_truth_clean.csv` | SEDAM tax table (TLP/TLI/TLO in UPFS units, output of `clean_sedam_ground_truth.py`) |
| `IBGE_CNAE_Subclass2.3.csv` | CNAE reference (code → description) |
| `Lista de atividades LAS E CNAES.xlsx` | CNAE codes eligible for simplified LAS licensing |
| `SEMA_ANEXO_I_full.csv` | Raw activity data (input to `limpar_portes.py`) |

### Municipal Configuration (hardcoded in `calculadora_taxas.py`)
```python
MUNICIPIOS_CONFIG = {
    "Ariquemes - RO": {"ufir": 85.15, "lei": "Lei 2.349/2019"},
    "Porto Velho - RO": {"ufir": 81.22, "lei": "Lei Municipal"},
}
```

### Support Modules
- `database.py` — SQLite init/read/write for calculation audit trail
- `pollution_potential_mapping.py` — fallback reference mappings (activity → default potencial + measurement type)
- `limpar_portes.py` — parses Brazilian-formatted numeric ranges into MIN/MAX CSV columns
- `clean_sedam_ground_truth.py` — deduplicates SEDAM CSV with manual `OVERRIDES` dict for conflict resolution

### Testing
`test_examples.py` uses AST parsing to extract logic functions from `calculadora_taxas.py` without triggering the Streamlit UI, enabling unit-level testing of classification logic.
