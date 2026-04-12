import os
import io
import threading
import uuid
import time

import pandas as pd
from flask import Blueprint, jsonify, request, render_template, send_file

import config
from .processor import processar, processar_multi, exportar_xlsx

bp = Blueprint('main', __name__)

# ---------------------------------------------------------------------------
# Constantes e cache
# ---------------------------------------------------------------------------

FILTER_COLS = [
    'Unidade de Ensino',
    'Nome de Curso',
    'Tipo de Curso',
    'Tipo de Oferta',
    'Turno',
]
NAN_SENTINEL = 'Não informado'

_cache = {'combos': None, 'mtime': None}

# ---------------------------------------------------------------------------
# Job store para processamento assíncrono
# ---------------------------------------------------------------------------
_jobs = {}  # {job_id: {status, result, error, started_at}}


def _cleanup_old_jobs():
    """Remove jobs com mais de 1 hora."""
    cutoff = time.time() - 3600
    for jid in list(_jobs.keys()):
        if _jobs[jid].get('started_at', 0) < cutoff:
            del _jobs[jid]


def _get_combos():
    """Retorna DataFrame com combinações únicas das 5 colunas-filtro (cacheado)."""
    mtime = os.path.getmtime(config.PARQUET_PATH)
    if _cache['combos'] is None or _cache['mtime'] != mtime:
        df = pd.read_parquet(config.PARQUET_PATH, columns=FILTER_COLS)
        df['Turno'] = df['Turno'].fillna(NAN_SENTINEL)
        _cache['combos'] = df.drop_duplicates().reset_index(drop=True)
        _cache['mtime'] = mtime
    return _cache['combos']


def _carregar_df():
    return pd.read_parquet(config.PARQUET_PATH)


def _carregar_df_ef():
    return pd.read_parquet(config.PARQUET_EF_PATH)


def _aplicar_filtros(df, filtros):
    """Aplica filtros multi-select ao DataFrame. Trata NaN do Turno."""
    mask = pd.Series(True, index=df.index)
    for col in FILTER_COLS:
        vals = filtros.get(col, [])
        if not vals:
            continue
        if col == 'Turno' and NAN_SENTINEL in vals:
            vals_sem_sentinel = [v for v in vals if v != NAN_SENTINEL]
            if vals_sem_sentinel:
                mask &= df['Turno'].isin(vals_sem_sentinel) | df['Turno'].isna()
            else:
                mask &= df['Turno'].isna()
        else:
            mask &= df[col].isin(vals)
    return df[mask]


def _build_rotulo(filtros):
    """Gera rótulo descritivo para Acesso/Excel a partir dos filtros."""
    unidades = filtros.get('Unidade de Ensino', [])
    cursos = filtros.get('Nome de Curso', [])
    tipos_curso = filtros.get('Tipo de Curso', [])
    tipos_oferta = filtros.get('Tipo de Oferta', [])
    turnos = filtros.get('Turno', [])

    partes = []

    if len(unidades) == 1:
        partes.append(unidades[0])
    elif len(unidades) > 1:
        partes.append(f'{len(unidades)} unidades')

    if len(cursos) == 1:
        partes.append(cursos[0])
    elif len(cursos) > 1:
        partes.append(f'{len(cursos)} cursos')

    if len(tipos_curso) == 1:
        partes.append(tipos_curso[0])

    if len(tipos_oferta) == 1:
        partes.append(tipos_oferta[0])
    elif len(tipos_oferta) > 1:
        partes.append(f'{len(tipos_oferta)} ofertas')

    if len(turnos) == 1:
        partes.append(turnos[0])

    return ' - '.join(partes) if partes else 'Todos os dados'


