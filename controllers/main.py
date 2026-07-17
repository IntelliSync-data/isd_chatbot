# -*- coding: utf-8 -*-

import json
import logging
from ..services.chatbot_service import ChatbotService, ChatbotServiceFactory
from odoo import http, fields
from odoo.http import request
from concurrent.futures import ThreadPoolExecutor
import time

_logger = logging.getLogger(__name__)

# Dynamic base URL configuration - no more hard-coding


def get_base_url():
    """Get base URL from system parameters or request"""
    try:
        # Try to get from system parameters first
        base_url = request.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')
        if base_url:
            return base_url

        # Fallback to request base URL
        if hasattr(request, 'httprequest'):
            return request.httprequest.url_root.rstrip('/')

        # Final fallback (should not happen in normal operation)
        return 'https://e-hub.intellisyncdata.com'
    except:
        return 'https://e-hub.intellisyncdata.com'


class ChatbotController(http.Controller):

    def _cors_headers(self):
        """Return CORS headers based on allowed origins config"""
        ICPSudo = request.env['ir.config_parameter'].sudo()
        allowed = ICPSudo.get_param('isd_chatbot.cors_origins', default='')
        origin = request.httprequest.headers.get('Origin', '')
        allowed_list = [o.strip() for o in allowed.split(',') if o.strip()]
        if origin and origin in allowed_list:
            allow_origin = origin
        elif not allowed_list:
            allow_origin = '*'
        else:
            allow_origin = allowed_list[0]
        return [
            ('Access-Control-Allow-Origin', allow_origin),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type'),
        ]

    @http.route('/chatbot/widget.js', type='http', auth='public', website=True)
    def chatbot_widget_js(self, **kwargs):
        """Serve the chatbot JavaScript widget"""
        ICPSudo = request.env['ir.config_parameter'].sudo()
        phone = ICPSudo.get_param('isd_chatbot.widget_phone', default='')
        zalo_link = ICPSudo.get_param('isd_chatbot.widget_zalo_link', default='')
        messenger_link = ICPSudo.get_param('isd_chatbot.widget_messenger_link', default='')

        def icon_url(param_key):
            att_id = int(ICPSudo.get_param(param_key, default=0) or 0)
            return '%s/web/image/ir.attachment/%d/datas' % (get_base_url(), att_id) if att_id else ''

        icon_toggle = icon_url('isd_chatbot.icon_toggle_id')
        icon_chat = icon_url('isd_chatbot.icon_chat_id')
        icon_phone = icon_url('isd_chatbot.icon_phone_id')
        icon_zalo = icon_url('isd_chatbot.icon_zalo_id')
        icon_messenger = icon_url('isd_chatbot.icon_messenger_id')

        js_content = """
(function() {
    'use strict';

    // Chatbot configuration
    const CHATBOT_CONFIG = {
        apiUrl: '%s',
        phone: '%s',
        zaloLink: '%s',
        messengerLink: '%s',
        icons: {
            toggle: '%s',
            chat: '%s',
            phone: '%s',
            zalo: '%s',
            messenger: '%s',
        },
    };

    // ── Icons ──────────────────────────────────────────────────────────────────
    const FALLBACK_ICONS = {
        toggle: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
        close:  `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
        chat:      `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
        phone:     `<svg width="22" height="22" viewBox="0 0 24 24" fill="white"><path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1-9.4 0-17-7.6-17-17 0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1L6.6 10.8z"/></svg>`,
        zalo:      `<svg width="22" height="22" viewBox="0 0 50 50" fill="white"><text y="38" font-size="38" font-family="Arial" font-weight="bold">Z</text></svg>`,
        messenger: `<svg width="22" height="22" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.477 2 2 6.145 2 11.259c0 2.913 1.454 5.512 3.726 7.21V22l3.405-1.869c.909.252 1.871.388 2.869.388 5.523 0 10-4.145 10-9.259C22 6.145 17.523 2 12 2zm1.008 12.472l-2.548-2.717-4.976 2.717 5.474-5.808 2.61 2.717 4.913-2.717-5.473 5.808z"/></svg>`,
    };
    function icon(name, size) {
        const url = CHATBOT_CONFIG.icons[name];
        if (url) return `<img src="${url}" width="${size || 28}" height="${size || 28}" alt="${name}" style="display:block;"/>`;
        return FALLBACK_ICONS[name] || '';
    }

    // ── HTML ───────────────────────────────────────────────────────────────────
    function createChatbotHTML() {
        const contactBtns = [];
        if (CHATBOT_CONFIG.messengerLink) {
            contactBtns.push(`
                <a href="${CHATBOT_CONFIG.messengerLink}" target="_blank" class="cb-fab cb-fab-messenger" title="Messenger">
                    ${icon('messenger')}
                </a>`);
        }
        if (CHATBOT_CONFIG.zaloLink) {
            contactBtns.push(`
                <a href="${CHATBOT_CONFIG.zaloLink}" target="_blank" class="cb-fab cb-fab-zalo" title="Zalo">
                    ${icon('zalo')}
                </a>`);
        }
        if (CHATBOT_CONFIG.phone) {
            contactBtns.push(`
                <a href="tel:${CHATBOT_CONFIG.phone}" class="cb-fab cb-fab-phone" title="Gọi điện">
                    ${icon('phone')}
                </a>`);
        }
        contactBtns.push(`
            <button id="cb-chat-btn" class="cb-fab cb-fab-chat" title="Chat">
                ${icon('chat')}
            </button>`);

        return `
        <div id="odoo-chatbot" class="cb-container">
            <div id="cb-fab-list" class="cb-fab-list" style="display:none;">
                ${contactBtns.join('')}
            </div>
            <button id="cb-toggle" class="cb-fab cb-fab-toggle">
                <span id="cb-icon-plus">${icon('toggle')}</span>
                <span id="cb-icon-close" style="display:none;">${FALLBACK_ICONS.close}</span>
            </button>
            <div id="chatbot-window" class="chatbot-window" style="display:none;">
                <div class="chatbot-header">
                    <h3>Hỗ trợ trực tuyến</h3>
                    <button id="chatbot-close" class="chatbot-close">${FALLBACK_ICONS.close}</button>
                </div>
                <div id="chatbot-messages" class="chatbot-messages">
                    <div class="message bot-message">
                        <div class="message-content">Xin chào! Tôi có thể giúp gì cho bạn?</div>
                    </div>
                </div>
                <div class="chatbot-input-area">
                    <input type="text" id="chatbot-input" placeholder="Nhập tin nhắn..." />
                    <button id="chatbot-send">Gửi</button>
                </div>
                <div id="customer-form" class="customer-form" style="display:none;">
                    <h4>Vui lòng để lại thông tin để được tư vấn</h4>
                    <input type="text" id="customer-name" placeholder="Họ và tên *" required />
                    <input type="email" id="customer-email" placeholder="Email *" required />
                    <input type="tel" id="customer-phone" placeholder="Số điện thoại" />
                    <input type="datetime-local" id="customer-datetime" />
                    <button id="submit-info">Gửi thông tin</button>
                </div>
            </div>
        </div>`;
    }

    // ── CSS ────────────────────────────────────────────────────────────────────
    function createChatbotCSS() {
        const css = `
            .cb-container {
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                align-items: flex-end;
                gap: 12px;
                font-family: Arial, sans-serif;
            }
            .cb-fab-list {
                display: flex;
                flex-direction: column;
                align-items: flex-end;
                gap: 12px;
            }
            .cb-fab {
                width: 52px;
                height: 52px;
                border-radius: 50%%;
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                text-decoration: none;
                color: white;
            }
            .cb-fab:hover { transform: scale(1.1); box-shadow: 0 6px 16px rgba(0,0,0,0.25); }
            .cb-fab-toggle { background: #3d6b8c; width: 56px; height: 56px; padding: 0 }
            .cb-fab-chat    { background: #3d6b8c; padding: 0; }
            .cb-fab-phone   { background: #3d6b8c; }
            .cb-fab-zalo    { background: #3d6b8c; font-weight: bold; font-size: 20px; }
            .cb-fab-messenger { background: #3d6b8c; }
            .cb-fab-toggle #cb-icon-plus image { width: 100%; height: 100%; }
            .cb-fab-chat img, .cb-fab-phone img, .cb-fab-zalo img, .cb-fab-messenger img {
                width: 100%%;
                height: 100%%;
                border-radius: 100%%;
            }
            .chatbot-window {
                position: absolute;
                bottom: 72px;
                right: 0;
                width: 350px;
                height: 500px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.18);
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            .chatbot-header {
                background: #3d6b8c;
                color: white;
                padding: 14px 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .chatbot-header h3 { margin: 0; font-size: 15px; }
            .chatbot-close {
                background: none;
                border: none;
                color: white;
                cursor: pointer;
                display: flex;
                align-items: center;
                padding: 0;
            }
            .chatbot-messages {
                flex: 1;
                padding: 14px;
                overflow-y: auto;
                background: #f8f9fa;
            }
            .message { margin-bottom: 12px; display: flex; }
            .bot-message .message-content {
                background: #e9ecef;
                padding: 10px 14px;
                border-radius: 18px;
                max-width: 80%%;
                word-wrap: break-word;
                font-size: 14px;
            }
            .user-message { justify-content: flex-end; }
            .user-message .message-content {
                background: #3d6b8c;
                color: white;
                padding: 10px 14px;
                border-radius: 18px;
                max-width: 80%%;
                word-wrap: break-word;
                font-size: 14px;
            }
            .chatbot-input-area {
                padding: 12px;
                border-top: 1px solid #dee2e6;
                display: flex;
                gap: 8px;
            }
            .chatbot-input-area input {
                flex: 1;
                padding: 9px 14px;
                border: 1px solid #dee2e6;
                border-radius: 20px;
                outline: none;
                font-size: 14px;
            }
            .chatbot-input-area button {
                background: #3d6b8c;
                color: white;
                border: none;
                padding: 9px 18px;
                border-radius: 20px;
                cursor: pointer;
                font-size: 14px;
            }
            .customer-form {
                padding: 14px;
                border-top: 1px solid #dee2e6;
                background: #f8f9fa;
            }
            .customer-form h4 { margin: 0 0 12px; font-size: 13px; color: #495057; }
            .customer-form input {
                width: 100%%;
                padding: 9px;
                margin-bottom: 8px;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                box-sizing: border-box;
                font-size: 13px;
            }
            .customer-form button {
                width: 100%%;
                background: #28a745;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                cursor: pointer;
                font-weight: bold;
                font-size: 14px;
            }
            .customer-form button:hover { background: #218838; }
        `;
        const style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    }

    // ── Init ───────────────────────────────────────────────────────────────────
    function initChatbot() {
        createChatbotCSS();
        document.body.insertAdjacentHTML('beforeend', createChatbotHTML());
        bindEvents();
    }

    // ── Events ─────────────────────────────────────────────────────────────────
    function bindEvents() {
        const toggle   = document.getElementById('cb-toggle');
        const fabList  = document.getElementById('cb-fab-list');
        const chatBtn  = document.getElementById('cb-chat-btn');
        const chatWin  = document.getElementById('chatbot-window');
        const closeBtn = document.getElementById('chatbot-close');
        const input    = document.getElementById('chatbot-input');
        const sendBtn  = document.getElementById('chatbot-send');
        const submitBtn = document.getElementById('submit-info');
        const iconPlus  = document.getElementById('cb-icon-plus');
        const iconClose = document.getElementById('cb-icon-close');

        let menuOpen = false;

        toggle.addEventListener('click', () => {
            menuOpen = !menuOpen;
            fabList.style.display = menuOpen ? 'flex' : 'none';
            iconPlus.style.display  = menuOpen ? 'none'  : 'flex';
            iconClose.style.display = menuOpen ? 'flex'  : 'none';
            if (!menuOpen) chatWin.style.display = 'none';
        });

        if (chatBtn) {
            chatBtn.addEventListener('click', () => {
                chatWin.style.display = chatWin.style.display === 'none' ? 'flex' : 'none';
            });
        }

        closeBtn.addEventListener('click', () => {
            chatWin.style.display = 'none';
        });

        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(); });
        if (submitBtn) submitBtn.addEventListener('click', submitCustomerInfo);
    }

    // ── State ──────────────────────────────────────────────────────────────────
    window.chatbotSessionId = null;

    // ── Send message ───────────────────────────────────────────────────────────
    async function sendMessage() {
        const input = document.getElementById('chatbot-input');
        const message = input.value.trim();
        if (!message) return;
        addMessage(message, 'user');
        input.value = '';
        try {
            const response = await fetch(CHATBOT_CONFIG.apiUrl + '/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: "2.0", params: { message, session_id: window.chatbotSessionId } })
            });
            const data = await response.json();
            if (data.result?.success) {
                if (data.result.session_id) window.chatbotSessionId = data.result.session_id;
                addMessage(data.result?.response, 'bot');
                const responseType = data.result?.response_type || 'none';
                if (responseType === 'form') {
                    showCustomerForm();
                    window.chatbotUserInfoMode = false;
                } else if (responseType === 'prompt') {
                    window.chatbotUserInfoMode = true;
                } else {
                    window.chatbotUserInfoMode = false;
                }
            } else {
                addMessage('Xin lỗi, có lỗi xảy ra. Vui lòng thử lại.', 'bot');
            }
        } catch (error) {
            addMessage('Xin lỗi, có lỗi xảy ra. Vui lòng thử lại sau.', 'bot');
        }
    }

    function addMessage(content, type) {
        const container = document.getElementById('chatbot-messages');
        const div = document.createElement('div');
        div.className = `message ${type}-message`;
        div.innerHTML = `<div class="message-content">${content}</div>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    function showCustomerForm() {
        document.getElementById('customer-form').style.display = 'block';
        document.querySelector('.chatbot-input-area').style.display = 'none';
    }

    async function submitCustomerInfo() {
        const name     = document.getElementById('customer-name').value.trim();
        const email    = document.getElementById('customer-email').value.trim();
        const phone    = document.getElementById('customer-phone').value.trim();
        const datetime = document.getElementById('customer-datetime').value;
        if (!name || !email) { alert('Vui lòng nhập họ tên và email'); return; }
        try {
            const response = await fetch(CHATBOT_CONFIG.apiUrl + '/submit_info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: "2.0", params: { name, email, phone, consultation_datetime: datetime, session_id: window.chatbotSessionId } })
            });
            const data = await response.json();
            if (data.result.success) {
                addMessage('Cảm ơn! Thông tin của bạn đã được ghi nhận. Chúng tôi sẽ liên hệ với bạn sớm nhất có thể.', 'bot');
                document.getElementById('customer-form').style.display = 'none';
                document.querySelector('.chatbot-input-area').style.display = 'flex';
                ['customer-name','customer-email','customer-phone','customer-datetime'].forEach(id => document.getElementById(id).value = '');
            } else {
                alert('Có lỗi xảy ra. Vui lòng thử lại.');
            }
        } catch (error) {
            alert('Có lỗi xảy ra. Vui lòng thử lại.');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initChatbot);
    } else {
        initChatbot();
    }
    })();
        """ % (get_base_url() + '/chatbot/api', phone, zalo_link, messenger_link,
               icon_toggle, icon_chat, icon_phone, icon_zalo, icon_messenger)

        return request.make_response(
            js_content,
            headers=[
                ('Content-Type', 'application/javascript'),
                ('Cache-Control', 'public, max-age=3600'),
            ] + self._cors_headers()
        )

    @http.route(['/chatbot/api/chat', '/chatbot/api/submit_info'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def chatbot_api_preflight(self, **kwargs):
        return request.make_response('', headers=self._cors_headers())

    @http.route('/chatbot/api/chat', type='http', auth='public', methods=['POST'], csrf=False)
    def chatbot_chat(self, **kwargs):
        kwargs = json.loads(request.httprequest.data or '{}').get('params', {})
        """Handle chatbot conversation"""
        try:
            # Input validation for security
            validator = request.env['chatbot.security.validator'].sudo()
            is_valid, sanitized_data, errors = validator.sanitize_input_data(
                kwargs)

            if not is_valid:
                _logger.warning(f"Invalid input received: {errors}")
                return {'success': False, 'error': 'Invalid input data'}

            # Log để debug (using sanitized data)
            _logger.info(f"Chatbot received kwargs: {sanitized_data}")

            message = sanitized_data.get('message', '').strip()
            session_id = sanitized_data.get('session_id', '')

            if not message:
                _logger.warning(f"Empty message received: {sanitized_data}")
                return {'success': False, 'error': 'Empty message'}

            user_ip = request.httprequest.environ.get('REMOTE_ADDR')
            user_agent = request.httprequest.environ.get('HTTP_USER_AGENT')

            chatbot_service: ChatbotService = ChatbotServiceFactory.get_service(env=request.env)
            message_dto = chatbot_service.chat(
                message, session_id, user_ip=user_ip, user_agent=user_agent, source_code='chatbot')

            bot_message = message_dto.bot_message
            session_id = message_dto.session_id
            customer_inquiry_created = message_dto.customer_inquiry_created
            conversation_ended = message_dto.conversation_ended

            result = {
                'success': True,
                'response': bot_message.content,
                'response_type': bot_message.response_type,
                'show_form': bot_message.response_type == 'form',
                'session_id': session_id,
                'customer_inquiry_created': customer_inquiry_created,
                'conversation_ended': conversation_ended
            }

        except Exception as e:
            _logger.error(f"Chatbot chat error: {str(e)}")
            result = {'success': False, 'error': f'Internal server error: {str(e)}'}

        return request.make_response(
            json.dumps({'result': result}),
            headers=[('Content-Type', 'application/json')] + self._cors_headers()
        )

    @http.route('/chatbot/api/submit_info', type='http', auth='public', methods=['POST'], csrf=False)
    def chatbot_submit_info(self, **kwargs):
        kwargs = json.loads(request.httprequest.data or '{}').get('params', {})
        """Handle customer information submission"""
        try:
            # Input validation for security
            validator = request.env['chatbot.security.validator'].sudo()
            is_valid, sanitized_data, errors = validator.sanitize_input_data(
                kwargs)

            if not is_valid:
                _logger.warning(f"Invalid input received: {errors}")
                result = {'success': False, 'error': 'Invalid input data'}
            else:
                name = sanitized_data.get('name', '').strip()
                email = sanitized_data.get('email', '').strip()

                missing_fields = []
                if not name:
                    missing_fields.append('name')
                if not email:
                    missing_fields.append('email')

                if missing_fields:
                    missing = ', '.join(missing_fields)
                    result = {'success': False, 'error': f'Vui lòng cung cấp: {missing}', 'missing_fields': missing_fields}
                else:
                    vals = {
                        'name': name,
                        'email': email,
                        'phone': sanitized_data.get('phone', '').strip(),
                        'message': sanitized_data.get('message', ''),
                    }

                    session_id = sanitized_data.get('session_id', '').strip()
                    if session_id:
                        conversation = request.env['chatbot.conversation'].sudo().search([
                            ('session_id', '=', session_id)
                        ], limit=1)
                        if conversation:
                            vals['conversation_id'] = conversation.id
                            _logger.info(f"Linked inquiry to conversation {conversation.id}")

                    consultation_datetime = sanitized_data.get('consultation_datetime')
                    if consultation_datetime:
                        from datetime import datetime
                        import pytz
                        try:
                            dt = datetime.fromisoformat(consultation_datetime)
                            tz_vietnam = pytz.timezone('Asia/Ho_Chi_Minh')
                            dt_vietnam = tz_vietnam.localize(dt)
                            dt_utc = dt_vietnam.astimezone(pytz.UTC)
                            dt_naive = dt_utc.replace(tzinfo=None)
                            _logger.info(f"Converted datetime from '{dt}' (Vietnam) to naive UTC: '{dt_naive}'")
                            vals['consultation_datetime'] = dt_naive
                        except ValueError as e:
                            _logger.warning(f"Invalid datetime format: {consultation_datetime} - Error: {e}")

                    inquiry = request.env['customer.inquiry'].sudo().create_from_chatbot(vals)
                    _logger.info(f"Created customer inquiry {inquiry.id} from chatbot")
                    result = {'success': True, 'inquiry_id': inquiry.id}

        except Exception as e:
            _logger.error(f"Chatbot submit info error: {str(e)}")
            result = {'success': False, 'error': 'Internal server error'}

        return request.make_response(
            json.dumps({'result': result}),
            headers=[('Content-Type', 'application/json')] + self._cors_headers()
        )

    @http.route('/chatbot/snippet', type='http', auth='public', website=True)
    def chatbot_snippet_info(self, **kwargs):
        """Provide information about chatbot integration"""
        snippet_code = f"""
<!-- ISD Chatbot Integration -->
<script src="{get_base_url()}/chatbot/widget.js"></script>
        """.strip()

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>ISD Chatbot Integration</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .code {{ background: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .highlight {{ background: #e7f3ff; padding: 20px; border-radius: 5px; border-left: 4px solid #007bff; }}
    </style>
</head>
<body>
    <h1>ISD Chatbot Integration</h1>
    
    <div class="highlight">
        <h3>🚀 Quick Integration</h3>
        <p>Add this code to any website to integrate the ISD chatbot:</p>
    </div>
    
    <div class="code">
        <pre>{snippet_code}</pre>
    </div>
    
    <h3>Features:</h3>
    <ul>
        <li>✅ Intelligent conversation handling with spaCy NLP</li>
        <li>✅ Customer inquiry collection</li>
        <li>✅ CRM integration</li>
        <li>✅ Calendar booking</li>
        <li>✅ Email notifications</li>
        <li>✅ Mobile responsive</li>
    </ul>
    
    <h3>API Endpoints:</h3>
    <ul>
        <li><code>GET {get_base_url()}/chatbot/widget.js</code> - Chatbot widget JavaScript</li>
        <li><code>POST {get_base_url()}/chatbot/api/chat</code> - Send message to chatbot</li>
        <li><code>POST {get_base_url()}/chatbot/api/submit_info</code> - Submit customer information</li>
    </ul>
    
    <p><strong>Note:</strong> Make sure the ISD Chatbot module is installed and configured properly.</p>
</body>
</html>
        """

        return request.make_response(
            html_content,
            headers=[('Content-Type', 'text/html')]
        )

    def _process_user_info_message(self, message):
        """Process a message containing user information from prompt mode"""
        _logger.info(
            f"PROMPT MODE: Processing raw message without analysis: {message}")

        # Sử dụng phương thức create trực tiếp thay vì thông qua create_from_chatbot để tránh phân tích
        CustomerInquiry = request.env['customer.inquiry'].sudo()

        # Create customer inquiry với tin nhắn gốc
        # Sử dụng chuỗi rỗng cho các trường bắt buộc name và email
        vals = {
            'name': ' ',   # Chuỗi rỗng cho trường bắt buộc
            'email': ' ',  # Chuỗi rỗng cho trường bắt buộc
            'message': message,    # Lưu tin nhắn gốc của khách hàng
            'state': 'new',       # Trạng thái mới
        }

        try:
            # Tạo inquiry trực tiếp không thông qua phương thức có thể gọi phân tích
            inquiry = CustomerInquiry.create(vals)
            _logger.info(
                f"PROMPT MODE: Successfully created raw customer inquiry, ID: {inquiry.id}, with message: {message}")
            return {
                'success': True,
                'response': "Cảm ơn! Thông tin của bạn đã được ghi nhận. Chúng tôi sẽ liên hệ với bạn sớm.",
                'response_type': 'none'
            }
        except Exception as e:
            _logger.error(
                f"PROMPT MODE ERROR: Failed to create inquiry: {str(e)}")
            return {
                'success': False,
                'error': 'Không thể lưu thông tin. Vui lòng thử lại.'
            }

    @http.route('/isd_chatbot/webhook', type='http', auth='public', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'], csrf=False)
    def webhook_receiver(self, **kwargs):
        """
        Universal webhook endpoint to receive any HTTP method and store all request data
        Responds with HTTP 200 OK status
        """
        try:
            # Get HTTP method
            http_method = request.httprequest.method

            # Get request body data - always try to get body for all methods
            request_body = ''
            try:
                # Always attempt to read request body regardless of method
                raw_data = request.httprequest.get_data(as_text=True)
                if raw_data:
                    request_body = raw_data
                elif http_method == 'GET' and request.httprequest.args:
                    # Only fall back to query params for GET if no body
                    request_body = json.dumps(dict(request.httprequest.args))
            except Exception as e:
                _logger.warning(f"Failed to read request body: {e}")
                request_body = ''

            # Get query parameters - always separate from body
            query_params = ''
            if request.httprequest.args:
                query_params = dict(request.httprequest.args)

            # Get all request headers (excluding sensitive ones)
            headers_dict = {}
            for header_name, header_value in request.httprequest.headers:
                # Skip sensitive headers
                if header_name.lower() not in ['authorization', 'cookie', 'set-cookie']:
                    headers_dict[header_name] = header_value
            request_headers = json.dumps(headers_dict, indent=2)

            # Get request metadata
            source_ip = request.httprequest.environ.get(
                'REMOTE_ADDR', 'unknown')
            user_agent = request.httprequest.environ.get('HTTP_USER_AGENT', '')
            full_url = request.httprequest.url

            # Calculate payload size
            total_size = len(request_body.encode(
                'utf-8')) if request_body else 0

            # Extract webhook metadata from request body if it's JSON
            webhook_type = None
            event_type = None

            send_msg, sender_id = "", ""
            if request_body:
                try:
                    if request.httprequest.content_type and 'application/json' in request.httprequest.content_type:
                        payload = json.loads(request_body)
                        if isinstance(payload, dict):
                            webhook_type = payload.get(
                                'type', payload.get('webhook_type'))
                            event_type = payload.get(
                                'event', payload.get('event_type'))

                            send_msg = payload.get(
                                'message', {}).get('text', '')
                            sender_id = payload.get('sender', {}).get('id', '')
                except (json.JSONDecodeError, TypeError):
                    pass  # Not JSON or invalid JSON, that's okay

            # Store webhook in database
            webhook_vals = {
                'json_data': request_body,
                'http_method': http_method,
                'query_params': json.dumps(query_params, indent=2) if query_params else '',
                'request_headers': request_headers,
                'full_url': full_url,
                'source_ip': source_ip,
                'user_agent': user_agent,
                'webhook_type': webhook_type,
                'event_type': event_type,
                'payload_size': total_size,
                'status': 'received'
            }

            webhook = request.env['chatbot.webhook.log'].sudo().create(
                webhook_vals)

            _logger.info(
                f"📨 WEBHOOK: {http_method} request stored as {webhook.webhook_id} from {source_ip}")

            try:
                merchant = query_params.get('merchant', '') if query_params else ''
                if send_msg and sender_id and merchant:
                    def _process_webhook_message(env,send_msg, sender_id, source_ip, user_agent, merchant):
                        # Process the message using chatbot service
                        chatbot_service: ChatbotService = ChatbotServiceFactory.get_service(
                            provider=merchant, env=env)
                        chatbot_service.chat(
                            send_msg, session_id=sender_id, user_ip=source_ip, user_agent=user_agent, zalo_sender_id=sender_id)


                    # _process_webhook_message(send_msg=send_msg, sender_id=sender_id, source_ip=source_ip, user_agent=user_agent, merchant=merchant)
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        executor.submit(_process_webhook_message, env=request.env, send_msg=send_msg, sender_id=sender_id, source_ip=source_ip, user_agent=user_agent, merchant=merchant)

                    _logger.info(
                        f"Processed webhook message from sender {sender_id} in background thread.")
            
            except Exception as e:
                _logger.error(f"Error processing webhook data: {str(e)}")

            # Return HTTP 200 OK status (no text content)
            return request.make_response(
                "",  # Empty response body
                status=200,
                headers=[
                    ('Access-Control-Allow-Origin', '*'),
                    ('Access-Control-Allow-Methods',
                     'GET, POST, PUT, DELETE, PATCH, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                ]
            )

        except Exception as e:
            _logger.error(
                f"❌ WEBHOOK ERROR: Failed to process {request.httprequest.method} webhook: {str(e)}")

            # Even on error, still return 200 OK as many webhook services expect this
            return request.make_response(
                "",  # Empty response body
                status=200,
                headers=[
                    ('Access-Control-Allow-Origin', '*')
                ]
            )

    @http.route('/isd_chatbot/webhook', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def webhook_options(self, **kwargs):
        """Handle CORS preflight requests for all HTTP methods"""
        return request.make_response(
            "",
            status=200,
            headers=[
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods',
                 'GET, POST, PUT, DELETE, PATCH, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            ]
        )
