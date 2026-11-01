from . import models

# (model, label, search fields with weight, display fields, extra domain)
DEFAULT_CONFIGS = [
    ('res.partner', 'Contacts',
     [('name', 20), ('email', 10), ('phone', 10), ('ref', 10), ('vat', 5)],
     ['email', 'phone', 'city'], '[]'),
    ('product.template', 'Products',
     [('name', 20), ('default_code', 15), ('barcode', 15)],
     ['default_code', 'list_price'], '[]'),
    ('sale.order', 'Sales Orders',
     [('name', 20), ('partner_id', 10), ('client_order_ref', 10)],
     ['partner_id', 'amount_total', 'state'], '[]'),
    ('purchase.order', 'Purchase Orders',
     [('name', 20), ('partner_id', 10), ('partner_ref', 10)],
     ['partner_id', 'amount_total', 'state'], '[]'),
    ('account.move', 'Invoices',
     [('name', 20), ('partner_id', 10), ('ref', 10)],
     ['partner_id', 'amount_total', 'state'], "[('move_type', '!=', 'entry')]"),
]


def _ydod_create_default_configs(env):
    """Create the default search configurations for installed models (idempotent)."""
    Config = env['ydod.global.search.model'].sudo().with_context(active_test=False)
    existing = set(Config.search([]).mapped('model_name'))
    wanted = [c for c in DEFAULT_CONFIGS if c[0] in env.registry and c[0] not in existing]
    if not wanted:
        return
    names = {f for c in wanted for f in [s[0] for s in c[2]] + c[3]}
    fields = env['ir.model.fields'].sudo().search([
        ('model', 'in', [c[0] for c in wanted]), ('name', 'in', list(names)),
    ])
    by_key = {(f.model, f.name): f for f in fields}
    vals_list = []
    for model, label, search_fields, display_fields, domain in wanted:
        lines = []
        sequence = 10
        for fname, weight in search_fields:
            field = by_key.get((model, fname))
            if field:
                lines.append((0, 0, {
                    'field_id': field.id, 'sequence': sequence, 'weight': weight,
                    'use_search': True, 'use_display': fname in display_fields,
                }))
                sequence += 10
        for fname in display_fields:
            field = by_key.get((model, fname))
            if field and fname not in dict(search_fields):
                lines.append((0, 0, {
                    'field_id': field.id, 'sequence': sequence, 'weight': 0,
                    'use_search': False, 'use_display': True,
                }))
                sequence += 10
        if any(line[2]['use_search'] for line in lines):
            vals_list.append({
                'name': label,
                'model_id': fields.filtered(lambda f, m=model: f.model == m)[:1].model_id.id,
                'sequence': 10 * (len(vals_list) + 1),
                'extra_domain': domain,
                'field_ids': lines,
            })
    Config.create(vals_list)
