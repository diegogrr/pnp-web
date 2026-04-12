# Alterações em relação ao notebook original

Este documento descreve as mudanças realizadas nos arquivos `app/processor.py` e
`app/routes.py` em relação à lógica original do notebook `GeraTabelasPNP.ipynb`
e, posteriormente, em relação ao notebook `GeraTabelasPNP_v2.ipynb`.

As alterações são de quatro naturezas distintas: **correções de bugs**,
**adaptação para suporte a múltiplos filtros**, **refatoração estrutural** para
viabilizar essa adaptação, e **migração para a base de microdados de eficiência**
introduzida na versão 2 do notebook. Nenhuma fórmula de cálculo, critério de
classificação ou regra de negócio foi alterada sem justificativa documentada.

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
significado dos dados. A fórmula do IEA permanece sem alteração.

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

---

## 4. Migração para a base de microdados de eficiência (notebook v2)

Esta seção documenta as mudanças realizadas em **2026-04-12** para incorporar
a lógica do notebook `GeraTabelasPNP_v2.ipynb`, que substitui o cálculo manual
de conclusão, evasão, retenção e IEA por dados pré-calculados provenientes da
Plataforma Nilo Peçanha.

### 4.1 Contexto e motivação

O professor Nilson identificou erros sistemáticos nos cálculos das abas
**Conclusão**, **Evasão**, **Retenção** e **Eficiência**. A raiz do problema
estava na metodologia de classificação do notebook v1: as funções `define_evadido`,
`define_retido` e `define_concluinte` inferiam a situação de cada aluno com base
em campos de data e categoria presentes no parquet de matrículas, mas essa
inferência não correspondia aos critérios utilizados oficialmente pela plataforma
Nilo Peçanha para calcular ciclos de eficiência.

A solução adotada pelo professor foi utilizar diretamente a base de **dados
de eficiência** (`pnp_eficiencia_ifsp_20192024.parquet`), base gerada a partir dos microdados disponibilizada pela
própria plataforma, que já contém a situação de ciclo de cada matrícula
previamente calculada. Isso elimina completamente a necessidade de derivar
essas classificações na aplicação.

### 4.2 Dois parquets independentes

O projeto passou a utilizar dois arquivos parquet com papéis distintos:

| Arquivo | Papel | Tabelas geradas |
|---|---|---|
| `pnp_ifsp_20192024.parquet` | Matrículas totais | tabela1–5 (aba Matrícula) |
| `pnp_eficiencia_ifsp_20192024.parquet` | Microdados de eficiência (ciclo) | tabela6–25 (Conclusão, Evasão, Retenção, Eficiência) |

Os dois arquivos **nunca são mesclados ou cruzados entre si**. Ambos são
filtrados de forma independente com os mesmos critérios de seleção antes de
serem passados ao pipeline de processamento.

### 4.3 O que foi removido de `processor.py`

As seguintes funções de classificação linha a linha, presentes no notebook v1,
foram removidas integralmente por não serem mais necessárias:

- `define_ingressante` — identificava se o aluno era ingressante naquele ano
- `define_evadido` — detectava evasão pela categoria da situação
- `define_retido` — detectava retenção por comparação entre ano corrente e ano de conclusão previsto
- `define_concluinte` — detectava conclusão pela categoria da situação
- `define_situacao` — mapeava a situação para os rótulos `'Conclusão'`, `'Evasão'` ou `'Em Curso'`
- `define_situacao_ciclo` — ajustava a situação para o contexto de ciclo (usado no cálculo do IEA v1)

Também foram removidas as funções `gera_eficiencia_ciclo` e
`gera_eficiencia_ciclo_estratificado` da versão 1, que operavam com um loop
ano a ano, filtrando matrículas por data de conclusão prevista e deduplicando
por `Código da Matricula`.

### 4.4 O que foi adicionado e alterado

**`DIC_SITUACAO` (nova constante):**
Dicionário que mapeia os valores de `Categoria da Situação` presentes no parquet
de eficiência para os rótulos padronizados usados internamente:

```python
DIC_SITUACAO = {
    'Concluintes': 'Conclusão',
    'Concluídos':  'Conclusão',
    'Evadidos':    'Evasão',
    'Em Curso':    'Retenção',
    'Em curso':    'Retenção',
}
```

