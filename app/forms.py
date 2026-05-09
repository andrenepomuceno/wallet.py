import pandas as pd
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange

class GenericExtractAddForm(FlaskForm):
    date = StringField('Date', validators=[DataRequired()], default=pd.to_datetime("today").date)
    asset = StringField('Asset', validators=[DataRequired()])
    movimentation = StringField('Movimentation', validators=[DataRequired()], default='Buy')
    quantity = FloatField('Quantity', default=0)
    price = FloatField('Price', default=0)
    total = FloatField('Total', default=0)
    submit = SubmitField('Submit')

class B3MovimentationFilterForm(FlaskForm):
    entrada_saida = StringField('Direction')
    data = StringField('Date')
    movimentacao = StringField('Movimentation')
    produto = StringField('Produto')
    instituicao = StringField('Institution')
    quantidade = FloatField('Quantity')
    preco_unitario = FloatField('Price')
    valor_operacao = FloatField('Total')
    submit = SubmitField('Submit')

class AvenueExtractAddForm(FlaskForm):
    data = StringField('Data', validators=[DataRequired()], default=pd.to_datetime("today").date)
    hora = StringField('Hora', validators=[DataRequired()], default=pd.to_datetime("today").time)
    liquidacao = StringField('Settlement', validators=[DataRequired()], default=pd.to_datetime("today").date)
    descricao = StringField('Description', default='')
    valor = FloatField('Valor (U$)', default=0)
    saldo = FloatField('Saldo em Conta (U$)', default=0)
    entrada_saida = StringField('Direction', default='Credit')
    produto = StringField('Produto')
    movimentacao = StringField('Operation', validators=[DataRequired()], default='Purchase')
    quantidade = FloatField('Quantidade', default=0)
    preco_unitario = FloatField('Unit Price', default=0)
    submit = SubmitField('Submit')

class B3NegotiationAddForm(FlaskForm):
    date = StringField('Date', validators=[DataRequired()], default=pd.to_datetime("today").date)
    movimentation = StringField('Movimentation', validators=[DataRequired()], default='Compra')
    mercado = StringField('Market', validators=[DataRequired()], default='Spot Market')
    prazo = StringField('Prazo/Vencimento', validators=[DataRequired()], default='-')
    instituicao = StringField('Institution', validators=[DataRequired()], default='')
    codigo = StringField('Trading Code', validators=[DataRequired()], default='')
    quantity = FloatField('Quantity', default=0)
    price = FloatField('Price', default=0)
    total = FloatField('Total', default=0)
    submit = SubmitField('Submit')

class PortfolioTargetForm(FlaskForm):
    """Dynamic form for setting target weights per asset class.

    Fields are added at runtime by the route before rendering; this base class
    carries only the submit button so WTForms CSRF protection still applies.
    The route adds one FloatField per asset_class after instantiating this form.
    """
    submit = SubmitField('Save Weights')


class ApiConfigForm(FlaskForm):
    gemini_api_key = PasswordField('Gemini API Key', validators=[Optional()])
    serper_api_key = PasswordField('Serper API Key', validators=[Optional()])
    cache_default_ttl = IntegerField(
        'Default TTL (s)', validators=[Optional(), NumberRange(min=0)])
    cache_yfinance_ttl = IntegerField(
        'TTL Yahoo Finance (s)', validators=[Optional(), NumberRange(min=0)])
    cache_exchange_ttl = IntegerField(
        'USD Quote TTL (s)', validators=[Optional(), NumberRange(min=0)])
    cache_scraping_ttl = IntegerField(
        'TTL scraping (s)', validators=[Optional(), NumberRange(min=0)])
    cache_serper_ttl = IntegerField(
        'TTL Serper (s)', validators=[Optional(), NumberRange(min=0)])
    cache_gemini_ttl = IntegerField(
        'TTL Gemini (s)', validators=[Optional(), NumberRange(min=0)])
    cache_asset_ttl = IntegerField(
        'TTL processamento por ativo (s)', validators=[Optional(), NumberRange(min=0)])
    cache_consolidate_ttl = IntegerField(
        'TTL consolidado global (s)', validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField('Salvar Configuracoes')