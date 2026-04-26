"""Transaction-source ORM models: B3, Avenue, Generic."""
from app import db


class B3Movimentation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    entrada_saida = db.Column(db.String)
    data = db.Column(db.String)
    movimentacao = db.Column(db.String)
    produto = db.Column(db.String)
    instituicao = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)
    valor_operacao = db.Column(db.Float)

    def __repr__(self):
        return f'<B3Movimentation {self.id}>'


class B3Negotiation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    data = db.Column(db.String)
    tipo = db.Column(db.String)
    mercado = db.Column(db.String)
    prazo = db.Column(db.String)
    instituicao = db.Column(db.String)
    codigo = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco = db.Column(db.Float)
    valor = db.Column(db.Float)

    def __repr__(self):
        return f'<B3Negotiation {self.id}>'


class AvenueExtract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    data = db.Column(db.String)
    hora = db.Column(db.String)
    liquidacao = db.Column(db.String)
    descricao = db.Column(db.String)
    valor = db.Column(db.Float)
    saldo = db.Column(db.Float)

    entrada_saida = db.Column(db.String)
    produto = db.Column(db.String)
    movimentacao = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)

    def __repr__(self):
        return f'<AvenueExtract {self.id}>'


class GenericExtract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    date = db.Column(db.String)
    asset = db.Column(db.String)
    movimentation = db.Column(db.String)
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total = db.Column(db.Float)
    # TODO currency support

    def __repr__(self):
        return f'<GenericExtract {self.id}>'
