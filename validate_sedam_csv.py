import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


PORTE_CANON = {
    "MINIMO": "Mínimo",
    "PEQUENO": "Pequeno",
    "MEDIO": "Médio",
    "GRANDE": "Grande",
    "EXCEPCIONAL": "Excepcional",
    "-": "-",
}

POT_CANON = {
    "BAIXO": "Baixo",
    "MEDIO": "Médio",
    "ALTO": "Alto",
}


def strip_accents(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_code_style(text: str) -> str:
    t = strip_accents(text).upper()
    t = t.replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t)
    return t


def canonicalize_keywords(text: str) -> str:
    t = normalize_code_style(text)

    # Normaliza palavras quebradas por espaçamento de OCR.
    replacements = {
        r"A\s*N\s*E\s*X\s*O": "ANEXO",
        r"P\s*O\s*R\s*T\s*E": "PORTE",
        r"P\s*O\s*T\s*E\s*N\s*C\s*I\s*A\s*L": "POTENCIAL",
        r"P\s*O\s*L\s*U\s*I\s*D\s*O\s*R": "POLUIDOR",
        r"T\s*L\s*P": "TLP",
        r"T\s*L\s*I": "TLI",
        r"T\s*L\s*O": "TLO",
        r"U\s*P\s*F\s*S": "UPFS",
        r"I\s*S\s*E\s*N\s*T\s*O": "ISENTO",
        r"M\s*I\s*N\s*I\s*M\s*O": "MINIMO",
        r"P\s*E\s*Q\s*U\s*E\s*N\s*O": "PEQUENO",
        r"M\s*E\s*D\s*I\s*O": "MEDIO",
        r"G\s*R\s*A\s*N\s*D\s*E": "GRANDE",
        r"E\s*X\s*C\s*E\s*P\s*C\s*I\s*O\s*N\s*A\s*L": "EXCEPCIONAL",
        r"B\s*A\s*I\s*X\s*O": "BAIXO",
        r"A\s*L\s*T\s*O": "ALTO",
    }
    for pattern, repl in replacements.items():
        t = re.sub(pattern, repl, t, flags=re.IGNORECASE)

    t = re.sub(r"\s+", " ", t)
    return t


def normalize_anexo(value: str) -> str:
    t = canonicalize_keywords(value)
    m = re.search(r"ANEXO\s+([IVXLCDM]+)", t)
    if not m:
        return ""
    return f"ANEXO {m.group(1)}"


def normalize_porte(value: str) -> str:
    t = canonicalize_keywords(value)
    if t.strip() == "-":
        return "-"
    for key, val in PORTE_CANON.items():
        if key in t:
            return val
    return ""


def normalize_potencial(value: str) -> str:
    t = canonicalize_keywords(value)
    for key, val in POT_CANON.items():
        if key in t:
            return val
    return ""


def normalize_num(value) -> float:
    s = str(value if value is not None else "").strip().upper()
    s = strip_accents(s)
    if s in {"", "NAN", "NONE"}:
        return 0.0
    if "ISENTO" in s:
        return 0.0
    s = s.replace(",", ".")
    s = re.sub(r"[^0-9.]", "", s)
    if s == "":
        return 0.0
    return float(s)


@dataclass
class PdfRow:
    anexo: str
    descricao: str
    porte: str
    potencial: str
    tlp: float
    tli: float
    tlo: float
    page_start: int


