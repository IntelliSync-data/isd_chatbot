from odoo import fields, models, api, _


class InquiryAssignWizard(models.TransientModel):
    _name = 'inquiry.assign.wizard'
    _description = 'Assign User to Inquiry'

    inquiry_id = fields.Many2one('customer.inquiry', required=True)
    assigned_user_id = fields.Many2one(
        'res.users', string='Assign To', required=True,
        default=lambda self: self.env.user,
    )
    next_action = fields.Char()

    def action_confirm(self):
        self.ensure_one()
        self.inquiry_id.assigned_user_id = self.assigned_user_id
        if self.next_action == 'save_to_crm':
            self.inquiry_id.action_save_to_crm()
        elif self.next_action == 'booking':
            self.inquiry_id.action_booking()
        return {'type': 'ir.actions.act_window_close'}
