from odoo import fields, models


class YdodBackupLog(models.Model):
    _name = 'ydod.backup.log'
    _description = 'Backup Execution Log'
    _order = 'run_date desc, id desc'
    _rec_name = 'db_name'

    config_id = fields.Many2one(
        'ydod.backup.config',
        string='Backup Configuration',
        required=True,
        ondelete='cascade',
        index=True,
    )
    run_date = fields.Datetime(
        string='Execution Date',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    db_name = fields.Char(string='Database Name', required=True)
    destination_summary = fields.Char(string='Destination Summary')
    file_size = fields.Float(string='File Size (MB)', digits=(16, 2))
    duration = fields.Float(string='Duration (Seconds)', digits=(16, 2))
    status = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('failed', 'Failed'),
        ],
        string='Status',
        required=True,
        default='success',
        index=True,
    )
    error_message = fields.Text(string='Error Details')

    _config_date_idx = models.Index("(config_id, run_date)")
