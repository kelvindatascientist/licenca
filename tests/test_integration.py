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
