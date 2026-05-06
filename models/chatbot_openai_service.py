# -*- coding: utf-8 -*-

import json
import requests
import re
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ChatbotOpenAIService(models.AbstractModel):
    """Service for OpenAI API integration"""
    _name = 'chatbot.openai.service'
    _description = 'ChatBot OpenAI Service'

    @api.model
    def is_openai_available(self):
        """Check if OpenAI service is available and configured"""
        try:
            config = self.env['chatbot.config']._sync_config_parameters()
            return (
                config.openai_enabled and 
                (config.openai_api_key or '').strip()
            )
        except Exception as e:
            _logger.error(f"Error checking OpenAI availability: {e}")
            return False

    @api.model
    def get_openai_config(self):
        """Get OpenAI configuration"""
        config = self.env['chatbot.config']._sync_config_parameters()
        
        if not config.openai_enabled:
            raise UserError(_("OpenAI API not enabled in configuration"))
            
        api_key = (config.openai_api_key or '').strip()
        if not api_key:
            raise UserError(_("OpenAI API key not configured"))
        
        return {
            'api_key': api_key,
            'model': config.openai_model or 'gpt-3.5-turbo',
            'enabled': True
        }

    @api.model
    def extract_customer_info(self, message):
        """
        Extract customer information from message using OpenAI

        Args:
            message (str): Customer message to analyze

        Returns:
            dict: Extracted information or error details

        Structure:
            {
                'success': bool,
                'data': {
                    'name': str or None,
                    'email': str or None,
                    'phone': str or None,
                    'datetime': str or None (ISO format)
                },
                'log': list of log messages,
                'error': str or None
            }
        """
        log = []
        
        try:
            # Get configuration
            config = self.get_openai_config()
            log.append(f"Using OpenAI model: {config['model']}")
            
            # Prepare API request
            system_prompt = """You are an information extraction assistant for a Vietnamese chatbot for study abroad consultation.
Extract the following information from the user's message in Vietnamese:
- Name (tên)
- Email address (email)
- Phone number (số điện thoại)
- Datetime for consultation (ngày giờ tư vấn)

Return the information in a JSON format with keys: name, email, phone, datetime.
If any information is missing, leave its value as null.
For datetime, standardize to ISO format YYYY-MM-DD HH:MM if possible, get everything regarding datetime on this prompt.
Only return the JSON without any explanations or other text."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config['api_key']}"
            }
            
            payload = {
                "model": config['model'],
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 500
            }
            
            log.append("Calling OpenAI API...")
            
            # Make API call
            response = requests.post(
                "https://api.openai.com/v1/chat/completions", 
                headers=headers,
                json=payload,
                timeout=30  # Add timeout for security
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            log.append("OpenAI API call successful")
            
            # Extract content from response
            if 'choices' not in response_data or not response_data['choices']:
                log.append("No choices in OpenAI response")
                return {
                    'success': False,
                    'data': {},
                    'log': log,
                    'error': 'No response from OpenAI'
                }
            
            content = response_data['choices'][0]['message']['content']
            log.append(f"Raw API response: {content}")
            
            # Parse JSON response
            try:
                # Find JSON content (in case there's surrounding text)
                json_match = re.search(r'(\{.*\})', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                    
                extracted_info = json.loads(content)
                log.append("Successfully parsed JSON response")
                
                # Validate and clean extracted data
                cleaned_data = self._clean_extracted_data(extracted_info, log)
                
                return {
                    'success': True,
                    'data': cleaned_data,
                    'log': log,
                    'error': None
                }
                
            except json.JSONDecodeError as e:
                log.append(f"Error parsing JSON: {e}")
                return {
                    'success': False,
                    'data': {},
                    'log': log,
                    'error': f'Failed to parse OpenAI response: {str(e)}'
                }
                
        except requests.exceptions.RequestException as e:
            log.append(f"API request error: {e}")
            return {
                'success': False,
                'data': {},
                'log': log,
                'error': f'Error calling OpenAI API: {str(e)}'
            }
        except Exception as e:
            log.append(f"Unexpected error: {e}")
            return {
                'success': False,
                'data': {},
                'log': log,
                'error': f'Unexpected error: {str(e)}'
            }

    @api.model
    def _clean_extracted_data(self, raw_data, log):
        """
        Clean and validate extracted data
        
        Args:
            raw_data (dict): Raw data from OpenAI
            log (list): Log messages list to append to
            
        Returns:
            dict: Cleaned data
        """
        cleaned = {}
        
        # Clean name
        if raw_data.get('name'):
            cleaned['name'] = str(raw_data['name']).strip()
            log.append(f"Extracted name: {cleaned['name']}")
        
        # Clean email
        if raw_data.get('email'):
            cleaned['email'] = str(raw_data['email']).strip().lower()
            log.append(f"Extracted email: {cleaned['email']}")
        
        # Clean phone
        if raw_data.get('phone'):
            # Remove spaces and special characters but preserve the format
            clean_phone = re.sub(r'[-\s.]', '', str(raw_data['phone']))
            cleaned['phone'] = clean_phone
            log.append(f"Extracted phone: {clean_phone}")

        # Clean datetime
        if raw_data.get('datetime'):
            try:
                from datetime import datetime
                import pytz
                
                datetime_str = str(raw_data['datetime'])
                
                # Handle timezone information
                if 'Z' in datetime_str:  # UTC time
                    datetime_str = datetime_str.replace('Z', '+00:00')
                elif '+' not in datetime_str and '-' not in datetime_str[-6:]:
                    # If no timezone, assume Vietnam timezone (UTC+7)
                    datetime_str = f"{datetime_str}+07:00"
                    
                # Parse datetime string to datetime object with timezone
                dt = datetime.fromisoformat(datetime_str)
                
                # Convert to naive datetime for Odoo (remove timezone info)
                if dt.tzinfo:
                    dt = dt.astimezone(pytz.UTC)
                    dt = dt.replace(tzinfo=None)
                    
                cleaned['datetime'] = dt
                log.append(f"Extracted datetime: {dt} (will display in user timezone)")
            except Exception as e:
                log.append(f"Error parsing datetime: {e} - Value: {raw_data['datetime']}")
        
        return cleaned