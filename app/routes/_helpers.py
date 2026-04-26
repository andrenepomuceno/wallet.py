"""Cross-cutting helpers shared by route modules."""
from flask import flash, redirect, url_for

from app import app, db
from app.utils.memocache import invalidate_processing_cache


def format_money(value):
    if value >= 1e12:
        return f"{value / 1e12:.2f} T"
    elif value >= 1e9:
        return f"{value / 1e9:.2f} B"
    elif value >= 1e6:
        return f"{value / 1e6:.2f} M"
    elif value >= 1e3:
        return f"{value / 1e3:.2f} K"
    return str(value)


app.jinja_env.filters['format_money'] = format_money


def flash_form_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Error validating field {getattr(form, field).label.text}: {error}")


def collect_form_errors(form):
    errors = []
    for field, field_errors in form.errors.items():
        label = getattr(form, field).label.text
        for error in field_errors:
            errors.append(f"Error validating field {label}: {error}")
    return errors


def process_manual_entry(model, form, field_map, with_origin_id=True):
    """Validate/dedup/insert a manual entry and return a structured result."""
    if not form.validate_on_submit():
        if form.errors:
            app.logger.debug('Not submit. Errors: %s', form.errors)
            return {
                'success': False,
                'errors': collect_form_errors(form),
                'inserted': False,
            }
        return {
            'success': False,
            'errors': [],
            'inserted': False,
        }

    values = {col: getattr(form, attr).data for attr, col in field_map.items()}
    filter_kwargs = dict(values)
    if with_origin_id:
        filter_kwargs['origin_id'] = 'FORM'

    if model.query.filter_by(**filter_kwargs).first():
        app.logger.info('New entry already exists in the database!')
        return {
            'success': False,
            'errors': ['Entry already exists in the database.'],
            'inserted': False,
        }

    insert_kwargs = dict(values)
    if with_origin_id:
        insert_kwargs['origin_id'] = 'FORM'
    db.session.add(model(**insert_kwargs))
    db.session.commit()
    invalidate_processing_cache()
    app.logger.info('Added new entry to database!')

    return {
        'success': True,
        'errors': [],
        'messages': ['Entry added successfully!'],
        'inserted': True,
    }


def process_manual_transaction(form, translator, dedup_keys=None):
    """Validate `form`, build a Transaction via `translator(form_values)`,
    dedup by `dedup_keys` (Transaction column names), insert if new.

    `translator` receives a dict {form_attr: value} from the form and must
    return a kwargs dict suitable for `Transaction(**kwargs)`.
    """
    from app.models import Transaction

    if not form.validate_on_submit():
        if form.errors:
            app.logger.debug('Not submit. Errors: %s', form.errors)
            return {'success': False, 'errors': collect_form_errors(form), 'inserted': False}
        return {'success': False, 'errors': [], 'inserted': False}

    form_values = {f.name: f.data for f in form if f.name not in ('csrf_token', 'submit')}
    kwargs = translator(form_values)

    if dedup_keys:
        filter_kwargs = {k: kwargs.get(k) for k in dedup_keys}
        if Transaction.query.filter_by(**filter_kwargs).first():
            app.logger.info('Manual transaction already exists.')
            return {
                'success': False,
                'errors': ['Entry already exists in the database.'],
                'inserted': False,
            }

    if not kwargs.get('origin_id'):
        # Stable origin_id for FORM rows so re-submits dedup
        import hashlib
        token = '|'.join(f'{k}={kwargs.get(k)}' for k in sorted(kwargs))
        kwargs['origin_id'] = 'FORM:' + hashlib.sha256(token.encode()).hexdigest()[:16]

    db.session.add(Transaction(**kwargs))
    db.session.commit()
    invalidate_processing_cache()
    app.logger.info('Added new manual Transaction.')
    return {
        'success': True,
        'errors': [],
        'messages': ['Entry added successfully!'],
        'inserted': True,
    }


def handle_manual_transaction(form, translator, redirect_endpoint, dedup_keys=None):
    result = process_manual_transaction(form, translator, dedup_keys=dedup_keys)
    if result.get('success'):
        for msg in result.get('messages', ['Entry added successfully!']):
            flash(msg)
        return redirect(url_for(redirect_endpoint))
    for error in result.get('errors', []):
        flash(error)
    return None


def handle_manual_entry(model, form, field_map, redirect_endpoint, with_origin_id=True):
    """Validate `form`, dedup against `model` by field values, insert if new.

    `field_map` maps form attribute names to model column names.
    Returns a redirect Response on success, otherwise None (caller must render).
    """
    result = process_manual_entry(
        model,
        form,
        field_map,
        with_origin_id=with_origin_id,
    )

    if result.get('success'):
        for msg in result.get('messages', ['Entry added successfully!']):
            flash(msg)
        return redirect(url_for(redirect_endpoint))

    for error in result.get('errors', []):
        flash(error)

    return None
