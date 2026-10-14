from odoo import fields, models

WON_LOST_FIELDS = {'active', 'probability', 'stage_id'}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    competitor_ids = fields.Many2many(
        'ydod.crm.competitor', relation='ydod_crm_competitor_lead_rel',
        column1='lead_id', column2='competitor_id', string='Competitors')

    def _ydod_get_won_status(self):
        """ Won: active with probability 100. Lost: archived with probability 0. """
        self.ensure_one()
        if self.active and self.probability == 100:
            return 'won'
        if not self.active and self.probability == 0:
            return 'lost'
        return 'pending'

    def write(self, vals):
        if not WON_LOST_FIELDS.intersection(vals):
            return super().write(vals)
        won_status_before = {lead.id: lead._ydod_get_won_status() for lead in self}
        res = super().write(vals)
        for lead in self:
            won_status = lead._ydod_get_won_status()
            if lead.competitor_ids and won_status in ('won', 'lost') \
                    and won_status_before.get(lead.id) != won_status:
                lead._create_competitor_results(won_status)
        return res

    def _create_competitor_results(self, won_status):
        self.ensure_one()
        self.env['ydod.crm.competitor.result'].create([{
            'competitor_id': competitor.id,
            'lead_id': self.id,
            'result': won_status,
            'stage_id': self.stage_id.id,
            'close_date': fields.Datetime.now(),
            'expected_revenue': self.expected_revenue,
            'company_currency': self.company_currency.id,
            'team_id': self.team_id.id,
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
        } for competitor in self.competitor_ids])
