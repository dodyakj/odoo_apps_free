from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    openwa_session_id = fields.Many2one('openwa.session', string="WhatsApp Session", ondelete='set null',
                                        index='btree_not_null', readonly=True)
    openwa_wa_number = fields.Char(string="WhatsApp Number", readonly=True)
    openwa_partner_id = fields.Many2one('res.partner', string="WhatsApp Contact", readonly=True)

    def message_post(self, *, message_type='notification', **kwargs):
        message = super().message_post(message_type=message_type, **kwargs)
        if (len(self) == 1 and self.openwa_session_id and message_type == 'comment'
                and not self.env.context.get('openwa_skip_send') and not self.env.user._is_public()):
            self._openwa_forward(message)
        return message

    def _openwa_forward(self, message):
        """A reply written in a WhatsApp conversation of Discuss is sent back to the contact."""
        body = html2plaintext(message.body or '').strip()
        attachments = message.attachment_ids
        if not body and not attachments:
            return
        error = False
        try:
            log = self.env['openwa.message']._openwa_send(
                self.openwa_session_id, self.openwa_partner_id, body, attachment=attachments[:1],
                wa_number=self.openwa_wa_number, check_opt_in=False, channel=self)
            error = log.status == 'failed' and log.error
        except UserError as exc:
            error = str(exc)
        if error:
            self.with_context(openwa_skip_send=True).message_post(
                body=self.env._("Not delivered over WhatsApp: %s", error), message_type='notification')
