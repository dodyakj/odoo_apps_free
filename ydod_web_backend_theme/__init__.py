from . import controllers
from . import models


def uninstall_hook(env):
    env['res.config.settings']._ydod_remove_theme()
