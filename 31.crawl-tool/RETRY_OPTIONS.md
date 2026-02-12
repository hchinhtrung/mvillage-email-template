# 🔄 RETRY OPTIONS - How to Run

## ⚡ Quick Test (RECOMMENDED - Start here!)

Chỉ retry **50 cells đầu** để test success rate (5-10 phút):

```python
# Edit retry_na_cells.py - dòng 28-29:
TEST_MODE = True      # ✅ Enable test mode
AUTO_START = True     # ✅ Skip confirmation
```

Sau đó chạy:

```bash
cd /Users/hchinhtrung/Documents/GitHub/mvillage-email-template/31.crawl-tool
python3 retry_na_cells.py
```

**Expected**: Xong trong 5-10 phút, xem success rate bao nhiêu

---

## 🚀 Full Retry (After test successful)

Retry **toàn bộ 1041 cells** (~3.6 giờ):

```python
# Edit retry_na_cells.py - dòng 28-29:
TEST_MODE = False     # ❌ Disable test mode
AUTO_START = True     # ✅ Auto start
```

Chạy:

```bash
python3 retry_na_cells.py
```

---

## ⚡ Speed vs Stealth Trade-off

### Current Config (Balanced):

```python
NUM_WORKERS = 2
DELAY_RANGE = (3, 7)
MAX_RETRIES = 5
```

- Time: 3.6 giờ
- Expected success: 50-60%

### Faster (More risk of detection):

```python
NUM_WORKERS = 4        # ⬆️ More parallel
DELAY_RANGE = (2, 4)   # ⬇️ Shorter delays
MAX_RETRIES = 3        # ⬇️ Fewer retries
```

- Time: ~1.5 giờ
- Expected success: 40-50%

### Safer (Slower but better success):

```python
NUM_WORKERS = 1        # ⬇️ One at a time
DELAY_RANGE = (5, 10)  # ⬆️ Longer delays
MAX_RETRIES = 7        # ⬆️ More retries
```

- Time: ~6-8 giờ
- Expected success: 60-70%

---

## 📊 Recommended Workflow

### Step 1: Quick Test

```python
TEST_MODE = True      # 50 cells only
NUM_WORKERS = 2
DELAY_RANGE = (3, 7)
```

Run and check success rate in ~10 minutes

### Step 2a: If test shows >50% success

```python
TEST_MODE = False     # Full retry
# Keep same config
```

Go ahead with full retry

### Step 2b: If test shows <50% success

```python
TEST_MODE = False
NUM_WORKERS = 1       # More stealth
DELAY_RANGE = (5, 10)
MAX_RETRIES = 7
```

Slower but better success rate

---

## 🎯 My Recommendation

**Start with this** (edit lines 18-23 in retry_na_cells.py):

```python
NUM_WORKERS = 2
MAX_RETRIES = 5
DELAY_RANGE = (3, 7)
PAGE_TIMEOUT = 30
ELEMENT_WAIT = 20
RETRY_BACKOFF = 2.0

TEST_MODE = True      # ✅ Test 50 cells first
AUTO_START = True     # ✅ Auto start
```

Run test → Check results → Decide next steps

---

## 💡 Tips

1. **Run at night**: 2-6 AM Vietnam time (Agoda less busy)
2. **Monitor first 10 cells**: If lots of ❌ → Stop and increase delays
3. **Check network**: Stable internet connection needed
4. **Don't close terminal**: Let it run in background

---

## 🐛 If Errors Occur

Common issues:

- Chrome driver crashes → Restart script
- Too many NAs → Increase DELAY_RANGE
- EOFError → Set AUTO_START = True
- Timeout errors → Increase PAGE_TIMEOUT
