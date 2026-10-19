from odoo import api, fields, models, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    document_ids = fields.One2many("contact_document", "partner_id", string="Compliance Documents")
    document_count = fields.Integer(string="Document Count", compute="_compute_document_count", aggregator="count")
    document_status = fields.Selection([
        ('valid', 'Valid'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('none', 'No Documents')
    ], string="Compliance Status", compute="_compute_document_status", store=True, aggregator="count")

    @api.depends('document_ids.state')
    def _compute_document_count(self):
        for partner in self:
            partner.document_count = len(partner.document_ids)

    @api.depends('document_ids.state')
    def _compute_document_status(self):
        for partner in self:
            docs = partner.document_ids
            if not docs:
                partner.document_status = 'none'
            elif any(d.state == 'expired' for d in docs):
                partner.document_status = 'expired'
            elif any(d.state == 'expiring' for d in docs):
                partner.document_status = 'expiring'
            else:
                partner.document_status = 'valid'

    def action_view_compliance_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Compliance Documents'),
            'res_model': 'contact_document',
            'domain': [('partner_id', '=', self.id)],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {'default_partner_id': self.id},
        }
