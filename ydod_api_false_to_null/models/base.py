"""False-to-None conversion logic for API responses."""

from odoo import api, models


def _get_field_types(model: models.Model) -> dict[str, str]:
    """Return the field types declared by a model."""
    return {fname: field.type for fname, field in model._fields.items()}


def _get_comodel_names(model: models.Model) -> dict[str, str]:
    """Return relational field names and their comodel names."""
    return {
        fname: field.comodel_name
        for fname, field in model._fields.items()
        if field.type in ('many2one', 'one2many', 'many2many') and field.comodel_name
    }


def _should_convert(env: api.Environment) -> bool:
    """Check if False-to-None conversion should be applied.

    Context key 'api_false_to_null' takes precedence over global parameter.
    """
    context_val = env.context.get('api_false_to_null')
    if context_val is not None:
        return bool(context_val)
    return env['ir.config_parameter'].sudo().get_bool('ydod_api_false_to_null.enabled')


def _convert_false_to_null(model: models.Model, result):
    """Recursively convert False to None for non-Boolean fields in result."""
    if not result:
        return result

    metadata = {
        model._name: (_get_field_types(model), _get_comodel_names(model)),
    }

    def get_metadata(current_model: models.Model) -> tuple[dict[str, str], dict[str, str]]:
        if current_model._name not in metadata:
            metadata[current_model._name] = (
                _get_field_types(current_model),
                _get_comodel_names(current_model),
            )
        return metadata[current_model._name]

    def convert_record(
        record: dict,
        current_model: models.Model,
    ) -> dict:
        if not isinstance(record, dict):
            return record

        current_field_types, current_comodel_names = get_metadata(current_model)

        converted = {}
        for key, value in record.items():
            field_type = current_field_types.get(key)
            comodel = current_comodel_names.get(key)

            if comodel and isinstance(value, dict):
                converted[key] = convert_record(value, current_model.env[comodel])
            elif comodel and isinstance(value, list):
                child_model = current_model.env[comodel]
                converted[key] = [
                    convert_record(item, child_model) if isinstance(item, dict) else item
                    for item in value
                ]
            elif value is False and field_type != 'boolean':
                converted[key] = None
            else:
                converted[key] = value
        return converted

    if isinstance(result, list):
        return [convert_record(r, model) for r in result]
    elif isinstance(result, dict) and 'records' in result:
        # web_read format: {'records': [...], 'length': ..., 'ids': ...}
        result = result.copy()
        result['records'] = [convert_record(r, model) for r in result['records']]
        return result
    else:
        return convert_record(result, model)


# Monkey-patch models.Model methods
_original_read = models.Model.read
_original_search_read = models.Model.search_read


@api.model
def _patched_read(self, fields=None, load='_classic_read'):
    result = _original_read(self, fields=fields, load=load)
    if load != 'web' and _should_convert(self.env):
        return _convert_false_to_null(self, result)
    return result


@api.model
def _patched_search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **kwargs):
    result = _original_search_read(self, domain=domain, fields=fields, offset=offset, limit=limit, order=order, **kwargs)
    if _should_convert(self.env):
        return _convert_false_to_null(self, result)
    return result


models.Model.read = _patched_read
models.Model.search_read = _patched_search_read


class ApiFalseToNullBase(models.AbstractModel):
    _inherit = 'base'

    @api.readonly
    def web_read(self, specification):
        result = super().web_read(specification)
        if _should_convert(self.env):
            return _convert_false_to_null(self, result)
        return result
