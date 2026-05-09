"""Portfolio rebalancing page: ideal/target vs actual/current comparison."""
from flask import flash, redirect, render_template, request, url_for
from wtforms import FloatField
from wtforms.validators import NumberRange, Optional

from app import app
from app.forms import PortfolioTargetForm
from app.processing import process_consolidate_request, process_rebalance_request
from app.processing.rebalance import save_targets
from app.utils.memocache import invalidate_processing_cache


def _build_target_form(asset_classes, saved_targets):
    """Dynamically add one FloatField per asset class to PortfolioTargetForm."""
    for cls in asset_classes:
        field_name = _class_to_field(cls)
        if not hasattr(PortfolioTargetForm, field_name):
            setattr(
                PortfolioTargetForm,
                field_name,
                FloatField(
                    cls,
                    validators=[Optional(), NumberRange(min=0, max=100)],
                    default=0.0,
                ),
            )
    form = PortfolioTargetForm()
    # Pre-populate with saved values
    for cls in asset_classes:
        field = getattr(form, _class_to_field(cls), None)
        if field is not None and cls in saved_targets:
            field.data = saved_targets[cls]
    return form


def _class_to_field(cls: str) -> str:
    """Convert an asset_class name to a valid Python identifier for the form field."""
    return 'w_' + ''.join(c if c.isalnum() else '_' for c in cls).strip('_').lower()


def _parse_weights(form, asset_classes) -> tuple[dict, list]:
    """Extract weights from submitted form data; return (weights_dict, errors)."""
    weights = {}
    errors = []
    for cls in asset_classes:
        field = getattr(form, _class_to_field(cls), None)
        if field is None:
            weights[cls] = 0.0
            continue
        val = field.data
        if val is None:
            val = 0.0
        if val < 0 or val > 100:
            errors.append(f"Peso de '{cls}' fora do intervalo 0–100.")
        weights[cls] = round(float(val), 4)

    return weights, errors


@app.route('/rebalance', methods=['GET', 'POST'])
def view_rebalance():
    info = process_consolidate_request()

    if not info['valid']:
        flash('Nenhum dado encontrado. Faça upload de um extrato primeiro.')
        return redirect(url_for('home'))

    rebalance_info = process_rebalance_request(info)
    saved_targets = rebalance_info.get('targets', {})

    # Determine list of active asset classes from consolidation
    from app.processing.rebalance import _classes_from_consolidate
    class_rows = _classes_from_consolidate(info)
    asset_classes = [r['asset_class'] for r in class_rows]

    # Include classes that have a target but no current position
    for cls in saved_targets:
        if cls not in asset_classes:
            asset_classes.append(cls)
    asset_classes = sorted(set(asset_classes))

    form = _build_target_form(asset_classes, saved_targets)

    if request.method == 'POST' and form.validate_on_submit():
        weights, errors = _parse_weights(form, asset_classes)
        if errors:
            for err in errors:
                flash(err)
        else:
            save_targets(weights)
            invalidate_processing_cache()
            flash('Pesos salvos com sucesso!')
            return redirect(url_for('view_rebalance'))

    return render_template(
        'view_rebalance.html',
        html_title='Rebalance',
        rebalance_info=rebalance_info,
        form=form,
        asset_classes=asset_classes,
    )
