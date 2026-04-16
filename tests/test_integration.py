"""
Integration tests: real CSV/xlsx data files and isolated SQLite database.
"""
import math
import sqlite3

import pandas as pd
import pytest


# ═══════════════════════════════════════════════════════════════
# verificar_cnaes_em_las — real LAS spreadsheet
# ═══════════════════════════════════════════════════════════════

class TestVerificarCnaesEmLasReal:
    def test_cnae_las_conhecido_retorna_true(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        is_las, matches = fn(["1099-6/04 - Fabricação de gelo comum"], df_las)
        assert is_las is True
        assert len(matches) > 0

    def test_cnae_nao_existente_retorna_false(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        is_las, matches = fn(["9999-9/99 - Atividade completamente fictícia"], df_las)
        assert is_las is False
        assert matches == []

    def test_lista_vazia_retorna_false(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        is_las, matches = fn([], df_las)
        assert is_las is False
        assert matches == []

    def test_df_vazio_retorna_false(self, logic):
        fn = logic["verificar_cnaes_em_las"]
        is_las, matches = fn(["1099-6/04"], pd.DataFrame())
        assert is_las is False

    def test_matches_tem_campos_esperados(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        _, matches = fn(["1099-6/04 - Fabricação de gelo comum"], df_las)
        if matches:
            m = matches[0]
            assert "cnae_codigo" in m
            assert "item_las" in m
            assert "atividade_las" in m

    def test_matches_contem_cnae_informado(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        display = "1099-6/04 - Fabricação de gelo comum"
        _, matches = fn([display], df_las)
        if matches:
            assert matches[0]["cnae_display"] == display

    def test_varios_cnaes_detecta_pelo_menos_um_las(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        cnaes = [
            "9999-9/99 - Fictício",
            "1099-6/04 - Fabricação de gelo comum",
        ]
        is_las, matches = fn(cnaes, df_las)
        assert is_las is True


# ═══════════════════════════════════════════════════════════════
# obter_taxa_ufar — real SEMA table (taxas_ambientais_ufar.csv)
# ═══════════════════════════════════════════════════════════════
# From the CSV: ANEXO="ANEXOII" (no space), PORTE="Mínimo", POTENCIAL_POLUIDOR="Baixo"
# The code normalises ANEXO by removing spaces before comparison.

class TestObterTaxaUfarSema:
    @pytest.mark.parametrize("servico,col", [
        ("Licença Prévia",        "TLP"),
        ("Licença de Instalação", "TLI"),
        ("Licença de Operação",   "TLO"),
    ])
    def test_retorna_valor_positivo_para_combinacao_valida(
        self, logic, df_taxas_sema, servico, col
    ):
        fn = logic["obter_taxa_ufar"]
        val = fn(df_taxas_sema, "ANEXO II", "Mínimo", "Baixo", servico)
        assert val > 0, f"Expected positive value for {servico}, got {val}"

    def test_combinacao_invalida_retorna_default_lp(self, logic, df_taxas_sema):
        fn = logic["obter_taxa_ufar"]
        val = fn(df_taxas_sema, "ANEXO_INEXISTENTE", "Gigante", "BAIXO",
                 "Licença Prévia")
        assert val == 50  # hard-coded default

    def test_retorna_float(self, logic, df_taxas_sema):
        fn = logic["obter_taxa_ufar"]
        val = fn(df_taxas_sema, "ANEXO II", "Mínimo", "Baixo", "Licença Prévia")
        assert isinstance(val, float)

    def test_maior_porte_tem_valor_maior_ou_igual(self, logic, df_taxas_sema):
        """Larger sizes should cost at least as much as smaller sizes."""
        fn = logic["obter_taxa_ufar"]
        val_minimo  = fn(df_taxas_sema, "ANEXO II", "Mínimo",  "Baixo", "Licença Prévia")
        val_pequeno = fn(df_taxas_sema, "ANEXO II", "Pequeno", "Baixo", "Licença Prévia")
        assert val_pequeno >= val_minimo


# ═══════════════════════════════════════════════════════════════
# obter_taxa_ufar — real SEDAM table
# ═══════════════════════════════════════════════════════════════
# From the CSV: ANEXO="ANEXO II", PORTE="Excepcional", POTENCIAL_POLUIDOR="Alto"

class TestObterTaxaUfarSedam:
    def test_retorna_valor_positivo(self, logic, df_taxas_sedam):
        fn = logic["obter_taxa_ufar"]
        val = fn(df_taxas_sedam, "ANEXO II", "Excepcional", "Alto", "Licença Prévia")
        assert val > 0

    def test_lp_menor_que_lo(self, logic, df_taxas_sedam):
        """TLP should typically be less than TLO for SEDAM."""
        fn = logic["obter_taxa_ufar"]
        tlp = fn(df_taxas_sedam, "ANEXO II", "Excepcional", "Alto", "Licença Prévia")
        tlo = fn(df_taxas_sedam, "ANEXO II", "Excepcional", "Alto", "Licença de Operação")
        assert tlo >= tlp


# ═══════════════════════════════════════════════════════════════
# calcular_taxa — real SEMA table
# ═══════════════════════════════════════════════════════════════

class TestCalcularTaxaIntegracao:
    def test_valor_reais_equals_ufar_times_ufir(self, logic, df_taxas_sema):
        fn = logic["calcular_taxa"]
        ufir = 85.15
        valor_reais, valor_ufar = fn(
            "Licença Prévia", "Pequeno", "ANEXO II", "Baixo", df_taxas_sema, ufir,
        )
        assert math.isclose(valor_reais, valor_ufar * ufir, rel_tol=1e-9)

    def test_ufir_ariquemes_produz_valor_esperado(self, logic, df_taxas_sema):
        fn = logic["calcular_taxa"]
        # ANEXOII / Mínimo / Baixo / TLP = 7 UFAR (from CSV)
        # 7 * 85.15 = 596.05
        valor_reais, valor_ufar = fn(
            "Licença Prévia", "Mínimo", "ANEXO II", "Baixo", df_taxas_sema, 85.15,
        )
        assert valor_ufar == pytest.approx(7.0)
        assert valor_reais == pytest.approx(7.0 * 85.15)

    @pytest.mark.parametrize("municipio,ufir", [
        ("Ariquemes - RO", 85.15),
        ("Porto Velho - RO", 81.22),
    ])
    def test_valores_variam_por_municipio(self, logic, df_taxas_sema, municipio, ufir):
        fn = logic["calcular_taxa"]
        valor_reais, valor_ufar = fn(
            "Licença Prévia", "Mínimo", "ANEXO II", "Baixo", df_taxas_sema, ufir,
        )
        assert math.isclose(valor_reais, valor_ufar * ufir, rel_tol=1e-9)


# ═══════════════════════════════════════════════════════════════
# preparar_atividades — real ANEXO I
# ═══════════════════════════════════════════════════════════════

class TestPrepararAtividades:
    def test_adiciona_colunas_necessarias(self, logic, df_atividades):
        fn = logic["preparar_atividades"]
        result = fn(df_atividades)
        assert "ITEM_STR" in result.columns
        assert "ITEM_BASE" in result.columns
        assert "IS_GRUPO" in result.columns

    def test_grupos_nao_tem_ponto_no_item(self, logic, df_atividades):
        fn = logic["preparar_atividades"]
        result = fn(df_atividades)
        grupos = result[result["IS_GRUPO"]]
        for item in grupos["ITEM_STR"]:
            assert "." not in item, f"Grupo item should not contain '.': {item}"

    def test_subatividades_tem_ponto_no_item(self, logic, df_atividades):
        fn = logic["preparar_atividades"]
        result = fn(df_atividades)
        subs = result[~result["IS_GRUPO"]]
        assert not subs.empty
        for item in subs["ITEM_STR"]:
            assert "." in item, f"Sub-item should contain '.': {item}"

    def test_nao_modifica_dataframe_original(self, logic, df_atividades):
        fn = logic["preparar_atividades"]
        original_cols = list(df_atividades.columns)
        fn(df_atividades)
        assert list(df_atividades.columns) == original_cols


# ═══════════════════════════════════════════════════════════════
# Pipeline: enquadramento final with real LAS data
# ═══════════════════════════════════════════════════════════════

class TestEnquadramentoPipelineReal:
    def test_cnae_las_enquadra_como_las(self, logic, df_las):
        verificar = logic["verificar_cnaes_em_las"]
        calcular  = logic["calcular_enquadramento_final"]

        is_las, _ = verificar(["1099-6/04 - Fabricação de gelo comum"], df_las)
        info, las_aplicavel = calcular(
            municipio="Ariquemes - RO",
            possui_mapeamento_cnae=True,
            potencial_poluidor="Alto",
            possui_cnae_las=is_las,
        )
        assert info["enquadramento"] == "LAS"
        assert las_aplicavel is True

    def test_cnae_sem_las_alto_potencial_vai_sedam(self, logic, df_las):
        verificar = logic["verificar_cnaes_em_las"]
        calcular  = logic["calcular_enquadramento_final"]

        is_las, _ = verificar(["9999-9/99 - Fictício"], df_las)
        info, _ = calcular(
            municipio="Ariquemes - RO",
            possui_mapeamento_cnae=True,
            potencial_poluidor="Alto",
            possui_cnae_las=is_las,
        )
        assert info["orgao"] == "SEDAM"

    def test_cnae_sem_las_baixo_potencial_vai_sema(self, logic, df_las):
        verificar = logic["verificar_cnaes_em_las"]
        calcular  = logic["calcular_enquadramento_final"]

        is_las, _ = verificar(["9999-9/99 - Fictício"], df_las)
        info, _ = calcular(
            municipio="Ariquemes - RO",
            possui_mapeamento_cnae=True,
            potencial_poluidor="Baixo",
            possui_cnae_las=is_las,
        )
        assert info["orgao"] == "SEMA"


# ═══════════════════════════════════════════════════════════════
# database — isolated per-test via tmp_db fixture
# ═══════════════════════════════════════════════════════════════

class TestDatabase:
    def test_init_db_cria_tabela_calculos(self, tmp_db):
        import database
        database.init_db()
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='calculos'"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_init_db_e_idempotente(self, tmp_db):
        import database
        database.init_db()
        database.init_db()  # second call should not raise

    def test_salvar_e_listar_round_trip(self, tmp_db):
        import database
        database.init_db()
        database.salvar_calculo(
            municipio="Ariquemes - RO",
            grupo="1 - Extrativismo",
            atividade="Extração de madeira",
            medida="15 ha",
            porte="Pequeno",
            potencial="Baixo",
            valor_total=1282.50,
            cnpj_cpf="12.345.678/0001-99",
            cnaes="0220-9/01",
            email="user@empresa.com",
            telefone="(69) 99999-9999",
            usuario_login="kelvin",
            usuario_nome="Kelvin Pacheco",
        )
        df = database.listar_calculos()
        assert len(df) == 1
        row = df.iloc[0]
        assert row["municipio"] == "Ariquemes - RO"
        assert row["valor_total"] == pytest.approx(1282.50)
        assert row["cnpj_cpf"] == "12.345.678/0001-99"
        assert row["usuario_login"] == "kelvin"

    def test_listar_retorna_mais_recente_primeiro(self, tmp_db):
        import database
        database.init_db()
        database.salvar_calculo("Ariquemes - RO", "G1", "Atividade A", "1 ha",
                                "Mínimo", "Baixo", 100.0)
        database.salvar_calculo("Ariquemes - RO", "G2", "Atividade B", "5 ha",
                                "Pequeno", "Médio", 500.0)
        df = database.listar_calculos()
        assert df.iloc[0]["atividade"] == "Atividade B"  # ORDER BY id DESC

    def test_listar_banco_vazio_retorna_dataframe_vazio(self, tmp_db):
        import database
        database.init_db()
        df = database.listar_calculos()
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_multiplos_registros_salvos_corretamente(self, tmp_db):
        import database
        database.init_db()
        for i in range(5):
            database.salvar_calculo(
                municipio="Ariquemes - RO",
                grupo=f"G{i}",
                atividade=f"Atividade {i}",
                medida=f"{i} ha",
                porte="Pequeno",
                potencial="Baixo",
                valor_total=float(i * 100),
            )
        df = database.listar_calculos()
        assert len(df) == 5

    def test_migracao_adiciona_colunas_faltantes(self, tmp_db):
        """init_db must add columns missing from an older schema without data loss."""
        import database

        # Simulate an old schema without the newer columns
        conn = sqlite3.connect(tmp_db)
        conn.execute("""
            CREATE TABLE calculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT, municipio TEXT, grupo TEXT,
                atividade TEXT, medida TEXT, porte TEXT,
                potencial_poluidor TEXT, valor_total REAL
            )
        """)
        conn.execute(
            "INSERT INTO calculos (municipio, atividade, valor_total) "
            "VALUES ('Ariquemes - RO', 'Teste', 99.0)"
        )
        conn.commit()
        conn.close()

        # Migration should add missing columns without losing the existing row
        database.init_db()

        conn = sqlite3.connect(tmp_db)
        col_names = [r[1] for r in conn.execute("PRAGMA table_info(calculos)")]
        rows = conn.execute("SELECT * FROM calculos").fetchall()
        conn.close()

        for col in ["cnpj_cpf", "cnaes", "email", "telefone",
                    "usuario_login", "usuario_nome"]:
            assert col in col_names, f"Migration did not add column '{col}'"

        assert len(rows) == 1, "Existing data must be preserved after migration"

    def test_campos_opcionais_aceitam_string_vazia(self, tmp_db):
        import database
        database.init_db()
        # Should not raise
        database.salvar_calculo(
            municipio="Ariquemes - RO",
            grupo="G1", atividade="A1", medida="1 ha",
            porte="Mínimo", potencial="Baixo", valor_total=0.0,
            cnpj_cpf="", cnaes="", email="", telefone="",
            usuario_login="", usuario_nome="",
        )
        df = database.listar_calculos()
        assert len(df) == 1


# ═══════════════════════════════════════════════════════════════
# mapear_cnaes_para_atividades — exceções manuais de CNAE
# ═══════════════════════════════════════════════════════════════

class TestExcecoesMapeamentoCnae:
    def test_cnae_motocicletas_mapeia_para_veiculos_automotores(
        self, logic, df_cnaes, df_atividades
    ):
        """4543-9/00 deve mapear para oficina mecânica (ITEM 82.2), não para motocicletas."""
        preparar = logic["preparar_atividades"]
        mapear = logic["mapear_cnaes_para_atividades"]

        atividades_prep = preparar(df_atividades)
        resultados = mapear(
            ["4543-9/00 - Manutenção e reparação de motocicletas e motonetas"],
            df_cnaes,
            atividades_prep,
        )

        assert len(resultados) == 1
        r = resultados[0]
        assert r["mapeado"] is True, "Deveria mapear via exceção manual"
        assert r["atividade"] == "Manutenção e reparação de veículos automotores (oficina mecânica)"
        assert r["potencial"] == "Médio"

    def test_cnae_sem_excecao_usa_similaridade_normalmente(
        self, logic, df_cnaes, df_atividades
    ):
        """CNAEs sem exceção manual continuam usando o matcher de similaridade."""
        preparar = logic["preparar_atividades"]
        mapear = logic["mapear_cnaes_para_atividades"]

        atividades_prep = preparar(df_atividades)
        # 1099-6/04 não está nas exceções — deve usar similaridade
        resultados = mapear(
            ["1099-6/04 - Fabricação de gelo comum"],
            df_cnaes,
            atividades_prep,
        )
        assert len(resultados) == 1
        # Should either map or not, but must not raise
        assert isinstance(resultados[0]["mapeado"], bool)


# ═══════════════════════════════════════════════════════════════
# verificar_cnaes_em_las — edge cases with real spreadsheet
# ═══════════════════════════════════════════════════════════════

class TestVerificarCnaesEmLasEdgeCases:
    def test_alternate_format_still_matches(self, logic, df_las):
        """'1099-6/4' (without leading zero in subclass) must match '1099-6/04'."""
        fn = logic["verificar_cnaes_em_las"]
        is_las, matches = fn(["1099-6/4 - Fabricação de gelo comum"], df_las)
        assert is_las is True, "Short CNAE format should normalise to same key"

    def test_only_digits_format_matches(self, logic, df_las):
        """'1099604' (pure digits) must also resolve to the same LAS CNAE."""
        fn = logic["verificar_cnaes_em_las"]
        is_las, _ = fn(["1099604"], df_las)
        assert is_las is True

    def test_all_cnaes_non_las_returns_false(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        is_las, matches = fn(
            ["9999-9/99 - X", "8888-8/88 - Y", "7777-7/77 - Z"], df_las
        )
        assert is_las is False
        assert matches == []

    def test_matches_list_length_equals_las_hits(self, logic, df_las):
        """matches list must have one entry per LAS-matching CNAE, not per input."""
        fn = logic["verificar_cnaes_em_las"]
        # Two real LAS CNAEs + one non-LAS
        cnaes = [
            "1099-6/04 - Fabricação de gelo comum",
            "4723-7/00 - Comércio varejista de bebidas",
            "9999-9/99 - Fictício",
        ]
        is_las, matches = fn(cnaes, df_las)
        assert is_las is True
        assert len(matches) == 2

    def test_match_contains_all_expected_keys(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        _, matches = fn(["1099-6/04 - Fabricação de gelo comum"], df_las)
        required = {"cnae_display", "cnae_codigo", "item_las", "atividade_las"}
        assert required <= matches[0].keys()

    def test_match_item_las_is_nonempty(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        _, matches = fn(["1099-6/04 - Fabricação de gelo comum"], df_las)
        assert matches[0]["item_las"] != ""

    def test_match_atividade_las_is_nonempty(self, logic, df_las):
        fn = logic["verificar_cnaes_em_las"]
        _, matches = fn(["1099-6/04 - Fabricação de gelo comum"], df_las)
        assert matches[0]["atividade_las"] != ""


# ═══════════════════════════════════════════════════════════════
# obter_taxa_ufar — SEMA table: exact values from CSV
# ═══════════════════════════════════════════════════════════════

class TestObterTaxaUfarSemaExactValues:
    """Verify specific values directly from the SEMA CSV to catch regressions."""

    @pytest.mark.parametrize("porte,pot,servico,expected", [
        ("Mínimo",      "Baixo", "Licença Prévia",         7.0),
        ("Mínimo",      "Baixo", "Licença de Instalação",  7.0),
        ("Mínimo",      "Baixo", "Licença de Operação",   14.0),
        ("Mínimo",      "Médio", "Licença Prévia",          8.0),
        ("Mínimo",      "Alto",  "Licença Prévia",         10.0),
        ("Pequeno",     "Baixo", "Licença Prévia",         12.0),
        ("Excepcional", "Alto",  "Licença de Operação",   570.0),
    ])
    def test_valor_exato(self, logic, df_taxas_sema, porte, pot, servico, expected):
        fn = logic["obter_taxa_ufar"]
        val = fn(df_taxas_sema, "ANEXO II", porte, pot, servico)
        assert val == pytest.approx(expected), (
            f"SEMA ANEXO II / {porte} / {pot} / {servico}: expected {expected}, got {val}"
        )

    def test_tli_always_between_tlp_and_tlo_baixo(self, logic, df_taxas_sema):
        """TLP ≤ TLI ≤ TLO should hold for every porte at Baixo potencial."""
        fn = logic["obter_taxa_ufar"]
        portes = ["Mínimo", "Pequeno", "Médio", "Grande", "Excepcional"]
        for porte in portes:
            tlp = fn(df_taxas_sema, "ANEXO II", porte, "Baixo", "Licença Prévia")
            tli = fn(df_taxas_sema, "ANEXO II", porte, "Baixo", "Licença de Instalação")
            tlo = fn(df_taxas_sema, "ANEXO II", porte, "Baixo", "Licença de Operação")
            assert tlp <= tli <= tlo, (
                f"Order violation at {porte}/Baixo: TLP={tlp}, TLI={tli}, TLO={tlo}"
            )


# ═══════════════════════════════════════════════════════════════
# mapear_cnaes_para_atividades — edge cases
# ═══════════════════════════════════════════════════════════════

class TestMapearCnaesParaAtividadesEdgeCases:
    def test_empty_list_returns_empty(self, logic, df_cnaes, df_atividades):
        preparar = logic["preparar_atividades"]
        mapear = logic["mapear_cnaes_para_atividades"]
        atividades_prep = preparar(df_atividades)
        assert mapear([], df_cnaes, atividades_prep) == []

    def test_result_length_equals_input_length(self, logic, df_cnaes, df_atividades):
        preparar = logic["preparar_atividades"]
        mapear = logic["mapear_cnaes_para_atividades"]
        atividades_prep = preparar(df_atividades)
        cnaes = [
            "1099-6/04 - Fabricação de gelo comum",
            "9999-9/99 - Fictício",
            "4543-9/00 - Manutenção e reparação de motocicletas",
        ]
        resultados = mapear(cnaes, df_cnaes, atividades_prep)
        assert len(resultados) == 3

    def test_cnae_not_in_reference_is_not_mapped(self, logic, df_cnaes, df_atividades):
        """A CNAE absent from the IBGE reference gets denominacao='' → score 0 → mapeado=False."""
        preparar = logic["preparar_atividades"]
        mapear = logic["mapear_cnaes_para_atividades"]
        atividades_prep = preparar(df_atividades)
        resultados = mapear(["9999-9/99 - Atividade Fictícia"], df_cnaes, atividades_prep)
        assert resultados[0]["mapeado"] is False

    def test_result_has_all_required_keys(self, logic, df_cnaes, df_atividades):
        preparar = logic["preparar_atividades"]
        mapear = logic["mapear_cnaes_para_atividades"]
        atividades_prep = preparar(df_atividades)
        resultados = mapear(
            ["4543-9/00 - Manutenção e reparação de motocicletas e motonetas"],
            df_cnaes, atividades_prep,
        )
        required = {"cnae_display", "cnae_codigo", "cnae_denominacao",
                    "mapeado", "score", "grupo", "atividade", "potencial", "anexo"}
        assert required <= resultados[0].keys()

    def test_score_is_1_for_manual_override(self, logic, df_cnaes, df_atividades):
        """Manual EXCECOES_MAPEAMENTO_CNAE overrides must report score=1.0."""
        preparar = logic["preparar_atividades"]
        mapear = logic["mapear_cnaes_para_atividades"]
        atividades_prep = preparar(df_atividades)
        resultados = mapear(
            ["4543-9/00 - Manutenção e reparação de motocicletas e motonetas"],
            df_cnaes, atividades_prep,
        )
        assert resultados[0]["score"] == pytest.approx(1.0)


# ═══════════════════════════════════════════════════════════════
# Pipeline: enquadramento final with multiple municipalities
# ═══════════════════════════════════════════════════════════════

class TestEnquadramentoPipelineEdgeCases:
    def test_porto_velho_alto_potencial_goes_sema_not_sedam(self, logic, df_las):
        """Porto Velho must always route to SEMA regardless of potencial."""
        verificar = logic["verificar_cnaes_em_las"]
        calcular  = logic["calcular_enquadramento_final"]
        is_las, _ = verificar(["9999-9/99 - Fictício"], df_las)
        info, _ = calcular("Porto Velho - RO", True, "Alto", possui_cnae_las=is_las)
        assert info["orgao"] == "SEMA"

    def test_cnae_las_alternate_format_enquadra_como_las(self, logic, df_las):
        """Short CNAE format should also trigger LAS enquadramento."""
        verificar = logic["verificar_cnaes_em_las"]
        calcular  = logic["calcular_enquadramento_final"]
        is_las, _ = verificar(["1099-6/4 - Fabricação de gelo"], df_las)
        info, las_flag = calcular("Ariquemes - RO", True, "Alto", possui_cnae_las=is_las)
        assert info["enquadramento"] == "LAS"
        assert las_flag is True

    def test_multiple_cnaes_one_las_enquadra_como_las(self, logic, df_las):
        """Even if only one of several CNAEs is in LAS, the result must be LAS."""
        verificar = logic["verificar_cnaes_em_las"]
        calcular  = logic["calcular_enquadramento_final"]
        is_las, _ = verificar([
            "9999-9/99 - Fictício",
            "1099-6/04 - Fabricação de gelo comum",
        ], df_las)
        info, las_flag = calcular("Ariquemes - RO", True, "Alto", possui_cnae_las=is_las)
        assert info["enquadramento"] == "LAS"
