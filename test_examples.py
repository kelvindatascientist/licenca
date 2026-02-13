import ast
import json
from pathlib import Path

import pandas as pd


def _load_logic_functions():
    """
    Carrega apenas as funções de lógica de calculadora_taxas.py sem executar a UI do Streamlit.
    """
    file_path = Path(__file__).with_name("calculadora_taxas.py")
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    target_functions = {
        "normalizar_texto",
        "normalizar_cnae_codigo",
        "extrair_codigo_cnae_display",
        "verificar_cnaes_em_las",
        "definir_enquadramento",
        "calcular_enquadramento_final",
    }

    selected_nodes = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            selected_nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in target_functions:
            selected_nodes.append(node)

    module = ast.Module(body=selected_nodes, type_ignores=[])
    compiled = compile(module, filename=str(file_path), mode="exec")
    namespace = {}
    exec(compiled, namespace, namespace)
    return namespace


def _run_example():
    ns = _load_logic_functions()
    verificar_cnaes_em_las = ns["verificar_cnaes_em_las"]
    calcular_enquadramento_final = ns["calcular_enquadramento_final"]

    planilha_las = Path(__file__).with_name("Lista de atividades LAS E CNAES.xlsx")
    df_las = pd.read_excel(planilha_las, dtype=str).fillna("")

    # Exemplo solicitado
    cnaes = ["1099-6/04 - Fabricação de gelo comum"]
    medida_m2 = 200.0
    municipio = "Ariquemes - RO"
    potencial = "Alto"
    possui_mapeamento_cnae = False

    is_las, las_matches = verificar_cnaes_em_las(cnaes, df_las)
    enquadramento_info, las_aplicavel = calcular_enquadramento_final(
        municipio=municipio,
        possui_mapeamento_cnae=possui_mapeamento_cnae,
        potencial_poluidor=potencial,
        possui_cnae_las=is_las,
    )

    debug = {
        "cnaes_input": cnaes,
        "medida_m2": medida_m2,
        "municipio": municipio,
        "potencial_poluidor": potencial,
        "possui_mapeamento_cnae": possui_mapeamento_cnae,
        "is_las_na_planilha": is_las,
        "las_matches": las_matches,
        "las_aplicavel": las_aplicavel,
        "enquadramento_info": enquadramento_info,
    }
    return debug


def test_cnae_1099604_deve_ser_las():
    debug = _run_example()
    assert debug["enquadramento_info"]["enquadramento"] == "LAS", (
        "Esperado LAS para CNAE 1099-6/04 no cenário de teste. "
        f"Debug: {json.dumps(debug, ensure_ascii=False)}"
    )


if __name__ == "__main__":
    result = _run_example()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    assert result["enquadramento_info"]["enquadramento"] == "LAS", (
        "Esperado LAS para CNAE 1099-6/04. "
        f"Debug: {json.dumps(result, ensure_ascii=False)}"
    )
    print("OK: assert == LAS")
