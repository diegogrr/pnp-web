import pandas as pd
from flask import Blueprint, jsonify, request, render_template, send_file
import io

import config
from .processor import processar, exportar_xlsx

bp = Blueprint('main', __name__)


def _carregar_df():
    return pd.read_parquet(config.PARQUET_PATH)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/unidades')
def unidades():
    try:
        df = _carregar_df()
        lista = sorted(df['Unidade de Ensino'].dropna().unique().tolist())
        return jsonify(lista)
    except FileNotFoundError:
        return jsonify({'erro': 'Arquivo de dados não encontrado. Contate o administrador.'}), 500
    except Exception as e:
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
    except Exception as e:
        return jsonify({'erro': 'Erro ao carregar cursos.'}), 500


@bp.route('/processar', methods=['POST'])
def processar_dados():
    body = request.get_json(force=True)
    unidade = body.get('unidade', '')
    curso   = body.get('curso', '')
    if not unidade or not curso:
        return jsonify({'erro': 'Campos unidade e curso são obrigatórios.'}), 400
    try:
        dados = processar(unidade, curso)
        resultado = {}
        for aba, val in dados.items():
            df = val['df']
            # Converte MultiIndex de colunas para string para serialização JSON
            df.columns = [
                ' | '.join(str(c) for c in col) if isinstance(col, tuple) else str(col)
                for col in df.columns
            ]
            resultado[aba] = {
                'colunas': df.columns.tolist(),
                'linhas': df.fillna('').values.tolist(),
            }
        return jsonify(resultado)
    except FileNotFoundError:
        return jsonify({'erro': 'Arquivo de dados não encontrado. Contate o administrador.'}), 500
    except Exception as e:
        return jsonify({'erro': f'Erro no processamento: {str(e)}'}), 500


@bp.route('/exportar', methods=['POST'])
def exportar():
    body = request.get_json(force=True)
    unidade      = body.get('unidade', '')
    curso        = body.get('curso', '')
    nome_arquivo = body.get('nome_arquivo', 'saida').strip()
    if not unidade or not curso:
        return jsonify({'erro': 'Campos unidade e curso são obrigatórios.'}), 400
    if not nome_arquivo.endswith('.xlsx'):
        nome_arquivo += '.xlsx'
    try:
        dados  = processar(unidade, curso)
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
