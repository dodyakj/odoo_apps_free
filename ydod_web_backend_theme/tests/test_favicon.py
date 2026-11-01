import base64

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tools import BinaryBytes

PNG_B64 = b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
PNG = base64.b64decode(PNG_B64)


@tagged('post_install', '-at_install')
class TestFavicon(HttpCase):

    def test_favicon_route(self):
        company = self.env['res.company'].create({'name': 'yDoD Favicon Company A', 'ydod_favicon': BinaryBytes(PNG)})
        self.assertEqual(company.ydod_favicon_mimetype, 'image/png')
        self.env['res.users'].create({
            'name': 'yDoD Favicon User',
            'login': 'ydod_favicon_user',
            'password': 'ydod_favicon_user_pwd',
            'company_id': company.id,
            'company_ids': [Command.set(company.ids)],
            'group_ids': [Command.set(self.env.ref('base.group_user').ids)],
        })

        anonymous = self.url_open('/ydod_web_backend_theme/favicon')
        self.assertNotEqual(anonymous.content, PNG)

        self.authenticate('ydod_favicon_user', 'ydod_favicon_user_pwd')
        response = self.url_open('/ydod_web_backend_theme/favicon')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG)
        self.assertEqual(response.headers.get('Content-Type'), 'image/png')
        self.assertTrue(response.headers.get('ETag'))

    def test_favicon_rejects_executable(self):
        company = self.env['res.company'].create({'name': 'yDoD Favicon Company B'})
        payload = BinaryBytes(b'MZ\x90\x00\x03\x00\x00\x00' + b'\x00' * 64)
        with self.assertRaises(ValidationError):
            company.write({'ydod_favicon': payload})
