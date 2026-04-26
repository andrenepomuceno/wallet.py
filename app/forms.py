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
    entrada_saida = StringField('Entrada/Saída')
    data = StringField('Date')
    movimentacao = StringField('Movimentation')
    produto = StringField('Produto')
    instituicao = StringField('Instituição')
    quantidade = FloatField('Quantity')
    preco_unitario = FloatField('Price')
    valor_operacao = FloatField('Total')
    submit = SubmitField('Submit')

class AvenueExtractAddForm(FlaskForm):
    data = StringField('Data', validators=[DataRequired()], default=pd.to_datetime("today").date)
    hora = StringField('Hora', validators=[DataRequired()], default=pd.to_datetime("today").time)
    liquidacao = StringField('Liquidação', validators=[DataRequired()], default=pd.to_datetime("today").date)
    descricao = StringField('Descrição', default='')
    valor = FloatField('Valor (U$)', default=0)
    saldo = FloatField('Saldo em Conta (U$)', default=0)
    entrada_saida = StringField('Entrada/Saída', default='Credito')
    produto = StringField('Produto')
    movimentacao = StringField('Movimentação', validators=[DataRequired()], default='Compra')
    quantidade = FloatField('Quantidade', default=0)
    preco_unitario = FloatField('Preço Unitário', default=0)
    submit = SubmitField('Submit')

class B3NegotiationAddForm(FlaskForm):
    date = StringField('Date', validators=[DataRequired()], default=pd.to_datetime("today").date)
    movimentation = StringField('Movimentation', validators=[DataRequired()], default='Compra')
    mercado = StringField('Mercado', validators=[DataRequired()], default='Mercado à Vista')
    prazo = StringField('Prazo/Vencimento', validators=[DataRequired()], default='-')
    instituicao = StringField('Instituição', validators=[DataRequired()], default='')
    codigo = StringField('Código de Negociação', validators=[DataRequired()], default='')
    quantity = FloatField('Quantity', default=0)
    price = FloatField('Price', default=0)
    total = FloatField('Total', default=0)
    submit = SubmitField('Submit')

class ApiConfigForm(FlaskForm):
    gemini_api_key = PasswordField('Gemini API Key', validators=[Optional()])
    cache_default_ttl = IntegerField(
        'TTL padrão (s)', validators=[Optional(), NumberRange(min=0)])
    cache_yfinance_ttl = IntegerField(
        'TTL Yahoo Finance (s)', validators=[Optional(), NumberRange(min=0)])
    cache_exchange_ttl = IntegerField(
        'TTL cotação USD (s)', validators=[Optional(), NumberRange(min=0)])
    cache_scraping_ttl = IntegerField(
        'TTL scraping (s)', validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField('Salvar Configuracoes')