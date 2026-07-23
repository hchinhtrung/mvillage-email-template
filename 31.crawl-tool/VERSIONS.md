# Trip crawl versions

| Path | Vai trò |
|---|---|
| `crawler/` + `run_trip.ipynb` | Bản đang dùng — **v0.5.0** Camoufox browser-nav (Agoda stack) |
| `v1/` | Freeze snapshot = bản ổn trước speed-up |

## v0.5.0 — soft-block fix (2026-07-22)

Trip trước đây soft-block hàng loạt vì:
1. Browser-only nhưng **không mở Camoufox** (chỉ chromium + stealth)
2. Nhận skeleton `getHotelRoomList` rỗng → coi là soft-block
3. Thiếu DOM fallback sau scroll

Fix (port Agoda stack + logic notebook Trip v3.1):
- Mở Camoufox cho mọi run `engine=camoufox` (kể cả browser-only)
- `humanize` + `geoip` + OS fingerprint pool
- Ignore empty skeleton; scroll patient; DOM fallback trước khi retry
- Site profile Trip: `nav_attempts=3`, backoff dài hơn, locale theo host (`vn.trip.com` → `vi-VN`)

### Playwright pin (bắt buộc)

`playwright` **phải** `>=1.59,<1.60` (đang là `1.59.0`):
- `1.60.*` — crash Camoufox Firefox
- `1.61+` — lỗi `viewport.isMobile` / `Browser.setDefaultViewport` (Juggler từ chối)

Nếu thấy `Found property "<root>.viewport.isMobile"` → chạy:
```bash
.venv/bin/python -m pip install 'playwright>=1.59,<1.60'
.venv/bin/python -m playwright install chromium
```
Notebook cell ③ cũng tự pin khi phát hiện sai version.

- Ổn định → dùng **root** (`run_trip.ipynb`)
- Output ở `results/trip/`
