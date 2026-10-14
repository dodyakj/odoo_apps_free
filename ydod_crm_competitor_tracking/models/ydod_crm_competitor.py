from odoo import fields, models


class YdodCrmCompetitor(models.Model):
    _name = 'ydod.crm.competitor'
    _description = 'CRM Competitor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(required=True)
    website = fields.Char()
    notes = fields.Text()
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color Index')
    opportunity_ids = fields.Many2many(
        'crm.lead', relation='ydod_crm_competitor_lead_rel',
        column1='competitor_id', column2='lead_id',
        string='Opportunities', copy=False)
    opportunity_count = fields.Integer(compute='_compute_opportunity_count')
    result_ids = fields.One2many(
        'ydod.crm.competitor.result', 'competitor_id', string='Win/Loss History')
    won_count = fields.Integer(compute='_compute_result_counts')
    lost_count = fields.Integer(compute='_compute_result_counts')
    win_rate = fields.Float(
        string='Win Rate (%)', compute='_compute_result_counts', aggregator=None)

    def _compute_opportunity_count(self):
        for competitor in self:
            competitor.opportunity_count = len(competitor.opportunity_ids)

    def _compute_result_counts(self):
        for competitor in self:
            won = len(competitor.result_ids.filtered(lambda res: res.result == 'won'))
            lost = len(competitor.result_ids.filtered(lambda res: res.result == 'lost'))
            competitor.won_count = won
            competitor.lost_count = lost
            total = won + lost
            competitor.win_rate = (won / total) if total else 0.0

    def action_view_opportunities(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('crm.crm_lead_opportunities')
        action['domain'] = [('competitor_ids', 'in', self.id)]
        action['context'] = {'default_competitor_ids': [self.id]}
        return action
