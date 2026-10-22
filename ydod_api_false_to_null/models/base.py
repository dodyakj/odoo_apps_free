"""False-to-None conversion logic for API responses."""

from typing import Any

from odoo import api, models


_PARAMETER_KEY = 'ydod_api_false_to_null.enabled'
_SKIP_READ_CONVERSION_CONTEXT_KEY = '_ydod_api_false_to_null_skip_read'


def _get_field_types(model: models.Model) -> dict[str, str]:
    """Return the field types declared by a model."""
    return {name: field.type for name, field in model._fields.items()}


def _get_comodel_names(model: models.Model) -> dict[str, str]:
    """Return relational field names and their comodel names."""
    return {
        name: field.comodel_name
        for name, field in model._fields.items()
        if field.type in ('many2one', 'one2many', 'many2many') and field.comodel_name
    }


def _should_convert(env: api.Environment) -> bool:
    """Check whether conversion is enabled, with request context taking priority."""
    context_value = env.context.get('api_false_to_null')
    if context_value is not None:
        return bool(context_value)

    value = env['ir.config_parameter'].sudo().get_param(_PARAMETER_KEY, default='')
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _convert_false_to_null(model: models.Model, result: Any) -> Any:
    """Recursively convert False to None for non-Boolean fields in result."""
    if not result:
        return result

    metadata: dict[str, tuple[dict[str, str], dict[str, str]]] = {}

    def get_metadata(
        current_model: models.Model,
    ) -> tuple[dict[str, str], dict[str, str]]:
        if current_model._name not in metadata:
            metadata[current_model._name] = (
                _get_field_types(current_model),
                _get_comodel_names(current_model),
            )
        return metadata[current_model._name]

    def convert_record(record: Any, current_model: models.Model) -> Any:
        if not isinstance(record, dict):
            return record

        field_types, comodel_names = get_metadata(current_model)
        converted = {}
        for name, value in record.items():
            comodel_name = comodel_names.get(name)
            if comodel_name and isinstance(value, dict):
                converted[name] = convert_record(value, current_model.env[comodel_name])
            elif comodel_name and isinstance(value, list):
                child_model = current_model.env[comodel_name]
                converted[name] = [
                    convert_record(item, child_model) if isinstance(item, dict) else item
                    for item in value
                ]
            elif value is False and field_types.get(name) != 'boolean':
                converted[name] = None
            else:
                converted[name] = value
        return converted

    if isinstance(result, list):
        return [convert_record(record, model) for record in result]
    if isinstance(result, dict) and 'records' in result:
        converted = result.copy()
        converted['records'] = [
            convert_record(record, model) for record in result['records']
        ]
        return converted
    return convert_record(result, model)


_original_read = models.Model.read
_original_search_read = models.Model.search_read


@api.model
def _patched_read(
    self: models.Model,
    fields: list[str] | None = None,
    load: str = '_classic_read',
) -> list[dict[str, Any]]:
    result = _original_read(self, fields=fields, load=load)
    if (
        load != 'web'
        and not self.env.context.get(_SKIP_READ_CONVERSION_CONTEXT_KEY)
        and _should_convert(self.env)
    ):
        return _convert_false_to_null(self, result)
    return result


@api.model
def _patched_search_read(
    self: models.Model,
    domain: list[Any] | None = None,
    fields: list[str] | None = None,
    offset: int = 0,
    limit: int | None = None,
    order: str | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    should_convert = _should_convert(self.env)
    result = _original_search_read(
        self.with_context(**{_SKIP_READ_CONVERSION_CONTEXT_KEY: True}),
        domain=domain,
        fields=fields,
        offset=offset,
        limit=limit,
        order=order,
        **kwargs,
    )
    if should_convert:
        return _convert_false_to_null(self, result)
    return result


models.Model.read = _patched_read
models.Model.search_read = _patched_search_read


class ApiFalseToNullBase(models.AbstractModel):
    _inherit = 'base'

    @api.readonly
    def web_read(self, specification: dict[str, Any]) -> list[dict[str, Any]]:
        should_convert = (
            not self.env.context.get(_SKIP_READ_CONVERSION_CONTEXT_KEY)
            and _should_convert(self.env)
        )
        self = self.with_context(**{_SKIP_READ_CONVERSION_CONTEXT_KEY: True})
        result = super().web_read(specification)
        if should_convert:
            return _convert_false_to_null(self, result)
        return result
