"""Transaction-source ORM models.

`Transaction` is the unified table that all sources import into. The
per-source legacy models (`B3Movimentation`, `B3Negotiation`,
`AvenueExtract`, `GenericExtract`) remain temporarily — they are read by
the one-shot `migrate_legacy_to_transaction()` and dropped after a
successful migration.
"""
from sqlalchemy import Index

from app import db


class Transaction(db.Model):
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String, unique=True, index=True)

    # Discriminators
    source = db.Column(db.String, nullable=False)         # 'b3' | 'avenue' | 'generic' | 'manual'
    record_type = db.Column(db.String, nullable=False)    # 'movimentation' | 'negotiation' | 'extract'

    # Dates / time
    date = db.Column(db.String, nullable=False)           # 'YYYY-MM-DD'
    settlement_date = db.Column(db.String)                # Avenue liquidação
    time = db.Column(db.String)                           # Avenue hora

    # Asset identity
    asset = db.Column(db.String, index=True)              # Parsed ticker
    product = db.Column(db.String)                        # Original product/description
    institution = db.Column(db.String)                    # Broker

    # Movement classification
    raw_label = db.Column(db.String)                      # Original label from CSV
    category = db.Column(db.String, nullable=False)       # Canonical (see category_mapping)
    direction = db.Column(db.String)                      # 'Credito' | 'Debito'

    # Numerics
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total = db.Column(db.Float)
    balance = db.Column(db.Float)                         # Avenue saldo

    # Currency / overflow
    currency = db.Column(db.String, nullable=False, default='BRL')
    description = db.Column(db.String)                    # Avenue descrição
    meta = db.Column(db.JSON)                             # mercado, prazo, etc.

    __table_args__ = (
        Index('ix_transaction_source_asset_date', 'source', 'asset', 'date'),
    )

    def __repr__(self):
        return f'<Transaction {self.id} {self.source}/{self.record_type} {self.asset} {self.category}>'


# ---------------------------------------------------------------------------
# Legacy per-source models — kept ONLY until migrate_legacy_to_transaction()
# has run. They will be removed after Phase 5.
# ---------------------------------------------------------------------------


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
