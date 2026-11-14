# SmallBiz OS — Demo V0.2.2

**CRM + Inbox + Booking + AI trả lời SMS/WhatsApp + Voice AI + Workflow kéo thả.** Ứng dụng demo dùng FastAPI, SQLite và HTML/CSS/JS, hỗ trợ nhiều doanh nghiệp với quyền Owner/Staff.

**Trạng thái ngày 14/11/2026:** 33/33 test backend đạt; kiểm tra giao diện bằng Edge đạt. Request ra provider trong các test được mock. Chưa xác nhận vận hành Meta, Twilio, LLM và TTS với tài khoản thật trong đợt này.

> Đây là bản demo local, chưa sẵn sàng triển khai production nguyên trạng: còn tài khoản mẫu, thiếu CSRF/rate limiting và các thành phần vận hành production. Tích hợp thật phải được cấu hình có chủ đích; cuộc gọi, tin nhắn và AI có thể phát sinh phí.

## 1. Chạy nhanh

Cần Python **3.10+**. Mở terminal tại thư mục có `server.py`:

```powershell
py -m pip install -r requirements.txt
py server.py
```

Hoặc nhấp đúp `run_windows.bat`; script cài dependencies rồi chạy app. Mở **http://127.0.0.1:8000** và đăng nhập:

| Email | Mật khẩu | Quyền |
|---|---|---|
| `demo@smallbiz.local` | `demo123` | Owner cả hai doanh nghiệp mẫu |
| `luna@demo.local` | `demo123` | Owner Luna Nail Studio |
| `bright@demo.local` | `demo123` | Owner BrightHome Services |
| `staff@luna.demo` | `demo123` | Staff Luna Nail Studio |

SQLite được tạo ở `demo.sqlite3`. API credentials được mã hóa bằng Fernet, khóa lưu tại `.smallbiz-fernet-key`. **Sao lưu cả database và khóa; không đưa chúng hoặc `.env` lên Git.**

Linux/macOS: `sh run_mac_linux.sh`. Docker: `docker compose up --build`, bind localhost và lưu dữ liệu trong volume `/data`.

## 2. Tính năng hiện có

| Phân hệ | Hành vi |
|---|---|
| Overview / Contacts / Inbox / Calendar | Quản lý khách, tin nhắn và lịch hẹn; lưu SQLite, cách ly từng doanh nghiệp |
| Giao diện | Thao tác nhanh trên Overview; Inbox mobile; điều hướng bàn phím; cấu hình kênh chia thành tab |
| AI assistant | OpenAI, Groq, DeepSeek, OpenRouter, Gemini hoặc Custom OpenAI-compatible; hướng dẫn riêng của Owner |
| SMS | Mock mặc định; Twilio gửi thật có cổng môi trường, consent và webhook ký HMAC |
| WhatsApp | Meta Cloud API, hội thoại riêng, text reply, STOP/START và giới hạn cửa sổ 24 giờ |
| Voice Lab | gTTS/Edge-TTS, nhiều ngôn ngữ; thử đọc văn bản hoặc AI trả lời bằng giọng nói |
| Phone calls | Gọi nhân viên trước, sau đó dùng AI/SMS hoặc kết thúc khi không kết nối được |
| External agent | API Bearer token theo doanh nghiệp cho agent ngoài |
| Automations | Workflow kéo thả, nối nhánh, lưu/bật/tắt, log và dry-run |

**Chưa có:** Payment/Billing, Google Calendar sync, voice streaming, công cụ tự đặt lịch cho Built-in AI, workflow scheduler/wait/loops và vận hành production đầy đủ.

## 3. Cấu hình AI và thông tin doanh nghiệp

1. Đăng nhập Owner, vào **AI & channels → AI assistant**.
2. Chọn provider, nhập **API key** và **Model name**, nhấn **Save AI connection**. Với **Custom**, nhập Base URL như `https://llm.example.com/v1`; backend gọi `{base_url}/chat/completions`. Không nhập cả đường dẫn `/chat/completions` vào Base URL.
3. Điền **Business reply guidance** (tối đa 1.500 ký tự) cho giọng điệu, cách trả lời và khi nào cần người thật. Thêm FAQ đã duyệt ở **Business knowledge**; cập nhật thông tin doanh nghiệp/dịch vụ để cung cấp giá, giờ và chính sách cho AI.
4. **Save & test connection** lưu cấu hình đang nhập rồi thử provider. **AI playground** dùng cấu hình đã lưu. Hai cách thử này có thể tiêu tốn token, không gửi tin nhắn cho khách.
5. Với SMS, bật **Automatically answer SMS conversations set to Built-in AI** và đặt hội thoại trong Inbox thành **Built-in AI**. Contact phải có consent SMS. WhatsApp có công tắc auto-reply riêng.

