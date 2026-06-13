# -*- coding: utf-8 -*-
from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # OpenAI Settings
    chatbot_openai_enabled = fields.Boolean(
        string='Enable OpenAI Analysis',
        help='Enable OpenAI API integration for advanced text analysis')
    
    chatbot_openai_api_key = fields.Char(
        string='OpenAI API Key',
        help='Your OpenAI API key for authentication (stored securely as system parameter)')
    
    chatbot_openai_model = fields.Selection([
        ('gpt-3.5-turbo', 'GPT-3.5-Turbo'),
        ('gpt-4o-mini-2024-07-18', 'GPT-4o-Mini'),
        ('gpt-4-turbo', 'GPT-4-Turbo'),
        ('gpt-4', 'GPT-4'),
    ], string='OpenAI Model', default='gpt-4o-mini-2024-07-18',
       help='Select which OpenAI model to use for analysis')
    
    # Response Settings
    chatbot_default_message = fields.Text(
        string='Default Message',
        help='Message when no question pattern matches')
    
    chatbot_response_type = fields.Selection([
        ('default', 'Hiển thị form thông tin'),
        ('prompt', 'Yêu cầu nhập thông tin vào đoạn văn bản'),
        ('none', 'Không yêu cầu thông tin')
    ], string='Loại phản hồi khi không match', default='default',
       help='Cách xử lý khi không có mẫu phù hợp')
    
    chatbot_prompt_message = fields.Text(
        string='Prompt Message',
        help='Tin nhắn hướng dẫn khi chọ chế độ prompt')
    
    chatbot_end_message = fields.Text(
        string='End Message',
        help='Tin nhắn kết thúc cuộc hội thoại khi đã thu thập đủ thông tin')

    chatbot_missing_contact_message = fields.Text(
        string='Missing Contact Message',
        help='Tin nhắn yêu cầu bổ sung khi thiếu cả email và số điện thoại')

    # NLP Settings
    chatbot_language_model = fields.Selection([
        ('vi_core_news_lg', 'Vietnamese (Large)'),
        ('vi_core_news_md', 'Vietnamese (Medium)'),
        ('vi_core_news_sm', 'Vietnamese (Small)')
    ], string='Language Model', default='vi_core_news_lg',
       help='spaCy language model for question matching')
    
    chatbot_threshold = fields.Float(
        string='Similarity Threshold', default=0.8,
        help='Minimum similarity score required to match a pattern (between 0 and 1)')
    
    chatbot_zalo_oa_app_id = fields.Char('Zalo OA Api App ID',
                                            help="API App ID for Zalo OA integration",
                                            )
    chatbot_zalo_oa_secret_key = fields.Char('Zalo OA Api Secret Key',
                                            help="API Secret Key for Zalo OA integration",
                                            )
    chatbot_zalo_oa_api_token = fields.Text('Zalo OA Api Token',
                                            help="API Token for Zalo OA integration",
                                            )
    chatbot_zalo_oa_api_refresh_token = fields.Text('Zalo OA Api Refresh Token',
                                            help="API Refresh Token for Zalo OA integration",
                                            )

    # Widget contact buttons
    chatbot_widget_phone = fields.Char(string='Phone Number', help='Show phone button on widget if set (e.g. +84901234567)')
    chatbot_widget_zalo_link = fields.Char(string='Zalo Link', help='Show Zalo button on widget if set (e.g. https://zalo.me/xxx)')
    chatbot_widget_messenger_link = fields.Char(string='Messenger Link', help='Show Messenger button on widget if set (e.g. https://m.me/xxx)')
    # Get parameter values - Delegated to ChatbotConfig for centralized management
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        
        # Use centralized configuration management from chatbot.config
        config = self.env['chatbot.config']._sync_config_parameters()
        
        # Get additional parameters from system parameters for non-OpenAI settings
        ICPSudo = self.env['ir.config_parameter'].sudo()
        
        res.update(
            chatbot_openai_enabled=config.openai_enabled or False,
            chatbot_openai_api_key=config.openai_api_key or '',
            chatbot_openai_model=config.openai_model or 'gpt-3.5-turbo',
            chatbot_default_message=ICPSudo.get_param('isd_chatbot.default_message', default='Tôi không hiểu câu hỏi của bạn. Vui lòng đặt lại thông tin chi tiết hơn.'),
            chatbot_response_type=ICPSudo.get_param('isd_chatbot.response_type', default='default'),
            chatbot_prompt_message=ICPSudo.get_param('isd_chatbot.prompt_message', default='Vui lòng cung cấp thông tin của bạn (tên, email, số điện thoại, thời gian phù hợp để liên hệ):'),
            chatbot_end_message=ICPSudo.get_param('isd_chatbot.end_message', default='Cảm ơn! Thông tin của bạn đã được ghi nhận. Chúng tôi sẽ liên hệ với bạn sớm nhất có thể. Cuộc hội thoại đã kết thúc.'),
            chatbot_missing_contact_message=ICPSudo.get_param('isd_chatbot.missing_contact_message', default='Hãy bổ sung email hoặc số điện thoại để chúng tôi có thể liên hệ với bạn.'),
            chatbot_language_model=ICPSudo.get_param('isd_chatbot.language_model', default='vi_core_news_lg'),
            chatbot_threshold=float(ICPSudo.get_param('isd_chatbot.threshold', default=0.8)),
            chatbot_zalo_oa_app_id=ICPSudo.get_param('isd_chatbot.zalo_oa_app_id', default=''),
            chatbot_zalo_oa_secret_key=ICPSudo.get_param('isd_chatbot.zalo_oa_api_secret_key', default=''),
            chatbot_zalo_oa_api_token=ICPSudo.get_param('isd_chatbot.zalo_oa_api_token', default=''),
            chatbot_zalo_oa_api_refresh_token=ICPSudo.get_param('isd_chatbot.zalo_oa_api_refresh_token', default=''),
            chatbot_widget_phone=ICPSudo.get_param('isd_chatbot.widget_phone', default=''),
            chatbot_widget_zalo_link=ICPSudo.get_param('isd_chatbot.widget_zalo_link', default=''),
            chatbot_widget_messenger_link=ICPSudo.get_param('isd_chatbot.widget_messenger_link', default=''),
        )
        return res
    
    # Set parameter values - Delegated to ChatbotConfig for centralized management
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        
        # Set parameters through system parameters (same as before, but documented)
        # This maintains compatibility while delegating actual configuration logic
        ICPSudo.set_param('isd_chatbot.openai_enabled', self.chatbot_openai_enabled)
        ICPSudo.set_param('isd_chatbot.openai_api_key', self.chatbot_openai_api_key or '')
        ICPSudo.set_param('isd_chatbot.openai_model', self.chatbot_openai_model)
        ICPSudo.set_param('isd_chatbot.default_message', self.chatbot_default_message or '')
        ICPSudo.set_param('isd_chatbot.response_type', self.chatbot_response_type)
        ICPSudo.set_param('isd_chatbot.prompt_message', self.chatbot_prompt_message or '')
        ICPSudo.set_param('isd_chatbot.end_message', self.chatbot_end_message or '')
        ICPSudo.set_param('isd_chatbot.missing_contact_message', self.chatbot_missing_contact_message or '')
        ICPSudo.set_param('isd_chatbot.language_model', self.chatbot_language_model)
        ICPSudo.set_param('isd_chatbot.threshold', str(self.chatbot_threshold))
        ICPSudo.set_param('isd_chatbot.zalo_oa_app_id', self.chatbot_zalo_oa_app_id or '')
        ICPSudo.set_param('isd_chatbot.zalo_oa_api_secret_key', self.chatbot_zalo_oa_secret_key or '')
        ICPSudo.set_param('isd_chatbot.zalo_oa_api_token', self.chatbot_zalo_oa_api_token or '')
        ICPSudo.set_param('isd_chatbot.zalo_oa_api_refresh_token', self.chatbot_zalo_oa_api_refresh_token or '')
        ICPSudo.set_param('isd_chatbot.widget_phone', self.chatbot_widget_phone or '')
        ICPSudo.set_param('isd_chatbot.widget_zalo_link', self.chatbot_widget_zalo_link or '')
        ICPSudo.set_param('isd_chatbot.widget_messenger_link', self.chatbot_widget_messenger_link or '')
        
        # Trigger configuration sync to ensure consistency
        self.env['chatbot.config']._sync_config_parameters()
