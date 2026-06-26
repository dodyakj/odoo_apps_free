# -*- coding: utf-8 -*-
#################################################################################
# Author      : dodyakj
# Copyright(c): 2026 dodyakj
#
#
#
# yDoD REST API is provided free to use.
# Modify and redistribute at your own risk.
#################################################################################
{
  "name"                 :  "yDoD REST API",
  "summary"              :  """RESTful API untuk Odoo, memungkinkan akses dan modifikasi data melalui HTTP.""",
  "category"             :  "Extra Tools",
  "version"              :  "1.0.1",
  "author"               :  "dodyakj",
  "website"              :  "https://profile.dodyakj.online",
  "description"          :  """yDoD REST API
RESTful API untuk Odoo
Tambahkan, ubah, hapus, dan ambil data melalui endpoint REST
Dikembangkan oleh dodyakj""",
  "live_test_url"        :  "https://profile.dodyakj.online",
  "depends"              :  ['base'],
  "data"                 :  [
                             'security/ir.model.access.csv',
                             'views/rest_api_views.xml',
                             'views/templates.xml',
                             'views/res_user.xml',
                             'views/login_token.xml',
                            ],
  
  "demo"                 :  ['demo/demo.xml'],
  "images"               :  ['static/description/Banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "price"                :  0,
  "currency"             :  "USD",
  "external_dependencies":  {'python': ['Pyjwt']},
}
