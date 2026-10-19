from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ContactDocumentNotifyWizard(models.TransientModel):
    _name = "contact_document_notify_wizard"
    _description = "Send Compliance Notification Wizard"

    document_ids = fields.Many2many("contact_document", string="Documents to Notify", default=lambda self: self._default_document_ids())
    message = fields.Text(string="Custom Message", required=True, default=lambda self: _("Dear Partner,\n\nPlease note that one or more of your compliance documents registered with us have expired or are approaching their expiry date. Kindly provide updated copies at your earliest convenience.\n\nBest regards,\nCompliance Department"))

    def _default_document_ids(self):
        active_ids = self.env.context.get('active_ids', [])
        if active_ids and self.env.context.get('active_model') == 'contact_document':
            return active_ids
        return []

    def action_send_notification(self):
        self.ensure_one()
        if not self.document_ids:
            raise UserError(_("Please select at least one document."))
        
        count = 0
        for doc in self.document_ids:
            if doc.partner_id:
                doc.message_post(
                    body=f"<p>{self.message}</p>",
                    subject=_("Compliance Document Expiry Notice: %s") % doc.name,
                    partner_ids=doc.partner_id.commercial_partner_id.ids
                )
                count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notifications Sent'),
                'message': _('Successfully sent compliance notifications for %s documents.') % count,
                'type': 'success',
                'sticky': False,
            }
        }
