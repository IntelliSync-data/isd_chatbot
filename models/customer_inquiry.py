# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class CustomerInquiry(models.Model):
    _name = 'customer.inquiry'
    _description = 'Customer Inquiry from Chatbot'
    _order = 'create_date desc'
    _rec_name = 'name'
    # Đã loại bỏ kế thừa mail.thread và mail.activity.mixin
    # _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Name', required=True)
    email = fields.Char('Email')
    phone = fields.Char('Phone')
    consultation_datetime = fields.Datetime('Consultation Date & Time')
    message = fields.Text('Message (Raw Input)', help='Original customer message - never modified')
    analyzed_message = fields.Text('Analyzed Message', help='Customer message after analysis')
    state = fields.Selection([
        ('new', 'New'),
        ('saved_to_crm', 'Saved to CRM'),
        ('booked', 'Booked'),
    ], string='Status', default='new', tracking=True)
    
    # Relations
    conversation_id = fields.Many2one('chatbot.conversation', string='Related Conversation', readonly=True)
    crm_lead_id = fields.Many2one('crm.lead', string='CRM Lead', readonly=True)
    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event', readonly=True)
    assigned_user_id = fields.Many2one('res.users', string='Assigned User')

    # Survey Integration
    survey_user_input_id = fields.Many2one('survey.user_input', string='Survey Response', readonly=True, help='Link to the created survey user input')
    student_id = fields.Many2one('op.student', string='Student', readonly=True, help='Link to the created student record in EduCat')
    
    # Computed fields
    conversation_session_id = fields.Char(related='conversation_id.session_id', string='Conversation Session', readonly=True)
    conversation_total_messages = fields.Integer(related='conversation_id.total_messages', string='Total Messages', readonly=True)
    crm_lead_name = fields.Char(related='crm_lead_id.name', string='Lead Name', readonly=True)
    calendar_event_name = fields.Char(related='calendar_event_id.name', string='Event Name', readonly=True)
    
    # Additional fields for message analysis
    analyzed = fields.Boolean('Analyzed', default=False, help="Whether the message has been analyzed")
    analysis_date = fields.Datetime('Analysis Date', readonly=True)
    analysis_log = fields.Text('Analysis Log', readonly=True)
    
    # Source tracking
    source_id = fields.Many2one('inquiry.source', string='Source', help="Source of the inquiry", ondelete='restrict')

    # Computed field for invite user button visibility
    can_invite_user = fields.Boolean('Can Invite User', compute='_compute_can_invite_user')
    invite_button_text = fields.Char('Invite Button Text', compute='_compute_invite_button_text')

    @api.constrains('email', 'phone')
    def _check_contact_info(self):
        """Ensure at least email or phone is provided"""
        for record in self:
            if not record.email and not record.phone:
                raise UserError(_("At least email or phone number must be provided."))

    def action_save_to_crm(self):
        """Save customer inquiry to CRM as a lead and create/update contact"""
        for record in self:
            if record.crm_lead_id:
                raise UserError(_("This inquiry has already been saved to CRM."))
            
            if not record.name or not record.email:
                raise UserError(_("Name and email are required to save to CRM."))
                
            # Tìm contact hiện có hoặc tạo mới
            partner = self.env['res.partner'].search([('email', '=', record.email)], limit=1)
            
            if not partner:
                # Tạo contact mới
                partner_vals = {
                    'name': record.name,
                    'email': record.email,
                    'phone': record.phone.replace(' ', '') if record.phone else False,
                    'comment': f"Created from chatbot inquiry on {record.create_date}",
                }
                partner = self.env['res.partner'].create(partner_vals)
                _logger.info(f"Created new partner {partner.id} for customer inquiry {record.id}")
            else:
                # Cập nhật contact nếu cần
                update_vals = {}
                if not partner.phone and record.phone:
                    update_vals['phone'] = record.phone.replace(' ', '') if record.phone else False
                if update_vals:
                    partner.write(update_vals)
                    _logger.info(f"Updated existing partner {partner.id} for customer inquiry {record.id}")
            
            # Tìm team mặc định (Sales)
            sales_team = self.env['crm.team'].search([('name', 'like', 'Sales')], limit=1)
            
            # Create CRM lead
            lead_vals = {
                'name': f"Chatbot Inquiry - {record.name}",
                'contact_name': record.name,
                'email_from': record.email,
                'phone': record.phone.replace(' ', '') if record.phone else False,
                'description': record.message or f"Customer inquiry from chatbot on {record.create_date}",
                'user_id': record.assigned_user_id.id if record.assigned_user_id else False,
                'team_id': sales_team.id if sales_team else False,  # Gán team Sales nếu tìm thấy
                'stage_id': self._get_default_crm_stage(),
                'partner_id': partner.id,  # Liên kết với contact
            }
            
            lead = self.env['crm.lead'].create(lead_vals)
            record.write({
                'crm_lead_id': lead.id,
                'state': 'saved_to_crm'
            })
            
            _logger.info(f"Created CRM lead {lead.id} for customer inquiry {record.id}")
            
            # Hiển thị thông báo thành công
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _(f"Created CRM lead and linked to {partner.name}"),
                    'type': 'success',
                    'sticky': False,
                }
            }
    
    def action_add_datetime(self):
        """Open wizard to add/edit consultation datetime"""
        return {
            'name': _('Set Consultation Date and Time'),
            'type': 'ir.actions.act_window',
            'res_model': 'customer.inquiry',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('isd_chatbot.view_customer_inquiry_datetime_form').id,
            'target': 'new',
        }
    
    def action_booking(self):
        """Create calendar booking with discuss meeting link and send confirmation emails"""
        for record in self:
            # Validate email before proceeding
            if not record.email:
                raise UserError(_("Email is required to create a booking."))
                
            # Ensure customer is saved to CRM first
            if not record.crm_lead_id:
                record.action_save_to_crm()
            
            if not record.consultation_datetime:
                raise UserError(_("Please set consultation date and time before booking."))
            
            if record.calendar_event_id:
                raise UserError(_("This inquiry has already been booked."))
            
            # Find or create partner
            partner = self.env['res.partner'].search([('email', '=', record.email)], limit=1)
            if not partner:
                partner_vals = {
                    'name': record.name,
                    'email': record.email,
                    'phone': record.phone.replace(' ', '') if record.phone else False,
                    'comment': f"Created from chatbot booking on {fields.Datetime.now()}",
                }
                partner = self.env['res.partner'].create(partner_vals)
                _logger.info(f"Created partner {partner.id} for booking")
            
            try:
                # Create calendar event with Odoo's built-in videocall
                event_vals = {
                    'name': f"Consultation - {record.name}",
                    'start': record.consultation_datetime,
                    'stop': fields.Datetime.from_string(record.consultation_datetime) + timedelta(hours=1),
                    'duration': 1,  # 1 hour by default
                    'partner_ids': [(4, partner.id)],  # Add customer as attendee
                    'user_id': record.assigned_user_id.id if record.assigned_user_id else self.env.user.id,
                    'description': f"Customer inquiry: {record.message}",
                }
                
                # Add assigned user as attendee
                if record.assigned_user_id:
                    event_vals['partner_ids'].append((4, record.assigned_user_id.partner_id.id))
                
                event = self.env['calendar.event'].create(event_vals)
                
                # Set videocall source to discuss and create videocall location
                event.write({'videocall_source': 'discuss'})
                event._set_discuss_videocall_location()
                _logger.info(f"Created event {event.id} with videocall location: {event.videocall_location}")
                
                # Link the event to the inquiry
                record.write({
                    'calendar_event_id': event.id,
                    'state': 'booked'
                })
                
                # Get the videocall URL from the created event
                videocall_url = None
                if event.videocall_location:
                    videocall_url = event.videocall_location
                
                # Send confirmation emails with meeting link
                record._send_booking_confirmation_emails(videocall_url)
                
                # Hiển thị thông báo thành công
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': _("Calendar event created with videocall link and invitation emails sent!"),
                        'type': 'success',
                        'sticky': False,
                    }
                }
                
            except Exception as e:
                _logger.error(f"Error creating meeting: {str(e)}")
                raise UserError(_("Failed to create meeting: %s") % str(e))
    
    def _send_booking_confirmation_emails(self, videocall_url=None):
        """Send booking confirmation emails to customer and assigned user"""
        self.ensure_one()
        # Lưu videocall_url vào mô tả event để email template có thể sử dụng
        if videocall_url and self.calendar_event_id:
            old_description = self.calendar_event_id.description or ''
            if "Join the videocall:" not in old_description and videocall_url not in old_description:
                new_description = f"{old_description}\n\nJoin the videocall: {videocall_url}"
                self.calendar_event_id.write({'description': new_description})
                _logger.info(f"Updated calendar event with videocall link: {videocall_url}")
        
        # Email to customer
        customer_template = self.env.ref('isd_chatbot.email_template_customer_booking_confirmation', raise_if_not_found=False)
        if customer_template:
            customer_template.send_mail(self.id, force_send=True)
            _logger.info(f"Sent booking confirmation email to customer {self.email}")
        
        # Email to assigned user
        if self.assigned_user_id:
            user_template = self.env.ref('isd_chatbot.email_template_user_booking_notification', raise_if_not_found=False)
            if user_template:
                user_template.send_mail(self.id, force_send=True)
                _logger.info(f"Sent booking notification to user {self.assigned_user_id.name}")
    
    def _get_default_crm_stage(self):
        """Get default CRM stage for new leads"""
        stage = self.env['crm.stage'].search([('is_won', '=', False)], limit=1)
        return stage.id if stage else False
    
    @api.model
    def create_from_chatbot(self, vals):
        """Create customer inquiry from chatbot data"""
        # Check for required fields
        if not vals.get('name') or not vals.get('email'):
            raise UserError(_('Name and email are required to create inquiry'))
            
        # Assign default user if not specified
        if not vals.get('assigned_user_id'):
            vals['assigned_user_id'] = self._get_default_assigned_user()

        # Ensure the original message is saved if provided
        if 'message' not in vals and vals.get('original_message'):
            vals['message'] = vals.get('original_message')
            _logger.info(f"Using original_message as message field: {vals['message']}")
            
        # Create the inquiry
        inquiry = self.create(vals)
        _logger.info(f"Created customer inquiry {inquiry.id} from chatbot with data: {vals}")
        
        return inquiry
    
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle manual inquiries and set default source"""
        for vals in vals_list:
            # Set default source if not provided
            if not vals.get('source_id'):
                # Try to get source from context or default to chatbot
                source_code = self.env.context.get('default_source_code', 'chatbot')
                source = self.env['inquiry.source'].search([('code', '=', source_code)], limit=1)
                if source:
                    vals['source_id'] = source.id

            # If source is manual, set proper defaults
            if vals.get('source_id'):
                source = self.env['inquiry.source'].browse(vals['source_id'])
                if source.code == 'manual':
                    if not vals.get('assigned_user_id'):
                        vals['assigned_user_id'] = self._get_default_assigned_user()
                    _logger.info(f"Creating manual inquiry with data: {vals}")

        return super().create(vals_list)
    
    def _get_default_assigned_user(self):
        """Get default assigned user for new inquiries"""
        # Simple round-robin assignment (can be enhanced)
        users = self.env['res.users'].search([
            ('active', '=', True),
            ('share', '=', False),  # Internal users only
        ])
        if users:
            # Get user with least assigned inquiries
            user_counts = {}
            for user in users:
                count = self.search_count([('assigned_user_id', '=', user.id), ('state', '!=', 'booked')])
                user_counts[user.id] = count
            
            min_user_id = min(user_counts, key=user_counts.get)
            return min_user_id
        
        return self.env.user.id
        
    def action_save(self):
        """Save consultation date and time from wizard"""
        self.ensure_one()
        # Đơn giản chỉ cần đóng dialog, dữ liệu đã được lưu tự động
        return {'type': 'ir.actions.act_window_close'}
    
    def action_analyze_message(self):
        """Analyze message using OpenAI to extract user information"""
        self.ensure_one()
        
        if not self.message:
            raise UserError(_("No message content to analyze!"))
            
        if self.analyzed:
            # Ask for confirmation if already analyzed
            return {
                'type': 'ir.actions.act_window',
                'name': _('Re-analyze message'),
                'res_model': 'customer.inquiry.analyze.confirm',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_inquiry_id': self.id},
            }
            
        return self._analyze_message()
    
    def _analyze_message(self):
        """Extract info from message using OpenAI API - Refactored to use service"""
        self.ensure_one()
        
        if not self.message:
            raise UserError(_("No message content to analyze!"))
        
        # Use the OpenAI service instead of direct API calls
        openai_service = self.env['chatbot.openai.service']
        
        # Check if OpenAI is available
        if not openai_service.is_openai_available():
            raise UserError(_("OpenAI service is not available or configured"))
        
        # Extract information using the service
        result = openai_service.extract_customer_info(self.message)
        
        # Always update the analysis log
        log_text = '\n'.join(result.get('log', []))
        
        try:
            if not result['success']:
                # Update log and raise error
                self.write({'analysis_log': log_text})
                raise UserError(_(result.get('error', 'Unknown error during analysis')))
            
            # Process successful result
            extracted_data = result.get('data', {})
            updates = {}
            
            # Convert datetime objects to string for JSON serialization
            serializable_data = self._make_json_serializable(extracted_data)
            
            # Save extracted info to analyzed_message field for reference
            updates['analyzed_message'] = json.dumps(serializable_data, indent=2, ensure_ascii=False)
            
            # Update fields with extracted information (only if present)
            if extracted_data.get('name'):
                updates['name'] = extracted_data['name']

            if extracted_data.get('email'):
                updates['email'] = extracted_data['email']

            if extracted_data.get('phone'):
                updates['phone'] = extracted_data['phone']

            if extracted_data.get('datetime'):
                updates['consultation_datetime'] = extracted_data['datetime']

            # Mark as analyzed with metadata
            updates['analyzed'] = True
            updates['analysis_date'] = fields.Datetime.now()
            updates['analysis_log'] = log_text
            
            self.write(updates)
            return True
            
        except Exception:
            # Ensure log is always saved, even on error
            self.write({'analysis_log': log_text})
            raise
    
    def action_invite_user(self):
        """Invite user to the system or resend invitation, and optionally create survey + student"""
        self.ensure_one()

        if not self.email:
            raise UserError(_("Email is required to send invitation"))

        # Get existing user if any
        existing_user = self._get_user_by_email(self.email)

        if existing_user and not self._is_user_never_connected(existing_user):
            # User exists and has already connected
            raise UserError(_("User with email '%s' is already active in the system") % self.email)

        try:
            if existing_user and self._is_user_never_connected(existing_user):
                # User exists but never connected - resend invitation
                existing_user.with_context(create_user=True).action_reset_password()
                message = _("Invitation resent to %s") % self.email
            else:
                # No user exists - create new user and send invitation
                users = self.env['res.users'].web_create_users([self.email])
                message = _("Invitation sent to %s") % self.email

            # Create survey user input from first available mapping
            if not self.survey_user_input_id:
                # Get survey from any mapping (all mappings belong to same survey)
                mapping = self.env['survey.question.mapping'].sudo().search([], limit=1)
                if mapping and mapping.survey_id:
                    self._create_survey_user_input(mapping.survey_id)
                    message += _(", Survey response created")

            # Create or update student record if not already created
            if not self.student_id:
                self._create_or_update_student()
                message += _(", Student record created/updated")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("Failed to send invitation: %s") % str(e))
    
    def _create_survey_user_input(self, survey):
        """Create survey user input from inquiry data and apply field mappings"""
        self.ensure_one()

        if not survey:
            return

        # Find or create partner
        partner = self.env['res.partner'].sudo().search([('email', '=', self.email)], limit=1)
        if not partner:
            partner = self.env['res.partner'].sudo().create({
                'name': self.name,
                'email': self.email,
                'phone': self.phone,
            })

        # Create survey user input
        survey_vals = {
            'survey_id': survey.id,
            'partner_id': partner.id,
            'email': self.email,
            'state': 'new',
            'test_entry': False,
        }

        user_input = self.env['survey.user_input'].sudo().create(survey_vals)

        # Apply field mappings to pre-fill survey answers
        mappings = self.env['survey.question.mapping'].get_mappings_for_survey(survey.id)
        for inquiry_field, question in mappings.items():
            value = getattr(self, inquiry_field, None)
            if value:
                self._create_survey_answer(user_input, question, value)

        # Update inquiry with survey user input
        self.write({'survey_user_input_id': user_input.id})

        _logger.info(f"Created survey user input {user_input.id} for inquiry {self.id} with {len(mappings)} pre-filled answers")
        return user_input

    def _create_survey_answer(self, user_input, question, value):
        """Create a survey answer line for a given question and value"""
        answer_vals = {
            'user_input_id': user_input.id,
            'question_id': question.id,
            'answer_type': question.question_type,
            'skipped': False,
        }

        # Map value to appropriate field based on question type
        if question.question_type in ['char_box', 'text_box']:
            if question.question_type == 'char_box':
                answer_vals['value_char_box'] = str(value)
            else:
                answer_vals['value_text_box'] = str(value)
        elif question.question_type == 'numerical_box':
            try:
                answer_vals['value_numerical_box'] = float(value)
            except (ValueError, TypeError):
                _logger.warning(f"Cannot convert value '{value}' to number for question {question.id}")
                return
        elif question.question_type == 'date':
            answer_vals['value_date'] = value if isinstance(value, fields.Date) else str(value)
        elif question.question_type == 'datetime':
            answer_vals['value_datetime'] = value if isinstance(value, fields.Datetime) else str(value)

        self.env['survey.user_input.line'].sudo().create(answer_vals)
        _logger.info(f"Created answer for question '{question.title}' with value '{value}'")

    def _create_or_update_student(self):
        """Create or update student record in EduCat"""
        self.ensure_one()

        # Find or create partner for student
        partner = self.env['res.partner'].sudo().search([('email', '=', self.email)], limit=1)
        if not partner:
            partner = self.env['res.partner'].sudo().create({
                'name': self.name,
                'email': self.email,
                'phone': self.phone,
            })

        # Check if student already exists with this email
        student = self.env['op.student'].sudo().search([('email', '=', self.email)], limit=1)

        student_vals = {
            'partner_id': partner.id,
            'first_name': self.name,
            'email': self.email,
            'phone': self.phone,
        }

        # Add survey fields if available
        chatbot_config = self.env['chatbot.config'].sudo().search([], limit=1)
        if chatbot_config and chatbot_config.survey_id:
            student_vals['survey_id'] = chatbot_config.survey_id.id
        if self.survey_user_input_id:
            student_vals['survey_user_input_id'] = self.survey_user_input_id.id

        if student:
            # Update existing student
            student.sudo().write(student_vals)
            _logger.info(f"Updated existing student {student.id} for inquiry {self.id}")
        else:
            # Create new student
            student = self.env['op.student'].sudo().create(student_vals)
            _logger.info(f"Created new student {student.id} for inquiry {self.id}")

        # Link student to inquiry
        self.write({'student_id': student.id})
        return student

    @api.model
    def _can_invite_user(self, email):
        """Check if user can be invited (email exists and not registered or never connected)"""
        if not email:
            return False
            
        # Check if user already exists and is active (has logged in before)
        active_user = self.env['res.users'].search([
            ('email', '=', email),
            ('active', '=', True),
            ('login_date', '!=', False)  # User has logged in before
        ], limit=1)
        
        # Can invite if no active user found (either no user exists or user never connected)
        return not active_user
    
    @api.model
    def _get_user_by_email(self, email):
        """Get user by email if exists"""
        if not email:
            return False
        return self.env['res.users'].search([
            ('email', '=', email),
            ('active', '=', True)
        ], limit=1)
    
    @api.model
    def _is_user_never_connected(self, user):
        """Check if user has never connected (login_date is False)"""
        return user and not user.login_date
    
    @api.depends('email')
    def _compute_can_invite_user(self):
        """Compute if user can be invited based on email"""
        for record in self:
            record.can_invite_user = self._can_invite_user(record.email)
    
    @api.depends('email')
    def _compute_invite_button_text(self):
        """Compute button text based on user status"""
        for record in self:
            if not record.email:
                record.invite_button_text = "Invite User"
                continue
                
            user = self._get_user_by_email(record.email)
            if not user:
                # No user exists
                record.invite_button_text = "Invite User"
            elif self._is_user_never_connected(user):
                # User exists but never connected
                record.invite_button_text = "Resend Invite"
            else:
                # User exists and has connected
                record.invite_button_text = "Invite User"
    
    def _make_json_serializable(self, data):
        """Convert datetime objects to string for JSON serialization"""
        if isinstance(data, dict):
            return {key: self._make_json_serializable(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._make_json_serializable(item) for item in data]
        elif isinstance(data, datetime):
            return data.strftime('%Y-%m-%d %H:%M:%S')
        elif hasattr(data, 'strftime'):  # Handle other datetime-like objects
            return data.strftime('%Y-%m-%d %H:%M:%S')
        else:
            return data
