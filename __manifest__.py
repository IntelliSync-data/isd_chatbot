# -*- coding: utf-8 -*-
{
    'name': 'ISD Chatbot',
    'version': '18.0.1.0.0',
    'summary': 'Intelligent Chatbot for Odoo 18.0 with CRM and Calendar Integration',
    'description': """
        This module provides an intelligent chatbot for Odoo 18.0, allowing
        for automated conversation handling, customer inquiry collection,
        and seamless integration with Odoo CRM, Calendar, and Email.
        
        Features:
        - Easy integration with JavaScript snippet
        - Intelligent conversation handling with spaCy NLP
        - Customer inquiry collection and management
        - CRM and Calendar integration
        - Automated email notifications
    """,
    'author': 'ISD Company',
    'website': 'https://intellisyncdata.com',
    'category': 'ISD Modules',
    'depends': ['base', 'crm', 'calendar', 'mail', 'web', 'survey', 'openeducat_core'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/default_data.xml',
        'data/inquiry_source_data.xml',
        'data/webhook_cron.xml',
        'views/a_res_config_settings_views.xml',
        'views/chatbot_config_views.xml',
        'views/customer_inquiry_views.xml',
        'views/chatbot_conversation_views.xml',
        'views/webhook_log_views.xml',
        'views/menu_items.xml',
        'views/survey_mapping_views.xml',
        'views/inquiry_source_views.xml',
        'wizard/views/customer_inquiry_analyze_confirm_view.xml',
        'wizard/views/inquiry_api_doc_wizard_view.xml',
    ],
    # 'assets': {
    #     'web.assets_frontend': [
    #         'isd_chatbot/static/src/js/chatbot_widget.js',
    #         'isd_chatbot/static/src/xml/chatbot_widget.xml',
    #     ],
    # },
    'external_dependencies': {
        'python': ['spacy'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
