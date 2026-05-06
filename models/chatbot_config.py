# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
import re

_logger = logging.getLogger(__name__)

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    _logger.warning("spaCy not available. Please install spaCy: pip install spacy")


class ChatbotConfig(models.Model):
    _name = 'chatbot.config'
    _description = 'Chatbot Configuration'
    _order = 'sequence, id'

    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence', default=10)
    question = fields.Text('Question Pattern', required=True, help="Question pattern to match")
    answer = fields.Text('Answer', required=True, help="Answer to provide when pattern matches")
    active = fields.Boolean('Active', default=True)
    threshold = fields.Float('Similarity Threshold', default=0.8, 
                           help="Minimum similarity score (0.0 to 1.0) to trigger this response")
    
    # Configuration fields
    default_message = fields.Text('Default Message', 
                                default="Tôi không hiểu câu hỏi của bạn. Vui lòng để lại thông tin để được tư vấn.",
                                help="Message when no pattern matches")
    response_type = fields.Selection([
        ('form', 'Hiển thị form thông tin'),
        ('prompt', 'Yêu cầu nhập thông tin dạng văn bản'),
        ('none', 'Không yêu cầu thông tin')
    ], string='Loại phản hồi khi không match', default='form',
        help="Cách xử lý khi không tìm thấy câu trả lời phù hợp")
    prompt_message = fields.Text('Prompt Message',
                               default="Vui lòng cung cấp thông tin của bạn (tên, email, số điện thoại, thời gian phù hợp để liên hệ):",
                               help="Tin nhắn hướng dẫn khi sử dụng chế độ prompt")
    end_message = fields.Text('End Message',
                             default="Cảm ơn! Thông tin của bạn đã được ghi nhận. Chúng tôi sẽ liên hệ với bạn sớm nhất có thể. Cuộc hội thoại đã kết thúc.",
                             help="Tin nhắn kết thúc cuộc hội thoại khi đã thu thập đủ thông tin")
    missing_contact_message = fields.Text('Missing Contact Message',
                             default="Hãy bổ sung email hoặc số điện thoại để chúng tôi có thể liên hệ với bạn.",
                             help="Tin nhắn yêu cầu bổ sung khi thiếu cả email và số điện thoại")
    language_model = fields.Selection([
        ('en_core_web_sm', 'English Small'),
        ('en_core_web_md', 'English Medium'),
        ('vi_core_news_sm', 'Vietnamese Small'),
    ], string='Language Model', default='en_core_web_sm')
    
    # OpenAI API Configuration
    openai_api_key = fields.Char('OpenAI API Key', 
                                help="API key for OpenAI integration", 
                                config_parameter='isd_chatbot.openai_api_key')
    openai_model = fields.Selection([
        ('gpt-3.5-turbo', 'GPT-3.5-Turbo'),
        ('gpt-4', 'GPT-4'),
    ], string='OpenAI Model', default='gpt-3.5-turbo',
        help="OpenAI model to use for analysis",
        config_parameter='isd_chatbot.openai_model')
    openai_enabled = fields.Boolean('Enable OpenAI Analysis', 
                                   default=False,
                                   help="Enable OpenAI API for user info extraction",
                                   config_parameter='isd_chatbot.openai_enabled')

    zalo_oa_app_id = fields.Char('Zalo OA App ID',
                                help="API App ID for Zalo OA integration", 
                                config_parameter='isd_chatbot.zalo_oa_app_id')
    zalo_oa_api_secret_key = fields.Char('Zalo OA Api Secret Key',
                                help="API Secret Key for Zalo OA integration", 
                                config_parameter='isd_chatbot.zalo_oa_api_secret_key')
    zalo_oa_api_token = fields.Char('Zalo OA Api Token', 
                                help="API Token for Zalo OA integration", 
                                config_parameter='isd_chatbot.zalo_oa_api_token')

    zalo_oa_api_refresh_token = fields.Char('Zalo OA Api Refresh Token',
                                help="API Refresh Token for Zalo OA integration",
                                config_parameter='isd_chatbot.zalo_oa_api_refresh_token')

    # Survey Integration
    survey_id = fields.Many2one('survey.survey', string='Default Survey Template',
                               help='Survey template to use when inviting users from inquiries')

    @api.model
    def get_chatbot_response(self, user_message):
        """Get chatbot response for user message using spaCy similarity matching"""
        if not SPACY_AVAILABLE:
            return self._get_default_message(), self._get_response_type(), None, 0.0
        
        try:
            # Load spaCy model
            nlp = self._load_spacy_model()
            if not nlp:
                return self._get_default_message(), self._get_response_type(), None, 0.0
            
            user_doc = nlp(user_message.lower())
            best_match = None
            best_score = 0.0
            
            _logger.info(f"🔍 CHATBOT REQUEST: Processing user message: '{user_message}' (lowercased: '{user_message.lower()}')")
            
            # Find best matching question pattern
            configs = self.search([('active', '=', True)])
            _logger.info(f"📊 CHATBOT STATUS: Found {len(configs)} active configs to check")
            
            for config in configs:
                # Split question patterns by lines only (not by spaces)
                patterns = []
                for line in config.question.split('\n'):
                    line = line.strip()
                    if line:
                        patterns.append(line)
                
                _logger.info(f"🎯 CHATBOT CONFIG: '{config.name}' - patterns={patterns}")
                
                # Check similarity with each pattern
                max_similarity = 0.0
                for pattern in patterns:
                    pattern_doc = nlp(pattern.lower())
                    similarity = user_doc.similarity(pattern_doc)
                    max_similarity = max(max_similarity, similarity)
                    _logger.info(f"  📝 PATTERN MATCH: '{pattern}' → similarity={similarity:.3f}")
                
                _logger.info(f"🔄 THRESHOLD CHECK: '{config.name}' - max_similarity={max_similarity:.3f} vs threshold={config.threshold}")
                
                if max_similarity > best_score and max_similarity >= config.threshold:
                    best_score = max_similarity
                    best_match = config
                    _logger.info(f"✅ NEW BEST MATCH: '{config.name}' with score {max_similarity:.3f}")
            
            if best_match:
                _logger.info(f"🎉 CHATBOT SUCCESS: Matched '{best_match.name}' with similarity {best_score:.3f}")
                _logger.info(f"📤 CHATBOT RESPONSE: Returning answer from '{best_match.name}' config")
                return best_match.answer, 'none', best_match, best_score  # Match found, no need for additional input
            else:
                _logger.warning(f"❌ CHATBOT NO MATCH: No patterns matched for '{user_message}', returning default message")
                message, response_type = self._get_default_message(), self._get_response_type()
                
                # If in prompt mode, return the prompt message instead
                if response_type == 'prompt':
                    active_config = self.search([('active', '=', True)], limit=1)
                    if active_config and active_config.prompt_message:
                        message = active_config.prompt_message
                        _logger.info(f"📋 CHATBOT PROMPT: Using prompt message instead of default")
                
                _logger.info(f"📤 CHATBOT DEFAULT: Returning default response (type: {response_type})")
                return message, response_type, None, 0.0
                
        except Exception as e:
            _logger.error(f"Error in chatbot response: {str(e)}")
            return self._get_default_message(), self._get_response_type(), None, 0.0
        
    def _load_spacy_model(self):
        """Load spaCy model based on configuration"""
        try:
            # Ưu tiên lấy từ Default Settings
            default_config = self.search([('name', '=', 'Default Settings')], limit=1)
            if default_config and default_config.language_model:
                model_name = default_config.language_model
            else:
                # Fallback to any active config if Default Settings not found
                config = self.search([('active', '=', True)], limit=1)
                model_name = config.language_model if config else 'en_core_web_sm'
            
            _logger.info(f"Loading spaCy model: {model_name}")
            return spacy.load(model_name)
        except OSError:
            _logger.warning(f"spaCy model not found. Please install: python -m spacy download {model_name}")
            return None
        except Exception as e:
            _logger.error(f"Error loading spaCy model: {str(e)}")
            return None
    
    def _get_default_message(self):
        """Get default message when no match found"""
        # Đọc từ ir.config_parameter global settings
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        default_message = IrConfigParam.get_param('isd_chatbot.default_message')
        
        # Kiểm tra nếu có giá trị từ ir.config_parameter
        if default_message:
            return default_message
        
        # Fallback to Default Settings if param not found
        default_config = self.search([('name', '=', 'Default Settings')], limit=1)
        if default_config and default_config.default_message:
            return default_config.default_message
            
        # Fallback to any active config if Default Settings not found
        config = self.search([('active', '=', True)], limit=1)
        if config and config.default_message:
            return config.default_message
            
        return "Tôi không hiểu câu hỏi của bạn. Vui lòng để lại thông tin để được tư vấn."
    
    def _set_zalo_oa_api_tokens(self, api_token, refresh_token):
        """Set Zalo OA API Token and Refresh Token in configuration"""
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        IrConfigParam.set_param('isd_chatbot.zalo_oa_api_token', api_token)
        IrConfigParam.set_param('isd_chatbot.zalo_oa_api_refresh_token', refresh_token)
        _logger.info("Zalo OA API tokens updated in configuration")

    
    def _get_zalo_oa_api_token(self):
        """Get Zalo OA API Token from configuration"""
        # Đọc từ ir.config_parameter global settings
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        api_token = IrConfigParam.get_param('isd_chatbot.zalo_oa_api_token')
        
        # Kiểm tra nếu có giá trị từ ir.config_parameter
        if api_token:
            return api_token
        
        # Fallback to Default Settings if param not found
        default_config = self.search([('name', '=', 'Default Settings')], limit=1)
        if default_config and default_config.zalo_oa_api_token:
            return default_config.zalo_oa_api_token
            
        # Fallback to any active config if Default Settings not found
        config = self.search([('active', '=', True)], limit=1)
        if config and config.zalo_oa_api_token:
            return config.zalo_oa_api_token
            
        return ""
    
    def _get_zalo_oa_api_refresh_token(self):
        """Get Zalo OA API Token from configuration"""
        # Đọc từ ir.config_parameter global settings
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        refresh_token = IrConfigParam.get_param('isd_chatbot.zalo_oa_api_refresh_token')
        
        # Kiểm tra nếu có giá trị từ ir.config_parameter
        if refresh_token:
            return refresh_token
        
        # Fallback to Default Settings if param not found
        default_config = self.search([('name', '=', 'Default Settings')], limit=1)
        if default_config and default_config.zalo_oa_api_refresh_token:
            return default_config.zalo_oa_api_refresh_token

        # Fallback to any active config if Default Settings not found
        config = self.search([('active', '=', True)], limit=1)
        if config and config.zalo_oa_api_refresh_token:
            return config.zalo_oa_api_refresh_token

        return ""
    
    def _get_zalo_oa_api_secret_key(self):
        """Get Zalo OA API Secret Key from configuration"""
        # Đọc từ ir.config_parameter global settings
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        secret_key = IrConfigParam.get_param('isd_chatbot.zalo_oa_api_secret_key')
        
        # Kiểm tra nếu có giá trị từ ir.config_parameter
        if secret_key:
            return secret_key
        
        # Fallback to Default Settings if param not found
        default_config = self.search([('name', '=', 'Default Settings')], limit=1)
        if default_config and default_config.zalo_oa_api_secret_key:
            return default_config.zalo_oa_api_secret_key

        # Fallback to any active config if Default Settings not found
        config = self.search([('active', '=', True)], limit=1)
        if config and config.zalo_oa_api_secret_key:
            return config.zalo_oa_api_secret_key

        return ""
    
    def _get_zalo_oa_app_id(self):
        """Get Zalo OA API App ID from configuration"""
        # Đọc từ ir.config_parameter global settings
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        app_id = IrConfigParam.get_param('isd_chatbot.zalo_oa_app_id')

        # Kiểm tra nếu có giá trị từ ir.config_parameter
        if app_id:
            return app_id

        # Fallback to Default Settings if param not found
        default_config = self.search([('name', '=', 'Default Settings')], limit=1)
        if default_config and default_config.zalo_oa_app_id:
            return default_config.zalo_oa_app_id

        # Fallback to any active config if Default Settings not found
        config = self.search([('active', '=', True)], limit=1)
        if config and config.zalo_oa_app_id:
            return config.zalo_oa_app_id

        return ""
        
    def _get_response_type(self):
        """Get response type when no match found"""
        # Đọc từ ir.config_parameter global settings
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        response_type = IrConfigParam.get_param('isd_chatbot.response_type')
        
        # Kiểm tra nếu có giá trị hợp lệ từ ir.config_parameter
        if response_type in ['default', 'prompt', 'none']:
            return response_type
        
        # Fallback to Default Settings if param not found
        default_config = self.search([('name', '=', 'Default Settings')], limit=1)
        if default_config:
            return default_config.response_type
            
        # Fallback to any active config if Default Settings not found
        config = self.search([('active', '=', True)], limit=1)
        if config:
            return config.response_type
            
        return "default"  # Default to form if no config found
        
    def _get_end_message(self):
        """Get end message when conversation should end"""
        # Đọc từ ir.config_parameter global settings
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        end_message = IrConfigParam.get_param('isd_chatbot.end_message')

        # Kiểm tra nếu có giá trị từ ir.config_parameter
        if end_message:
            return end_message

        # Fallback to Default Settings if param not found
        default_config = self.search([('name', '=', 'Default Settings')], limit=1)
        if default_config and default_config.end_message:
            return default_config.end_message

        # Fallback to any active config if Default Settings not found
        config = self.search([('active', '=', True)], limit=1)
        if config and config.end_message:
            return config.end_message

        return "Cảm ơn! Thông tin của bạn đã được ghi nhận. Chúng tôi sẽ liên hệ với bạn sớm nhất có thể. Cuộc hội thoại đã kết thúc."

    def _get_missing_contact_message(self):
        """Get message when user provides name but missing both email and phone"""
        # Đọc từ ir.config_parameter global settings
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        missing_contact_message = IrConfigParam.get_param('isd_chatbot.missing_contact_message')

        # Kiểm tra nếu có giá trị từ ir.config_parameter
        if missing_contact_message:
            return missing_contact_message

        # Fallback to Default Settings if param not found
        default_config = self.search([('name', '=', 'Default Settings')], limit=1)
        if default_config and default_config.missing_contact_message:
            return default_config.missing_contact_message

        # Fallback to any active config if Default Settings not found
        config = self.search([('active', '=', True)], limit=1)
        if config and config.missing_contact_message:
            return config.missing_contact_message

        return "Hãy bổ sung email hoặc số điện thoại để chúng tôi có thể liên hệ với bạn."

    @api.model
    def open_global_settings(self):
        """Open the global settings form view"""
        # Find the Default Settings record or create one if it doesn't exist
        default_settings = self.search([('name', '=', 'Default Settings')], limit=1)
        if not default_settings:
            default_settings = self.create({
                'name': 'Default Settings',
                'question': 'default',
                'answer': 'Default response',
                'threshold': 0.8,
                'default_message': 'Tôi không hiểu câu hỏi của bạn. Vui lòng để lại thông tin liên hệ để được tư vấn cụ thể hơn.',
                'language_model': 'en_core_web_sm',
                'response_type': 'form',
                'prompt_message': 'Vui lòng cung cấp họ tên, email và số điện thoại của bạn để chúng tôi liên hệ hỗ trợ.',
                'end_message': 'Cảm ơn! Thông tin của bạn đã được ghi nhận. Chúng tôi sẽ liên hệ với bạn sớm nhất có thể. Cuộc hội thoại đã kết thúc.',
                'active': True,
            })
        
        # Return an action that opens the form view of the default settings record
        return {
            'name': _('Global Settings'),
            'view_mode': 'form',
            'res_model': 'chatbot.config',
            'res_id': default_settings.id,
            'type': 'ir.actions.act_window',
            'view_id': self.env.ref('isd_chatbot.view_chatbot_global_settings_form').id,
            'target': 'current',
        }
        
    def save_settings(self):
        """Save the global settings without closing the form"""
        # This method is triggered by the Save button in the global settings form
        # We don't need to do anything special here as Odoo will save the record automatically
        # Just return a notification to confirm changes were saved
        
        # Log the save operation
        _logger.info(f"Chatbot global settings saved: {self.name}")
        
        # Display a success notification without closing the form
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Settings Saved'),
                'message': _('Chatbot global settings have been updated successfully.'),
                'sticky': False,
                'type': 'success'
                # Removed the 'next' action to keep the form open
            }
        }
        
    @api.model
    def _sync_config_parameters(self):
        """Synchronize config parameters from ir.config_parameter to chatbot.config record"""
        # Find the default settings record
        settings = self.search([('name', '=', 'Default Settings')], limit=1)
        if not settings:
            # If not found, try to find any record
            settings = self.search([], limit=1)
            if not settings:
                # Create a new settings record if none exists
                settings = self.create({
                    'name': 'Default Settings',
                    'question': 'default',
                    'answer': 'Default response',
                    'threshold': 0.8,
                    'active': True,
                })
                _logger.info('Created new default chatbot settings record')
        
        # Get values from ir.config_parameter
        ICPSudo = self.env['ir.config_parameter'].sudo()
        openai_enabled = ICPSudo.get_param('isd_chatbot.openai_enabled', default=False)
        openai_api_key = ICPSudo.get_param('isd_chatbot.openai_api_key', default='')
        openai_model = ICPSudo.get_param('isd_chatbot.openai_model', default='gpt-3.5-turbo')
        zalo_oa_app_id = ICPSudo.get_param('isd_chatbot.zalo_oa_app_id', default='')
        zalo_oa_api_secret_key = ICPSudo.get_param('isd_chatbot.zalo_oa_api_secret_key', default='')
        zalo_oa_api_token = ICPSudo.get_param('isd_chatbot.zalo_oa_api_token', default='')
        zalo_oa_api_refresh_token = ICPSudo.get_param('isd_chatbot.zalo_oa_api_refresh_token', default='')
        
        # Update the settings record
        settings.write({
            'openai_enabled': openai_enabled == 'True' if isinstance(openai_enabled, str) else bool(openai_enabled),
            'openai_api_key': openai_api_key,
            'openai_model': openai_model,
            'zalo_oa_app_id': zalo_oa_app_id,
            'zalo_oa_api_token': zalo_oa_api_token,
            'zalo_oa_api_refresh_token': zalo_oa_api_refresh_token,
            'zalo_oa_api_secret_key': zalo_oa_api_secret_key,
        })
        
        _logger.info(f"Synchronized OpenAI settings: enabled={openai_enabled}, model={openai_model}")
        return settings
        
    @api.model
    def parse_user_info(self, message):
        """Parse user information from a message using regex patterns and NLP"""
        result = {
            'name': None,
            'email': None,
            'phone': None,
            'datetime': None,
            'missing_fields': []
        }
        
        if not SPACY_AVAILABLE:
            result['missing_fields'] = ['name', 'email']
            return result
        
        try:
            # Load spaCy model
            nlp = self._load_spacy_model()
            if not nlp:
                result['missing_fields'] = ['name', 'email']
                return result
                
            # Process message
            doc = nlp(message)
            
            # Log original message for debugging
            _logger.info(f"Parsing user info from message: {message}")
            _logger.info(f"Processing message: {doc}")
            
            # Extract email using regex pattern
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_matches = re.findall(email_pattern, message)
            if email_matches:
                result['email'] = email_matches[0]
                _logger.info(f"Extracted email: {result['email']}")
            
            # Extract phone numbers - improved pattern for Vietnamese numbers
            phone_pattern = r'\b(\d{10}|\d{11}|\d{3}[-\s.]\d{3}[-\s.]\d{4}|\d{4}[-\s.]\d{3}[-\s.]\d{3})\b'
            phone_matches = re.findall(phone_pattern, message)
            if phone_matches:
                # Clean up the phone number format
                phone = phone_matches[0]
                if isinstance(phone, tuple):  # If the regex group returns a tuple
                    phone = phone[0]
                # Remove common separators
                phone = re.sub(r'[-\s.]', '', phone)
                result['phone'] = phone
                _logger.info(f"Extracted phone: {result['phone']}")
            
            # Extract datetime - looking for Vietnamese date format and time
            # Pattern for dates like: 25/06/2025, 25-06-2025, 25.06.2025 with optional time like 22:00 or 22 giờ
            _logger.info(f"Original message for datetime extraction: '{message}'")
            
            date_patterns = [
                # Pattern for DD/MM/YYYY with giờ format - high priority
                r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[\s,]+(?:lúc|at)?\s*(\d{1,2})\s*(?:gi[oơờ]|h))',
                # Pattern for DD/MM/YYYY + optional time with hours and minutes
                r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[\s,]+(?:lúc|at)?\s*(\d{1,2})[:h](\d{2}))?',
                # Pattern for common Vietnamese words for dates with giờ format
                r'ngày\s+(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[\s,]+(?:lúc|at)?\s*(\d{1,2})\s*(?:gi[oơờ]|h))',
                # Pattern for common Vietnamese words for dates
                r'ngày\s+(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[\s,]+(?:lúc|at)?\s*(\d{1,2})[:h](\d{2}))?',
                # Pattern with book/đặt keywords with giờ format
                r'(?:book|đặt|đặt lịch)[\s:]+(?:ngày\s+)?(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[\s,]+(?:lúc|at)?\s*(\d{1,2})\s*(?:gi[oơờ]|h))',
                # Pattern with book/đặt keywords
                r'(?:book|đặt|đặt lịch)[\s:]+(?:ngày\s+)?(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[\s,]+(?:lúc|at)?\s*(\d{1,2})[:h](\d{2}))?'
            ]
            
            for pattern in date_patterns:
                datetime_matches = re.search(pattern, message, re.IGNORECASE)
                if datetime_matches:
                    day = int(datetime_matches.group(1))
                    month = int(datetime_matches.group(2))
                    year = int(datetime_matches.group(3))
                    
                    # Default to 9:00 if no time specified
                    hour = 9
                    minute = 0
                    
                    # Check if time hour is specified (group 4)
                    if datetime_matches.lastindex >= 4 and datetime_matches.group(4):
                        hour = int(datetime_matches.group(4))
                        
                        # Check if minutes are specified (group 5)
                        if datetime_matches.lastindex >= 5 and datetime_matches.group(5):
                            # Try to convert to int, default to 0 if fails
                            try:
                                minute_str = datetime_matches.group(5)
                                minute = int(minute_str) if minute_str else 0
                            except (ValueError, TypeError):
                                minute = 0
                    
                    # Import here to avoid circular dependencies
                    try:
                        # Create datetime string
                        dt_str = f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"
                        result['datetime'] = dt_str
                        _logger.info(f"Extracted datetime: {result['datetime']} from pattern: {pattern}")
                        _logger.info(f"Match groups: {[datetime_matches.group(i) for i in range(1, datetime_matches.lastindex+1) if datetime_matches.group(i)]}") 
                        break
                    except ValueError as e:
                        _logger.warning(f"Invalid date values: {e}")
            
            # Try to extract name - focus on the beginning of the message
            # This assumes name is usually at the beginning before other information
            name_candidates = []
            seen_tokens = set()
            
            # Trích xuất tên sử dụng NER của spaCy
            # Tìm entity PERSON trong document đã xử lý bởi spaCy
            names = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
            
            # Log các thực thể được nhận dạng
            for ent in doc.ents:
                _logger.info(f"Detected entity: '{ent.text}' with label '{ent.label_}'")
            
            if names:
                # Nếu tìm thấy thực thể PERSON, sử dụng nó
                result['name'] = names[0]  # Lấy tên đầu tiên được nhận dạng
                _logger.info(f"Found name via NER: '{result['name']}'")
            else:
                # Nếu không tìm thấy thực thể PERSON, sử dụng phương pháp dự phòng
                _logger.info("No PERSON entity found, using fallback name extraction method")
                
                # Clean message for name extraction by removing detected parts
                clean_message = message
                if result['email']:
                    clean_message = clean_message.replace(result['email'], '')
                if result['phone']:
                    clean_message = clean_message.replace(result['phone'], '')
                
                # Remove date/time text patterns
                for pattern in date_patterns:
                    clean_message = re.sub(pattern, '', clean_message, flags=re.IGNORECASE)
                    
                # Remove common keywords that shouldn't be in names
                keywords_to_remove = [
                    r'\b(sdt|sđt|phone|s\s*[oó]đi[eệ]n\s*tho[aạ]i)\b', 
                    r'\b(email|mail|g?mail)\b',
                    r'\b(book|booking|đ[aặ]́t(?:\s*l[iị]ch)?)\b', 
                    r'\b(ng[aà]y|date|th[oơờ]i\s*gian)\b',
                    r'\b(l[uú]c|at|v[aà]o)\b', 
                    r'\bgi[oơờ]\b',
                    r'\bt[eê]n\s*:?\s*\b',
                    r'\b[,;:\-]\b',
                    r'\s{2,}'  # Replace multiple spaces with one space
                ]
                
                for pattern in keywords_to_remove:
                    clean_message = re.sub(pattern, ' ', clean_message, flags=re.IGNORECASE)
                
                # Replace multiple spaces and trim
                clean_message = re.sub(r'\s+', ' ', clean_message).strip()
                
                _logger.info(f"Cleaned message for fallback name extraction: '{clean_message}'")
                
                # Process clean message to extract name using fallback method
                clean_doc = nlp(clean_message)
            
            # First look for proper nouns as name candidates
            for token in clean_doc:
                if token.pos_ in ['PROPN'] and len(token.text) > 1 and token.text not in seen_tokens:
                    name_candidates.append(token.text)
                    seen_tokens.add(token.text)
            
            # If no proper nouns found, try first 2-3 words that aren't helpers or special chars
            if not name_candidates:
                skip_pos = ['PUNCT', 'NUM', 'SYM', 'SPACE']
                for token in clean_doc[:10]:  # Look only at beginning of message
                    if token.pos_ not in skip_pos and len(token.text) > 1 and token.text not in seen_tokens:
                        name_candidates.append(token.text)
                        seen_tokens.add(token.text)
                        if len(name_candidates) >= 3:  # Collect up to 3 name parts
                            break
                    
            if name_candidates:
                result['name'] = ' '.join(name_candidates)
                _logger.info(f"Extracted name: {result['name']}")
            
            # Check for missing required fields
            if not result['name']:
                result['missing_fields'].append('name')
            if not result['email']:
                result['missing_fields'].append('email')
                
            return result
            
        except Exception as e:
            _logger.error(f"Error parsing user info: {str(e)}")
            result['missing_fields'] = ['name', 'email']
            return result
