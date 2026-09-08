# -*- coding: utf-8 -*-

import hashlib
import hmac
import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase


def _sign(body, secret):
    raw = body.encode('utf-8') if isinstance(body, str) else body
    digest = hmac.new(secret.encode('utf-8'), raw, hashlib.sha256).hexdigest()
    return 'sha256=%s' % digest


def _fb_text_payload(psid='PSID1', text='hello', mid='m_1', page_id='PAGE1', is_echo=False):
    message = {'mid': mid, 'text': text}
    if is_echo:
        message['is_echo'] = True
    return {
        'object': 'page',
        'entry': [{
            'id': page_id,
            'messaging': [{
                'sender': {'id': psid},
                'recipient': {'id': page_id},
                'message': message,
            }],
        }],
    }


@tagged('post_install', '-at_install', 'isd_chatbot')
class TestFacebookWebhook(HttpCase):

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('isd_chatbot.facebook_enabled', True)
        ICP.set_param('isd_chatbot.facebook_page_access_token', 'page-token')
        ICP.set_param('isd_chatbot.facebook_app_secret', 'app-secret')
        ICP.set_param('isd_chatbot.facebook_app_id', 'app-id')
        ICP.set_param('isd_chatbot.facebook_verify_token', 'verify-me')
        ICP.set_param('isd_chatbot.facebook_page_id', 'PAGE1')
        ICP.set_param('isd_chatbot.widget_messenger_link', 'https://m.me/testpage')
        self._secret = 'app-secret'

    def _post_facebook(self, payload, signed=True, merchant='facebook'):
        body = json.dumps(payload)
        headers = {'Content-Type': 'application/json'}
        if signed:
            headers['X-Hub-Signature-256'] = _sign(body, self._secret)
        url = '/isd_chatbot/webhook?merchant=%s' % merchant
        resp = self.url_open(url, data=body, headers=headers)
        self.env.invalidate_all()
        return resp

    def test_signed_text_creates_facebook_conversation(self):
        from unittest.mock import patch
        with patch(
            'odoo.addons.isd_chatbot.services.chatbot_service.FacebookChatbotServiceAdapter.send_reply',
            return_value=None,
        ):
            resp = self._post_facebook(_fb_text_payload(text='hello'))
        self.assertEqual(resp.status_code, 200)
        self.env.invalidate_all()
        conv = self.env['chatbot.conversation'].sudo().search([
            ('session_id', '=', 'facebook:PSID1'),
        ], limit=1)
        self.assertTrue(conv)
        self.assertEqual(conv.source_id.code, 'facebook')
        self.assertTrue(conv.message_ids)

    def test_disabled_creates_no_conversation(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'isd_chatbot.facebook_enabled', False)
        before = self.env['chatbot.conversation'].sudo().search_count([])
        resp = self._post_facebook(_fb_text_payload(mid='m_disabled'))
        self.assertEqual(resp.status_code, 200)
        after = self.env['chatbot.conversation'].sudo().search_count([])
        self.assertEqual(before, after)

    def test_unconfigured_creates_no_conversation(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'isd_chatbot.facebook_page_access_token', '')
        before = self.env['chatbot.conversation'].sudo().search_count([])
        resp = self._post_facebook(_fb_text_payload(mid='m_unconf'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            before, self.env['chatbot.conversation'].sudo().search_count([]))

    def test_widget_chat_still_works_when_facebook_disabled(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'isd_chatbot.facebook_enabled', False)
        payload = json.dumps({
            'params': {'message': 'hello', 'session_id': 'widget-sess-1'},
        })
        resp = self.url_open(
            '/chatbot/api/chat',
            data=payload,
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content.decode('utf-8'))
        self.assertTrue(data.get('result', {}).get('success'))

    def test_get_verify_success_and_failures(self):
        ok = self.url_open(
            '/isd_chatbot/webhook?merchant=facebook&hub.mode=subscribe'
            '&hub.verify_token=verify-me&hub.challenge=abc123')
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.content.decode('utf-8'), 'abc123')

        bad = self.url_open(
            '/isd_chatbot/webhook?merchant=facebook&hub.mode=subscribe'
            '&hub.verify_token=wrong&hub.challenge=abc123')
        self.assertEqual(bad.status_code, 403)

        self.env['ir.config_parameter'].sudo().set_param(
            'isd_chatbot.facebook_enabled', False)
        disabled = self.url_open(
            '/isd_chatbot/webhook?merchant=facebook&hub.mode=subscribe'
            '&hub.verify_token=verify-me&hub.challenge=abc123')
        self.assertEqual(disabled.status_code, 403)

        missing = self.url_open(
            '/isd_chatbot/webhook?hub.mode=subscribe'
            '&hub.verify_token=verify-me&hub.challenge=abc123')
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.content.decode('utf-8'), '')

    def test_bad_signature_and_missing_merchant(self):
        before = self.env['chatbot.conversation'].sudo().search_count([])
        resp = self._post_facebook(_fb_text_payload(mid='m_badsig'), signed=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            before, self.env['chatbot.conversation'].sudo().search_count([]))

        resp2 = self.url_open(
            '/isd_chatbot/webhook',
            data=json.dumps(_fb_text_payload(mid='m_nomerc')),
            headers={
                'Content-Type': 'application/json',
                'X-Hub-Signature-256': _sign(
                    json.dumps(_fb_text_payload(mid='m_nomerc')), self._secret),
            },
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(
            before, self.env['chatbot.conversation'].sudo().search_count([]))

    def test_echo_and_replay_mid(self):
        from unittest.mock import patch
        with patch(
            'odoo.addons.isd_chatbot.services.chatbot_service.FacebookChatbotServiceAdapter.send_reply',
            return_value=None,
        ):
            echo = self._post_facebook(
                _fb_text_payload(text='hi', mid='m_echo', is_echo=True))
            self.assertEqual(echo.status_code, 200)
            self.assertFalse(self.env['chatbot.message'].sudo().search([
                ('external_message_id', '=', 'm_echo'),
            ]))

            first = self._post_facebook(
                _fb_text_payload(text='hello again', mid='m_replay'))
            self.assertEqual(first.status_code, 200)
            count = self.env['chatbot.message'].sudo().search_count([
                ('external_message_id', '=', 'm_replay'),
            ])
            self.assertEqual(count, 1)
            second = self._post_facebook(
                _fb_text_payload(text='hello again', mid='m_replay'))
            self.assertEqual(second.status_code, 200)
            self.assertEqual(self.env['chatbot.message'].sudo().search_count([
                ('external_message_id', '=', 'm_replay'),
            ]), 1)

    def test_channel_query_ignored_zalo_merchant_routes(self):
        from unittest.mock import patch
        before = self.env['chatbot.conversation'].sudo().search_count([
            ('session_id', 'like', 'facebook:%'),
        ])
        body = json.dumps(_fb_text_payload(mid='m_channel'))
        resp = self.url_open(
            '/isd_chatbot/webhook?channel=facebook',
            data=body,
            headers={
                'Content-Type': 'application/json',
                'X-Hub-Signature-256': _sign(body, self._secret),
            },
        )
        self.assertEqual(resp.status_code, 200)
        after = self.env['chatbot.conversation'].sudo().search_count([
            ('session_id', 'like', 'facebook:%'),
        ])
        self.assertEqual(before, after)

        with patch(
            'odoo.addons.isd_chatbot.services.chatbot_service.ZaloChatbotServiceAdapter.chat',
            autospec=True,
        ) as zalo_chat:
            zalo_body = json.dumps({
                'message': {'text': 'zalo hi'},
                'sender': {'id': 'ZALO1'},
            })
            zresp = self.url_open(
                '/isd_chatbot/webhook?merchant=zalo',
                data=zalo_body,
                headers={'Content-Type': 'application/json'},
            )
            self.assertEqual(zresp.status_code, 200)
            self.assertTrue(zalo_chat.called)

    def test_widget_js_keeps_messenger_link_when_facebook_off(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'isd_chatbot.facebook_enabled', False)
        resp = self.url_open('/chatbot/widget.js')
        self.assertEqual(resp.status_code, 200)
        js = resp.content.decode('utf-8')
        self.assertIn('https://m.me/testpage', js)
        self.assertNotIn('page-token', js)
        self.assertNotIn('app-secret', js)
        self.assertNotIn('verify-me', js)
