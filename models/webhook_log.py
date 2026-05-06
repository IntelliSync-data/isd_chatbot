# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)


class WebhookLog(models.Model):
    _name = 'chatbot.webhook.log'
    _description = 'Chatbot Webhook Log'
    _order = 'create_date desc'
    _rec_name = 'webhook_id'

    webhook_id = fields.Char(
        string='Webhook ID',
        readonly=True,
        help='Auto-generated webhook identifier'
    )
    
    json_data = fields.Text(
        string='Request Body',
        help='Raw request body data received from webhook'
    )
    
    json_data_formatted = fields.Text(
        string='Formatted JSON',
        compute='_compute_json_formatted',
        help='Pretty formatted JSON for better readability'
    )
    
    payload_size = fields.Integer(
        string='Payload Size (bytes)',
        compute='_compute_payload_size',
        store=True,
        help='Size of the JSON payload in bytes'
    )
    
    source_ip = fields.Char(
        string='Source IP',
        help='IP address of the webhook sender'
    )
    
    user_agent = fields.Text(
        string='User Agent',
        help='User agent of the webhook request'
    )
    
    http_method = fields.Char(
        string='HTTP Method',
        help='HTTP method used for the request (GET, POST, PUT, DELETE, PATCH)'
    )
    
    query_params = fields.Text(
        string='Query Parameters',
        help='URL query parameters from the request'
    )
    
    request_headers = fields.Text(
        string='Request Headers',
        help='HTTP headers from the request'
    )
    
    full_url = fields.Char(
        string='Full URL',
        help='Complete URL with query parameters'
    )
    
    webhook_type = fields.Char(
        string='Webhook Type',
        help='Type of webhook if specified in payload'
    )
    
    event_type = fields.Char(
        string='Event Type',
        help='Event type if specified in payload'
    )
    
    status = fields.Selection([
        ('received', 'Received'),
        ('processed', 'Processed'),
        ('error', 'Error'),
        ('ignored', 'Ignored')
    ], string='Status', default='received', required=True)
    
    processing_notes = fields.Text(
        string='Processing Notes',
        help='Notes about webhook processing'
    )
    
    error_message = fields.Text(
        string='Error Message',
        help='Error details if processing failed'
    )
    
    created_at = fields.Datetime(
        string='Received At',
        default=fields.Datetime.now,
        required=True,
        help='When the webhook was received'
    )
    
    updated_at = fields.Datetime(
        string='Last Updated',
        default=fields.Datetime.now,
        required=True,
        help='Last update timestamp'
    )
    
    processed_at = fields.Datetime(
        string='Processed At',
        help='When the webhook was processed'
    )

    def _generate_webhook_id(self):
        """Generate webhook ID after record creation"""
        if self.id:
            from datetime import datetime
            date_part = self.create_date.strftime('%Y%m%d') if self.create_date else datetime.now().strftime('%Y%m%d')
            return f"WH-{self.id:06d}-{date_part}"
        return "New Webhook"

    @api.depends('json_data')
    def _compute_json_formatted(self):
        for record in self:
            if record.json_data:
                try:
                    parsed_json = json.loads(record.json_data)
                    record.json_data_formatted = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    record.json_data_formatted = record.json_data
            else:
                record.json_data_formatted = ""

    @api.depends('json_data')
    def _compute_payload_size(self):
        for record in self:
            if record.json_data:
                record.payload_size = len(record.json_data.encode('utf-8'))
            else:
                record.payload_size = 0

    @api.model
    def create(self, vals):
        vals['updated_at'] = fields.Datetime.now()
        
        # Extract webhook metadata from JSON payload
        if vals.get('json_data'):
            try:
                payload = json.loads(vals['json_data'])
                
                # Extract common webhook fields
                if isinstance(payload, dict):
                    vals['webhook_type'] = payload.get('type', payload.get('webhook_type'))
                    vals['event_type'] = payload.get('event', payload.get('event_type'))
                    
            except (json.JSONDecodeError, TypeError) as e:
                _logger.warning(f"Failed to parse webhook JSON payload: {e}")
                vals['status'] = 'error'
                vals['error_message'] = f"Invalid JSON payload: {str(e)}"

        webhook_log = super().create(vals)
        
        # Generate webhook_id after creation when we have the ID
        webhook_log.webhook_id = webhook_log._generate_webhook_id()
        
        _logger.info(f"📥 WEBHOOK RECEIVED: {webhook_log.webhook_id} - Size: {webhook_log.payload_size} bytes")
        
        return webhook_log

    def write(self, vals):
        vals['updated_at'] = fields.Datetime.now()
        return super().write(vals)

    def action_mark_processed(self):
        """Mark webhook as processed"""
        self.write({
            'status': 'processed',
            'processed_at': fields.Datetime.now(),
            'processing_notes': 'Manually marked as processed'
        })

    def action_mark_error(self):
        """Mark webhook as error"""
        self.write({
            'status': 'error',
            'processing_notes': 'Manually marked as error'
        })

    def action_reprocess(self):
        """Reset webhook status for reprocessing"""
        self.write({
            'status': 'received',
            'processed_at': None,
            'error_message': None,
            'processing_notes': 'Reset for reprocessing'
        })

    def get_parsed_json(self):
        """Get parsed JSON data as Python object"""
        if not self.json_data:
            return None
        
        try:
            return json.loads(self.json_data)
        except (json.JSONDecodeError, TypeError):
            return None

    @api.model
    def cleanup_old_webhooks(self, days=30):
        """Clean up old webhook logs (called by cron job)"""
        cutoff_date = fields.Datetime.now() - fields.timedelta(days=days)
        old_webhooks = self.search([('create_date', '<', cutoff_date)])
        
        if old_webhooks:
            count = len(old_webhooks)
            old_webhooks.unlink()
            _logger.info(f"🧹 WEBHOOK CLEANUP: Deleted {count} webhook logs older than {days} days")
            
        return True