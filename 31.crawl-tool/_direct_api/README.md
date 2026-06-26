# Agoda Hybrid Crawler (direct-API curl_cffi + browser fallback)

Hướng đi **mới**: direct-API (curl_cffi) lo nhóm KS dễ cho nhanh, **browser fallback** (đúng phương pháp notebook cũ: 7 ngày/tuần + xoay fingerprint + 3 vòng retry) lo nhóm KS khó.

**Mục tiêu: phủ giá chính xác nhiều nhất — coverage không bao giờ thấp hơn bản cũ.** Ô nào direct không ra giá thật (NA *hoặc* SOLD OUT nghi ngờ) đều được browser crawl lại (browser = nguồn tin cậy).

## Ý tưởng cốt lõi

| | Notebook hiện tại | Prototype này |
|---|---|---|
| Mỗi giá tốn | 1 lần mở Chromium + điều hướng + cuộn + chờ XHR (~30–60s) | 1 request HTTP/2 đã "ấm" (~1s) |
| Browser dùng khi | **mọi query** (hotels × weeks × days) | **1 lần / khách sạn** để mồi session |
| Né anti-bot bằng | stealth lúc điều hướng (dễ bị Akamai chấm điểm) | giả vân tay **TLS/JA3 + HTTP2 của Chrome thật** (`curl_cffi`) |

Lý do nhanh hơn **không** phải bắn nhiều request hơn — mà vì bỏ được "thuế browser" mỗi query. Giữ **nguyên nhịp an toàn** hiện tại vẫn nhanh hơn 5–15×.

## Sự thật kỹ thuật quan trọng (từ nghiên cứu)
- Agoda đứng sau **Akamai Bot Manager**. Cookie `_abck` bị buộc theo **TLS + IP** → warm và replay **phải cùng 1 IP, cùng 1 major Chrome** (ở đây: Chrome 131 ↔ `impersonate="chrome131"`).
- `room-grid` **không phải GET với query param**. Live-probe: `GET → 405`, `POST {} → 400 "api key invalid"`. Nó là **POST cần `apiKey`** + JSON body. → Vì vậy prototype **bắt nguyên văn** request thật rồi replay, không tự đoán hình dạng.

## Cài đặt
```bash
pip install -r requirements.txt
playwright install chromium
```

## Chạy theo GATE (đừng nhân rộng trước khi qua từng gate)

> ⚠️ **Phải chạy trên máy/IP của bạn.** Session warm bị buộc theo IP — capture ở IP khác sẽ vô dụng.

### Gate 0 — Bắt 1 request room-grid thật *(make-or-break)*
```bash
python agoda_direct.py capture --url "https://www.agoda.com/.../hotel/...html" --room "Narra Double"
```
Warm sẽ thử lần lượt nhiều profile (UA↔TLS khớp nhau: chrome131/124/120/116) tới khi bắt được, rồi **ghi lại profile thắng** để replay dùng đúng `impersonate` đó.
Kỳ vọng: in ra `✅ Bắt được room-grid (profile chromeXXX): POST …`, số cookie agoda > 0, lưu `_capture/capture.json`. `--room` để sanity-check giá ngay.
Nếu `❌ Mọi profile đều fail` → bị chặn lúc warm; thử lại, đổi mạng (4G), hoặc đặt `HEADLESS=False` trong file.

### Gate 1 — Chứng minh replay được
```bash
python agoda_direct.py replay
```
- **1a verbatim PASS** = cookie/TLS/IP khớp, apiKey trong header hoạt động.
- **1b đổi ngày PASS** = đổi `checkin` trong body vẫn ra dữ liệu → **fan-out direct khả thi** (1 warm → nhiều ngày).
- 1a PASS nhưng 1b FAIL → checkin bị buộc theo lần load trang → dùng chế độ **warm theo từng khách sạn** (đã là mặc định ở Gate 2).
- 1a FAIL → TLS/IP/cookie không khớp hoặc thiếu apiKey.

### Gate 2 — Crawl thử nhỏ + đo
```bash
python agoda_direct.py crawl --input agoda1.csv --max 5 --weeks 2
```
`--input` tự dò trong cây `31.crawl-tool/` nếu không thấy ở thư mục hiện tại (vd `agoda1.csv` → `../agoda/agoda1/agoda1.csv`).
Chế độ mặc định: **warm 1 lần/khách sạn** (1 page-load) rồi replay các tuần qua `curl_cffi`.
In ra: % có giá, số NA/SOLD OUT, thời gian/KS. **Bar để nhân rộng:**
- 5 KS gồm 2 KS dễ + 3 KS lớn (Marriott/Sheraton/MGallery/Vedana — vốn hay bị NA giả).
- Giá khớp với notebook trên KS dễ; **completion KS lớn ≥ hôm nay**; nhanh hơn rõ rệt.

## Thang fallback (nếu một gate fail)
1. **Direct thuần** (gate 2 pass) → nhân rộng.
2. **Warm theo từng KS** (mặc định) — robust nếu checkin buộc theo session.
3. **Đa dạng IP miễn phí**: phát 4G/airplane-mode toggle làm lane 2, IP nhà làm lane 3, chia ~100–200 KS theo thời gian để không IP nào vượt ngưỡng.
4. **Hybrid**: giữ notebook Playwright cho ~10–20 KS khó nhất, direct-API cho phần còn lại.
5. (Đóng vòng) Agoda Affiliate API **miễn phí nhưng ToS cấm dùng cho so sánh giá** → không khả thi; Makcorps (trả phí) nếu cần dữ liệu sạch.

## Quy tắc bất biến (chống NA giả — gốc rễ vấn đề hiện tại)
- **KHÔNG** ghi NA/SOLD OUT khi gặp `403/429/503` hay `rooms` rỗng thiếu `propertyName` → đó là soft-block, phải retry.
- Chỉ ghi SOLD OUT khi `rooms` có dữ liệu và đúng phòng sold-out (logic `extract_from_agoda` giữ nguyên từ notebook).
- Re-warm session sau ~60 query hoặc khi gặp chuỗi block.

## File
- `agoda_direct.py` — toàn bộ prototype (3 lệnh: capture / replay / crawl), parser tái dùng nguyên vẹn từ `crawl price AGODA - 1.ipynb`.
- `_capture/capture.json` — sinh ra ở Gate 0 (không commit).
