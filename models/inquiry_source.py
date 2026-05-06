# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class InquirySource(models.Model):
    _name = 'inquiry.source'
    _description = 'Customer Inquiry Source'
    _order = 'sequence, name'

    name = fields.Char('Source Name', required=True, help='Display name of the inquiry source')
    code = fields.Selection([
        ('chatbot', 'Chatbot'),
        ('manual', 'Manual Entry'),
        ('zalo', 'Zalo'),
        ('facebook', 'Facebook'),
        ('website', 'Website'),
        ('phone_call', 'Phone Call'),
        ('email', 'Email'),
        ('other', 'Other'),
    ], string='Source Code', required=True, help='Technical identifier for the source')
    active = fields.Boolean('Active', default=True)
    sequence = fields.Integer('Sequence', default=10)
    description = fields.Text('Description')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Source code must be unique!')
    ]

    @api.model
    def _get_default_sources(self):
        """Create default sources if they don't exist"""
        default_sources = [
            {'name': 'Chatbot', 'code': 'chatbot', 'sequence': 1},
            {'name': 'Manual Entry', 'code': 'manual', 'sequence': 2},
            {'name': 'Zalo', 'code': 'zalo', 'sequence': 3},
        ]

        for source_data in default_sources:
            existing = self.search([('code', '=', source_data['code'])], limit=1)
            if not existing:
                self.create(source_data)
