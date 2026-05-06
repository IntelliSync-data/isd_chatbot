import json
import logging
from typing import Any, Dict, Optional, Tuple
import uuid
import requests
from urllib3 import Retry
from requests.adapters import HTTPAdapter
import odoo

from ..services.dtos.chat_response_dto import ChatResponseDTO
from odoo import SUPERUSER_ID, api, fields
from odoo.tools.config import config

_logger = logging.getLogger(__name__)


class ChatbotService:
    def __init__(self, env: Any = None):
        self._env = env

    def chat(self, message: str, session_id: str, **kwargs) -> ChatResponseDTO:
        # Save user message
        env = self._env
        conversation = self._get_or_create_conversation(
            session_id, **kwargs)

        env['chatbot.message'].sudo().create([{
            'conversation_id': conversation.id,
            'message_type': 'user',
            'content': message,
        }])

        # First, always try to extract user information from the message
        chatbot_config = env['chatbot.config'].sudo()

        customer_inquiry_created = False
        conversation_ended = False

        try:
            # Extract user information from every message
            user_info = chatbot_config.parse_user_info(message)
            _logger.info(f"Extracted user info from message: {user_info}")

            # Check if we have user information
            has_name = user_info.get(
                'name') and user_info.get('name').strip() != ''
            has_email = user_info.get(
                'email') and user_info.get('email').strip() != ''
            has_phone = user_info.get(
                'phone') and user_info.get('phone').strip() != ''

            # Validate: Must have name AND (email OR phone)
            # If user provides name but missing BOTH email and phone, reject
            if has_name and not has_email and not has_phone:
                _logger.info(
                    "User provided name but missing both email and phone - requesting contact info")

                # Get the configured missing contact message
                missing_contact_msg = chatbot_config._get_missing_contact_message()

                # Save bot response
                env['chatbot.message'].sudo().create([{
                    'conversation_id': conversation.id,
                    'message_type': 'bot',
                    'content': missing_contact_msg,
                }])

                return ChatResponseDTO(
                    message=missing_contact_msg,
                    response_type='prompt',  # Still show form to collect info
                    conversation_ended=False,
                    customer_inquiry_created=False
                )

            # If we have name AND at least email OR phone, save the inquiry
            if has_name and (has_email or has_phone):
                _logger.info(
                    "Complete user information detected - ending conversation")

                # Create customer inquiry with complete information
                inquiry_vals = {
                    'message': message,  # Store original message
                    'name': user_info['name'].strip(),
                    'email': user_info['email'].strip() if has_email else False,
                    'phone': user_info['phone'].strip() if has_phone else False,
                    'state': 'new',
                    'conversation_id': conversation.id,  # Link to conversation
                    'source_id': conversation.source_id.id if conversation.source_id else False  # Copy source from conversation
                }

                # Handle consultation datetime if extracted
                if user_info.get('datetime'):
                    try:
                        from datetime import datetime
                        import pytz
                        # Parse the extracted datetime string
                        dt = datetime.fromisoformat(user_info['datetime'])
                        # Assume Vietnam timezone for extracted datetime
                        tz_vietnam = pytz.timezone('Asia/Ho_Chi_Minh')
                        dt_vietnam = tz_vietnam.localize(dt)
                        # Convert to UTC for storage
                        dt_utc = dt_vietnam.astimezone(pytz.UTC)
                        dt_naive = dt_utc.replace(tzinfo=None)
                        inquiry_vals['consultation_datetime'] = dt_naive
                        _logger.info(
                            f"Added consultation datetime: {dt_naive}")
                    except Exception as e:
                        _logger.warning(
                            f"Failed to parse extracted datetime: {e}")

                inquiry = env['customer.inquiry'].sudo().create(
                    [inquiry_vals])
                customer_inquiry_created = True

                # End the conversation
                conversation.sudo().write({
                    'customer_inquiry_id': inquiry.id,
                    'status': 'ended',
                    'end_time': fields.Datetime.now()
                })
                conversation_ended = True

                # Get the configured end message
                response = chatbot_config._get_end_message()
                response_type = 'none'
                matched_config = 'conversation_ended'
                similarity_score = 1.0

                _logger.info(
                    f"Conversation ended - created customer inquiry {inquiry.id}")

        except Exception as e:
            _logger.error(f"Error processing user info: {str(e)}")
            conversation_ended = False

        # If we didn't end the conversation, get normal chatbot response
        if not conversation_ended:
            response, response_type, matched_config, similarity_score = chatbot_config.get_chatbot_response(
                message)

        # Save bot response
        bot_message = env['chatbot.message'].sudo().create([{
            'conversation_id': conversation.id,
            'message_type': 'bot',
            'content': response,
            'response_type': response_type,
            'matched_config': matched_config,
            'similarity_score': similarity_score,
        }])

        # self._cleanup()

        return ChatResponseDTO(
            bot_message=bot_message,
            session_id=conversation.session_id,
            customer_inquiry_created=customer_inquiry_created,
            conversation_ended=conversation_ended
        )

    def _get_or_create_conversation(self, session_id, **kwargs):
        env = self._env
        conversation = env['chatbot.conversation'].sudo().search(
            [('session_id', '=', session_id), ('status', '=', 'active')], limit=1)
        if not conversation:
            new_session_id = str(session_id or uuid.uuid4())

            # Get source_id from source_code if provided
            source_id = False
            if kwargs.get('source_code'):
                source = env['inquiry.source'].sudo().search([('code', '=', kwargs['source_code'])], limit=1)
                if source:
                    source_id = source.id

            conversation = env['chatbot.conversation'].sudo().create([{
                'session_id': new_session_id,
                'user_ip': kwargs.get('user_ip'),
                'user_agent': kwargs.get('user_agent'),
                'source_id': source_id,  # Set source from parameter
                'status': 'active'
            }])
        return conversation


