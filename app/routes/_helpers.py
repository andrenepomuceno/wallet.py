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


def handle_manual_entry(model, form, field_map, redirect_endpoint, with_origin_id=True):
    """Validate `form`, dedup against `model` by field values, insert if new.

    `field_map` maps form attribute names to model column names.
    Returns a redirect Response on success, otherwise None (caller must render).
    """
    if not form.validate_on_submit():
        if form.errors:
            app.logger.debug('Not submit. Errors: %s', form.errors)
            flash_form_errors(form)
        return None

    values = {col: getattr(form, attr).data for attr, col in field_map.items()}
    filter_kwargs = dict(values)
    if with_origin_id:
        filter_kwargs['origin_id'] = 'FORM'

    if model.query.filter_by(**filter_kwargs).first():
        app.logger.info('New entry already exists in the database!')
        flash('Entry already exists in the database.')
        return None

    insert_kwargs = dict(values)
    if with_origin_id:
        insert_kwargs['origin_id'] = 'FORM'
    db.session.add(model(**insert_kwargs))
    db.session.commit()
    invalidate_processing_cache()
    app.logger.info('Added new entry to database!')
    flash('Entry added successfully!')
    return redirect(url_for(redirect_endpoint))
