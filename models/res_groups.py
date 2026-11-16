# -*- coding: utf-8 -*-
from odoo import api, models

CATEGORY = 'base.module_category_services'
ROLES = ('group_chatbot_guest', 'group_chatbot_user', 'group_chatbot_editor',
         'group_chatbot_manager', 'group_chatbot_admin')


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.model
    def get_groups_by_application(self):
        """Show the chatbot roles as one dropdown.

        Odoo offers a dropdown only for a straight ladder of roles. User and
        Editor are separate branches that Manager combines, so Odoo would show
        checkboxes. It makes the same exception for Accounting, where Auditor
        and Invoicing sit side by side under Accountant.
        """
        res = super().get_groups_by_application()
        category = self.env.ref(CATEGORY, raise_if_not_found=False)
        roles = self.browse()
        for xmlid in ROLES:
            roles |= self.env.ref('isd_chatbot.%s' % xmlid, raise_if_not_found=False) or self.browse()
        out = []
        for app, kind, groups, category_name in res:
            # "Services" is shared: only while it holds exactly the chatbot roles,
            # so a group another module adds there never disappears into a dropdown
            if category and app == category and kind == 'boolean' and groups == roles:
                order = {g: len(g.trans_implied_ids & groups) for g in groups}
                ordered = groups.sorted(key=lambda g: (order[g], g.id))
                parent = app.parent_id
                name = (parent.sequence, parent.name) if parent else (100, 'Other')
                out.append((app, 'selection', ordered, name))
            else:
                out.append((app, kind, groups, category_name))
        return out