class ZaloChatbotServiceAdapter(ChatbotService):
    _base_api = "https://openapi.zalo.me/v3.0/oa"

    def __init__(self, env: Any = None):
        super().__init__(env=env)
        # Any Zalo-specific initialization can go here

    def _get_or_create_conversation(self, session_id, **kwargs):
        """Override to automatically set source to 'zalo' for Zalo conversations"""
        # Force source_code to 'zalo' for all Zalo conversations
        kwargs['source_code'] = 'zalo'
        return super()._get_or_create_conversation(session_id, **kwargs)

    def _get_session_request(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_access_token(self) -> str:
        chatbot_config = self._env['chatbot.config'].sudo()
        return chatbot_config._get_zalo_oa_api_token() or ''

    def _get_refresh_token(self) -> str:
        chatbot_config = self._env['chatbot.config'].sudo()
        return chatbot_config._get_zalo_oa_api_refresh_token() or ''

    def _get_secret_key(self) -> str:
        chatbot_config = self._env['chatbot.config'].sudo()
        return chatbot_config._get_zalo_oa_api_secret_key() or ''

    def _get_app_id(self) -> str:
        chatbot_config = self._env['chatbot.config'].sudo()
        return chatbot_config._get_zalo_oa_app_id() or ''

    def chat(self, message: str, session_id: str, **kwargs) -> ChatResponseDTO:
        # You can add Zalo-specific pre-processing here if needed
        response_dto = super().chat(message, session_id, **kwargs)

        bot_message = response_dto.bot_message

        zalo_sender_id = kwargs.get('zalo_sender_id', "")
        msg = bot_message.content

        def _send_zalo_message(zalo_sender_id: str, msg: str, _access_token: str) -> Optional[Dict[str, Any]]:
            payload = json.dumps({
                "recipient": {
                    "user_id": zalo_sender_id
                },
                "message": {
                    "text": msg
                }
            })
            headers = {
                'Content-Type': 'application/json',
                'access_token': _access_token
            }

            # Create a session object
            s = self._get_session_request()
            # Make requests using the session
            res = s.post(f'{self._base_api}/message/cs',
                         headers=headers, data=payload)

            if res.status_code != 200:
                _logger.error(
                    f"Failed to send Zalo message: {res.status_code} - {res.text}")
            else:
                return res.json()

        res_data = _send_zalo_message(zalo_sender_id, msg, self._get_access_token())
        if res_data is not None and res_data.get('error') == -216:
            _logger.info("Zalo access token expired, refreshing token...")
            n_access_token, n_refresh_token = self._refresh_token()
            _send_zalo_message(zalo_sender_id, msg, n_access_token)

        return response_dto

    def _refresh_token(self) -> Tuple[str, str]:
        url = "https://oauth.zaloapp.com/v4/oa/access_token"

        payload = 'app_id={}&grant_type=refresh_token&refresh_token={}'.format(
            self._get_app_id(), self._get_refresh_token())
        headers = {
            'secret_key': self._get_secret_key(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        s = self._get_session_request()
        res = s.post(url, headers=headers, data=payload)

        res_data = res.json()
        n_refresh_token = res_data.get('refresh_token', '')
        n_access_token = res_data.get('access_token', '')

        chatbot_config = self._env['chatbot.config'].sudo()
        chatbot_config._set_zalo_oa_api_tokens(
            n_access_token, n_refresh_token)

        return n_access_token, n_refresh_token


class ChatbotServiceFactory:
    @staticmethod
    def get_service(provider: str = "default", env: Any = None) -> ChatbotService:
        if provider == 'zalo':
            return ZaloChatbotServiceAdapter(env=env)

        return ChatbotService(env=env)
