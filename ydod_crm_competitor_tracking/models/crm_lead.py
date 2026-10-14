from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    competitor_ids = fields.Many2many(
        'ydod.crm.competitor', relation='ydod_crm_competitor_lead_rel',
        column1='lead_id', column2='competitor_id', string='Competitors')

    def write(self, vals):
        won_status_before = {lead.id: lead.won_status for lead in self}
        res = super().write(vals)
        for lead in self:
            if lead.competitor_ids and lead.won_status in ('won', 'lost') \
                    and won_status_before.get(lead.id) != lead.won_status:
                lead._create_competitor_results()
        return res

    def _create_competitor_results(self):
        self.ensure_one()
        self.env['ydod.crm.competitor.result'].create([{
            'competitor_id': competitor.id,
            'lead_id': self.id,
            'result': self.won_status,
            'stage_id': self.stage_id.id,
            'close_date': fields.Datetime.now(),
            'expected_revenue': self.expected_revenue,
            'company_currency': self.company_currency.id,
            'team_id': self.team_id.id,
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
        } for competitor in self.competitor_ids])
