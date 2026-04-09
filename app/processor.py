import io

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string
from openpyxl.utils.dataframe import dataframe_to_rows

import config

# ---------------------------------------------------------------------------
# Constantes extraídas do notebook (cell [20]) — NÃO ALTERAR
# ---------------------------------------------------------------------------

ano_inicial = 2019
ano_final = 2024

dic_ordem = {
    'Quant.': ['Quant.', '%'],
    'Cor / Raça': ['Amarela', 'Branca', 'Indígena', 'Parda', 'Preta', 'Não declarada'],
    'Renda Familiar': ['0<RFP<=0,5', '0,5<RFP<=1', '1<RFP<=1,5', '1,5<RFP<=2,5', '2,5<RFP<=3,5', 'RFP>3,5', 'Não declarada'],
    'Sexo': ['M', 'F'],
    'Faixa Etária': ['Menor de 14 anos',
          '15 a 19 anos',
          '20 a 24 anos',
          '25 a 29 anos',
          '30 a 34 anos',
          '35 a 39 anos',
          '40 a 44 anos',
          '45 a 49 anos',
          '50 a 54 anos',
          '55 a 59 anos',
          'Maior de 60 anos']
}

# ---------------------------------------------------------------------------
# Funções extraídas do notebook (cell [17]) — NÃO ALTERAR
# ---------------------------------------------------------------------------

def define_ingressante(ent):
    if ent['Ano de Ingresso']==ent['Ano']:
        return 1
    else:
        return 0

def define_evadido(ent):
    if ent['Categoria da Situação']=='Evadidos':
        return 1
    else:
        return 0

def define_retido(ent):
    if ((ent['Situação de Matrícula']=='Em curso')&(ent['Ano']>=ent['Ano de Conclusão'])):
        return 1
    else:
        return 0

def define_concluinte(ent):
    if(ent['Categoria da Situação']=='Concluídos')|(ent['Categoria da Situação']=='Concluintes'):
        return 1
    else:
        return 0

def define_situacao(ent):
    if(ent['Categoria da Situação']=='Concluídos')|(ent['Categoria da Situação']=='Concluintes'):
        return 'Conclusão'
    elif(ent['Categoria da Situação']=='Evadidos'):
        return 'Evasão'
    else:
        return 'Em Curso'

# ---------------------------------------------------------------------------
# Funções extraídas do notebook (cell [21]) — NÃO ALTERAR
# ---------------------------------------------------------------------------

def gera_tabela_estratificada(df, prop):
    df_estrat = df.groupby(['Ano', prop])['Código da Matricula'].count().to_frame(name='Quant.')
    total_ano = df_estrat.groupby(level=0).transform('sum')
    df_estrat['%'] = (df_estrat['Quant.']/total_ano['Quant.']*100).round(2)

    #df_estrat = gera_tabela_estratificada(df,prop)
    df_estrat = df_estrat.unstack().swaplevel(0, 1, axis=1)

    index_row = pd.Index(range(ano_inicial, ano_final+1))
    df_estrat = df_estrat.reindex(index_row)

    index_col = pd.MultiIndex.from_product([dic_ordem[prop], dic_ordem['Quant.']], names=[prop, 'Quantidade'])
    df_estrat = df_estrat.reindex(index_col, axis=1).convert_dtypes().fillna(0)

    return df_estrat

# ---------------------------------------------------------------------------
# Função extraída do notebook (cell [22]) — NÃO ALTERAR
# ---------------------------------------------------------------------------

def escreve_tabela(wb, df, aba, col_inicio, linha_inicio):

    ws = wb[aba]

    if isinstance(col_inicio, str):
        c_idx_start = column_index_from_string(col_inicio)
    else:
        c_idx_start = col_inicio

    # header=False remove os nomes das colunas do Pandas
    rows = dataframe_to_rows(df, index=False, header=False)

    for r_idx, row in enumerate(rows, start=linha_inicio):
        for c_idx, value in enumerate(row, start=c_idx_start):
            ws.cell(row=r_idx, column=c_idx, value=value)

# ---------------------------------------------------------------------------
# Funções extraídas do notebook (cell [68]) — NÃO ALTERAR
# ---------------------------------------------------------------------------

def define_situacao_ciclo(ent):
    if ent['Ano']!=ent['Ano de Conclusão']+1:
        return 'Evasão'
    else:
        return ent['Situação']

def gera_eficiencia_ciclo(df):
    list_indicadores = []
    for ano in range(ano_inicial, ano_final+1):
        df_ciclo = df[(df['Ano']<=ano)&(df['Ano de Conclusão']==ano-1)].drop_duplicates(subset='Código da Matricula', keep='last')

        df_ciclo['Situação Ciclo'] = df.apply(define_situacao_ciclo, axis=1)
        list_indicadores.append(df_ciclo.groupby(['Situação Ciclo'])['Código da Matricula'].count().to_frame(name=ano).T)
    df_indicadores = pd.concat(list_indicadores)

    df_indicadores['Total'] = df_indicadores.sum(axis=1)
    df_indicadores['IEA'] = ((df_indicadores['Conclusão']+df_indicadores['Conclusão']*df_indicadores['Em Curso']/(df_indicadores['Conclusão']+df_indicadores['Evasão']))/df_indicadores['Total']*100).round(2)
    return df_indicadores

