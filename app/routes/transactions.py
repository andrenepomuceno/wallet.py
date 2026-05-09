"""Transaction list views: B3 movimentation/negotiation, Avenue, Generic.

All four views read from the unified `Transaction` table, filtered by
`source` and `record_type`. Manual entries are inserted as `Transaction`
rows by translating the form values through the same per-source
translators used by the importer.
"""
from flask import jsonify, render_template, request

from app import app, db
from app.forms import (
    AvenueExtractAddForm,
    B3MovimentationFilterForm,
    B3NegotiationAddForm,
    GenericExtractAddForm,
)
from app.import_translators import (
    avenue_extract_row,
    b3_negotiation_row,
    generic_extract_row,
)
from app.models import Transaction
from app.models.category_mapping import ALL_CATEGORIES
from app.processing import (
    process_avenue_extract_request,
    process_b3_movimentation_request,
    process_b3_negotiation_request,
    process_generic_extract_request,
    process_all_transactions_request,
)
from app.utils.memocache import invalidate_processing_cache

from ._helpers import handle_manual_transaction, process_manual_transaction


def _is_ajax_request(req):
    return req.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _b3_negotiation_translator(values):
    row = {
        'Data do Negócio': values.get('date'),
        'Tipo de Movimentação': values.get('movimentation'),
        'Mercado': values.get('mercado'),
        'Prazo/Vencimento': values.get('prazo'),
        'Instituição': values.get('instituicao'),
        'Código de Negociação': values.get('codigo'),
        'Quantidade': values.get('quantity') or 0.0,
        'Preço': values.get('price') or 0.0,
        'Valor': values.get('total') or 0.0,
    }
    return b3_negotiation_row(row)


def _avenue_translator(values):
    row = {
        'Data': values.get('data'),
        'Hora': values.get('hora'),
        'Liquidação': values.get('liquidacao'),
        'Descrição': values.get('descricao'),
        'Valor (U$)': values.get('valor') or 0.0,
        'Saldo da conta (U$)': values.get('saldo') or 0.0,
        'Entrada/Saída': values.get('entrada_saida'),
        'Produto': values.get('produto'),
        'Movimentação': values.get('movimentacao'),
        'Quantidade': values.get('quantidade') or 0.0,
        'Preço unitário': values.get('preco_unitario') or 0.0,
    }
    return avenue_extract_row(row)


def _generic_translator(values):
    row = {
        'Date': values.get('date'),
        'Asset': values.get('asset'),
        'Movimentation': values.get('movimentation'),
        'Quantity': values.get('quantity') or 0.0,
        'Price': values.get('price') or 0.0,
        'Total': values.get('total') or 0.0,
    }
    return generic_extract_row(row)


@app.route('/b3_movimentation', methods=['GET', 'POST'])
def view_movimentation():
    filter_form = B3MovimentationFilterForm()

    if request.method == 'POST' and _is_ajax_request(request):
        df = process_b3_movimentation_request(request)
        table_html = render_template('partials/extract_table.html', df=df)
        return jsonify({
            'success': True,
            'messages': [],
            'errors': [],
            'table_html': table_html,
        })

    df = process_b3_movimentation_request(request)
    return render_template('view_movimentation.html', html_title='B3 Movimentation',
                           df=df, filter_form=filter_form)


@app.route('/b3_negotiation', methods=['GET', 'POST'])
def view_negotiation():
    app.logger.info('view_negotiation')

    add_form = B3NegotiationAddForm()
    dedup = ('source', 'record_type', 'date', 'product', 'quantity', 'price')

    if request.method == 'POST' and _is_ajax_request(request):
        result = process_manual_transaction(
            add_form, _b3_negotiation_translator, dedup_keys=dedup,
        )
        df = process_b3_negotiation_request()
        table_html = render_template('partials/extract_table.html', df=df)
        return jsonify({
            'success': bool(result.get('success')),
            'messages': result.get('messages', []),
            'errors': result.get('errors', []),
            'table_html': table_html,
        })

    response = handle_manual_transaction(
        add_form, _b3_negotiation_translator,
        redirect_endpoint='view_negotiation', dedup_keys=dedup,
    )
    if response is not None:
        return response

    df = process_b3_negotiation_request()
    return render_template('view_negotiation.html', html_title='B3 Negotiation',
                           df=df, add_form=add_form)