def _extrair_filtros(body):
    """Extrai e valida dict de filtros do corpo da requisição."""
    filtros = body.get('filtros', {})
    tem_selecao = any(filtros.get(col) for col in FILTER_COLS)
    return filtros, tem_selecao


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/opcoes', methods=['POST'])
def opcoes():
    """Retorna opções válidas para cada dimensão dada a seleção atual."""
    try:
        body = request.get_json(force=True) or {}
        combos = _get_combos()

        filtros = {}
        for col in FILTER_COLS:
            vals = body.get(col, [])
            if vals:
                filtros[col] = vals

        resultado = {}
        for dim in FILTER_COLS:
            mask = pd.Series(True, index=combos.index)
            for other_dim in FILTER_COLS:
                if other_dim == dim:
                    continue
                if other_dim in filtros:
                    if other_dim == 'Turno' and NAN_SENTINEL in filtros[other_dim]:
                        vals_sem = [v for v in filtros[other_dim] if v != NAN_SENTINEL]
                        if vals_sem:
                            mask &= combos[other_dim].isin(vals_sem) | (combos[other_dim] == NAN_SENTINEL)
                        else:
                            mask &= combos[other_dim] == NAN_SENTINEL
                    else:
                        mask &= combos[other_dim].isin(filtros[other_dim])
            resultado[dim] = sorted(combos[mask][dim].unique().tolist())

        mask_all = pd.Series(True, index=combos.index)
        for dim in FILTER_COLS:
            if dim in filtros:
                mask_all &= combos[dim].isin(filtros[dim])
        resultado['_count'] = int(mask_all.sum())

        return jsonify(resultado)
    except FileNotFoundError:
        return jsonify({'erro': 'Arquivo de dados não encontrado. Contate o administrador.'}), 500
    except Exception:
        return jsonify({'erro': 'Erro ao carregar opções de filtro.'}), 500


@bp.route('/unidades')
def unidades():
    try:
        df = _carregar_df()
        lista = sorted(df['Unidade de Ensino'].dropna().unique().tolist())
        return jsonify(lista)
    except FileNotFoundError:
        return jsonify({'erro': 'Arquivo de dados não encontrado. Contate o administrador.'}), 500
    except Exception:
        return jsonify({'erro': 'Erro ao carregar unidades.'}), 500


@bp.route('/cursos')
def cursos():
    unidade = request.args.get('unidade', '')
    if not unidade:
        return jsonify({'erro': 'Parâmetro unidade é obrigatório.'}), 400
    try:
        df = _carregar_df()
        df_unidade = df[df['Unidade de Ensino'] == unidade]
        lista = sorted(df_unidade['Nome de Curso'].dropna().unique().tolist())
        return jsonify(lista)
    except FileNotFoundError:
        return jsonify({'erro': 'Arquivo de dados não encontrado. Contate o administrador.'}), 500
    except Exception:
        return jsonify({'erro': 'Erro ao carregar cursos.'}), 500


def _serializar_dados(dados):
    """Serializa o dict de DataFrames para JSON (lógica comum a /processar)."""
    resultado = {}
    for aba, val in dados.items():
        df = val['df']
        df.columns = [
            ' | '.join(str(c) for c in col) if isinstance(col, tuple) else str(col)
            for col in df.columns
        ]
        resultado[aba] = {
            'colunas': df.columns.tolist(),
            'linhas': df.fillna('').values.tolist(),
        }
    return resultado


@bp.route('/processar/iniciar', methods=['POST'])
def processar_iniciar():
    """Inicia o processamento em background e retorna job_id imediatamente."""
    body = request.get_json(force=True)
    filtros, tem_selecao = _extrair_filtros(body)

    if not tem_selecao:
        return jsonify({'erro': 'Selecione ao menos um filtro.'}), 400

    _cleanup_old_jobs()
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        'status': 'pending',
        'result': None,
        'error': None,
        'started_at': time.time(),
    }

    def _run():
        try:
            df       = _carregar_df()
            df_ef    = _carregar_df_ef()
            df_filtrado    = _aplicar_filtros(df, filtros)
            df_ef_filtrado = _aplicar_filtros(df_ef, filtros)
            if df_filtrado.empty:
                _jobs[job_id]['error'] = 'Nenhum dado encontrado para os filtros selecionados.'
                _jobs[job_id]['status'] = 'error'
                return
            rotulo    = _build_rotulo(filtros)
            turno_str = '/'.join(filtros.get('Turno', []))
            dados = processar_multi(df_filtrado, df_ef_filtrado, rotulo, turno_str)
            _jobs[job_id]['result'] = _serializar_dados(dados)
            _jobs[job_id]['dados_raw'] = dados
            _jobs[job_id]['status'] = 'done'
        except Exception as e:
            _jobs[job_id]['error'] = f'Erro no processamento: {str(e)}'
            _jobs[job_id]['status'] = 'error'

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'job_id': job_id})


