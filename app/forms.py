import pandas as pd
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField
from wtforms.validators import DataRequired

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
