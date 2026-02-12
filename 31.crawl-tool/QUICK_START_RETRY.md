# 🚀 QUICK START: Retry NA Cells

## 📊 Current Status
- ✅ Initial crawl: `hotel_prices_20260212.csv`
- ❌ Success rate: 24.2% (1041 NA cells)
- 🎯 Goal: Retry 1041 NA cells to improve to 60-70%

---

## ⚡ Option 1: Run Retry Script (RECOMMENDED)

### Step 1: Check files exist
```bash
cd /Users/hchinhtrung/Documents/GitHub/mvillage-email-template/31.crawl-tool

# These files should exist:
ls hotel_prices_20260212.csv  # ✅ Result file with NAs
ls raw.csv                     # ✅ Original input with URLs
ls retry_na_cells.py          # ✅ Retry script
```

### Step 2: Run retry script
```bash
python3 retry_na_cells.py
```

### What will happen:
1. Script analyzes `hotel_prices_20260212.csv`
2. Identifies 1041 NA cells
3. Shows estimated time (~2-3 hours)
4. Asks for confirmation
5. Crawls ONLY the NA cells với stealth mode
6. Saves to `hotel_prices_RETRY_YYYYMMDD_HHMM.csv`

### Configuration (if needed):
Edit top of `retry_na_cells.py`:
```python
NUM_WORKERS = 2        # Fewer = safer (can try 1 for max stealth)
MAX_RETRIES = 5        # More retries per cell
DELAY_RANGE = (3, 7)   # Longer delays = safer
```

---

## ⚡ Option 2: Upgrade to Undetected ChromeDriver (Advanced)

### Install package:
```bash
pip install undetected-chromedriver
```

### Then create enhanced crawler:
I can modify your main crawler to use this library for better stealth.
Want me to do this?

---

## ⚡ Option 3: Manual Investigation (Debug)

### Check why specific hotels fail:
```python
# Run this to see which hotels have most NAs:
import pandas as pd

df = pd.read_csv('hotel_prices_20260212.csv')

# Count NAs per hotel
df['na_count'] = df[['price_w1', 'price_w2', 'price_w3', 'price_w4', 'price_w5', 'price_w6']].apply(
    lambda row: sum(pd.isna(row) or x == 'NA' for x in row), axis=1
)

# Hotels with most failures
worst = df.nlargest(20, 'na_count')[['hotel_name', 'na_count']]
print(worst)
```

This shows which hotels consistently fail (might need different selectors).

---

## 📈 Expected Results

### After Retry Script:
- **Best case**: 60-70% success (recover ~400-600 cells)
- **Realistic**: 50-60% success
- **Worst case**: 30-40% (Agoda detection too strong)

### If still <60% success after retry:
**Next steps:**
1. Use undetected-chromedriver (free upgrade)
2. Add residential proxies (~$200/month)
3. Accept current rate and manually fill critical gaps

---

## 🎯 My Recommendation

### For now:
```bash
# Just run this:
python3 retry_na_cells.py
```

### Wait for results, then decide:
- If success ≥ 60%: ✅ Good enough!
- If success < 60%: Consider proxies or undetected-chrome

---

## 💡 Pro Tips

1. **Run during off-peak hours**
   - Vietnam: Run at 2-6 AM (Agoda servers less busy)
   - Avoid 7-10 PM (peak booking time)

2. **Start with sample**
   - Edit script to retry only first 100 cells
   - Test success rate before full run

3. **Monitor live**
   - Watch console output
   - If seeing lots of ❌ early → stop and increase delays

4. **Save screenshots of failures**
   - Add this to understand why NA happens
   - I can add this feature if needed

---

## ❓ Questions?

**Q: How long will retry take?**
A: ~2-3 hours for 1041 cells with 2 workers

**Q: Can I run faster?**
A: Yes, increase `NUM_WORKERS = 4`, but success rate will drop

**Q: What if I still get mostly NAs?**
A: We'll need proxies or undetected-chrome (next level)

**Q: Can I retry again after this?**
A: Yes! You can run retry script multiple times on the output

---

## 🏃 Ready?

```bash
cd /Users/hchinhtrung/Documents/GitHub/mvillage-email-template/31.crawl-tool
python3 retry_na_cells.py
```

Let me know the results! 🚀