O mapeamento trata variações de capitalização (`'Em Curso'` e `'Em curso'`) e
de terminologia (`'Concluintes'` vs `'Concluídos'`) presentes nos dados. O
rótulo `'Retenção'` substitui `'Em Curso'` da versão anterior — semanticamente
equivalente, mas alinhado ao vocabulário do notebook v2.

**`gera_eficiencia_ciclo(df_ef)` (reescrita):**
Substituiu o loop ano a ano por um simples `groupby(['Ano', 'Situação'])` sobre
o DataFrame de eficiência já mapeado. Sem deduplicação, sem filtro de data.
Aplicado sobre `df_ef_curso` (parquet de eficiência filtrado), não sobre
`df_curso` (parquet de matrículas). As guardas defensivas para colunas ausentes
foram mantidas, adaptando o nome `'Em Curso'` para `'Retenção'`.

**`gera_eficiencia_ciclo_estratificado(df_ef, prop)` (reescrita):**
Mesma simplificação da função anterior, agora estratificada por uma propriedade
demográfica (`prop`). O groupby inclui o nível da propriedade e o IEA é
calculado antes do unstack.

**`_processar_df` (assinatura alterada):**
Passou a receber dois DataFrames: `_processar_df(df_curso, df_ef_curso, rotulo, turno_str='')`.
O mapeamento de `Situação` é realizado na entrada da função. O denominador dos
percentuais nas seções Conclusão, Evasão e Retenção (tabela6, tabela11, tabela16)
passou a ser `df_totais_ef` — o total de registros do parquet de eficiência por
ano — em vez de `df_totais` (total de matrículas). Isso é semanticamente correto:
a taxa de conclusão deve ser calculada sobre a base de eficiência, não sobre
todos os registros de matrícula.

**`processar_multi` e `processar` (assinaturas atualizadas):**
Ambas passaram a aceitar e repassar os dois DataFrames.

**`exportar_xlsx` (comportamento ampliado):**
Passou a escrever o turno selecionado na coluna B (células B7:B12) de todas as
abas do arquivo Excel, conforme o layout da nova `Planilha_Modelo.xlsx`.

**`routes.py` (carregamento dual):**
Adicionada a função `_carregar_df_ef()`. Os três pontos que chamam
`processar_multi` (endpoint síncrono, thread assíncrona e fallback do exportar)
agora carregam e filtram ambos os parquets antes de invocar o processador.
O cache de combinações (`_get_combos`) continua usando apenas o parquet
principal — as opções de filtro são derivadas da base de matrículas, que é o
superset de combinações disponíveis.

---

## 5. Correção do denominador nas tabelas estratificadas de Conclusão, Evasão e Retenção

**Função afetada:** `gera_tabela_estratificada`
**Arquivo:** `processor.py`
**Data:** 2026-04-12

### 5.1 O problema

As tabelas estratificadas por subcategoria demográfica (Cor/Raça, Renda Familiar,
Sexo e Faixa Etária) presentes nas abas **Conclusão**, **Evasão** e **Retenção**
apresentavam um erro de interpretação no cálculo da taxa percentual.

A função `gera_tabela_estratificada`, conforme extraída do notebook, calcula
internamente o denominador como o **total de registros do próprio DataFrame
passado por ano**. Para a aba Matrícula isso é correto: o percentual de alunos
brancos é calculado sobre o total de matrículas daquele ano. Porém, quando a
mesma função era chamada com o subset de concluintes (`df_concluintes`), o
denominador se tornava o **total de concluintes do ano** — o que responde a
uma pergunta diferente da pretendida.

**Exemplo concreto** — curso Letras - Língua Portuguesa, Campus Salto, ano 2023:

| | Valor | Cálculo |
|---|---|---|
| Brancos concluintes | 15 | — |
| Total concluintes (todos) | 22 | — |
| Total brancos (todas as situações) | 21 | — |
| **% calculada (errado)** | **68,18%** | 15 / 22 × 100 |
| **% correta** | **71,43%** | 15 / 21 × 100 |

A taxa errada responde: *"dos concluintes, quantos são brancos?"*  
A taxa correta responde: *"dos alunos brancos, quantos concluíram?"*