Ba chế độ Inbox: **Human** không tự trả lời; **Built-in AI** dùng provider đã cấu hình; **External AI** dùng agent ngoài qua API token. Hội thoại SMS mới mặc định Human. Staff có thể thử cấu hình đã lưu nhưng không sửa kết nối của Owner.

Prompt nền yêu cầu chỉ dùng thông tin doanh nghiệp, không bịa giá/lịch trống, không xác nhận booking chưa tạo và đề nghị người thật khi thiếu dữ kiện. **Đây là ràng buộc bằng prompt, chưa có bộ kiểm duyệt đầu ra bảo đảm AI không bao giờ vượt phạm vi.** Built-in AI chưa có công cụ tự đặt lịch; lời đề nghị chuyển người thật không tự phân công nhân viên trong Inbox.

API key đã lưu không được trả lại qua API cấu hình. Ô secret để trống khi lưu giữ giá trị cũ. Khi thử AI local HTTP, đặt `SMALLBIZ_ALLOW_LOCAL_AI=1` để cho phép `localhost`/`127.0.0.1`; mặc định hạn chế URL HTTP/private nhằm giảm SSRF.

## 4. SMS qua Twilio

Mặc định **Mock** chỉ lưu tin nhắn trong Inbox. Để gửi thật:

1. Chuẩn bị Account SID, Auth Token, số Twilio theo E.164 và consent hợp lệ của khách; hoàn tất yêu cầu đăng ký tương ứng với số/khu vực sử dụng.
2. Đặt `SMALLBIZ_ENABLE_LIVE_SMS=1` **trước khi chạy server, trong cùng terminal**.
3. Vào **AI & channels → SMS delivery**, nhập credential/số Twilio, chọn **Twilio · Sends real messages**, rồi **Save SMS settings**.
4. Để nhận SMS/cuộc gọi, cấu hình public HTTPS và `SMALLBIZ_PUBLIC_BASE_URL` khớp URL công khai. Các webhook:

| Mục đích | Method | Đường dẫn |
|---|---|---|
| Nhận SMS | POST | `/api/hooks/twilio/sms` |
| Trạng thái SMS | POST | `/api/hooks/twilio/status` |
| Nhận cuộc gọi | POST | `/api/hooks/twilio/voice` |

Ví dụ inbound SMS URL: `https://your-domain.example/api/hooks/twilio/sms`. Backend tự đính kèm status callback khi gửi và có public HTTPS URL.

Webhook được xác minh HMAC-SHA1; sự kiện SMS trùng MessageSid được loại bỏ. `STOP` thu hồi consent. SMS mới từ số chưa có trong CRM **không tự cấp consent**. Consent, số điện thoại hợp lệ và cổng live được kiểm tra trước khi gửi.

## 5. WhatsApp Business

1. Kết nối AI provider tại **AI assistant**. Mở tab **WhatsApp**, nhập **Phone Number ID**, **Access token**, **App secret** và **Webhook verify token**.
2. Cấu hình callback GET/POST `https://your-domain.example/api/hooks/whatsapp` trong Meta app, dùng verify token đã lưu và đăng ký sự kiện `messages`.
3. Chọn Graph API version được Meta app hỗ trợ bằng `SMALLBIZ_META_GRAPH_API_VERSION`. Source mặc định `v25.0`; chưa xác nhận phiên bản này trên tài khoản thật của anh.
4. Bật **Automatically reply to new WhatsApp conversations using Built-in AI**, rồi lưu. Hội thoại mới dùng Built-in AI; hội thoại đã có giữ nguyên Human/Built-in/External, điều chỉnh trong Inbox.

Webhook kiểm tra chữ ký SHA-256 và loại sự kiện trùng. SMS và WhatsApp có conversation riêng dù cùng số khách. Quyền phản hồi WhatsApp được ghi riêng, không tự cấp consent SMS. `STOP` chặn gửi thủ công và tự động; `START` bật lại.

