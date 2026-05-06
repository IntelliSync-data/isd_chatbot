# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class InquiryAPIController(http.Controller):
    """REST API Controller for Customer Inquiry CRUD operations"""

    def _json_response(self, data, status=200):
        """Return JSON response with proper headers"""
        return Response(
            json.dumps(data, ensure_ascii=False),
            content_type='application/json; charset=utf-8',
            status=status
        )

    def _get_inquiry_source_id(self, source_code):
        """Get inquiry source ID by code"""
        if not source_code:
            return False
        source = request.env['inquiry.source'].sudo().search([('code', '=', source_code)], limit=1)
        return source.id if source else False

    def _validate_inquiry_data(self, data, is_create=True):
        """Validate inquiry data"""
        errors = []

        # Required fields for creation
        if is_create:
            if not data.get('name'):
                errors.append("Field 'name' is required")

            # Must have at least email or phone
            if not data.get('email') and not data.get('phone'):
                errors.append("At least 'email' or 'phone' must be provided")

        # Validate email format if provided
        if data.get('email'):
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, data['email']):
                errors.append("Invalid email format")

        return errors

    def _prepare_inquiry_response(self, inquiry):
        """Prepare inquiry data for API response"""
        return {
            'id': inquiry.id,
            'name': inquiry.name,
            'email': inquiry.email or '',
            'phone': inquiry.phone or '',
            'message': inquiry.message or '',
            'analyzed_message': inquiry.analyzed_message or '',
            'consultation_datetime': inquiry.consultation_datetime.isoformat() if inquiry.consultation_datetime else None,
            'state': inquiry.state,
            'analyzed': inquiry.analyzed,
            'analysis_date': inquiry.analysis_date.isoformat() if inquiry.analysis_date else None,
            'source': {
                'id': inquiry.source_id.id if inquiry.source_id else None,
                'code': inquiry.source_id.code if inquiry.source_id else None,
                'name': inquiry.source_id.name if inquiry.source_id else None,
            },
            'assigned_user': {
                'id': inquiry.assigned_user_id.id if inquiry.assigned_user_id else None,
                'name': inquiry.assigned_user_id.name if inquiry.assigned_user_id else None,
            },
            'crm_lead_id': inquiry.crm_lead_id.id if inquiry.crm_lead_id else None,
            'calendar_event_id': inquiry.calendar_event_id.id if inquiry.calendar_event_id else None,
            'create_date': inquiry.create_date.isoformat() if inquiry.create_date else None,
            'write_date': inquiry.write_date.isoformat() if inquiry.write_date else None,
        }

    @http.route('/api/inquiry', type='http', auth='public', methods=['POST'], csrf=False)
    def create_inquiry(self, **kwargs):
        """
        Create a new customer inquiry

        POST /api/inquiry

        Request body (JSON):
        {
            "name": "Nguyen Van A",                      // Required
            "email": "test@example.com",                 // Optional (need email OR phone)
            "phone": "0123456789",                       // Optional (need email OR phone)
            "message": "Tôi muốn tư vấn du học",        // Optional
            "consultation_datetime": "2026-01-10 14:30:00",  // Optional
            "source_code": "manual",                     // Optional: chatbot, manual, zalo, facebook, website, phone_call, email, other
            "assigned_user_email": "admin@example.com"   // Optional: Email của user được assign
        }

        Response:
        {
            "success": true,
            "data": {...},
            "message": "Inquiry created successfully"
        }
        """
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))

            # Validate data
            errors = self._validate_inquiry_data(data, is_create=True)
            if errors:
                return self._json_response({
                    'success': False,
                    'errors': errors,
                    'message': 'Validation failed'
                }, status=400)

            # Get source ID
            source_id = self._get_inquiry_source_id(data.get('source_code', 'manual'))

            # Get assigned user by email if provided
            assigned_user_id = False
            if data.get('assigned_user_email'):
                user = request.env['res.users'].sudo().search([
                    ('email', '=', data['assigned_user_email'])
                ], limit=1)
                if user:
                    assigned_user_id = user.id

            # Prepare inquiry values
            inquiry_vals = {
                'name': data['name'],
                'email': data.get('email', False),
                'phone': data.get('phone', False),
                'message': data.get('message', ''),
                'consultation_datetime': data.get('consultation_datetime', False),
                'source_id': source_id,
                'assigned_user_id': assigned_user_id,
            }

            # Create inquiry
            inquiry = request.env['customer.inquiry'].sudo().create(inquiry_vals)

            _logger.info(f"Created inquiry {inquiry.id} via API")

            return self._json_response({
                'success': True,
                'data': self._prepare_inquiry_response(inquiry),
                'message': 'Inquiry created successfully'
            })

        except Exception as e:
            _logger.error(f"Error creating inquiry via API: {str(e)}")
            return self._json_response({
                'success': False,
                'error': str(e),
                'message': 'Failed to create inquiry'
            }, status=500)

    @http.route('/api/inquiry/<int:inquiry_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_inquiry(self, inquiry_id, **kwargs):
        """
        Get inquiry by ID

        GET /api/inquiry/{id}

        Response:
        {
            "success": true,
            "data": {...}
        }
        """
        try:
            inquiry = request.env['customer.inquiry'].sudo().browse(inquiry_id)

            if not inquiry.exists():
                return self._json_response({
                    'success': False,
                    'error': 'Inquiry not found',
                    'message': f'Inquiry with ID {inquiry_id} does not exist'
                }, status=404)

            return self._json_response({
                'success': True,
                'data': self._prepare_inquiry_response(inquiry)
            })

        except Exception as e:
            _logger.error(f"Error getting inquiry {inquiry_id}: {str(e)}")
            return self._json_response({
                'success': False,
                'error': str(e),
                'message': 'Failed to get inquiry'
            }, status=500)

    @http.route('/api/inquiry/list', type='http', auth='public', methods=['GET'], csrf=False)
    def list_inquiries(self, **kwargs):
        """
        List inquiries with optional filters

        GET /api/inquiry/list?limit=10&offset=0&state=new&source_code=chatbot

        Query parameters:
        - limit: Number of records (default: 10, max: 100)
        - offset: Offset for pagination (default: 0)
        - state: Filter by state (new, saved_to_crm, booked)
        - source_code: Filter by source code
        - analyzed: Filter by analyzed status (true/false)

        Response:
        {
            "success": true,
            "data": [...],
            "total": 50,
            "limit": 10,
            "offset": 0
        }
        """
        try:
            # Get pagination parameters from query string
            limit = min(int(kwargs.get('limit', 10)), 100)
            offset = int(kwargs.get('offset', 0))

            # Build domain
            domain = []

            if kwargs.get('state'):
                domain.append(('state', '=', kwargs['state']))

            if kwargs.get('source_code'):
                source = request.env['inquiry.source'].sudo().search([('code', '=', kwargs['source_code'])], limit=1)
                if source:
                    domain.append(('source_id', '=', source.id))

            if kwargs.get('analyzed') is not None:
                analyzed = str(kwargs['analyzed']).lower() == 'true'
                domain.append(('analyzed', '=', analyzed))

            # Get total count
            total = request.env['customer.inquiry'].sudo().search_count(domain)

            # Get inquiries
            inquiries = request.env['customer.inquiry'].sudo().search(
                domain,
                limit=limit,
                offset=offset,
                order='create_date desc'
            )

            return self._json_response({
                'success': True,
                'data': [self._prepare_inquiry_response(inquiry) for inquiry in inquiries],
                'total': total,
                'limit': limit,
                'offset': offset
            })

        except Exception as e:
            _logger.error(f"Error listing inquiries: {str(e)}")
            return self._json_response({
                'success': False,
                'error': str(e),
                'message': 'Failed to list inquiries'
            }, status=500)

    @http.route('/api/inquiry/<int:inquiry_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    def update_inquiry(self, inquiry_id, **kwargs):
        """
        Update inquiry by ID

        PUT /api/inquiry/{id}

        Request body (JSON):
        {
            "name": "Updated Name",
            "email": "updated@example.com",
            "phone": "0987654321"
        }

        Response:
        {
            "success": true,
            "data": {...},
            "message": "Inquiry updated successfully"
        }
        """
        try:
            inquiry = request.env['customer.inquiry'].sudo().browse(inquiry_id)

            if not inquiry.exists():
                return self._json_response({
                    'success': False,
                    'error': 'Inquiry not found',
                    'message': f'Inquiry with ID {inquiry_id} does not exist'
                }, status=404)

            data = json.loads(request.httprequest.data.decode('utf-8'))

            # Validate data
            errors = self._validate_inquiry_data(data, is_create=False)
            if errors:
                return self._json_response({
                    'success': False,
                    'errors': errors,
                    'message': 'Validation failed'
                }, status=400)

            # Prepare update values
            update_vals = {}

            # Only update provided fields
            if 'name' in data:
                update_vals['name'] = data['name']
            if 'email' in data:
                update_vals['email'] = data['email']
            if 'phone' in data:
                update_vals['phone'] = data['phone']
            if 'message' in data:
                update_vals['message'] = data['message']
            if 'source_code' in data:
                source_id = self._get_inquiry_source_id(data['source_code'])
                if source_id:
                    update_vals['source_id'] = source_id

            # Update inquiry
            inquiry.write(update_vals)

            _logger.info(f"Updated inquiry {inquiry_id} via API")

            return self._json_response({
                'success': True,
                'data': self._prepare_inquiry_response(inquiry),
                'message': 'Inquiry updated successfully'
            })

        except Exception as e:
            _logger.error(f"Error updating inquiry {inquiry_id}: {str(e)}")
            return self._json_response({
                'success': False,
                'error': str(e),
                'message': 'Failed to update inquiry'
            }, status=500)

    @http.route('/api/inquiry/<int:inquiry_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_inquiry(self, inquiry_id, **kwargs):
        """
        Delete inquiry by ID

        DELETE /api/inquiry/{id}

        Response:
        {
            "success": true,
            "message": "Inquiry deleted successfully"
        }
        """
        try:
            inquiry = request.env['customer.inquiry'].sudo().browse(inquiry_id)

            if not inquiry.exists():
                return self._json_response({
                    'success': False,
                    'error': 'Inquiry not found',
                    'message': f'Inquiry with ID {inquiry_id} does not exist'
                }, status=404)

            inquiry.unlink()

            _logger.info(f"Deleted inquiry {inquiry_id} via API")

            return self._json_response({
                'success': True,
                'message': 'Inquiry deleted successfully'
            })

        except Exception as e:
            _logger.error(f"Error deleting inquiry {inquiry_id}: {str(e)}")
            return self._json_response({
                'success': False,
                'error': str(e),
                'message': 'Failed to delete inquiry'
            }, status=500)

    @http.route('/api/inquiry/<int:inquiry_id>/analyze', type='http', auth='public', methods=['POST'], csrf=False)
    def analyze_inquiry(self, inquiry_id, **kwargs):
        """
        Analyze inquiry message using AI

        POST /api/inquiry/{id}/analyze

        Response:
        {
            "success": true,
            "data": {...},
            "message": "Inquiry analyzed successfully"
        }
        """
        try:
            inquiry = request.env['customer.inquiry'].sudo().browse(inquiry_id)

            if not inquiry.exists():
                return self._json_response({
                    'success': False,
                    'error': 'Inquiry not found',
                    'message': f'Inquiry with ID {inquiry_id} does not exist'
                }, status=404)

            if not inquiry.message:
                return self._json_response({
                    'success': False,
                    'error': 'No message to analyze',
                    'message': 'Inquiry has no message content'
                }, status=400)

            # Perform analysis
            inquiry._analyze_message()

            _logger.info(f"Analyzed inquiry {inquiry_id} via API")

            return self._json_response({
                'success': True,
                'data': self._prepare_inquiry_response(inquiry),
                'message': 'Inquiry analyzed successfully'
            })

        except Exception as e:
            _logger.error(f"Error analyzing inquiry {inquiry_id}: {str(e)}")
            return self._json_response({
                'success': False,
                'error': str(e),
                'message': 'Failed to analyze inquiry'
            }, status=500)
