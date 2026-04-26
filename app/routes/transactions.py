"""Transaction list views: B3 movimentation/negotiation, Avenue, Generic."""
from flask import render_template, request

from app import app
from app.forms import (
    AvenueExtractAddForm,
    B3MovimentationFilterForm,
    B3NegotiationAddForm,
    GenericExtractAddForm,
)
from app.models import AvenueExtract, B3Negotiation, GenericExtract
from app.processing import (
    process_avenue_extract_request,
    process_b3_movimentation_request,
    process_b3_negotiation_request,
    process_generic_extract_request,
)

from ._helpers import handle_manual_entry


@app.route('/b3_movimentation', methods=['GET', 'POST'])
def view_movimentation():
    filter_form = B3MovimentationFilterForm()
    df = process_b3_movimentation_request(request)
    return render_template('view_movimentation.html', html_title='B3 Movimentation',
                           df=df, filter_form=filter_form)


@app.route('/b3_negotiation', methods=['GET', 'POST'])
def view_negotiation():
    app.logger.info('view_negotiation')

    add_form = B3NegotiationAddForm()
    response = handle_manual_entry(
        B3Negotiation, add_form,
        field_map={
            'date': 'data', 'movimentation': 'tipo', 'mercado': 'mercado',
            'prazo': 'prazo', 'instituicao': 'instituicao', 'codigo': 'codigo',
            'quantity': 'quantidade', 'price': 'preco', 'total': 'valor',
        },
        redirect_endpoint='view_negotiation',
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
    response = handle_manual_entry(
        AvenueExtract, add_form,
        field_map={
            'data': 'data', 'hora': 'hora', 'liquidacao': 'liquidacao',
            'descricao': 'descricao', 'valor': 'valor', 'saldo': 'saldo',
            'entrada_saida': 'entrada_saida', 'produto': 'produto',
            'movimentacao': 'movimentacao', 'quantidade': 'quantidade',
            'preco_unitario': 'preco_unitario',
        },
        redirect_endpoint='view_extract',
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
    response = handle_manual_entry(
        GenericExtract, add_form,
        field_map={
            'date': 'date', 'asset': 'asset', 'movimentation': 'movimentation',
            'quantity': 'quantity', 'price': 'price', 'total': 'total',
        },
        redirect_endpoint='view_generic_extract',
        with_origin_id=False,
    )
    if response is not None:
        return response

    df = process_generic_extract_request()
    return render_template('view_generic.html', html_title='Generic Extract',
                           df=df, add_form=add_form)