# ---------------------------------------------------------------------------
# Função extraída do notebook (cell [69]) — NÃO ALTERAR
# ---------------------------------------------------------------------------

def gera_eficiencia_ciclo_estratificado(df, prop):
    list_indicadores = []
    for ano in range(ano_inicial, ano_final+1):
        df_ciclo = df[(df['Ano']<=ano)&(df['Ano de Conclusão']==ano-1)].drop_duplicates(subset='Código da Matricula', keep='last')

        df_ciclo['Situação Ciclo'] = df.apply(define_situacao_ciclo, axis=1)
        list_indicadores.append(df_ciclo.groupby(['Situação Ciclo', prop])['Código da Matricula'].count().to_frame(name=ano).unstack().T)
    df_indicadores = pd.concat(list_indicadores)

    df_indicadores['Total'] = df_indicadores.sum(axis=1)
    df_indicadores = df_indicadores.fillna(0)
    df_indicadores['IEA'] = ((df_indicadores['Conclusão']+df_indicadores['Conclusão']*df_indicadores['Em Curso']/(df_indicadores['Conclusão']+df_indicadores['Evasão']))/df_indicadores['Total']*100).round(2)

    df_indicadores = df_indicadores[['IEA']].unstack()
    df_indicadores.columns = df_indicadores.columns.droplevel(0)

    index_row = pd.Index(range(ano_inicial, ano_final+1))
    df_indicadores = df_indicadores.reindex(index_row)
    index_col = pd.Index(dic_ordem[prop])
    df_indicadores = df_indicadores.reindex(index_col, axis=1).fillna('')

    return df_indicadores

# ---------------------------------------------------------------------------
# Orquestradora: processar
# ---------------------------------------------------------------------------