@bp.route('/processar/status/<job_id>')
def processar_status(job_id):
    """Retorna o estado de um job de processamento."""
    job = _jobs.get(job_id)
    if not job:
        return jsonify({'erro': 'Job não encontrado ou expirado.'}), 404
    if job['status'] == 'pending':
        elapsed = int(time.time() - job['started_at'])
        return jsonify({'status': 'pending', 'elapsed': elapsed})
    if job['status'] == 'error':
        return jsonify({'status': 'error', 'erro': job['error']})
    # done: retorna resultado (mantém job para exportação via cache)
    result = job['result']
    job['result'] = None  # libera JSON serializado da memória
    return jsonify({'status': 'done', 'dados': result, 'job_id': job_id})


@bp.route('/processar', methods=['POST'])
def processar_dados():
    body = request.get_json(force=True)

    filtros, tem_selecao = _extrair_filtros(body)

    if not tem_selecao:
        return jsonify({'erro': 'Selecione ao menos um filtro.'}), 400

    try:
        df       = _carregar_df()
        df_ef    = _carregar_df_ef()
        df_filtrado    = _aplicar_filtros(df, filtros)
        df_ef_filtrado = _aplicar_filtros(df_ef, filtros)

        if df_filtrado.empty:
            return jsonify({'erro': 'Nenhum dado encontrado para os filtros selecionados.'}), 400

        rotulo    = _build_rotulo(filtros)
        turno_str = '/'.join(filtros.get('Turno', []))
        dados = processar_multi(df_filtrado, df_ef_filtrado, rotulo, turno_str)
        return jsonify(_serializar_dados(dados))
    except FileNotFoundError:
        return jsonify({'erro': 'Arquivo de dados não encontrado. Contate o administrador.'}), 500
    except Exception as e:
        return jsonify({'erro': f'Erro no processamento: {str(e)}'}), 500


@bp.route('/exportar', methods=['POST'])
def exportar():
    body = request.get_json(force=True)

    filtros, tem_selecao = _extrair_filtros(body)
    nome_arquivo = body.get('nome_arquivo', 'saida').strip()
    job_id = body.get('job_id')

    if not tem_selecao:
        return jsonify({'erro': 'Selecione ao menos um filtro.'}), 400
    if not nome_arquivo.endswith('.xlsx'):
        nome_arquivo += '.xlsx'

    try:
        # Tentar usar cache do processamento anterior
        dados = None
        if job_id and job_id in _jobs:
            dados = _jobs[job_id].get('dados_raw')

        if not dados:
            # Fallback: reprocessar (cache expirado ou ausente)
            df       = _carregar_df()
            df_ef    = _carregar_df_ef()
            df_filtrado    = _aplicar_filtros(df, filtros)
            df_ef_filtrado = _aplicar_filtros(df_ef, filtros)

            if df_filtrado.empty:
                return jsonify({'erro': 'Nenhum dado encontrado para os filtros selecionados.'}), 400

            rotulo    = _build_rotulo(filtros)
            turno_str = '/'.join(filtros.get('Turno', []))
            dados = processar_multi(df_filtrado, df_ef_filtrado, rotulo, turno_str)

        conteudo = exportar_xlsx(dados, nome_arquivo)
        return send_file(
            io.BytesIO(conteudo),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=nome_arquivo,
        )
    except FileNotFoundError:
        return jsonify({'erro': 'Arquivo de dados não encontrado. Contate o administrador.'}), 500
    except Exception as e:
        return jsonify({'erro': f'Erro na exportação: {str(e)}'}), 500
