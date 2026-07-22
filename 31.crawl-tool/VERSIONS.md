# Trip crawl versions

| Path | Vai trò |
|---|---|
| `crawler/` + `run_trip.ipynb` | Bản gốc đang dùng — **không đụng** khi làm v2 |
| `v1/` | Freeze snapshot = bản ổn |
| `v2/` | Speed-up (parallel + knobs) |

- Ổn định → dùng **root** hoặc **v1**
- Thử nhanh → dùng **v2** (`SPEED_PROFILE="fast"`), output ở `results/trip_v2/`