def extract_pdf_rows(pdf_path: Path, start_page_1based: int = 25) -> pd.DataFrame:
    """
    Extrai linhas de tabela do PDF usando extraction_mode='layout', que preserva colunas.
    Essa abordagem melhora significativamente o parsing do DOE (layout irregular).
    """
    reader = PdfReader(str(pdf_path))

    annex_blocks = []
    current = None
    for i in range(start_page_1based - 1, len(reader.pages)):
        page_no = i + 1
        page_text = reader.pages[i].extract_text(extraction_mode="layout") or ""
        for raw_line in page_text.splitlines():
            line = normalize_spaces(raw_line)
            if not line:
                continue

            m = re.match(r"^ANEXO\s+([IVXLCDM]+)\b", line, flags=re.IGNORECASE)
            if m:
                if current:
                    annex_blocks.append(current)
                current = {
                    "anexo": f"ANEXO {m.group(1).upper()}",
                    "page_start": page_no,
                    "lines": [],
                }
                continue

            if current is not None:
                current["lines"].append(line)

    if current:
        annex_blocks.append(current)

    porte_re = r"(Mínimo|Minimo|Pequeno|Médio|Medio|Grande|Excepcional|-)"
    pot_re = r"(Baixo|Médio|Medio|Alto)"
    num_re = r"(ISENTO|\d+)"

    re_full = re.compile(
        rf"^{porte_re}\s+{pot_re}\s+{num_re}\s+{num_re}\s+{num_re}(?:\b|\s)", flags=re.IGNORECASE
    )
    re_no_porte = re.compile(
        rf"^{pot_re}\s+{num_re}\s+{num_re}\s+{num_re}(?:\b|\s)", flags=re.IGNORECASE
    )
    re_porte_tlp = re.compile(rf"^{porte_re}\s+{num_re}\s*$", flags=re.IGNORECASE)
    re_pot_tli_tlo = re.compile(rf"^{pot_re}\s+{num_re}\s+{num_re}\s*$", flags=re.IGNORECASE)

    rows: list[PdfRow] = []
    for block in annex_blocks:
        anexo = block["anexo"]
        if anexo == "ANEXO I":
            continue

        description_lines = []
        in_table = False
        last_porte = None
        pending_row = None

        lines = block["lines"]
        for i, line in enumerate(lines):
            if "PORTE" in line and ("TLP" in line or "LP" in line):
                in_table = True
                continue

            if not in_table:
                description_lines.append(line)
                continue

            if (
                ("POLUIDOR" in line or "UPFS" in line or "UPF-RO" in line)
                and not re.search(r"\d|ISENTO", line, flags=re.IGNORECASE)
            ):
                continue

            m_full = re_full.match(line)
            if m_full:
                porte_raw, pot_raw, tlp_raw, tli_raw, tlo_raw = m_full.groups()
                last_porte = porte_raw
                pending_row = None
            else:
                m_no_porte = re_no_porte.match(line)
                if m_no_porte and last_porte:
                    pot_raw, tlp_raw, tli_raw, tlo_raw = m_no_porte.groups()
                    porte_raw = last_porte
                    pending_row = None
                elif m_no_porte and not last_porte:
                    pot_raw, tlp_raw, tli_raw, tlo_raw = m_no_porte.groups()

                    # Em alguns anexos a primeira linha de potencial aparece antes da linha com porte.
                    porte_raw = ""
                    for j in range(i + 1, min(i + 6, len(lines))):
                        next_line = lines[j]
                        if not next_line:
                            continue
                        m_next_full = re_full.match(next_line)
                        if m_next_full:
                            porte_raw = m_next_full.group(1)
                            break
                        m_next_porte_tlp = re_porte_tlp.match(next_line)
                        if m_next_porte_tlp:
                            porte_raw = m_next_porte_tlp.group(1)
                            break
                    if not porte_raw:
                        continue
                    pending_row = None
                else:
                    m_porte_tlp = re_porte_tlp.match(line)
                    if m_porte_tlp:
                        porte_raw, tlp_raw = m_porte_tlp.groups()
                        last_porte = porte_raw
                        pending_row = (porte_raw, tlp_raw)
                        continue

                    m_pot_tli_tlo = re_pot_tli_tlo.match(line)
                    if m_pot_tli_tlo and pending_row:
                        pot_raw, tli_raw, tlo_raw = m_pot_tli_tlo.groups()
                        porte_raw, tlp_raw = pending_row
                        pending_row = None
                    elif m_no_porte:
                        # Sem porte explícito: tenta inferir pelo próximo porte da tabela.
                        pot_raw, tlp_raw, tli_raw, tlo_raw = m_no_porte.groups()
                        porte_raw = ""
                        for j in range(i + 1, min(i + 6, len(lines))):
                            next_line = lines[j]
                            m_next_full = re_full.match(next_line)
                            if m_next_full:
                                porte_raw = m_next_full.group(1)
                                break
                            m_next_porte_tlp = re_porte_tlp.match(next_line)
                            if m_next_porte_tlp:
                                porte_raw = m_next_porte_tlp.group(1)
                                break
                        if not porte_raw:
                            continue
                    else:
                        continue

            porte_norm = normalize_porte(porte_raw)
            pot_norm = normalize_potencial(pot_raw)
            descricao = normalize_spaces(" ".join(description_lines))

            rows.append(
                PdfRow(
                    anexo=anexo,
                    descricao=descricao,
                    porte=porte_norm,
                    potencial=pot_norm,
                    tlp=normalize_num(tlp_raw),
                    tli=normalize_num(tli_raw),
                    tlo=normalize_num(tlo_raw),
                    page_start=int(block["page_start"]),
                )
            )

    if not rows:
        return pd.DataFrame(
            columns=["ANEXO", "DESCRICAO", "PORTE", "POTENCIAL_POLUIDOR", "TLP", "TLI", "TLO", "PAGE_START"]
        )

    df = pd.DataFrame(
        [
            {
                "ANEXO": r.anexo,
                "DESCRICAO": r.descricao,
                "PORTE": r.porte,
                "POTENCIAL_POLUIDOR": r.potencial,
                "TLP": r.tlp,
                "TLI": r.tli,
                "TLO": r.tlo,
                "PAGE_START": r.page_start,
            }
            for r in rows
        ]
    )

    # Dedup por linha completa.
    df = df.drop_duplicates(
        subset=["ANEXO", "PORTE", "POTENCIAL_POLUIDOR", "TLP", "TLI", "TLO"]
    ).reset_index(drop=True)
    return df


