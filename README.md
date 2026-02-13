# 🌿 Calculadora de Taxas - Licenciamento Ambiental

**Atenas Projetos Ambientais - Sistema Inteligente de Cálculo**

Este projeto é uma aplicação web desenvolvida em Python com [Streamlit](https://streamlit.io/) para calcular taxas de licenciamento ambiental (LP, LI, LO) com base na legislação municipal (foco em Ariquemes/RO - Lei 2.349/2019 e Porto Velho). O sistema detecta automaticamente o potencial poluidor, classifica o porte do empreendimento e gera relatórios em PDF.

## ✨ Funcionalidades

*   **Autenticação Segura**: Acesso restrito via login/senha (hash seguro) e gestão de sessão.
*   **Gestão de Formulário Wizard**: Passo-a-passo intuitivo para preenchimento dos dados do empreendimento.
*   **Detecção Automática de Potencial Poluidor**: Baseada na atividade selecionada (Anexo I).
*   **Cálculo Automático de Porte**: Classificação (Mínimo a Excepcional) baseada na medida (Área, Potência ou Funcionários) conforme limites legais.
*   **Cálculo de Taxas (UFAR -> R$)**: Conversão automática de unidades fiscais para Reais baseada na configuração municipal.
*   **Geração de Relatório PDF**: Resumo profissional com todos os dados e valores calculados, pronto para envio ao cliente.
*   **Histórico de Cálculos**: Armazenamento automático de todas as simulações em banco de dados SQLite local.
*   **Área Administrativa**: Visualização e exportação do histórico de cálculos (CSV) para usuários admin.

## 🛠️ Tecnologias Utilizadas

*   **Python 3.8+**
*   **Streamlit**: Framework de interface web.
*   **Pandas**: Manipulação de dados (CSV e cálculos).
*   **Streamlit-Authenticator**: Gestão de autenticação.
*   **FPDF**: Geração de documentos PDF.
*   **SQLite**: Persistência de dados leve.
*   **YAML**: Configuração e credenciais.

## 🚀 Como Executar

### Pré-requisitos

Certifique-se de ter o Python instalado. Recomenda-se o uso de um ambiente virtual.

### Instalação

1.  Clone o repositório:
    ```bash
    git clone <url-do-repositorio>
    cd licenca
    ```

2.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```

### Configuração de Credenciais

1.  O arquivo `config.yaml` contém as configurações de autenticação.
2.  Para adicionar novos usuários ou resetar senhas, utilize o utilitário `generate_keys.py`:
    ```bash
    python generate_keys.py senha_desejada
    ```
3.  Copie o hash gerado e atualize o campo `password` no `config.yaml`.

### Executando a Aplicação

Rode o comando:

```bash
streamlit run calculadora_taxas.py
```

A aplicação abrirá automaticamente no seu navegador padrão (geralmente em `http://localhost:8501`).

## 📂 Estrutura de Arquivos

*   `calculadora_taxas.py`: Aplicação principal.
*   `database.py`: Módulo de interação com o banco de dados SQLite (`historico_calculos.db`).
*   `config.yaml`: Arquivo de configuração (credenciais, cookie, etc).
*   `generate_keys.py`: Script utilitário para gerar hashes de senhas.
*   `ANEXO_I_cleaned_with_portes.csv`: Base de dados das atividades e faixas de porte.
*   `taxas_ambientais_ufar.csv`: Tabela de valores das taxas em UFAR.
*   `IBGE_CNAE_Subclass2.3.csv`: Base de dados de CNAEs.

## 🧠 Lógica Principal (calculadora_taxas.py)

O coração da aplicação reside no script `calculadora_taxas.py`, que orquestra todo o fluxo de dados:

1.  **Carregamento de Dados (`@st.cache_data`)**:
    *   Tabelas de atividades (Anexo I), taxas (UFAR) e CNAEs são carregadas em memória e cacheadas para performance.
    *   Colunas numéricas e strings são normalizadas para evitar erros de comparação.

2.  **Detecção de Potencial Poluidor**:
    *   Ao selecionar uma atividade, o sistema consulta o atributo `POTENCIAL_POLUIDOR` direto do CSV mapeado.
    *   A função `normalizar_potencial_poluidor` garante que termos como "Pequeno", "Médio" e "Alto" sejam padronizados.
    *   *Visualização*: O usuário vê imediatamente um indicador colorido (Verde/Amarelo/Vermelho).

3.  **Classificação Inteligente de Porte (`classificar_porte_por_linha_valor`)**:
    *   Diferente de sistemas rígidos, este algoritmo varre as faixas de porte (Mínimo a Excepcional) definidas nas colunas `PORTE_*_MIN` e `PORTE_*_MAX` da atividade.
    *   Compara o valor medido (área, potência, etc.) com esses intervalos.
    *   *Lógica Inclusiva*: Trata casos extremos (ex: "Até 2 ha") e intermediários com precisão.

4.  **Cálculo Financeiro (`obter_taxa_ufar` e `calcular_taxa`)**:
    *   Cruza os dados: `Anexo` + `Porte Calculado` + `Potencial Poluidor` + `Tipo de Licença`.
    *   Busca o valor exato em UFAR na tabela de taxas (`taxas_ambientais_ufar.csv`).
    *   Multiplica pela UFAR do município (configurada em código, ex: Ariquemes = 85.15) para obter o valor em Reais.

5.  **Persistência**:
    *   Ao final, todos os dados calculados são enviados para a função `salvar_calculo` e gravados no banco SQLite local.

## 📝 Notas Legais

> ⚠️ **Atenção**: Este simulador utiliza dados oficiais da Lei 2.349/2019 de Ariquemes/RO como base. Os valores são estimativas e podem variar. Consulte sempre o órgão ambiental competente para os valores oficiais atualizados.

---
Desenvolvido por **Atenas Projetos Ambientais**.
