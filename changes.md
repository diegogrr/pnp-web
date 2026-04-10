# Alterações em relação ao notebook original

Este documento descreve as mudanças realizadas nos arquivos `app/processor.py` e
`app/routes.py` em relação à lógica original do notebook `GeraTabelasPNP.ipynb`.

As alterações são de três naturezas distintas: **correções de bugs**, **adaptação
para suporte a múltiplos filtros** e **refatoração estrutural** para viabilizar
essa adaptação. Nenhuma fórmula de cálculo, critério de classificação ou regra
de negócio foi alterada.

---

## 1. Correção: KeyError em cursos sem concluintes

**Funções afetadas:** `gera_eficiencia_ciclo` e `gera_eficiencia_ciclo_estratificado`
**Arquivo:** `processor.py`

A fórmula do IEA referencia diretamente as colunas `Conclusão`, `Em Curso` e `Evasão`
no DataFrame resultante do `groupby(['Situação Ciclo'])`. No notebook, isso funciona
porque o curso analisado sempre possui ao menos um aluno em cada situação no período.
Na aplicação web, ao consultar qualquer um dos 1.062 cursos da base, aproximadamente
60% deles não possuem nenhum concluinte entre 2019 e 2024 — fazendo com que a coluna
`Conclusão` não seja criada e a fórmula do IEA lance `KeyError: 'Conclusão'`.

**O que foi adicionado** logo antes do cálculo de `Total` e `IEA` em ambas as funções:

```python
for col in ['Conclusão', 'Em Curso', 'Evasão']:
    if col not in df_indicadores.columns:
        df_indicadores[col] = 0
```

Este bloco garante que as três colunas esperadas existam com valor zero quando
nenhum aluno do grupo possuir aquela situação — comportamento coerente com o
significado dos dados. A fórmula do IEA permanece intacta.

---

## 2. Correção: desalinhamento de linhas na aba Matrícula

**Função afetada:** `_processar_df` (seção Matrícula, variável `tabela1`)
**Arquivo:** `processor.py`

No notebook, o curso analisado sempre possui dados em todos os anos do intervalo
2019–2024. Na aplicação, ao consultar cursos com histórico parcial (por exemplo,
um curso criado em 2023), `tabela1` — a contagem total de matrículas por ano —
retornava apenas as linhas com dados reais, enquanto as tabelas estratificadas
(`tabela2` a `tabela5`) sempre retornavam 6 linhas via `reindex`. O `concat`
horizontal desalinhava os dados: o ano 2023 ficava na mesma linha que 2019.

**O que foi alterado:** aplicado `reindex(index_row).fillna(0).astype(int)` em
`tabela1`, alinhando-a ao intervalo completo 2019–2024 — o mesmo padrão já
utilizado nas tabelas equivalentes das seções Conclusão, Evasão e Retenção.

**Importante:** a variável `df_totais` (usada como divisor nos cálculos de
percentual das demais seções) **não** foi reindexada, pois isso causaria divisão
por zero nos anos sem dados. Apenas `tabela1`, destinada à visualização e
exportação, recebeu a correção.

---

## 3. Adaptação para múltiplos filtros

Esta é a principal mudança em relação ao notebook original, que sempre processava
exatamente um curso de uma unidade específica.

### 3.1 Refatoração da função `processar` em `processor.py`

No notebook, existe uma única função que carrega o parquet, filtra por unidade e
curso, e executa o pipeline de geração de tabelas. Para suportar combinações
arbitrárias de filtros, essa função foi dividida em três:

- **`processar(unidade, curso)`** — mantida para compatibilidade, agora apenas
  carrega o parquet, filtra pelos dois campos e chama `_processar_df`.

- **`_processar_df(df_curso, rotulo)`** — contém o corpo original do pipeline
  (derivação de colunas, geração das 25 tabelas). Recebe um DataFrame já filtrado
  e um rótulo descritivo. Nenhuma linha de lógica foi alterada aqui.

- **`processar_multi(df_filtrado, rotulo)`** — novo ponto de entrada público.
  Recebe um DataFrame já filtrado externamente (por `routes.py`) e delega
  para `_processar_df`. É essa função que a aplicação web chama ao processar
  qualquer combinação de filtros.

O rótulo descritivo (exibido na aba Acesso e no Excel) é construído em
`routes.py` pela função `_build_rotulo(filtros)`, que gera textos como
`"3 unidades - Técnico em Informática - Integrado"` dependendo do que foi
selecionado.

### 3.2 Filtragem multi-select em `routes.py`

A lógica de filtragem do DataFrame principal foi centralizada na função
`_aplicar_filtros(df, filtros)` em `routes.py`. Ela recebe o DataFrame completo
e um dicionário com as seleções do usuário para cada uma das cinco dimensões:

- **Unidade de Ensino**
- **Nome de Curso**
- **Tipo de Curso** *(novo)*
- **Tipo de Oferta** *(novo)*
- **Turno** *(novo)*

Para cada dimensão, se o usuário selecionou valores, um filtro `isin()` é
aplicado. Os filtros são cumulativos (AND lógico). Se nenhum valor foi
selecionado para uma dimensão, ela não é filtrada — equivalente a "todos".

Isso permite, por exemplo, gerar tabelas agregadas para todos os cursos
"Técnico em Automação" do IFSP, independente de unidade, turno ou tipo de
oferta — algo não previsto no notebook original.

### 3.3 Tratamento especial para a coluna Turno

Aproximadamente 3% dos registros (~13.000 matrículas) possuem valor nulo
(`NaN`) na coluna `Turno`. Para que esses registros apareçam na interface
e possam ser incluídos ou excluídos pelo usuário, foi adotado um padrão
de *sentinel*:

- No cache de combinações e na interface, os nulos são exibidos como
  `"Não informado"`.
- Quando o usuário seleciona `"Não informado"`, a função `_aplicar_filtros`
  converte essa seleção de volta para um filtro `df['Turno'].isna()`.
- O sentinel **nunca chega ao `processor.py`** — o DataFrame entregue a
  `processar_multi` já contém os nulos originais.

### 3.4 Cache de combinações para resposta rápida dos filtros em cascata

Para que a atualização dos filtros em cascata seja instantânea (sem recarregar
o parquet a cada interação), `routes.py` mantém em memória um cache de
combinações únicas das cinco dimensões — aproximadamente 1.900 linhas e 40 KB.
O endpoint `POST /opcoes` consulta esse cache para retornar as opções válidas
dado o estado atual dos filtros. O cache é invalidado automaticamente se o
arquivo parquet for substituído (verificação via `os.path.getmtime`).

---

## Resumo das funções alteradas ou criadas

| Função | Arquivo | Tipo de alteração |
|---|---|---|
| `gera_eficiencia_ciclo` | `processor.py` | Correção de bug (guard block) |
| `gera_eficiencia_ciclo_estratificado` | `processor.py` | Correção de bug (guard block) |
| `_processar_df` | `processor.py` | Correção de bug (reindex tabela1) + criada por refatoração |
| `processar` | `processor.py` | Refatorada (agora chama `_processar_df`) |
| `processar_multi` | `processor.py` | Criada (entrada para filtros multi-select) |
| `_aplicar_filtros` | `routes.py` | Criada (filtragem multi-select com suporte a NaN) |
| `_build_rotulo` | `routes.py` | Criada (rótulo descritivo a partir dos filtros) |
| `_get_combos` | `routes.py` | Criada (cache de combinações para cascata) |