Chỉ hỗ trợ **text trong cửa sổ 24 giờ**, tính từ thời gian tin nhắn khách gửi. Webhook đến trễ không mở lại cửa sổ. Chưa hỗ trợ template, media hoặc đồng bộ delivered/read receipts. `SMALLBIZ_ENABLE_LIVE_SMS` **chỉ chặn SMS**, không chặn WhatsApp khi kênh này đã được cấu hình thật.

## 6. Voice Lab và cuộc gọi bận

### Thử giọng nói trong trình duyệt

Mở **Voice Lab**, chọn `gTTS`/`Edge-TTS`, ngôn ngữ, voice và lưu. **Speak text** đọc văn bản; **Ask AI & speak answer** gọi AI rồi đọc đáp án. **Microphone** dùng SpeechRecognition nếu trình duyệt hỗ trợ và được cấp quyền, không phải chức năng STT của gTTS/Edge-TTS.

Với tiếng Việt, Edge-TTS thử tối đa 3 lần khi gặp `NoAudioReceived`; nếu vẫn lỗi, dùng gTTS tiếng Việt mà không đổi voice đã lưu. UI và header `X-TTS-Engine: gtts-fallback` cho biết fallback được dùng. Cả hai engine cần mạng và có thể lỗi; không có bảo đảm SLA trong app.

### Chuyển cuộc gọi khi nhân viên bận

1. Lưu credential/số Twilio ở **SMS delivery**; có thể giữ SMS mode Mock khi chỉ dùng Voice AI.
2. Trong **Phone calls**, nhập số nhân viên E.164, ví dụ `+15125550123`. Số này phải khác số Twilio. Chọn fallback rồi **Save call settings**.
3. Đặt Twilio inbound Voice webhook POST đến `https://your-domain.example/api/hooks/twilio/voice` và cấu hình public HTTPS URL trên server.

Luồng: **khách gọi số Twilio → gọi nhân viên với timeout 20 giây → xử lý `busy`/`no-answer`/`failed`/`canceled` theo fallback:**

| Fallback | Điều kiện và hành vi |
|---|---|
| Answer with Voice AI | Bật Voice AI ở **Voice Lab → Phone call settings**, cấu hình AI provider; trả lời theo lượt, giới hạn 8 lượt mỗi cuộc gọi |
| Send a consented SMS | Contact đã tồn tại, có `consent_sms`, SMS mode Twilio và `SMALLBIZ_ENABLE_LIVE_SMS=1` |
| End with a short message | Phát thông báo rồi kết thúc; không tự chuyển AI |

Callback trùng CallSid không gửi SMS hai lần. Mock chỉ lưu Inbox, không nói với khách là đã gửi thật. Fallback thiếu điều kiện sẽ kết thúc bằng thông báo. Nếu không có số nhân viên, Voice AI đã bật nhận cuộc gọi trực tiếp.

Phone AI dùng Twilio `Gather` nhận dạng giọng nói → LLM → TTS `Play`, với `Say` làm fallback; **không phải hội thoại streaming realtime**. Số điện thoại ngoài Twilio phải được định tuyến về Twilio trước; app không tự phát hiện cuộc gọi nhỡ trên mọi số điện thoại.

## 7. Workflow và External agent

Workflow hiện có trigger **Incoming SMS**, **Missed call (sự kiện demo)**, **Booking created**; điều kiện consent/keyword; action SMS, AI reply, thêm tag, chuyển Human và ghi log. Mỗi flow có một trigger, tối đa 25 nodes/40 edges, không có vòng lặp.

**Run test là dry-run:** không gửi tin, gọi LLM hoặc đổi CRM. Workflow Enabled mới chạy theo sự kiện. Demo inbound/missed-call không gửi SMS thật dù Twilio Live đang bật. Nhánh fallback cuộc gọi thật ở mục 6 hoạt động riêng; chưa kích hoạt workflow Missed call.

Tab **External agent** hiển thị API theo workspace cho agent riêng: inbox/context, reply, availability/book và handoff. Chọn External AI trong Inbox. Chi tiết ở `docs/AI_INTEGRATION.md` và `docs/WORKFLOW_AND_CHANNELS.md`; API docs local tại `http://127.0.0.1:8000/api/docs`.

## 8. Biến môi trường

File `.env` **không tự nạp**. Đặt biến trước khi chạy app, ví dụ PowerShell:

```powershell
$env:SMALLBIZ_PUBLIC_BASE_URL="https://your-domain.example"
$env:SMALLBIZ_ENABLE_LIVE_SMS="0"  # chỉ đổi 1 khi chủ động bật gửi SMS thật
$env:SMALLBIZ_META_GRAPH_API_VERSION="v25.0"  # thay theo Meta app của anh
py server.py
```

