# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SurveyQuestionMapping(models.Model):
    _name = 'survey.question.mapping'
    _description = 'Survey Question Mapping for Customer Inquiry'
    _order = 'sequence, id'

    name = fields.Char('Name', compute='_compute_name', store=True)
    sequence = fields.Integer('Sequence', default=10)

    # Survey fields
    survey_id = fields.Many2one('survey.survey', string='Survey', required=True, ondelete='cascade')
    question_id = fields.Many2one('survey.question', string='Survey Question', required=True,
                                  domain="[('survey_id', '=', survey_id)]")

    # Inquiry field mapping
    inquiry_field = fields.Selection([
        ('name', 'Name'),
        ('email', 'Email'),
        ('phone', 'Phone'),
    ], string='Inquiry Field', required=True, help='Field from customer.inquiry to map')

    active = fields.Boolean('Active', default=True)

    @api.depends('inquiry_field', 'question_id')
    def _compute_name(self):
        for record in self:
            if record.inquiry_field and record.question_id:
                record.name = f"{dict(self._fields['inquiry_field'].selection).get(record.inquiry_field)} → {record.question_id.title}"
            else:
                record.name = 'New Mapping'

    @api.constrains('survey_id', 'inquiry_field')
    def _check_unique_mapping(self):
        """Ensure one inquiry field is only mapped to one question per survey"""
        for record in self:
            if record.survey_id and record.inquiry_field:
                existing = self.search([
                    ('survey_id', '=', record.survey_id.id),
                    ('inquiry_field', '=', record.inquiry_field),
                    ('id', '!=', record.id),
                    ('active', '=', True)
                ])
                if existing:
                    raise ValidationError(_(
                        f"The field '{dict(self._fields['inquiry_field'].selection).get(record.inquiry_field)}' "
                        f"is already mapped to question '{existing[0].question_id.title}' for this survey."
                    ))

    @api.model
    def get_mappings_for_survey(self, survey_id):
        """Get all active mappings for a survey"""
        mappings = self.search([
            ('survey_id', '=', survey_id),
            ('active', '=', True)
        ])
        return {m.inquiry_field: m.question_id for m in mappings}
