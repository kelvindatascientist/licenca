import pandas as pd
import unicodedata
import re
import math

INPUT_PATH = "SEMA_ANEXO_I_full.csv"
OUTPUT_PATH = "ANEXO_I_cleaned_with_portes.csv"


def strip_accents(s: str) -> str:
    """Remove acentos: 'Até' -> 'Ate'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def parse_interval_to_min_max(text: str) -> tuple[float | None, float | None]:
    """
    Converte textos como:
      - 'até2'
      - 'Até25'
      - 'de2,0001até 10'
      - 'de 50,01 a 100'
      - 'acimade60'
    em (min, max).

    None significa sem limite (ex.: max=None => infinito).
    """
    if not isinstance(text, str):
        return (None, None)

    text = text.strip()
    if not text or text == "-":
        return (None, None)

    t = strip_accents(text).lower()
    t = t.replace(" ", "")
    t = t.replace(",", ".")
    nums = re.findall(r"\d+(?:\.\d+)?", t)

    # 'atéX' / 'AteX'  -> [0, X]
    if t.startswith("ate"):
        if not nums:
            return (None, None)
        upper = float(nums[0])
        return (0.0, upper)

    # 'deAateB' ou 'deAaB'  -> [A, B]
    if t.startswith("de"):
        m = re.match(
            r"de(?P<low>\d+(?:\.\d+)?)(?:ate|a)(?P<high>\d+(?:\.\d+)?)",
            t,
        )
        if m:
            low = float(m.group("low"))
            high = float(m.group("high"))
            return (low, high)

    # 'acimadeX' / 'acima deX'  -> (X, +inf)
    if t.startswith("acimade") or t.startswith("acima"):
        if not nums:
            return (None, None)
        low = float(nums[0])
        return (low, None)

    # fallback: se só tem 1 número, assume [0, num]
    if len(nums) == 1:
        v = float(nums[0])
        return (0.0, v)
    elif len(nums) >= 2:
        low, high = map(float, nums[:2])
        return (low, high)

    return (None, None)


def main():
    df = pd.read_csv(INPUT_PATH, dtype=str)

    porte_cols = [
        "PORTE_MINIMO",
        "PORTE_PEQUENO",
        "PORTE_MEDIO",
        "PORTE_GRANDE",
        "PORTE_EXCEPCIONAL",
    ]

    df_clean = df.copy()

    for col in porte_cols:
        mins = []
        maxs = []
        for val in df_clean[col]:
            lo, hi = parse_interval_to_min_max(val)
            mins.append(lo)
            maxs.append(hi)
        df_clean[f"{col}_MIN"] = mins
        df_clean[f"{col}_MAX"] = maxs

    # Garante que todos *_MIN / *_MAX são numéricos (NaN quando não houver)
    for col in [c for c in df_clean.columns if c.endswith("_MIN") or c.endswith("_MAX")]:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

    df_clean.to_csv(OUTPUT_PATH, index=False)
    print(f"Arquivo limpo salvo em: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