| Biến | Ý nghĩa |
|---|---|
| `SMALLBIZ_DB` | Đường dẫn SQLite; mặc định `demo.sqlite3` trong source |
| `SMALLBIZ_KEY_FILE` | Khóa mã hóa; mặc định `.smallbiz-fernet-key` |
| `SMALLBIZ_PUBLIC_BASE_URL` | URL HTTPS công khai cho webhook và audio cuộc gọi |
| `SMALLBIZ_ENABLE_LIVE_SMS` | Chỉ `1` mới cho phép gửi Twilio SMS thật |
| `SMALLBIZ_META_GRAPH_API_VERSION` | Version Meta Graph API dùng gửi WhatsApp |
| `SMALLBIZ_ALLOW_LOCAL_AI` | `1` cho phép thử AI local qua HTTP |

Xem thêm `.env.example`. Không đưa API key vào JS/frontend hoặc source công khai.

## 9. Kiểm thử

Chạy từ thư mục có `server.py`. Backend cần `requirements-dev.txt`; Node.js dùng cho smoke test JS. Dùng terminal riêng và database/key tạm:

```powershell
py -m pip install -r requirements-dev.txt
$qaDir = Join-Path ([IO.Path]::GetTempPath()) ("smallbiz-tests-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $qaDir | Out-Null
$env:SMALLBIZ_DB = Join-Path $qaDir "test.sqlite3"
$env:SMALLBIZ_KEY_FILE = Join-Path $qaDir "key"
py -m unittest discover -s tests -p "test_*.py" -v
node tests/ui_vm_smoke.cjs
```

Mở terminal mới khi chạy lại app với dữ liệu thường. Browser smoke cần Playwright và Microsoft Edge đã cài trên Windows; Playwright chưa nằm trong `requirements-dev.txt`:

```powershell
py tests/ux_smoke.py
```

Script browser tự chạy server cổng `8766` với database/key tạm. Ảnh QA lưu ở thư mục tạm hoặc nơi đặt qua `SMALLBIZ_QA_OUTPUT`.

Kết quả local **14/11/2026**: 33 test backend/API, Python/JS syntax, Node VM smoke đều đạt. Playwright Edge đạt trên 7 trang ở 390/740/1024/1440 px, gồm lưu AI/WhatsApp/cuộc gọi/Voice, tab bàn phím, modal, Inbox mobile, workflow, chuyển doanh nghiệp và quyền Staff.

**Chưa xác nhận:** Meta/Twilio/LLM/TTS thật, public HTTPS end-to-end và production deployment. Kiểm thử mock không chứng minh tài khoản hoặc webhook nhà cung cấp đã sẵn sàng. Chi tiết: `docs/IMPLEMENTATION_STATUS.md`.

## 10. Source và cập nhật bản đang dùng

| Đường dẫn | Nội dung |
|---|---|
| `server.py` | FastAPI, auth, CRM, Inbox, booking và API external AI |
| `enhancements.py` | Provider AI, SMS/WhatsApp, TTS/Voice, workflow và schema bổ sung |
| `static/` | Giao diện; `app.js`, `studio.js`, `usability.js` và CSS |
| `tests/` | Backend/API, Node VM và Playwright smoke |
| `docs/`, `examples/` | Tài liệu tích hợp và adapter AI mẫu |

Dừng server, sao lưu **database cùng khóa mã hóa** trước khi cập nhật. Giữ đồng bộ backend/frontend, đặc biệt `server.py`, `enhancements.py`, `static/studio.js` và `static/usability.js`; không ghi đè dữ liệu đang dùng bằng database/khóa mẫu. Khởi động lại server rồi Ctrl+F5.

Startup bổ sung cột cấu hình trong `integrations`, `contacts.consent_whatsapp` và bảng `whatsapp_sessions` cho schema cũ. Đợt kiểm thử này chỉ dùng database/key tạm, không áp dụng lên database đang dùng.

Các thay đổi tương thích V0.2.1 được giữ: Custom gateway dùng `stream: false`, thông báo lỗi empty/HTML/SSE/HTTP rõ hơn; Save & test lưu cấu hình trên màn hình trước khi thử. V0.2.2 bổ sung retry/fallback TTS tiếng Việt; source local ngày 14/11/2026 bổ sung UX, WhatsApp, hướng dẫn doanh nghiệp và xử lý cuộc gọi bận.