Essa segunda interpretação é a pretendida pelo professor Nilson: a
estratificação deve mostrar a taxa de conclusão (evasão, retenção) **dentro de
cada grupo demográfico**, e não a composição demográfica de cada situação.

### 5.2 A solução

A função `gera_tabela_estratificada` recebeu um parâmetro opcional `df_denominador`:

```python
def gera_tabela_estratificada(df, prop, df_denominador=None):
    df_estrat = df.groupby(['Ano', prop])['Código da Matricula'].count().to_frame(name='Quant.')

    if df_denominador is None:
        # Matrícula: denominador = total do ano no próprio subset
        total_ano = df_estrat.groupby(level=0).transform('sum')
    else:
        # Conclusão / Evasão / Retenção: denominador = total por (Ano, subcategoria)
        # no DataFrame de eficiência completo (todas as situações)
        total_ano = df_denominador.groupby(['Ano', prop])['Código da Matricula'].count().to_frame(name='Quant.')

    df_estrat['%'] = (df_estrat['Quant.'] / total_ano['Quant.'] * 100).round(2)
    ...
```

Quando `df_denominador=None` (chamadas da aba Matrícula), o comportamento é
exatamente o mesmo de antes: o percentual de cada subcategoria é calculado sobre
o total de matrículas do ano. Isso garante que os valores já validados da aba
Matrícula permaneçam inalterados e que a soma dos percentuais continue sendo
100% por linha de ano.

Quando `df_denominador=df_ef_curso` (chamadas das abas Conclusão, Evasão e
Retenção), o denominador para cada célula `(Ano, subcategoria)` é o total de
alunos daquela subcategoria no parquet de eficiência — independente de sua
situação. Isso permite responder corretamente: *"dos 21 alunos brancos em 2023,
15 concluíram (71,43%), 3 evadiram e 1 foi retido."*

### 5.3 O que foi e o que não foi alterado

**Alterado:**
- Assinatura de `gera_tabela_estratificada`: adicionado `df_denominador=None`
- 12 chamadas em `_processar_df`: tabela7–10 (Conclusão), tabela12–15 (Evasão)
  e tabela17–20 (Retenção) agora passam `df_ef_curso` como denominador
- Os valores de `%` nessas 12 tabelas foram corrigidos

**Não alterado:**
- Valores absolutos (`Quant.`) em todas as tabelas — apenas o `%` mudou
- Aba **Matrícula** (tabela2–5): chamadas sem `df_denominador`, comportamento idêntico
- Aba **Eficiência** (tabela22–25): usa `gera_eficiencia_ciclo_estratificado`, função separada, sem impacto
- Totais de linha (tabela6, tabela11, tabela16): calculados diretamente sobre `df_totais_ef`, sem envolver `gera_tabela_estratificada`
- IEA: calculado por `gera_eficiencia_ciclo`, sem envolver `gera_tabela_estratificada`

---

## Resumo das funções alteradas ou criadas

| Função | Arquivo | Tipo de alteração |
|---|---|---|
| `gera_eficiencia_ciclo` | `processor.py` | Correção de bug (guard block) + reescrita v2 (groupby simples) |
| `gera_eficiencia_ciclo_estratificado` | `processor.py` | Correção de bug (guard block) + reescrita v2 (groupby simples) |
| `gera_tabela_estratificada` | `processor.py` | Parâmetro `df_denominador` — corrige % nas abas de ciclo |
| `_processar_df` | `processor.py` | Assinatura ampliada (dois DFs); Correção reindex tabela1; criada por refatoração |
| `processar` | `processor.py` | Atualizada: carrega ambos os parquets |
| `processar_multi` | `processor.py` | Atualizada: aceita `df_ef_filtrado` e `turno_str` |
| `exportar_xlsx` | `processor.py` | Escreve turno na coluna B do Excel |
| `_carregar_df_ef` | `routes.py` | Criada (carrega parquet de eficiência) |
| `_aplicar_filtros` | `routes.py` | Criada (filtragem multi-select com suporte a NaN) |
| `_build_rotulo` | `routes.py` | Criada (rótulo descritivo a partir dos filtros) |
| `_get_combos` | `routes.py` | Criada (cache de combinações para cascata) |
