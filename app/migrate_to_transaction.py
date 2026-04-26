"""One-shot migration: legacy per-source tables → unified `transaction` table.

Runs at startup (after `db.create_all()`) and is idempotent: it only does
work when at least one legacy table still exists in the database. After
copying, the legacy tables are dropped.

Legacy → Transaction translation reuses the same `import_translators`
helpers used by the importer, so the canonical category mapping stays in
one place.
"""
import logging

from sqlalchemy import inspect

from app import db
from app.import_translators import (
    avenue_extract_row,
    b3_movimentation_row,
    b3_negotiation_row,
    generic_extract_row,
)
from app.models import (
    AvenueExtract,
    B3Movimentation,
    B3Negotiation,
    GenericExtract,
    Transaction,
)

logger = logging.getLogger(__name__)


_LEGACY_TABLES = {
    'b3_movimentation': B3Movimentation,
    'b3_negotiation': B3Negotiation,
    'avenue_extract': AvenueExtract,
    'generic_extract': GenericExtract,
}


def _b3_mov_to_dict(r):
    return {
        'Entrada/Saída': r.entrada_saida,
        'Data': r.data,
        'Movimentação': r.movimentacao,
        'Produto': r.produto,
        'Instituição': r.instituicao,
        'Quantidade': r.quantidade or 0.0,
        'Preço unitário': r.preco_unitario or 0.0,
        'Valor da Operação': r.valor_operacao or 0.0,
    }


def _b3_neg_to_dict(r):
    return {
        'Data do Negócio': r.data,
        'Tipo de Movimentação': r.tipo,
        'Mercado': r.mercado,
        'Prazo/Vencimento': r.prazo,
        'Instituição': r.instituicao,
        'Código de Negociação': r.codigo,
        'Quantidade': r.quantidade or 0.0,
        'Preço': r.preco or 0.0,
        'Valor': r.valor or 0.0,
    }


def _avenue_to_dict(r):
    return {
        'Data': r.data,
        'Hora': r.hora,
        'Liquidação': r.liquidacao,
        'Descrição': r.descricao,
        'Valor (U$)': r.valor or 0.0,
        'Saldo da conta (U$)': r.saldo or 0.0,
        'Entrada/Saída': r.entrada_saida,
        'Produto': r.produto,
        'Movimentação': r.movimentacao,
        'Quantidade': r.quantidade,
        'Preço unitário': r.preco_unitario,
    }


def _generic_to_dict(r):
    return {
        'Date': r.date,
        'Asset': r.asset,
        'Movimentation': r.movimentation,
        'Quantity': r.quantity or 0.0,
        'Price': r.price or 0.0,
        'Total': r.total or 0.0,
    }


_PIPELINES = (
    # (model, suffix, dict_fn, translator)
    (B3Movimentation, ':mov', _b3_mov_to_dict, b3_movimentation_row),
    (B3Negotiation, ':neg', _b3_neg_to_dict, b3_negotiation_row),
    (AvenueExtract, ':av', _avenue_to_dict, avenue_extract_row),
    (GenericExtract, ':gen', _generic_to_dict, generic_extract_row),
)


def _existing_origin_ids():
    return {
        oid for (oid,) in db.session.query(Transaction.origin_id).all()
    }


def _migrate_table(model, suffix, dict_fn, translator, existing):
    rows = model.query.all()
    added = 0
    skipped = 0
    for r in rows:
        # Avenue/Generic legacy origin_id was 'filepath:hash:idx' or 'FORM'.
        # We append the suffix so re-runs don't collide and so it lines up
        # with the new importer convention.
        legacy_oid = r.origin_id or f'legacy-{model.__name__}-{r.id}'
        new_oid = legacy_oid if legacy_oid.endswith(suffix) else legacy_oid + suffix
        if new_oid in existing:
            skipped += 1
            continue
        try:
            kwargs = translator(dict_fn(r))
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception('Failed to translate %s id=%s: %s', model.__name__, r.id, exc)
            continue
        kwargs['origin_id'] = new_oid
        db.session.add(Transaction(**kwargs))
        existing.add(new_oid)
        added += 1
    return added, skipped


def _legacy_tables_present():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    return [name for name in _LEGACY_TABLES if name in table_names]


def migrate_legacy_to_transaction(drop_legacy=True):
    """Migrate any rows from the four legacy tables into `transaction`.

    Returns a summary dict ``{table: (added, skipped)}``. No-op if the
    legacy tables don't exist.
    """
    present = _legacy_tables_present()
    if not present:
        return {}

    logger.info('Starting legacy → Transaction migration. Tables: %s', present)
    summary = {}
    existing = _existing_origin_ids()

    for model, suffix, dict_fn, translator in _PIPELINES:
        if model.__tablename__ not in present:
            continue
        added, skipped = _migrate_table(model, suffix, dict_fn, translator, existing)
        summary[model.__tablename__] = (added, skipped)
        logger.info('  %s: added=%d skipped=%d', model.__tablename__, added, skipped)

    db.session.commit()

    if drop_legacy:
        for name in present:
            try:
                db.session.execute(db.text(f'DROP TABLE IF EXISTS {name}'))
            except Exception:  # pragma: no cover
                logger.exception('Failed to drop legacy table %s', name)
        db.session.commit()
        logger.info('Dropped legacy tables: %s', present)

    return summary
