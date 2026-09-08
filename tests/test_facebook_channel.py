# -*- coding: utf-8 -*-

from unittest.mock import MagicMock, patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.isd_chatbot.services.chatbot_service import (
    ChatbotServiceFactory,
    FacebookChatbotServiceAdapter,
)


@tagged('post_install', '-at_install', 'isd_chatbot')
class TestFacebookChannel(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['inquiry.source']._get_default_sources()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('isd_chatbot.facebook_enabled', True)
        ICP.set_param('isd_chatbot.facebook_page_access_token', 'page-token')
        ICP.set_param('isd_chatbot.facebook_app_secret', 'app-secret')
        ICP.set_param('isd_chatbot.facebook_app_id', 'app-id')

    def _service(self):
        return FacebookChatbotServiceAdapter(env=self.env)

    def test_factory_and_session_source(self):
        service = ChatbotServiceFactory.get_service('facebook', env=self.env)
        self.assertIsInstance(service, FacebookChatbotServiceAdapter)
        with patch.object(service, 'send_reply', return_value=None):
            dto = service.chat('hello', 'PSID99', facebook_sender_id='PSID99')
        conv = self.env['chatbot.conversation'].search([
            ('session_id', '=', 'facebook:PSID99'),
        ], limit=1)
        self.assertTrue(conv)
        self.assertEqual(conv.source_id.code, 'facebook')
        self.assertEqual(dto.session_id, 'facebook:PSID99')

    def test_name_and_contact_creates_one_inquiry(self):
        service = self._service()
        info = {
            'name': 'Ada Lovelace',
            'email': 'ada@example.com',
            'phone': None,
            'datetime': None,
        }
        with patch.object(
            type(self.env['chatbot.config']), 'parse_user_info', return_value=info
        ), patch.object(service, 'send_reply', return_value=None):
            dto = service.chat(
                'Ada Lovelace ada@example.com',
                'PSID-INQ',
                facebook_sender_id='PSID-INQ',
            )
        self.assertTrue(dto.customer_inquiry_created)
        self.assertTrue(dto.conversation_ended)
        inquiries = self.env['customer.inquiry'].search([
            ('conversation_id.session_id', '=', 'facebook:PSID-INQ'),
        ])
        self.assertEqual(len(inquiries), 1)
        self.assertEqual(inquiries.source_id.code, 'facebook')
        self.assertEqual(inquiries.message, 'Ada Lovelace ada@example.com')
        self.assertFalse(inquiries.crm_lead_id)
        self.assertEqual(inquiries.state, 'new')

    def test_name_only_no_inquiry(self):
        service = self._service()
        info = {
            'name': 'Ada Lovelace',
            'email': None,
            'phone': None,
            'datetime': None,
        }
        with patch.object(
            type(self.env['chatbot.config']), 'parse_user_info', return_value=info
        ), patch.object(service, 'send_reply', return_value=None):
            dto = service.chat(
                'Ada Lovelace',
                'PSID-NAME',
                facebook_sender_id='PSID-NAME',
            )
        self.assertFalse(dto.customer_inquiry_created)
        self.assertFalse(dto.conversation_ended)
        self.assertFalse(self.env['customer.inquiry'].search([
            ('conversation_id.session_id', '=', 'facebook:PSID-NAME'),
        ]))

    def test_ended_psid_starts_new_conversation(self):
        service = self._service()
        info = {
            'name': 'Ada Lovelace',
            'email': 'ada@example.com',
            'phone': None,
            'datetime': None,
        }
        with patch.object(
            type(self.env['chatbot.config']), 'parse_user_info', return_value=info
        ), patch.object(service, 'send_reply', return_value=None):
            service.chat(
                'Ada Lovelace ada@example.com',
                'PSID-RE',
                facebook_sender_id='PSID-RE',
            )
        first = self.env['chatbot.conversation'].search([
            ('session_id', '=', 'facebook:PSID-RE'),
        ])
        self.assertEqual(len(first), 1)
        self.assertEqual(first.status, 'ended')
        with patch.object(
            type(self.env['chatbot.config']),
            'parse_user_info',
            return_value={'name': None, 'email': None, 'phone': None, 'datetime': None},
        ), patch.object(service, 'send_reply', return_value=None):
            service.chat('hello again', 'PSID-RE', facebook_sender_id='PSID-RE')
        convs = self.env['chatbot.conversation'].search([
            ('session_id', '=', 'facebook:PSID-RE'),
        ], order='id')
        self.assertEqual(len(convs), 2)
        self.assertEqual(convs[0].status, 'ended')
        self.assertEqual(convs[1].status, 'active')
        self.assertEqual(first.id, convs[0].id)

    def test_user_cannot_read_unassigned_inquiry(self):
        source = self.env['inquiry.source'].search([('code', '=', 'facebook')], limit=1)
        inquiry = self.env['customer.inquiry'].sudo().create({
            'name': 'Hidden Lead',
            'email': 'hidden@example.com',
            'message': 'from facebook',
            'source_id': source.id,
        })
        group = self.env.ref('isd_chatbot.group_chatbot_user', raise_if_not_found=False)
        if not group:
            self.skipTest('Chatbot user group missing')
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Chatbot User FB',
            'login': 'fb_chatbot_user',
            'groups_id': [(6, 0, [
                group.id,
                self.env.ref('base.group_user').id,
            ])],
        })
        visible = self.env['customer.inquiry'].with_user(user).search([
            ('id', '=', inquiry.id),
        ])
        self.assertFalse(visible)

    def test_facebook_source_exists_and_filters(self):
        source = self.env['inquiry.source'].search([('code', '=', 'facebook')], limit=1)
        self.assertTrue(source)
        fb = self.env['customer.inquiry'].create({
            'name': 'FB Lead',
            'email': 'fb@example.com',
            'message': 'fb',
            'source_id': source.id,
        })
        chatbot = self.env['inquiry.source'].search([('code', '=', 'chatbot')], limit=1)
        if chatbot:
            self.env['customer.inquiry'].create({
                'name': 'Web Lead',
                'email': 'web@example.com',
                'message': 'web',
                'source_id': chatbot.id,
            })
        only_fb = self.env['customer.inquiry'].search([
            ('source_id.code', '=', 'facebook'),
            ('id', 'in', fb.ids + (chatbot and chatbot.ids or [])),
        ])
        self.assertIn(fb, only_fb)
        self.assertTrue(all(r.source_id.code == 'facebook' for r in only_fb))

    def test_graph_non_190_no_retry_and_190_refresh_once(self):
        service = self._service()

        def fail_other(*_a, **_k):
            return 'error'

        service._send_facebook_message = MagicMock(side_effect=fail_other)
        service._refresh_page_token = MagicMock(return_value='new-token')
        status = service.send_reply('PSID', 'hello')
        self.assertEqual(status, 'error')
        service._refresh_page_token.assert_not_called()
        self.assertEqual(service._send_facebook_message.call_count, 1)

        service._send_facebook_message = MagicMock(side_effect=['expired', None])
        service._refresh_page_token = MagicMock(return_value='new-token')
        status = service.send_reply('PSID', 'hello')
        self.assertIsNone(status)
        service._refresh_page_token.assert_called_once()
        self.assertEqual(service._send_facebook_message.call_count, 2)

        service._send_facebook_message = MagicMock(side_effect=['expired', 'expired'])
        service._refresh_page_token = MagicMock(return_value='new-token')
        status = service.send_reply('PSID', 'hello')
        self.assertEqual(status, 'expired')
        self.assertEqual(service._send_facebook_message.call_count, 2)

    def test_dedup_mid_skips_second_chat(self):
        service = self._service()
        with patch.object(service, 'send_reply', return_value=None):
            service.chat(
                'hello', 'PSID-DEDUP',
                facebook_sender_id='PSID-DEDUP',
                external_message_id='m_unique',
            )
            service.chat(
                'hello', 'PSID-DEDUP',
                facebook_sender_id='PSID-DEDUP',
                external_message_id='m_unique',
            )
        self.assertEqual(self.env['chatbot.message'].search_count([
            ('external_message_id', '=', 'm_unique'),
        ]), 1)
