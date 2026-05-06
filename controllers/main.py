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

    @http.route('/chatbot/widget.js', type='http', auth='public', website=True)
    def chatbot_widget_js(self, **kwargs):
        """Serve the chatbot JavaScript widget"""
        js_content = """
(function() {
    'use strict';
    
    // Chatbot configuration
    const CHATBOT_CONFIG = {
        apiUrl: '%s',
        position: 'bottom-right',
        theme: 'default'
    };
    
    // Create chatbot HTML structure
    function createChatbotHTML() {
        return `
            <div id="odoo-chatbot" class="odoo-chatbot-container">
                <div id="chatbot-toggle" class="chatbot-toggle">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                </div>
                <div id="chatbot-window" class="chatbot-window" style="display: none;">
                    <div class="chatbot-header">
                        <h3>Hỗ trợ trực tuyến</h3>
                        <button id="chatbot-close" class="chatbot-close">&times;</button>
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
                    <div id="customer-form" class="customer-form" style="display: none;">
                        <h4>Vui lòng để lại thông tin để được tư vấn</h4>
                        <input type="text" id="customer-name" placeholder="Họ và tên *" required />
                        <input type="email" id="customer-email" placeholder="Email *" required />
                        <input type="tel" id="customer-phone" placeholder="Số điện thoại" />
                        <input type="datetime-local" id="customer-datetime" placeholder="Thời gian mong muốn" />
                        <button id="submit-info">Gửi thông tin</button>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Create chatbot CSS
    function createChatbotCSS() {
        const css = `
            .odoo-chatbot-container {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 9999;
                font-family: Arial, sans-serif;
            }
            
            .chatbot-toggle {
                width: 60px;
                height: 60px;
                background: #007bff;
                border-radius: 50%%;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                color: white;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transition: all 0.3s ease;
            }
            
            .chatbot-toggle:hover {
                background: #0056b3;
                transform: scale(1.1);
            }
            
            .chatbot-window {
                position: absolute;
                bottom: 70px;
                right: 0;
                width: 350px;
                height: 500px;
                background: white;
                border-radius: 10px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            
            .chatbot-header {
                background: #007bff;
                color: white;
                padding: 15px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .chatbot-header h3 {
                margin: 0;
                font-size: 16px;
            }
            
            .chatbot-close {
                background: none;
                border: none;
                color: white;
                font-size: 20px;
                cursor: pointer;
                padding: 0;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .chatbot-messages {
                flex: 1;
                padding: 15px;
                overflow-y: auto;
                background: #f8f9fa;
            }
            
            .message {
                margin-bottom: 15px;
                display: flex;
            }
            
            .bot-message .message-content {
                background: #e9ecef;
                padding: 10px 15px;
                border-radius: 18px;
                max-width: 80%%;
                word-wrap: break-word;
            }
            
            .user-message {
                justify-content: flex-end;
            }
            
            .user-message .message-content {
                background: #007bff;
                color: white;
                padding: 10px 15px;
                border-radius: 18px;
                max-width: 80%%;
                word-wrap: break-word;
            }
            
            .chatbot-input-area {
                padding: 15px;
                border-top: 1px solid #dee2e6;
                display: flex;
                gap: 10px;
            }
            
            .chatbot-input-area input {
                flex: 1;
                padding: 10px;
                border: 1px solid #dee2e6;
                border-radius: 20px;
                outline: none;
            }
            
            .chatbot-input-area button {
                background: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 20px;
                cursor: pointer;
            }
            
            .customer-form {
                padding: 15px;
                border-top: 1px solid #dee2e6;
                background: #f8f9fa;
            }
            
            .customer-form h4 {
                margin: 0 0 15px 0;
                font-size: 14px;
                color: #495057;
            }
            
            .customer-form input {
                width: 100%%;
                padding: 10px;
                margin-bottom: 10px;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                box-sizing: border-box;
            }
            
            .customer-form button {
                width: 100%%;
                background: #28a745;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 5px;
                cursor: pointer;
                font-weight: bold;
            }
            
            .customer-form button:hover {
                background: #218838;
            }
        `;
        
        const style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    }
    
    // Initialize chatbot
    function initChatbot() {
        // Create CSS
        createChatbotCSS();
        
        // Create HTML
        const chatbotHTML = createChatbotHTML();
        document.body.insertAdjacentHTML('beforeend', chatbotHTML);
        
        // Bind events
        bindEvents();
    }
    
    // Bind chatbot events
    function bindEvents() {
        const toggle = document.getElementById('chatbot-toggle');
        const window = document.getElementById('chatbot-window');
        const close = document.getElementById('chatbot-close');
        const input = document.getElementById('chatbot-input');
        const sendBtn = document.getElementById('chatbot-send');
        const submitBtn = document.getElementById('submit-info');
        
        toggle.addEventListener('click', () => {
            window.style.display = window.style.display === 'none' ? 'flex' : 'none';
        });
        
        close.addEventListener('click', () => {
            window.style.display = 'none';
        });
        
        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
        
        submitBtn.addEventListener('click', submitCustomerInfo);
    }
    
    // State management
    window.chatbotSessionId = null; // Store conversation session ID
    
    // Send message to chatbot
    async function sendMessage() {
        const input = document.getElementById('chatbot-input');
        const message = input.value.trim();
        
        if (!message) return;
        
        // Add user message to chat
        addMessage(message, 'user');
        input.value = '';
        
        try {
            // Prepare params with session ID
            const params = { 
                message: message,
                session_id: window.chatbotSessionId
            };
            
            // Gọi API
            const response = await fetch(CHATBOT_CONFIG.apiUrl + '/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: "2.0", 
                    params: params
                })
            });
            
            const data = await response.json();
            
            if (data.result?.success) {
                // Update session ID from server response
                if (data.result.session_id) {
                    window.chatbotSessionId = data.result.session_id;
                }

                addMessage(data.result?.response, 'bot');
                
                // Xử lý theo loại phản hồi
                const responseType = data.result?.response_type || 'none';
                
                if (responseType === 'form') {
                    // Hiển thị form nhập thông tin
                    showCustomerForm();
                    window.chatbotUserInfoMode = false;
                } 
                else if (responseType === 'prompt') {
                    // Chuyển sang chế độ prompt để xử lý thông tin người dùng
                    window.chatbotUserInfoMode = true;
                    
                    // Nếu có thông tin thiếu, hiển thị yêu cầu bổ sung
                    if (data.result?.missing_fields) {
                        const missing = data.result.missing_fields.join(', ');
                        console.log('Missing fields:', missing);
                    }
                }
                else {
                    // Chế độ none - không làm gì cả
                    window.chatbotUserInfoMode = false;
                }
            } else {
                console.error('Chatbot error:', data);
                addMessage('Xin lỗi, có lỗi xảy ra. Vui lòng thử lại.', 'bot');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            addMessage('Xin lỗi, có lỗi xảy ra. Vui lòng thử lại sau.', 'bot');
        }
    }
    
    // Add message to chat
    function addMessage(content, type) {
        const messagesContainer = document.getElementById('chatbot-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        messageDiv.innerHTML = `<div class="message-content">${content}</div>`;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Show customer form
    function showCustomerForm() {
        document.getElementById('customer-form').style.display = 'block';
        document.querySelector('.chatbot-input-area').style.display = 'none';
    }
    
    // Submit customer information
    async function submitCustomerInfo() {
        const name = document.getElementById('customer-name').value.trim();
        const email = document.getElementById('customer-email').value.trim();
        const phone = document.getElementById('customer-phone').value.trim();
        const datetime = document.getElementById('customer-datetime').value;
        
        if (!name || !email) {
            alert('Vui lòng nhập họ tên và email');
            return;
        }
        
        try {
            const response = await fetch(CHATBOT_CONFIG.apiUrl + '/submit_info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: {
                        name: name,
                        email: email,
                        phone: phone,
                        consultation_datetime: datetime,
                        session_id: window.chatbotSessionId
                    }
                })
            });
            
            const data = await response.json();
            
            if (data.result.success) {
                addMessage('Cảm ơn! Thông tin của bạn đã được ghi nhận. Chúng tôi sẽ liên hệ với bạn sớm nhất có thể.', 'bot');
                document.getElementById('customer-form').style.display = 'none';
                document.querySelector('.chatbot-input-area').style.display = 'flex';
                
                // Clear form
                document.getElementById('customer-name').value = '';
                document.getElementById('customer-email').value = '';
                document.getElementById('customer-phone').value = '';
                document.getElementById('customer-datetime').value = '';
            } else {
                alert('Có lỗi xảy ra. Vui lòng thử lại.');
            }
        } catch (error) {
            console.error('Submit error:', error);
            alert('Có lỗi xảy ra. Vui lòng thử lại.');
        }
    }
    
    // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initChatbot);
        } else {
            initChatbot();
        }
    })();
        """ % (get_base_url() + '/chatbot/api')

        return request.make_response(
            js_content,
            headers=[
                ('Content-Type', 'application/javascript'),
                ('Cache-Control', 'public, max-age=3600'),
            ]
        )

    @http.route('/chatbot/api/chat', type='json', auth='public', methods=['POST'], csrf=False)
    def chatbot_chat(self, **kwargs):
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

            return {
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
            return {'success': False, 'error': f'Internal server error: {str(e)}'}

    @http.route('/chatbot/api/submit_info', type='json', auth='public', methods=['POST'], csrf=False)
    def chatbot_submit_info(self, **kwargs):
        """Handle customer information submission"""
        try:
            # Input validation for security
            validator = request.env['chatbot.security.validator'].sudo()
            is_valid, sanitized_data, errors = validator.sanitize_input_data(
                kwargs)

            if not is_valid:
                _logger.warning(f"Invalid input received: {errors}")
                return {'success': False, 'error': 'Invalid input data'}

            name = sanitized_data.get('name', '').strip()
            email = sanitized_data.get('email', '').strip()

            # Kiểm tra các trường bắt buộc
            missing_fields = []
            if not name:
                missing_fields.append('name')
            if not email:
                missing_fields.append('email')

            if missing_fields:
                missing = ', '.join(missing_fields)
                return {
                    'success': False,
                    'error': f'Vui lòng cung cấp: {missing}',
                    'missing_fields': missing_fields
                }

            # Prepare data
            vals = {
                'name': name,
                'email': email,
                'phone': sanitized_data.get('phone', '').strip(),
                'message': sanitized_data.get('message', ''),
            }

            # Link to conversation if session_id is provided
            session_id = sanitized_data.get('session_id', '').strip()
            if session_id:
                conversation = request.env['chatbot.conversation'].sudo().search([
                    ('session_id', '=', session_id)
                ], limit=1)
                if conversation:
                    vals['conversation_id'] = conversation.id
                    _logger.info(f"Linked inquiry to conversation {conversation.id}")

            # Handle consultation datetime
            consultation_datetime = sanitized_data.get('consultation_datetime')
            if consultation_datetime:
                from datetime import datetime
                import pytz
                try:
                    # Parse datetime string - assuming user input is in Vietnam timezone
                    # Input from datetime-local is in format YYYY-MM-DDTHH:MM without timezone info
                    dt = datetime.fromisoformat(consultation_datetime)

                    # Xác định rõ múi giờ Vietnam cho thời gian người dùng nhập
                    tz_vietnam = pytz.timezone('Asia/Ho_Chi_Minh')
                    dt_vietnam = tz_vietnam.localize(dt)

                    # Convert to UTC for storage in database (Odoo stores datetime in UTC)
                    dt_utc = dt_vietnam.astimezone(pytz.UTC)

                    # Remove timezone info to make it naive (Odoo expects naive datetime)
                    dt_naive = dt_utc.replace(tzinfo=None)

                    _logger.info(
                        f"Converted datetime from '{dt}' (Vietnam) to naive UTC: '{dt_naive}'")
                    vals['consultation_datetime'] = dt_naive
                except ValueError as e:
                    _logger.warning(
                        f"Invalid datetime format: {consultation_datetime} - Error: {e}")

            # Create customer inquiry
            inquiry = request.env['customer.inquiry'].sudo(
            ).create_from_chatbot(vals)

            _logger.info(f"Created customer inquiry {inquiry.id} from chatbot")

            return {'success': True, 'inquiry_id': inquiry.id}

        except Exception as e:
            _logger.error(f"Chatbot submit info error: {str(e)}")
            return {'success': False, 'error': 'Internal server error'}

    @http.route('/chatbot/snippet', type='http', auth='public', website=True)
    def chatbot_snippet_info(self, **kwargs):
        """Provide information about chatbot integration"""
        snippet_code = f"""
<!-- Odoo Chatbot Integration -->
<script src="{get_base_url()}/chatbot/widget.js"></script>
        """.strip()

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Odoo Chatbot Integration</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .code {{ background: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .highlight {{ background: #e7f3ff; padding: 20px; border-radius: 5px; border-left: 4px solid #007bff; }}
    </style>
</head>
<body>
    <h1>Odoo Chatbot Integration</h1>
    
    <div class="highlight">
        <h3>🚀 Quick Integration</h3>
        <p>Add this code to any website to integrate the Odoo chatbot:</p>
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
    
    <p><strong>Note:</strong> Make sure the Odoo Chatbot module is installed and configured properly.</p>
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
