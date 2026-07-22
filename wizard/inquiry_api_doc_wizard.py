# -*- coding: utf-8 -*-
from odoo import models, fields, api


class InquiryApiDocWizard(models.TransientModel):
    _name = 'inquiry.api.doc.wizard'
    _description = 'Inquiry API Documentation'

    api_documentation = fields.Html(string='API Documentation', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'api_documentation' in fields_list:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
            res['api_documentation'] = self._generate_docs(base_url)
        return res

    def _generate_docs(self, base_url):
        return f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto;">

<h2 style="color: #875a7b; border-bottom: 2px solid #875a7b; padding-bottom: 8px;">Customer Inquiry API</h2>

<p style="color: #666;">Base URL: <code style="background: #f4f4f4; padding: 2px 8px; border-radius: 4px;">{base_url}</code></p>

<!-- CREATE -->
<div style="background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #28a745;">
<h3 style="margin-top:0;"><span style="background: #28a745; color: white; padding: 2px 10px; border-radius: 4px; font-size: 13px;">POST</span> &nbsp; /api/inquiry</h3>
<p><strong>Create a new customer inquiry</strong></p>
<p><strong>Request body (JSON):</strong></p>
<pre style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; overflow-x: auto;">{{
  "name": "Nguyen Van A",                         // Required
  "email": "test@example.com",                    // Optional (need email OR phone)
  "phone": "0123456789",                          // Optional (need email OR phone)
  "message": "Tôi muốn tư vấn",                  // Optional
  "consultation_datetime": "2026-01-10 14:30:00", // Optional
  "source_code": "manual",                        // Optional: chatbot, manual, zalo, facebook, website, phone_call, email, other
  "assigned_user_email": "admin@example.com"      // Optional
}}</pre>
<p><strong>Response:</strong></p>
<pre style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; overflow-x: auto;">{{
  "success": true,
  "data": {{ "id": 1, "name": "...", "email": "...", "state": "new", ... }},
  "message": "Inquiry created successfully"
}}</pre>
<p><strong>cURL:</strong></p>
<pre style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; overflow-x: auto;">curl -X POST {base_url}/api/inquiry \\
  -H "Content-Type: application/json" \\
  -d '{{"name": "Test", "email": "test@example.com", "message": "Hello"}}'</pre>
</div>

<!-- GET BY ID -->
<div style="background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #007bff;">
<h3 style="margin-top:0;"><span style="background: #007bff; color: white; padding: 2px 10px; border-radius: 4px; font-size: 13px;">GET</span> &nbsp; /api/inquiry/&lt;id&gt;</h3>
<p><strong>Get inquiry by ID</strong></p>
<pre style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; overflow-x: auto;">curl {base_url}/api/inquiry/1</pre>
</div>

<!-- LIST -->
<div style="background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #007bff;">
<h3 style="margin-top:0;"><span style="background: #007bff; color: white; padding: 2px 10px; border-radius: 4px; font-size: 13px;">GET</span> &nbsp; /api/inquiry/list</h3>
<p><strong>List inquiries with filters &amp; pagination</strong></p>
<table style="width: 100%; border-collapse: collapse; margin: 8px 0;">
<tr style="background: #e9ecef;"><th style="padding: 6px 10px; text-align: left;">Param</th><th style="padding: 6px 10px; text-align: left;">Type</th><th style="padding: 6px 10px; text-align: left;">Description</th></tr>
<tr><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;"><code>limit</code></td><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;">int</td><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;">Max records (default 10, max 100)</td></tr>
<tr><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;"><code>offset</code></td><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;">int</td><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;">Pagination offset (default 0)</td></tr>
<tr><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;"><code>state</code></td><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;">string</td><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;">new, saved_to_crm, booked</td></tr>
<tr><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;"><code>source_code</code></td><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;">string</td><td style="padding: 6px 10px; border-bottom: 1px solid #dee2e6;">chatbot, manual, zalo, etc.</td></tr>
<tr><td style="padding: 6px 10px;"><code>analyzed</code></td><td style="padding: 6px 10px;">bool</td><td style="padding: 6px 10px;">true / false</td></tr>
</table>
<pre style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; overflow-x: auto;">curl "{base_url}/api/inquiry/list?limit=10&amp;state=new"</pre>
</div>

<!-- UPDATE -->
<div style="background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #ffc107;">
<h3 style="margin-top:0;"><span style="background: #ffc107; color: #333; padding: 2px 10px; border-radius: 4px; font-size: 13px;">PUT</span> &nbsp; /api/inquiry/&lt;id&gt;</h3>
<p><strong>Update an inquiry</strong></p>
<pre style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; overflow-x: auto;">curl -X PUT {base_url}/api/inquiry/1 \\
  -H "Content-Type: application/json" \\
  -d '{{"name": "Updated Name", "phone": "0987654321"}}'</pre>
</div>

<!-- DELETE -->
<div style="background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #dc3545;">
<h3 style="margin-top:0;"><span style="background: #dc3545; color: white; padding: 2px 10px; border-radius: 4px; font-size: 13px;">DELETE</span> &nbsp; /api/inquiry/&lt;id&gt;</h3>
<p><strong>Delete an inquiry</strong></p>
<pre style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; overflow-x: auto;">curl -X DELETE {base_url}/api/inquiry/1</pre>
</div>

<!-- ANALYZE -->
<div style="background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #6f42c1;">
<h3 style="margin-top:0;"><span style="background: #6f42c1; color: white; padding: 2px 10px; border-radius: 4px; font-size: 13px;">POST</span> &nbsp; /api/inquiry/&lt;id&gt;/analyze</h3>
<p><strong>Analyze inquiry message using AI</strong></p>
<pre style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; overflow-x: auto;">curl -X POST {base_url}/api/inquiry/1/analyze</pre>
</div>

<!-- Response structure -->
<h3 style="color: #875a7b; margin-top: 24px;">Response Data Structure</h3>
<pre style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; overflow-x: auto;">{{
  "id": 1,
  "name": "Nguyen Van A",
  "email": "test@example.com",
  "phone": "0123456789",
  "message": "...",
  "analyzed_message": "...",
  "consultation_datetime": "2026-01-10T14:30:00",
  "state": "new",              // new | saved_to_crm | booked
  "analyzed": false,
  "analysis_date": null,
  "source": {{ "id": 1, "code": "manual", "name": "Manual" }},
  "assigned_user": {{ "id": 2, "name": "Admin" }},
  "crm_lead_id": null,
  "calendar_event_id": null,
  "create_date": "2026-01-10T10:00:00",
  "write_date": "2026-01-10T10:00:00"
}}</pre>

</div>
"""
