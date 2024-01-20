from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField
from wtforms.validators import DataRequired, NumberRange
import pandas as pd

class GenericExtractForm(FlaskForm):
    date = StringField('Date', validators=[DataRequired()], default=pd.to_datetime("today").date)
    asset = StringField('Asset', validators=[DataRequired()])
    movimentation = StringField('Movimentation', validators=[DataRequired()], default='Buy')
    quantity = FloatField('Quantity', default=0)
    price = FloatField('Price', default=0)
    total = FloatField('Total', default=0)
    submit = SubmitField('Submit')