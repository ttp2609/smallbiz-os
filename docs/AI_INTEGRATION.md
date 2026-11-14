# SmallBiz OS V0.2 — AI provider và External Agent API

## Hai chế độ AI độc lập

1. **Built-in AI:** Chọn provider trong **AI Integration**, nhập key/model, bật `Automatically answer ...`, chuyển Inbox conversation sang **Built-in AI**. Server gọi Chat Completions API theo cấu hình từng business.
2. **External AI:** Chuyển conversation sang **External AI**, rồi dùng Bearer token của chính business để agent ngoài polling inbound → lấy context → gửi câu trả lời. Agent không cần dùng AI provider ở UI.

Chế độ mặc định **Human** không tự phản hồi. Không có AI reply nếu chưa cấu hình key hoặc chưa bật chế độ tương ứng.

## Built-in provider

Preset: OpenAI, Groq, DeepSeek, OpenRouter, Gemini (OpenAI-compatible). Chọn **Custom** cho API hỗ trợ format `POST {base_url}/chat/completions`.

- Request: `Authorization: Bearer <key>`, `{model,messages,temperature,max_tokens}`.
- Response: `choices[0].message.content` là string hoặc danh sách có phần tử text.
- Prompt hệ thống đưa vào business, dịch vụ, FAQ và lịch sử gần đây (khi có conversation ID).
- API test: `POST /api/ai/provider/test` và `POST /api/ai/chat` (cookie login). Không gửi SMS.
- Key được mã hóa và lưu backend; API GET chỉ cung cấp `key_set`, không trả raw key.
- AI không được phép tự đặt lịch thông qua tool-calling ở V0.2; muốn book, dùng External AI API dưới đây.

## External AI API

Gửi `Authorization: Bearer YOUR_WORKSPACE_INTEGRATION_TOKEN`. API token chỉ Owner được xem và rotate ở UI. Các route:

| Method | Route | Ý nghĩa |
|---|---|---|
| GET | `/api/integrations/ai/inbox` | Danh sách inbound chưa xử lý trong conversation mode External |
| GET | `/api/integrations/ai/context/{conversation_id}` | Business, contact, 25 messages, FAQ, services, staff |
| GET | `/api/integrations/ai/availability?date=YYYY-MM-DD&staff_id=1&service_id=1` | Booking slots theo timezone |
| POST | `/api/integrations/ai/reply` | Trả lời inbound, idempotent theo inbound_message_id |
| POST | `/api/integrations/ai/book` | Tạo booking có kiểm tra overlap và quyền business |
| POST | `/api/integrations/ai/handoff` | Trả hội thoại về Human |

Ví dụ:

```http
POST /api/integrations/ai/reply
Authorization: Bearer YOUR_WORKSPACE_INTEGRATION_TOKEN
Content-Type: application/json

{
  "conversation_id": 1,
  "inbound_message_id": 25,
  "reply": "Sure! Which service would you like?"
}
```

Output ở mode Mock là `mock_sent`; nếu chủ doanh nghiệp đã bật Twilio Live, hệ thống kiểm tra consent trước khi gửi đi. Trả lời tự động không đảm bảo khách đã đồng ý nhận marketing; cần quản trị consent theo quy định địa phương.

## Test and Voice endpoints

| Method | Route | Ý nghĩa |
|---|---|---|
| GET/PUT | `/api/ai/provider` | Cấu hình provider, nhận key mới qua PUT nhưng GET không trả key |
| GET/PUT | `/api/voice/config` | TTS/language/voice/STT locale/greeting/phone voice flag |
| POST | `/api/voice/speak` | Sinh MP3 từ `{ "text": "..." }`; trả `audio/mpeg` |
| POST | `/api/voice/turn` | Sinh text reply từ configured LLM; app UI gọi speak sau |
| GET/PUT | `/api/sms/config` | Chọn Mock/Twilio và cấu hình credential |

**Giới hạn:** Google gTTS/Edge-TTS chỉ là TTS, browser STT phụ thuộc trình duyệt; điện thoại sử dụng Twilio Gather và Twilio có thể tính phí STT. Chat Completions không đồng nghĩa agent có quyền gọi tool; muốn tự book cần External AI API hoặc phiên bản tích hợp công cụ sau.