@app.route('/avenue', methods=['GET', 'POST'])
def view_extract():
    app.logger.info('view_extract')

    add_form = AvenueExtractAddForm()
    dedup = ('source', 'date', 'description', 'total')

    if request.method == 'POST' and _is_ajax_request(request):
        result = process_manual_transaction(
            add_form, _avenue_translator, dedup_keys=dedup,
        )
        df = process_avenue_extract_request()
        table_html = render_template('partials/extract_table.html', df=df)
        return jsonify({
            'success': bool(result.get('success')),
            'messages': result.get('messages', []),
            'errors': result.get('errors', []),
            'table_html': table_html,
        })

    response = handle_manual_transaction(
        add_form, _avenue_translator,
        redirect_endpoint='view_extract', dedup_keys=dedup,
    )
    if response is not None:
        return response

    df = process_avenue_extract_request()
    return render_template('view_extract.html', html_title='Avenue Extract',
                           df=df, add_form=add_form)


@app.route('/generic', methods=['GET', 'POST'])
def view_generic_extract():
    app.logger.info('view_generic_extract')

    add_form = GenericExtractAddForm()
    dedup = ('source', 'date', 'asset', 'quantity', 'price', 'total')

    if request.method == 'POST' and _is_ajax_request(request):
        result = process_manual_transaction(
            add_form, _generic_translator, dedup_keys=dedup,
        )
        df = process_generic_extract_request()
        table_html = render_template('partials/extract_table.html', df=df)
        return jsonify({
            'success': bool(result.get('success')),
            'messages': result.get('messages', []),
            'errors': result.get('errors', []),
            'table_html': table_html,
        })

    response = handle_manual_transaction(
        add_form, _generic_translator,
        redirect_endpoint='view_generic_extract', dedup_keys=dedup,
    )
    if response is not None:
        return response

    df = process_generic_extract_request()
    return render_template('view_generic.html', html_title='Generic Extract',
                           df=df, add_form=add_form)


@app.route('/transactions', methods=['GET', 'POST'])
def view_transactions():
    """Unified view: every row from the `transaction` table."""
    app.logger.info('view_transactions')

    if request.method == 'POST' and _is_ajax_request(request):
        df = process_all_transactions_request(request)
        table_html = render_template('partials/extract_table.html', df=df)
        return jsonify({
            'success': True,
            'messages': [],
            'errors': [],
            'table_html': table_html,
        })

    df = process_all_transactions_request(request)
    return render_template('view_transactions.html',
                           html_title='All Transactions', df=df,
                           all_categories=sorted(ALL_CATEGORIES))


# ---------------------------------------------------------------------------
# Transaction edit API
# ---------------------------------------------------------------------------

_EDITABLE_FIELDS = {
    'date', 'asset', 'product', 'raw_label', 'category',
    'direction', 'quantity', 'price', 'total', 'currency', 'description',
}

_FLOAT_FIELDS = {'quantity', 'price', 'total'}


@app.route('/api/transaction/<int:tx_id>', methods=['GET'])
def api_transaction_get(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    return jsonify({
        'id': tx.id,
        'date': tx.date or '',
        'asset': tx.asset or '',
        'product': tx.product or '',
        'raw_label': tx.raw_label or '',
        'category': tx.category or '',
        'direction': tx.direction or '',
        'quantity': tx.quantity if tx.quantity is not None else 0.0,
        'price': tx.price if tx.price is not None else 0.0,
        'total': tx.total if tx.total is not None else 0.0,
        'currency': tx.currency or 'BRL',
        'description': tx.description or '',
        'source': tx.source,
        'record_type': tx.record_type,
    })


@app.route('/api/transaction/<int:tx_id>', methods=['POST'])
def api_transaction_update(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    data = request.get_json(silent=True) or {}

    errors = []
    for field, value in data.items():
        if field not in _EDITABLE_FIELDS:
            continue
        if field in _FLOAT_FIELDS:
            try:
                value = float(value)
            except (TypeError, ValueError):
                errors.append(f"'{field}' must be a number.")
                continue
        setattr(tx, field, value)

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    try:
        db.session.commit()
        invalidate_processing_cache()
    except Exception as e:
        db.session.rollback()
        app.logger.error('Transaction update failed: %s', e)
        return jsonify({'success': False, 'errors': [str(e)]}), 500

    return jsonify({'success': True})


@app.route('/api/transaction/<int:tx_id>/delete', methods=['POST'])
def api_transaction_delete(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    try:
        db.session.delete(tx)
        db.session.commit()
        invalidate_processing_cache()
    except Exception as e:
        db.session.rollback()
        app.logger.error('Transaction delete failed: %s', e)
        return jsonify({'success': False, 'errors': [str(e)]}), 500
    return jsonify({'success': True})
