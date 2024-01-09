from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length

# class RegistrationForm(FlaskForm):
#     nome = StringField('Nome', validators=[DataRequired(), Length(min=2, max=50)])
#     email = StringField('Email', validators=[DataRequired(), Email()])
#     senha = PasswordField('Senha', validators=[DataRequired(), Length(min=6, max=35)])
#     submit = SubmitField('Registrar')

# class LoginForm(FlaskForm):
#     email = StringField('Email', validators=[DataRequired(), Email()])
#     senha = PasswordField('Senha', validators=[DataRequired()])
#     submit = SubmitField('Entrar')

# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     form = RegistrationForm()
#     if form.validate_on_submit():
#         # Aqui você pode adicionar a lógica para processar os dados do formulário
#         pass  # Substitua por sua lógica
#     return render_template('register.html', title='Registro', form=form)

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     form = LoginForm()
#     if form.validate_on_submit():
#         # Processar o login
#         pass  # Substitua por sua lógica
#     return render_template('login.html', title='Login', form=form)