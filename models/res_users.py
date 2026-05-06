# -*- coding: utf-8 -*-

from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_chatbot_agent = fields.Boolean('Chatbot Agent', default=False,
                                    help="User can be assigned to handle chatbot inquiries")
    chatbot_inquiry_count = fields.Integer('Chatbot Inquiries', compute='_compute_chatbot_inquiry_count')

    def _compute_chatbot_inquiry_count(self):
        """Compute number of assigned chatbot inquiries"""
        for user in self:
            user.chatbot_inquiry_count = self.env['customer.inquiry'].search_count([
                ('assigned_user_id', '=', user.id),
                ('state', '!=', 'booked')
            ])

