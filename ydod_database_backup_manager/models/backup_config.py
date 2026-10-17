# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import ftplib
import logging
import os
import shutil
import tempfile
import time
import traceback

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


def _dump_database(db_name, output_stream, backup_format='zip'):
    try:
        from odoo.service.db import dump_db
        dump_db(db_name, output_stream, backup_format=backup_format)
    except ImportError:
        from odoo.modules.db import dump
        dump(db_name, output_stream, backup_format=backup_format)


class YdodBackupConfig(models.Model):
    _name = 'ydod.backup.config'
    _description = 'Backup Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True)
    db_name = fields.Char(string='Database Name', required=True, default=lambda self: self.env.cr.dbname)
    backup_format = fields.Selection(
        selection=[
            ('zip', 'Zip (includes filestore)'),
            ('dump', 'SQL Dump (pg_dump)'),
        ],
        string='Backup Format',
        required=True,
        default='zip',
    )
    destination_type = fields.Selection(
        selection=[
            ('local', 'Local / Network Mount'),
            ('ftp', 'Remote FTP Server'),
        ],
        string='Destination Type',
        required=True,
        default='local',
    )
    local_path = fields.Char(string='Local / Mount Path', default='/var/odoo/backups')
    ftp_host = fields.Char(string='FTP Host')
    ftp_port = fields.Integer(string='FTP Port', default=21)
    ftp_user = fields.Char(string='FTP User')
    ftp_password = fields.Char(string='FTP Password')
    ftp_path = fields.Char(string='FTP Remote Path', default='/')
    retention_days = fields.Integer(
        string='Retention (Days)',
        default=7,
        help="Days to keep backup files before removal (0 = keep indefinitely).",
    )
    notify_user_ids = fields.Many2many(
        'res.users',
        'ydod_backup_config_res_users_rel',
        'config_id',
        'user_id',
        string='Failure Notification Users',
    )
    log_ids = fields.One2many('ydod.backup.log', 'config_id', string='Execution Logs')

    log_count = fields.Integer(string='Log Count', compute='_compute_log_count')
    last_run_date = fields.Datetime(string='Last Run Date', compute='_compute_last_run', store=True)
    last_run_status = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('failed', 'Failed'),
        ],
        string='Last Run Status',
        compute='_compute_last_run',
        store=True,
    )

    _sql_constraints = [
        ('check_retention_days', 'CHECK(retention_days >= 0)', 'Retention days must be zero or positive.'),
        ('check_ftp_port', 'CHECK(ftp_port > 0 AND ftp_port <= 65535)', 'FTP port must be between 1 and 65535.'),
    ]

    @api.constrains('destination_type', 'local_path', 'ftp_host')
    def _check_destination_settings(self):
        for config in self:
            if config.destination_type == 'local' and not config.local_path:
                raise ValidationError(_("Local / Mount path is required for local destination."))
            if config.destination_type == 'ftp' and not config.ftp_host:
                raise ValidationError(_("FTP Host is required for FTP destination."))

    @api.depends('log_ids')
    def _compute_log_count(self):
        read_group_res = self.env['ydod.backup.log']._read_group(
            domain=[('config_id', 'in', self.ids)],
            fields=['config_id'],
            groupby=['config_id'],
        )
        log_counts = {item['config_id'][0]: item['config_id_count'] for item in read_group_res}
        for config in self:
            config.log_count = log_counts.get(config.id, 0)

    @api.depends('log_ids.run_date', 'log_ids.status')
    def _compute_last_run(self):
        for config in self:
            latest = config.log_ids.sorted(key=lambda l: (l.run_date or datetime.min, l._origin.id or 0), reverse=True)[:1]
            config.last_run_date = latest.run_date if latest else False
            config.last_run_status = latest.status if latest else False

    def action_view_logs(self):
        self.ensure_one()
        return {
            'name': _('Execution Logs: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'ydod.backup.log',
            'view_mode': 'tree,form',
            'domain': [('config_id', '=', self.id)],
            'context': {'default_config_id': self.id, 'default_db_name': self.db_name},
        }

    def action_backup_now(self):
        if not self.env.user.has_group('ydod_database_backup_manager.group_backup_manager'):
            raise AccessError(_("Only Backup Managers can trigger manual backups."))
        for config in self:
            config._execute_backup()
        if len(self) == 1:
            msg = (
                _("Backup completed successfully for '%s'.") % self.name
                if self.last_run_status == 'success'
                else _("Backup failed for '%s'. Check logs for details.") % self.name
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Backup Execution'),
                    'message': msg,
                    'type': 'success' if self.last_run_status == 'success' else 'danger',
                    'sticky': False,
                },
            }
        return True

    @api.model
    def cron_run_backups(self):
        configs = self.search([('active', '=', True)])
        _logger.info("Executing scheduled backups for %d configuration(s)...", len(configs))
        for config in configs:
            try:
                config._execute_backup()
            except Exception as e:
                _logger.exception("Unexpected error in cron for config '%s': %s", config.name, e)

    def _execute_backup(self):
        self.ensure_one()
        start_time = time.time()
        db_name = self.db_name or self.env.cr.dbname
        ext = 'zip' if self.backup_format == 'zip' else 'dump'
        filename = f"backup_{db_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        destination_summary, file_size_mb = '', 0.0

        try:
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as temp_file:
                temp_path = temp_file.name
            try:
                with open(temp_path, 'wb') as stream:
                    _dump_database(db_name, stream, backup_format=self.backup_format)
                file_size_mb = round(os.path.getsize(temp_path) / (1024.0 * 1024.0), 2)

                if self.destination_type == 'local':
                    dest_dir = os.path.abspath(self.local_path)
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(temp_path, os.path.join(dest_dir, filename))
                    destination_summary = dest_dir
                    if self.retention_days > 0:
                        self._cleanup_local_backups(dest_dir, db_name, ext, self.retention_days)
                elif self.destination_type == 'ftp':
                    destination_summary = f"ftp://{self.ftp_user or 'anonymous'}@{self.ftp_host}:{self.ftp_port or 21}{self.ftp_path or '/'}"
                    ftp = ftplib.FTP()
                    ftp.connect(self.ftp_host, self.ftp_port or 21, timeout=30)
                    ftp.login(self.ftp_user or '', self.ftp_password or '')
                    if self.ftp_path and self.ftp_path != '/':
                        ftp.cwd(self.ftp_path)
                    with open(temp_path, 'rb') as f:
                        ftp.storbinary(f'STOR {filename}', f)
                    if self.retention_days > 0:
                        self._cleanup_ftp_backups(ftp, db_name, ext, self.retention_days)
                    ftp.quit()
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

            duration = round(time.time() - start_time, 2)
            log = self.env['ydod.backup.log'].sudo().create({
                'config_id': self.id,
                'run_date': fields.Datetime.now(),
                'db_name': db_name,
                'destination_summary': destination_summary,
                'file_size': file_size_mb,
                'duration': duration,
                'status': 'success',
                'error_message': False,
            })
            self.message_post(
                body=_("Database backup completed for <b>%s</b> (%s MB, %s s, %s)") % (
                    db_name, file_size_mb, duration, destination_summary
                ),
                subtype_xmlid='mail.mt_note',
            )
            return log
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            error_trace = traceback.format_exc()
            _logger.warning("Backup execution failed for configuration '%s': %s", self.name, e)
            log = self.env['ydod.backup.log'].sudo().create({
                'config_id': self.id,
                'run_date': fields.Datetime.now(),
                'db_name': db_name,
                'destination_summary': destination_summary or (self.local_path if self.destination_type == 'local' else self.ftp_host),
                'file_size': file_size_mb,
                'duration': duration,
                'status': 'failed',
                'error_message': error_trace,
            })
            self.message_post(
                body=_("<b>Backup failed for %s!</b><br/><pre>%s</pre>") % (db_name, error_trace),
                subtype_xmlid='mail.mt_comment',
            )
            self._send_failure_notification(error_trace)
            return log

    def _cleanup_local_backups(self, folder_path, db_name, ext, retention_days):
        if retention_days <= 0 or not os.path.isdir(folder_path):
            return
        now, retention_seconds = time.time(), retention_days * 86400
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        prefix, suffix = f"backup_{db_name}_", f".{ext}"
        for fname in os.listdir(folder_path):
            if fname.startswith(prefix) and fname.endswith(suffix):
                fpath = os.path.join(folder_path, fname)
                try:
                    if os.path.isfile(fpath):
                        expired = (now - os.path.getmtime(fpath)) > retention_seconds
                        if not expired:
                            try:
                                expired = datetime.strptime(fname[len(prefix):-len(suffix)], '%Y%m%d_%H%M%S') < cutoff_date
                            except Exception:
                                pass
                        if expired:
                            os.remove(fpath)
                            _logger.info("Purged outdated local backup: %s", fpath)
                except Exception as e:
                    _logger.warning("Failed to remove old backup %s: %s", fpath, e)

    def _cleanup_ftp_backups(self, ftp, db_name, ext, retention_days):
        if retention_days <= 0:
            return
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        prefix, suffix = f"backup_{db_name}_", f".{ext}"
        try:
            for fname in ftp.nlst():
                bname = os.path.basename(fname)
                if bname.startswith(prefix) and bname.endswith(suffix):
                    expired = False
                    try:
                        mdtm = ftp.sendcmd(f'MDTM {bname}')
                        if mdtm.startswith('213'):
                            expired = datetime.strptime(mdtm[4:].strip()[:14], '%Y%m%d%H%M%S') < cutoff_date
                    except Exception:
                        pass
                    if not expired:
                        try:
                            expired = datetime.strptime(bname[len(prefix):-len(suffix)], '%Y%m%d_%H%M%S') < cutoff_date
                        except Exception:
                            pass
                    if expired:
                        ftp.delete(bname)
                        _logger.info("Purged outdated FTP backup: %s", bname)
        except Exception as err:
            _logger.warning("Error during FTP retention cleanup: %s", err)

    def _send_failure_notification(self, error_trace):
        self.ensure_one()
        emails = [u.email for u in self.notify_user_ids if u.email]
        if not emails:
            return
        email_to = ', '.join(emails)
        template = self.env.ref('ydod_database_backup_manager.email_template_backup_failure', raise_if_not_found=False)
        if template:
            try:
                template.with_context(error_message=error_trace, db_name=self.db_name).send_mail(
                    self.id, email_values={'email_to': email_to}, force_send=True
                )
                return
            except Exception as e:
                _logger.warning("Failed to send mail template: %s", e)
        self.env['mail.mail'].sudo().create({
            'subject': f"[BACKUP ALERT] Database Backup Failed: {self.name} ({self.db_name})",
            'body_html': f"<p>Database backup failed for <b>{self.name}</b> (Database: {self.db_name}).</p><pre>{error_trace}</pre>",
            'email_to': email_to,
        }).send()
