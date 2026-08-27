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
            'external_message_id': kwargs.get('external_message_id') or False,
        }])

        chatbot_config = env['chatbot.config'].sudo()

        customer_inquiry_created = False
        conversation_ended = False

        # Step 1: Check if message contains concrete contact info (email or phone)
        import re
        has_email_raw = bool(re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', message))
        has_phone_raw = bool(re.search(r'\b(\d{10}|\d{11}|\d{3}[-\s.]\d{3}[-\s.]\d{4}|\d{4}[-\s.]\d{3}[-\s.]\d{3})\b', message))

        # Step 2: Only try user info extraction if message has email or phone
        if has_email_raw or has_phone_raw:
            try:
                user_info = chatbot_config.parse_user_info(message)
                _logger.info(f"Extracted user info from message: {user_info}")

                has_name = user_info.get('name') and user_info.get('name').strip() != ''
                has_email = user_info.get('email') and user_info.get('email').strip() != ''
                has_phone = user_info.get('phone') and user_info.get('phone').strip() != ''

                if has_name and not has_email and not has_phone:
                    missing_contact_msg = chatbot_config._get_missing_contact_message()
                    bot_missing = env['chatbot.message'].sudo().create([{
                        'conversation_id': conversation.id,
                        'message_type': 'bot',
                        'content': missing_contact_msg,
                        'response_type': 'prompt',
                    }])
                    return ChatResponseDTO(
                        bot_message=bot_missing,
                        session_id=conversation.session_id,
                        customer_inquiry_created=False,
                        conversation_ended=False,
                    )

                if has_name and (has_email or has_phone):
                    _logger.info("Complete user information detected - ending conversation")
                    inquiry_vals = {
                        'message': message,
                        'name': user_info['name'].strip(),
                        'email': user_info['email'].strip() if has_email else False,
                        'phone': user_info['phone'].strip() if has_phone else False,
                        'state': 'new',
                        'conversation_id': conversation.id,
                        'source_id': conversation.source_id.id if conversation.source_id else False,
                    }

                    if user_info.get('datetime'):
                        try:
                            from datetime import datetime
                            import pytz
                            dt = datetime.fromisoformat(user_info['datetime'])
                            tz_vietnam = pytz.timezone('Asia/Ho_Chi_Minh')
                            dt_vietnam = tz_vietnam.localize(dt)
                            dt_utc = dt_vietnam.astimezone(pytz.UTC)
                            dt_naive = dt_utc.replace(tzinfo=None)
                            inquiry_vals['consultation_datetime'] = dt_naive
                        except Exception as e:
                            _logger.warning(f"Failed to parse extracted datetime: {e}")

                    inquiry = env['customer.inquiry'].sudo().create([inquiry_vals])
                    customer_inquiry_created = True

                    conversation.sudo().write({
                        'customer_inquiry_id': inquiry.id,
                        'status': 'ended',
                        'end_time': fields.Datetime.now()
                    })
                    conversation_ended = True

                    response = chatbot_config._get_end_message()
                    response_type = 'none'
                    matched_config = 'conversation_ended'
                    similarity_score = 1.0

                    _logger.info(f"Conversation ended - created customer inquiry {inquiry.id}")

            except Exception as e:
                _logger.error(f"Error processing user info: {str(e)}")
                conversation_ended = False

        # Step 3: If no contact info found or extraction didn't end conversation, do Q&A
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


class FacebookChatbotServiceAdapter(ChatbotService):
    _graph_version = "v21.0"

    def _facebook_session_id(self, session_id, **kwargs):
        sender = kwargs.get('facebook_sender_id') or session_id or ''
        sender = str(sender)
        if sender.startswith('facebook:'):
            return sender
        return 'facebook:%s' % sender if sender else session_id

    def _get_or_create_conversation(self, session_id, **kwargs):
        kwargs['source_code'] = 'facebook'
        return super()._get_or_create_conversation(
            self._facebook_session_id(session_id, **kwargs), **kwargs)

    def chat(self, message: str, session_id: str, **kwargs) -> ChatResponseDTO:
        env = self._env
        mid = kwargs.get('external_message_id')
        if mid:
            existing = env['chatbot.message'].sudo().search(
                [('external_message_id', '=', mid)], limit=1)
            if existing:
                conversation = existing.conversation_id
                last_bot = env['chatbot.message'].sudo().search([
                    ('conversation_id', '=', conversation.id),
                    ('message_type', '=', 'bot'),
                ], order='id desc', limit=1)
                return ChatResponseDTO(
                    bot_message=last_bot or existing,
                    session_id=conversation.session_id,
                    customer_inquiry_created=False,
                    conversation_ended=conversation.status == 'ended',
                )

        response_dto = super().chat(message, session_id, **kwargs)
        sender_id = kwargs.get('facebook_sender_id') or ''
        bot_message = response_dto.bot_message
        text = bot_message.content if bot_message else ''
        self.last_send_status = None
        if sender_id and text:
            self.last_send_status = self.send_reply(sender_id, text)
            if self.last_send_status:
                _logger.warning("Facebook outbound send status: %s", self.last_send_status)
        return response_dto

    def _get_session_request(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _graph_messages_url(self):
        return "https://graph.facebook.com/%s/me/messages" % self._graph_version

    def _send_facebook_message(self, sender_id: str, text: str, token: str = None) -> Optional[str]:
        chatbot_config = self._env['chatbot.config'].sudo()
        access_token = token or chatbot_config._get_facebook_page_access_token() or ''
        if not access_token:
            _logger.error("Facebook send skipped: missing page access token")
            return 'unconfigured'
        payload = json.dumps({
            "recipient": {"id": sender_id},
            "messaging_type": "RESPONSE",
            "message": {"text": text},
        })
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % access_token,
        }
        try:
            res = self._get_session_request().post(
                self._graph_messages_url(), headers=headers, data=payload, timeout=15)
        except Exception as exc:
            _logger.error("Failed to send Facebook message: %s", exc)
            return 'error'
        try:
            data = res.json()
        except ValueError:
            data = {}
        if res.status_code == 200 and not data.get('error'):
            return None
        err = data.get('error') or {}
        code = err.get('code')
        _logger.error(
            "Failed to send Facebook message: %s - %s", res.status_code, res.text)
        if code == 190:
            return 'expired'
        return 'error'

    def _refresh_page_token(self) -> str:
        chatbot_config = self._env['chatbot.config'].sudo()
        app_id = chatbot_config._get_facebook_app_id()
        app_secret = chatbot_config._get_facebook_app_secret()
        current = chatbot_config._get_facebook_page_access_token()
        if not (app_id and app_secret and current):
            return ''
        url = "https://graph.facebook.com/%s/oauth/access_token" % self._graph_version
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'fb_exchange_token': current,
        }
        try:
            res = self._get_session_request().get(url, params=params, timeout=15)
            data = res.json()
        except Exception as exc:
            _logger.error("Facebook token refresh failed: %s", exc)
            return ''
        new_token = data.get('access_token') or ''
        if new_token:
            chatbot_config._set_facebook_page_access_token(new_token)
        return new_token

    def send_reply(self, sender_id: str, text: str) -> Optional[str]:
        """Send text; on OAuth 190 refresh once and resend once. Returns error key or None."""
        status = self._send_facebook_message(sender_id, text)
        if status != 'expired':
            return status
        new_token = self._refresh_page_token()
        if not new_token:
            return 'expired'
        return self._send_facebook_message(sender_id, text, token=new_token)


class ChatbotServiceFactory:
    @staticmethod
    def get_service(provider: str = "default", env: Any = None) -> ChatbotService:
        if provider == 'zalo':
            return ZaloChatbotServiceAdapter(env=env)
        if provider == 'facebook':
            return FacebookChatbotServiceAdapter(env=env)

        return ChatbotService(env=env)