def load_csv_ground_truth(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype=str).fillna("")

    needed = ["ANEXO", "DESCRICAO", "PORTE", "POTENCIAL_POLUIDOR", "TLP", "TLI", "TLO"]
    for c in needed:
        if c not in df.columns:
            raise ValueError(f"Coluna ausente no CSV: {c}")

    out = df[needed].copy()
    out["ANEXO"] = out["ANEXO"].map(normalize_anexo)
    out["PORTE"] = out["PORTE"].map(normalize_porte)
    out["POTENCIAL_POLUIDOR"] = out["POTENCIAL_POLUIDOR"].map(normalize_potencial)
    out["TLP"] = out["TLP"].map(normalize_num)
    out["TLI"] = out["TLI"].map(normalize_num)
    out["TLO"] = out["TLO"].map(normalize_num)
    out["DESCRICAO"] = out["DESCRICAO"].map(normalize_spaces)
    out = out.reset_index().rename(columns={"index": "CSV_ROW"})
    out["CSV_ROW"] = out["CSV_ROW"] + 1
    return out


def audit(csv_df: pd.DataFrame, pdf_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    key_cols = ["ANEXO", "PORTE", "POTENCIAL_POLUIDOR"]
    full_cols = ["ANEXO", "PORTE", "POTENCIAL_POLUIDOR", "TLP", "TLI", "TLO"]

    pdf_full_set = set(tuple(x) for x in pdf_df[full_cols].itertuples(index=False, name=None))
    pdf_key_set = set(tuple(x) for x in pdf_df[key_cols].itertuples(index=False, name=None))
    pdf_map_by_key = {}
    for _, row in pdf_df.iterrows():
        k = tuple(row[c] for c in key_cols)
        pdf_map_by_key.setdefault(k, set()).add(tuple(row[c] for c in ["TLP", "TLI", "TLO"]))

    detailed_rows = []
    for _, row in csv_df.iterrows():
        full_key = tuple(row[c] for c in full_cols)
        key = tuple(row[c] for c in key_cols)

        if full_key in pdf_full_set:
            status = "MATCH_EXATO"
            pdf_vals = ""
        elif key in pdf_key_set:
            status = "CHAVE_OK_VALOR_DIVERGENTE"
            vals = sorted(pdf_map_by_key.get(key, []))
            pdf_vals = "; ".join([f"TLP={v[0]} TLI={v[1]} TLO={v[2]}" for v in vals])
        else:
            status = "CHAVE_NAO_ENCONTRADA_NO_PDF"
            pdf_vals = ""

        detailed_rows.append(
            {
                "CSV_ROW": int(row["CSV_ROW"]),
                "STATUS": status,
                "ANEXO": row["ANEXO"],
                "PORTE": row["PORTE"],
                "POTENCIAL_POLUIDOR": row["POTENCIAL_POLUIDOR"],
                "TLP": row["TLP"],
                "TLI": row["TLI"],
                "TLO": row["TLO"],
                "VALORES_ENCONTRADOS_NO_PDF_PARA_CHAVE": pdf_vals,
            }
        )

    detailed_df = pd.DataFrame(detailed_rows).sort_values("CSV_ROW").reset_index(drop=True)

    csv_full = csv_df[full_cols].drop_duplicates().reset_index(drop=True)
    pdf_full = pdf_df[full_cols].drop_duplicates().reset_index(drop=True)

    merged_missing = pdf_full.merge(csv_full, on=full_cols, how="left", indicator=True)
    missing_in_csv = merged_missing[merged_missing["_merge"] == "left_only"].drop(columns=["_merge"])

    merged_extra = csv_full.merge(pdf_full, on=full_cols, how="left", indicator=True)
    extra_in_csv = merged_extra[merged_extra["_merge"] == "left_only"].drop(columns=["_merge"])

    summary = {
        "csv_rows_total": int(len(csv_df)),
        "csv_rows_match_exato": int((detailed_df["STATUS"] == "MATCH_EXATO").sum()),
        "csv_rows_chave_ok_valor_divergente": int(
            (detailed_df["STATUS"] == "CHAVE_OK_VALOR_DIVERGENTE").sum()
        ),
        "csv_rows_chave_nao_encontrada_no_pdf": int(
            (detailed_df["STATUS"] == "CHAVE_NAO_ENCONTRADA_NO_PDF").sum()
        ),
        "pdf_rows_extraidos_unicos": int(len(pdf_full)),
        "pdf_rows_nao_presentes_no_csv": int(len(missing_in_csv)),
        "csv_rows_nao_presentes_no_pdf": int(len(extra_in_csv)),
        "csv_chaves_duplicadas_anexo_porte_potencial": int(
            csv_df.duplicated(subset=key_cols).sum()
        ),
        "csv_anexos_total": int(csv_df["ANEXO"].nunique()),
        "pdf_anexos_total": int(pdf_df["ANEXO"].nunique()),
        "anexos_no_pdf_faltando_no_csv": sorted(
            list(set(pdf_df["ANEXO"].unique()) - set(csv_df["ANEXO"].unique()))
        ),
        "anexos_no_csv_nao_encontrados_no_pdf": sorted(
            list(set(csv_df["ANEXO"].unique()) - set(pdf_df["ANEXO"].unique()))
        ),
    }

    return detailed_df, missing_in_csv, extra_in_csv, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida CSV SEDAM linha a linha contra PDF.")
    parser.add_argument(
        "--pdf",
        default="/Users/kelvin.pacheco/Downloads/2 .SEDAM - Lei_3941-2016 -.pdf",
        help="Caminho do PDF da Lei SEDAM.",
    )
    parser.add_argument(
        "--csv",
        default="taxas_sedam_upfs_padrao.csv",
        help="CSV SEDAM ground truth para validar.",
    )
    parser.add_argument(
        "--outdir",
        default="auditoria_sedam",
        help="Pasta de saída dos relatórios.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    csv_path = Path(args.csv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    pdf_df = extract_pdf_rows(pdf_path)
    csv_df = load_csv_ground_truth(csv_path)
    detailed_df, missing_in_csv, extra_in_csv, summary = audit(csv_df, pdf_df)

    pdf_out = outdir / "pdf_extraido_linhas.csv"
    pdf_ground_truth_out = outdir / "ground_truth_extraida_do_pdf.csv"
    detailed_out = outdir / "validacao_linha_a_linha.csv"
    missing_out = outdir / "faltantes_no_csv.csv"
    extra_out = outdir / "extras_no_csv.csv"
    summary_out = outdir / "resumo.json"

    pdf_df.to_csv(pdf_out, index=False)
    pdf_df[["ANEXO", "DESCRICAO", "PORTE", "POTENCIAL_POLUIDOR", "TLP", "TLI", "TLO"]].to_csv(
        pdf_ground_truth_out, index=False
    )
    detailed_df.to_csv(detailed_out, index=False)
    missing_in_csv.to_csv(missing_out, index=False)
    extra_in_csv.to_csv(extra_out, index=False)
    summary_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Validação concluída.")
    print(f"- Extração PDF: {pdf_out}")
    print(f"- Ground truth sugerida (somente CSV): {pdf_ground_truth_out}")
    print(f"- Linha a linha CSV: {detailed_out}")
    print(f"- Faltantes no CSV: {missing_out}")
    print(f"- Extras no CSV: {extra_out}")
    print(f"- Resumo: {summary_out}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
