from contextlib import contextmanager

import odoo
from odoo import SUPERUSER_ID, api
from odoo.tools.config import config

@contextmanager
def db_env_cursor():
    registry = odoo.registry(config["db_name"])
    cursor = registry.cursor()
    try:
        env = api.Environment(cursor, SUPERUSER_ID, {})
        yield env  # This is where the 'with' block runs
    finally:
        cursor.close()  # Always executed, even if an error occurs
