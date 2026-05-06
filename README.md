# Odoo Chatbot Module

## Mô tả

Module Odoo Chatbot cung cấp một giải pháp chatbot thông minh cho Odoo 18.0, tích hợp với CRM, Calendar và hệ thống Email.

## Tính năng chính

- **Tích hợp dễ dàng**: JavaScript snippet để nhúng vào bất kỳ trang web nào
- **Xử lý hội thoại thông minh**: Sử dụng spaCy NLP để so khớp câu hỏi
- **Thu thập thông tin khách hàng**: Lưu trữ riêng biệt trước khi chuyển vào CRM
- **Tích hợp CRM**: Tự động tạo leads từ thông tin khách hàng
- **Quản lý lịch hẹn**: Tạo sự kiện Calendar và gửi email xác nhận
- **Giao diện quản lý**: Dashboard để quản lý cấu hình và thông tin khách hàng

## Cài đặt

### Yêu cầu hệ thống

1. **Odoo 18.0**
2. **Python packages** (đã được thêm vào requirements.txt):
   ```bash
   # Dependencies được cài tự động qua requirements.txt:
   # spacy==3.8.7
   # en_core_web_sm-3.8.0 (English language model)
   
   # Hoặc cài đặt thủ công:
   pip install spacy==3.8.7
   pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
   ```

### Cài đặt module

1. Copy thư mục `isd_chatbot` vào thư mục addons của Odoo
2. Restart Odoo server
3. Vào Apps, tìm "Odoo Chatbot" và cài đặt

## Cấu hình

### 1. Cấu hình Q&A

- Vào **Chatbot > Configuration > Q&A Configuration**
- Thêm các cặp câu hỏi - câu trả lời
- Điều chỉnh threshold (ngưỡng độ tương đồng)

### 2. Tích hợp vào website

Thêm đoạn code sau vào website của bạn:

```html
<!-- Odoo Chatbot Integration -->
<script src="http://your-odoo-domain.com/chatbot/widget.js"></script>
```

### 3. Quản lý thông tin khách hàng

- Vào **Chatbot > Customer Inquiries**
- Xem danh sách thông tin khách hàng từ chatbot
- Sử dụng các nút: "Save to CRM", "Add Datetime", "Booking"

## API Endpoints

- `GET /chatbot/widget.js` - JavaScript widget
- `POST /chatbot/api/chat` - Gửi tin nhắn đến chatbot
- `POST /chatbot/api/submit_info` - Gửi thông tin khách hàng
- `GET /chatbot/snippet` - Thông tin tích hợp

## Quy trình hoạt động

1. **Khách hàng gửi tin nhắn** → Chatbot sử dụng spaCy để tìm câu trả lời phù hợp
2. **Không tìm thấy câu trả lời** → Yêu cầu khách hàng nhập thông tin
3. **Thu thập thông tin** → Lưu vào database riêng (customer.inquiry)
4. **Quản lý xử lý** → "Save to CRM" để tạo lead
5. **Đặt lịch hẹn** → "Booking" để tạo calendar event và gửi email

## Tùy chỉnh

Module được thiết kế để dễ dàng tùy chỉnh:

- **Models**: Mở rộng các model trong `models/`
- **Views**: Tùy chỉnh giao diện trong `views/`
- **Controllers**: Thêm API endpoints trong `controllers/`
- **Frontend**: Tùy chỉnh widget trong `static/src/`

## Hỗ trợ

Để được hỗ trợ, vui lòng liên hệ qua email hoặc tạo issue trên repository.

## License

LGPL-3

