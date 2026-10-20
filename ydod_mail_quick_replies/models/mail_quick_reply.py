from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MailQuickReplyCategory(models.Model):
    _name = 'mail.quick.reply.category'
    _description = 'Quick Reply Category'
    _order = 'sequence, name, id'

    name = fields.Char(string="Category Name", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    reply_ids = fields.One2many('mail.quick.reply', 'category_id', string="Quick Replies")


class MailQuickReply(models.Model):
    _name = 'mail.quick.reply'
    _description = 'Mail Quick Reply'
    _order = 'sequence, id'

    name = fields.Char(
        string="Title",
        required=True,
        translate=True,
        help="A descriptive title for this quick reply."
    )
    shortcut = fields.Char(
        string="Shortcut",
        required=True,
        index=True,
        help="Short keyword used to quickly identify and trigger this reply."
    )
    category_id = fields.Many2one(
        'mail.quick.reply.category',
        string="Category",
        index=True,
        help="Optional category to organize your quick replies."
    )
    body = fields.Html(
        string="Content",
        required=True,
        translate=True,
        sanitize=True,
        help="The formatted text content of the canned response."
    )
    user_id = fields.Many2one(
        'res.users',
        string="Owner",
        index=True,
        default=lambda self: self.env.user,
        help="If set, this reply is private to the owner. Leave empty for global access."
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    @api.depends('name', 'shortcut')
    def _compute_display_name(self):
        for record in self:
            if record.shortcut:
                record.display_name = f"[{record.shortcut}] {record.name}"
            else:
                record.display_name = record.name or ""

    @api.constrains('shortcut', 'user_id')
    def _check_shortcut_unique(self):
        for record in self:
            if not record.shortcut:
                continue
            domain = [
                ('id', '!=', record.id),
                ('shortcut', '=', record.shortcut),
                ('user_id', '=', record.user_id.id),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    self.env._(
                        "The shortcut '%(shortcut)s' is already in use for this user / scope.",
                        shortcut=record.shortcut,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('shortcut'):
                vals['shortcut'] = vals['shortcut'].strip().lower()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('shortcut'):
            vals['shortcut'] = vals['shortcut'].strip().lower()
        return super().write(vals)