def processar(unidade, curso):
    """Executa o pipeline completo e retorna dict[nome_aba -> DataFrame]."""
    df1 = pd.read_parquet(config.PARQUET_PATH)

    df_unidade = df1[df1['Unidade de Ensino'] == unidade]
    df_curso = df_unidade[df_unidade['Nome de Curso'] == curso].copy()

    # Derivações de colunas (cells [16] e [18])
    df_curso['Ano de Ingresso'] = df_curso['Data de Inicio do Ciclo'].apply(lambda s: int(s.split('/')[2]))
    df_curso['Ano de Conclusão'] = df_curso['Data de Fim Previsto do Ciclo'].apply(lambda s: int(s.split('/')[2]))

    df_curso['Ingressante'] = df_curso.apply(define_ingressante, axis=1)
    df_curso['Evadido']     = df_curso.apply(define_evadido, axis=1)
    df_curso['Retido']      = df_curso.apply(define_retido, axis=1)
    df_curso['Concluinte']  = df_curso.apply(define_concluinte, axis=1)
    df_curso['Situação']    = df_curso.apply(define_situacao, axis=1)

    # --- Matrícula ---
    df_totais = df_curso.groupby(['Ano'])['Código da Matricula'].count().to_frame(name='Quant.')
    tabela1 = df_totais
    tabela2 = gera_tabela_estratificada(df_curso, 'Cor / Raça')
    tabela3 = gera_tabela_estratificada(df_curso, 'Renda Familiar')
    tabela4 = gera_tabela_estratificada(df_curso, 'Sexo')
    tabela5 = gera_tabela_estratificada(df_curso, 'Faixa Etária')

    # --- Conclusão ---
    df_concluintes = df_curso[df_curso['Concluinte'] == 1]
    df_totais_concl = df_concluintes.groupby(['Ano'])['Código da Matricula'].count().to_frame(name='Quant.')
    df_totais_concl['%'] = (df_totais_concl['Quant.']/df_totais['Quant.']*100).round(2)
    index_row = pd.Index(range(ano_inicial, ano_final+1))
    tabela6  = df_totais_concl.reindex(index_row).convert_dtypes().fillna(0)
    tabela7  = gera_tabela_estratificada(df_concluintes, 'Cor / Raça')
    tabela8  = gera_tabela_estratificada(df_concluintes, 'Renda Familiar')
    tabela9  = gera_tabela_estratificada(df_concluintes, 'Sexo')
    tabela10 = gera_tabela_estratificada(df_concluintes, 'Faixa Etária')

    # --- Evasão ---
    df_evadidos = df_curso[df_curso['Evadido'] == 1]
    df_totais_evad = df_evadidos.groupby(['Ano'])['Código da Matricula'].count().to_frame(name='Quant.')
    df_totais_evad['%'] = (df_totais_evad['Quant.']/df_totais['Quant.']*100).round(2)
    tabela11 = df_totais_evad.reindex(index_row).convert_dtypes().fillna(0)
    tabela12 = gera_tabela_estratificada(df_evadidos, 'Cor / Raça')
    tabela13 = gera_tabela_estratificada(df_evadidos, 'Renda Familiar')
    tabela14 = gera_tabela_estratificada(df_evadidos, 'Sexo')
    tabela15 = gera_tabela_estratificada(df_evadidos, 'Faixa Etária')

    # --- Retenção ---
    df_retidos = df_curso[df_curso['Retido'] == 1]
    df_totais_ret = df_retidos.groupby(['Ano'])['Código da Matricula'].count().to_frame(name='Quant.')
    df_totais_ret['%'] = (df_totais_ret['Quant.']/df_totais['Quant.']*100).round(2)
    tabela16 = df_totais_ret.reindex(index_row).convert_dtypes().fillna(0)
    tabela17 = gera_tabela_estratificada(df_retidos, 'Cor / Raça')
    tabela18 = gera_tabela_estratificada(df_retidos, 'Renda Familiar')
    tabela19 = gera_tabela_estratificada(df_retidos, 'Sexo')
    tabela20 = gera_tabela_estratificada(df_retidos, 'Faixa Etária')

    # --- Eficiência ---
    tabela21 = gera_eficiencia_ciclo(df_curso)[['IEA']].fillna('')
    tabela22 = gera_eficiencia_ciclo_estratificado(df_curso, 'Cor / Raça')
    tabela23 = gera_eficiencia_ciclo_estratificado(df_curso, 'Renda Familiar')
    tabela24 = gera_eficiencia_ciclo_estratificado(df_curso, 'Sexo')
    tabela25 = gera_eficiencia_ciclo_estratificado(df_curso, 'Faixa Etária')

    def _concat(*dfs):
        """Concatena DataFrames horizontalmente para visualização no frontend."""
        return pd.concat([df.reset_index() for df in dfs], axis=1)

    return {
        'Acesso': {
            'tabelas': [],
            'df': pd.DataFrame({'Curso': [curso]}),
        },
        'Matrícula': {
            'tabelas': [
                ('E', 7, tabela1), ('G', 7, tabela2), ('T', 7, tabela3),
                ('AI', 7, tabela4), ('AN', 7, tabela5),
            ],
            'df': _concat(tabela1, tabela2, tabela3, tabela4, tabela5),
        },
        'Conclusão': {
            'tabelas': [
                ('E', 7, tabela6), ('H', 7, tabela7), ('U', 7, tabela8),
                ('AJ', 7, tabela9), ('AO', 7, tabela10),
            ],
            'df': _concat(tabela6, tabela7, tabela8, tabela9, tabela10),
        },
        'Evasão': {
            'tabelas': [
                ('E', 7, tabela11), ('H', 7, tabela12), ('U', 7, tabela13),
                ('AJ', 7, tabela14), ('AO', 7, tabela15),
            ],
            'df': _concat(tabela11, tabela12, tabela13, tabela14, tabela15),
        },
        'Retenção': {
            'tabelas': [
                ('E', 7, tabela16), ('H', 7, tabela17), ('U', 7, tabela18),
                ('AJ', 7, tabela19), ('AO', 7, tabela20),
            ],
            'df': _concat(tabela16, tabela17, tabela18, tabela19, tabela20),
        },
        'Eficiência': {
            'tabelas': [
                ('E', 7, tabela21), ('G', 7, tabela22), ('N', 7, tabela23),
                ('V', 7, tabela24), ('Y', 7, tabela25),
            ],
            'df': _concat(tabela21, tabela22, tabela23, tabela24, tabela25),
        },
        'PAP': {
            'tabelas': [],
            'df': pd.DataFrame(),
        },
    }

# ---------------------------------------------------------------------------
# Orquestradora: exportar_xlsx
# ---------------------------------------------------------------------------

def exportar_xlsx(dados, nome_arquivo):
    """Escreve dados na planilha-modelo e retorna bytes do .xlsx."""
    with open(config.MODELO_PATH, 'rb') as f:
        buf = io.BytesIO(f.read())
    wb = load_workbook(buf)

    curso = dados['Acesso']['df']['Curso'].iloc[0]

    # Escreve nome do curso nas células A7:A12 de todas as abas (cell [14])
    sheets = ['Acesso', 'Matrícula', 'Conclusão', 'Evasão', 'Retenção', 'Eficiência', 'PAP']
    for sheet in sheets:
        for linha in range(7, 13):
            wb[sheet].cell(row=linha, column=1, value=curso)

    # Escreve cada tabela na aba correspondente usando a lista (col, linha, df)
    mapa_abas = {
        'Matrícula': dados['Matrícula']['tabelas'],
        'Conclusão': dados['Conclusão']['tabelas'],
        'Evasão':    dados['Evasão']['tabelas'],
        'Retenção':  dados['Retenção']['tabelas'],
        'Eficiência': dados['Eficiência']['tabelas'],
    }
    for aba, tabelas in mapa_abas.items():
        for col, linha, df in tabelas:
            escreve_tabela(wb, df, aba, col, linha)

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out.read()
