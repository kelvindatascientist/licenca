import argparse
from pathlib import Path

import pandas as pd


# Resolução explícita das chaves ambíguas do PDF (layout quebrado no DOE),
# revisadas manualmente nas páginas das tabelas.
OVERRIDES = {
    ("ANEXO II", "Mínimo", "Baixo"): (8.0, 8.0, 8.0),
    ("ANEXO XIX", "Mínimo", "Baixo"): (8.0, 8.0, 8.0),
    ("ANEXO XXVII", "Mínimo", "Baixo"): (5.0, 5.0, 5.0),
    ("ANEXO XLIII", "Médio", "Baixo"): (0.0, 0.0, 0.0),
    ("ANEXO XLIII", "Médio", "Médio"): (10.0, 10.0, 20.0),
    ("ANEXO XLIV", "Excepcional", "Médio"): (5.0, 40.0, 50.0),
    ("ANEXO XLIV", "Excepcional", "Alto"): (10.0, 50.0, 70.0),
    ("ANEXO XVII", "Médio", "Baixo"): (10.0, 25.0, 50.0),
    ("ANEXO XVII", "Médio", "Alto"): (10.0, 80.0, 170.0),
    ("ANEXO XVII", "Grande", "Médio"): (10.0, 60.0, 180.0),
    ("ANEXO XVII", "Grande", "Alto"): (10.0, 100.0, 230.0),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Saneia CSV SEDAM ground truth removendo ambiguidades de chave.")
    parser.add_argument("--input", default="taxas_sedam_upfs_ground_truth.csv")
    parser.add_argument("--output", default="taxas_sedam_upfs_ground_truth_clean.csv")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_csv(input_path)
    for c in ["TLP", "TLI", "TLO"]:
        df[c] = df[c].astype(float)

    key_cols = ["ANEXO", "PORTE", "POTENCIAL_POLUIDOR"]
    original_rows = len(df)

    # 1) Remove duplicidades exatas
    df = df.drop_duplicates().reset_index(drop=True)

    # 2) Resolve chaves conflitantes com overrides
    keep_rows = []
    for key, group in df.groupby(key_cols, sort=False):
        if len(group) == 1:
            keep_rows.append(group.iloc[0].to_dict())
            continue

        if key not in OVERRIDES:
            raise ValueError(
                f"Chave duplicada sem regra de resolução: {key}. "
                "Atualize o dicionário OVERRIDES após auditoria no PDF."
            )

        target = OVERRIDES[key]
        chosen = group[
            (group["TLP"] == target[0]) & (group["TLI"] == target[1]) & (group["TLO"] == target[2])
        ]
        if chosen.empty:
            raise ValueError(
                f"Override não encontrado no CSV para chave {key}: "
                f"esperado TLP/TLI/TLO={target}"
            )
        keep_rows.append(chosen.iloc[0].to_dict())

    clean_df = pd.DataFrame(keep_rows)

    # 3) Garantias finais
    dup_count = clean_df.duplicated(subset=key_cols).sum()
    if dup_count > 0:
        raise ValueError(f"Falha: CSV limpo ainda possui {dup_count} chaves duplicadas.")

    clean_df = clean_df.sort_values(["ANEXO", "PORTE", "POTENCIAL_POLUIDOR"]).reset_index(drop=True)
    clean_df.to_csv(output_path, index=False)

    print(f"Entrada: {input_path} ({original_rows} linhas)")
    print(f"Saída: {output_path} ({len(clean_df)} linhas)")
    print("Duplicidades por chave após limpeza: 0")


if __name__ == "__main__":
    main()
