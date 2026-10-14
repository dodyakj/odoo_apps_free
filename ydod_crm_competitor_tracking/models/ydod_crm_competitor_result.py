from odoo import fields, models


class YdodCrmCompetitorResult(models.Model):
    _name = 'ydod.crm.competitor.result'
    _description = 'Competitor Win/Loss Snapshot'
    _order = 'close_date desc, id desc'

    competitor_id = fields.Many2one(
        'ydod.crm.competitor', string='Competitor', required=True, ondelete='cascade', index=True)
    lead_id = fields.Many2one(
        'crm.lead', string='Opportunity', required=True, ondelete='cascade', index=True)
    result = fields.Selection([('won', 'Won'), ('lost', 'Lost')], string='Result', required=True)
    stage_id = fields.Many2one('crm.stage', string='Stage Reached')
    close_date = fields.Datetime(string='Closed On', default=fields.Datetime.now)
    expected_revenue = fields.Monetary(string='Deal Value', currency_field='company_currency')
    company_currency = fields.Many2one('res.currency', string='Currency')
    team_id = fields.Many2one('crm.team', string='Sales Team')
    partner_id = fields.Many2one('res.partner', string='Customer')
    user_id = fields.Many2one('res.users', string='Salesperson')
