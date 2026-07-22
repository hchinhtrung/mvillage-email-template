# Trip crawler — v2 (speed-up)

Bản thử nghiệm nhanh hơn v1. Root `crawler/` và folder `v1/` **không bị sửa**.

## Chạy

Mở [`run_trip.ipynb`](run_trip.ipynb):

1. Cell ① — chỉnh `SPEED_PROFILE`:
   - `"safe"` — giống v1
   - `"medium"` — 1 hotel, `weeks_parallel=3`, delay ngắn (**khuyến nghị**)
   - `"fast"` — 1 hotel, `weeks_parallel=4`

> Trip thường soft-block khi `hotels_parallel > 1`. Tăng tốc bằng song song **tuần trong 1 hotel**, không song song nhiều hotel.
2. Nên test trước: `MAX_HOTELS = 5` hoặc `10`
3. Chạy cell ② → ③ → ④

Output riêng: `../results/trip_v2/` (không đụng checkpoint v1).

## Rollback

Nếu v2 không ổn → mở lại [`../v1/run_trip.ipynb`](../v1/run_trip.ipynb) hoặc [`../run_trip.ipynb`](../run_trip.ipynb). Không cần copy file.

## Thay đổi kỹ thuật (so với v1)

- `Config.hotels_parallel` + soft-cap `max_browser_contexts`
- Round 1: `asyncio.gather` hotels khi `hotels_parallel > 1` (có lock khi ghi checkpoint)
- Notebook truyền knobs qua `crawler.arun(**profile)`
