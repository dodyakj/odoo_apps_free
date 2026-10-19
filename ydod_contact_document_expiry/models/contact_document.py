from odoo import api, fields, models, _
from datetime import date

class ContactDocument(models.Model):
    _name = "contact_document"
    _description = "Contact Compliance Document"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "expiry_date asc, name"

    name = fields.Char(string="Document Name / Ref", required=True, tracking=True)
    document_type_id = fields.Many2one("contact_document_type", string="Document Type", required=True, ondelete="restrict", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Contact", required=True, ondelete="cascade", tracking=True)
    document_number = fields.Char(string="Document Number", tracking=True)
    issue_date = fields.Date(string="Issue Date", tracking=True)
    expiry_date = fields.Date(string="Expiry Date", required=True, tracking=True)
    notes = fields.Html(string="Notes & Comments")
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments", help="Upload scanned copies of the certificate or ID.")
    
    state = fields.Selection([
        ('valid', 'Valid'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired')
    ], string="Compliance Status", compute="_compute_state", store=True, tracking=True, aggregator="count")

    days_to_expiry = fields.Integer(string="Days to Expiry", compute="_compute_state", store=True, aggregator="avg")
    alert_days = fields.Integer(string="Alert Threshold (Days)", related="document_type_id.alert_days", readonly=True)

    @api.depends('expiry_date', 'document_type_id.alert_days')
    def _compute_state(self):
        today = date.today()
        for doc in self:
            if not doc.expiry_date:
                doc.state = 'valid'
                doc.days_to_expiry = 9999
                continue
            
            delta = (doc.expiry_date - today).days
            doc.days_to_expiry = delta
            threshold = doc.document_type_id.alert_days if doc.document_type_id else 30

            if delta < 0:
                doc.state = 'expired'
            elif delta <= threshold:
                doc.state = 'expiring'
            else:
                doc.state = 'valid'

    @api.model
    def _cron_check_document_expiry(self):
        """Automated cron action to log activities or notifications for expiring documents."""
        today = date.today()
        docs = self.search([('state', 'in', ('expiring', 'expired'))])
        for doc in docs:
            user_id = doc.partner_id.user_id or self.env.user
            if doc.state == 'expired':
                note = _("Compliance Document '%s' for %s has EXPIRED on %s!") % (doc.name, doc.partner_id.name, doc.expiry_date)
            else:
                note = _("Compliance Document '%s' for %s is expiring soon on %s (%s days remaining).") % (doc.name, doc.partner_id.name, doc.expiry_date, doc.days_to_expiry)

            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'contact_document'),
                ('res_id', '=', doc.id),
                ('user_id', '=', user_id.id),
                ('date_deadline', '=', fields.Date.today())
            ])
            if not existing_activity:
                self.env['mail.activity'].create({
                    'res_model_id': self.env['ir.model']._get('contact_document').id,
                    'res_id': doc.id,
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': _('Document Compliance Alert'),
                    'note': note,
                    'date_deadline': fields.Date.today(),
                    'user_id': user_id.id,
                })
        return True
