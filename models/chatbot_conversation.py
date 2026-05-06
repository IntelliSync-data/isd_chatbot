from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ChatbotConversation(models.Model):
    _name = 'chatbot.conversation'
    _description = 'Chatbot Conversation History'
    _order = 'create_date desc'
    _rec_name = 'session_id'

    session_id = fields.Char('Session ID', required=True, help='Unique identifier for the conversation session')
    user_ip = fields.Char('User IP Address')
    user_agent = fields.Text('User Agent')
    start_time = fields.Datetime('Start Time', default=fields.Datetime.now)
    end_time = fields.Datetime('End Time')
    total_messages = fields.Integer('Total Messages', compute='_compute_total_messages', store=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('abandoned', 'Abandoned')
    ], string='Status', default='active')

    # Source mapping
    source_id = fields.Many2one('inquiry.source', string='Conversation Source', help='Source of this conversation (e.g., Zalo, Facebook, Website)')

    # Relations
    message_ids = fields.One2many('chatbot.message', 'conversation_id', string='Messages')
    customer_inquiry_id = fields.Many2one('customer.inquiry', string='Related Inquiry')
    
    @api.depends('message_ids')
    def _compute_total_messages(self):
        for record in self:
            record.total_messages = len(record.message_ids)
    
    def name_get(self):
        result = []
        for record in self:
            name = f"Session {record.session_id[:8]}... ({record.total_messages} messages)"
            result.append((record.id, name))
        return result


class ChatbotMessage(models.Model):
    _name = 'chatbot.message'
    _description = 'Chatbot Message'
    _order = 'create_date asc'
    _rec_name = 'message_preview'

    conversation_id = fields.Many2one('chatbot.conversation', string='Conversation', required=True, ondelete='cascade')
    discuss_channel_id = fields.Many2one('discuss.channel', string='Temporary Discuss Channel') # TEMPORARY
    message_type = fields.Selection([
        ('user', 'User Message'),
        ('bot', 'Bot Response')
    ], string='Message Type', required=True)
    content = fields.Text('Message Content', required=True)
    timestamp = fields.Datetime('Timestamp', default=fields.Datetime.now)
    response_type = fields.Char('Response Type', help='Type of bot response (form, none, etc.)')
    matched_config = fields.Char('Matched Config', help='Name of the config that matched this message')
    similarity_score = fields.Float('Similarity Score', help='Similarity score for matched pattern')
    
    message_preview = fields.Char('Preview', compute='_compute_message_preview', store=True)
    
    @api.depends('content', 'message_type')
    def _compute_message_preview(self):
        for record in self:
            prefix = "👤" if record.message_type == 'user' else "🤖"
            content = record.content or ""
            preview = content[:50] + "..." if len(content) > 50 else content
            record.message_preview = f"{prefix} {preview}"
