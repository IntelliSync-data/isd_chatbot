#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class CustomerInquiryAnalyzeConfirm(models.TransientModel):
    _name = 'customer.inquiry.analyze.confirm'
    _description = 'Confirm Analysis of Customer Inquiry Message'
    
    inquiry_id = fields.Many2one('customer.inquiry', string='Inquiry', required=True)
    name = fields.Char(related='inquiry_id.name')
    email = fields.Char(related='inquiry_id.email')
    phone = fields.Char(related='inquiry_id.phone')
    consultation_datetime = fields.Datetime(related='inquiry_id.consultation_datetime')
    message = fields.Text(related='inquiry_id.message')
    analysis_date = fields.Datetime(related='inquiry_id.analysis_date')
    
    def action_confirm(self):
        """Re-analyze the message even if it was already analyzed before"""
        self.ensure_one()
        return self.inquiry_id._analyze_message()
