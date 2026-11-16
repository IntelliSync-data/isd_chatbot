# -*- coding: utf-8 -*-
"""Make Editor sit beside User, on databases installed before 2026-09-14.

Back then Editor implied User. The change that made them separate branches
only added a link and never removed the old one, so on those databases every
Editor still saw the customer inquiries. This removes the old link and, for
people whose role is Editor (not Manager or above), the User rights it gave
them. A database installed after the change has no such link, and is left
alone: there a user ticked as both User and Editor chose to be.
"""
import logging

_logger = logging.getLogger(__name__)


def _group_id(cr, name):
    cr.execute("SELECT res_id FROM ir_model_data WHERE module = 'isd_chatbot' AND name = %s", (name,))
    row = cr.fetchone()
    return row and row[0]


def migrate(cr, version):
    editor = _group_id(cr, 'group_chatbot_editor')
    user = _group_id(cr, 'group_chatbot_user')
    manager = _group_id(cr, 'group_chatbot_manager')
    if not (editor and user and manager):
        return
    cr.execute("SELECT 1 FROM res_groups_implied_rel WHERE gid = %s AND hid = %s", (editor, user))
    if not cr.fetchone():
        return
    cr.execute("DELETE FROM res_groups_implied_rel WHERE gid = %s AND hid = %s", (editor, user))
    cr.execute("""
        DELETE FROM res_groups_users_rel r
         WHERE r.gid = %(user)s
           AND r.uid IN (SELECT uid FROM res_groups_users_rel WHERE gid = %(editor)s)
           AND r.uid NOT IN (SELECT uid FROM res_groups_users_rel WHERE gid = %(manager)s)
     RETURNING r.uid
    """, {'user': user, 'editor': editor, 'manager': manager})
    uids = [row[0] for row in cr.fetchall()]
    _logger.info("isd_chatbot: Editor no longer implies User; User rights removed from editors %s", uids)
