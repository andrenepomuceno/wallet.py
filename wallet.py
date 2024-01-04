from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import os
import logging

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wallet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entrada_saida = db.Column(db.String)
    data = db.Column(db.String)
    movimentacao = db.Column(db.String)
    produto = db.Column(db.String)
    instituicao = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)
    valor_operacao = db.Column(db.Float)

    def __repr__(self):
        return f'<Investment {self.id}>'

def initialize_database():
    db.create_all()

def process_file(file_path):
    app.logger.debug(f'Processing file: {file_path}')
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path)

    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Preço unitário'] = pd.to_numeric(df['Preço unitário'], errors='coerce').fillna(0.0)
    df['Valor da Operação'] = pd.to_numeric(df['Valor da Operação'], errors='coerce').fillna(0.0)
    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0.0)
    return df

def insert_data_into_db(df):
    for _, row in df.iterrows():
        # Verifica se a entrada já existe
        if not Investment.query.filter_by(data=row['Data'], movimentacao=row['Movimentação'],
                                          produto=row['Produto'], instituicao=row['Instituição']).first():
            new_entry = Investment(
                entrada_saida=row['Entrada/Saída'],
                data=row['Data'],
                movimentacao=row['Movimentação'],
                produto=row['Produto'],
                instituicao=row['Instituição'],
                quantidade=row['Quantidade'],
                preco_unitario=row['Preço unitário'],
                valor_operacao=row['Valor da Operação']
            )
            db.session.add(new_entry)
    db.session.commit()

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filepath = os.path.join('uploads', file.filename)
            file.save(filepath)
            app.logger.debug(f'File {file.filename} saved at {filepath}.')

            df = process_file(filepath)
            insert_data_into_db(df)

            return redirect(url_for('view_table'))
        else:
            app.logger.debug('No file provided for upload.')

    return render_template('index.html', message='')

@app.route('/view', methods=['GET', 'POST'])
def view_table():
    app.logger.debug('Rendering view table.')

    # Mapeamento dos nomes dos campos do formulário para os nomes das colunas na tabela
    column_map = {
        'Quantidade': Investment.quantidade,
        'Preço unitário': Investment.preco_unitario,
        'Valor da Operação': Investment.valor_operacao,
        'Entrada/Saída': Investment.entrada_saida,
        'Data': Investment.data,
        'Movimentação': Investment.movimentacao,
        'Produto': Investment.produto,
        'Instituição': Investment.instituicao
    }

    query = Investment.query.order_by(Investment.data.asc())

    if request.method == 'POST':
        filters = request.form.to_dict()
        for key, value in filters.items():
            if value and key in column_map:
                column = column_map[key]
                if key in ['Quantidade', 'Preço unitário', 'Valor da Operação']:
                    query = query.filter(column == value)
                else:
                    query = query.filter(column.like(f'%{value}%'))

    result = query.all()
    # Convertendo o resultado para um DataFrame do pandas
    df = pd.DataFrame([(d.entrada_saida, d.data, d.movimentacao, d.produto, d.instituicao, d.quantidade, d.preco_unitario, d.valor_operacao) for d in result], 
                      columns=['Entrada/Saída', 'Data', 'Movimentação', 'Produto', 'Instituição', 'Quantidade', 'Preço unitário', 'Valor da Operação'])

    return render_template('view_table.html', tables=[df.to_html(classes='data')], titles=df.columns.values)

if __name__ == '__main__':
    with app.app_context():
        initialize_database()
    app.run(debug=True)
