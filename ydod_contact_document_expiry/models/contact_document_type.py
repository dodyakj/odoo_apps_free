from odoo import api, fields, models, _

class ContactDocumentType(models.Model):
    _name = "contact_document_type"
    _description = "Contact Document Type"
    _order = "name"

    name = fields.Char(string="Document Type Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True)
    description = fields.Text(string="Description")
    alert_days = fields.Integer(string="Default Alert Days Before Expiry", default=30, required=True, help="Number of days before expiry to start raising alerts.")
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The document type code must be unique!')
    ]
