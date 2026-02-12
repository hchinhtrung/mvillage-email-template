# 🎯 BEST PRACTICES: Crawling OTA Platforms (Agoda, Booking.com, etc.)

## 📊 Current Situation Analysis
- **Success Rate**: 24.2% (333/1374 cells)
- **NA Rate**: 75.8% (1041/1374 cells)
- **Root Cause**: Aggressive bot detection + async pricing + rate limiting

---

## 🚀 Solution Hierarchy (Best to Worst)

### ⭐ Tier 1: OFFICIAL APIs (BEST - but not always available)
```
❌ Agoda: No public API
❌ Booking.com: Affiliate API (requires partnership)
✅ Expedia: Partner API (requires approval)
```
**Verdict**: Not viable for Agoda

---

### ⭐ Tier 2: SMART RETRY + ENHANCED STEALTH (RECOMMENDED)

#### Strategy A: Retry NA Cells (Implemented in `retry_na_cells.py`)
```python
# What it does:
1. Identify all NA cells from initial crawl
2. Retry only those cells với aggressive stealth:
   - Fewer workers (2 instead of 4)
   - Longer delays (3-7s instead of 1.5-3.5s)
   - More retries (5 instead of 3)
   - Longer timeouts (30s instead of 20s)
   - Better element waiting strategies
   - Multiple selector fallbacks

# Expected improvement:
- Should recover 40-60% of NA cells
- Trade-off: Slower but more thorough
```

#### Strategy B: Session + Cookie Management
```python
# Maintain browser sessions longer
- Don't close driver immediately
- Reuse sessions across hotels
- Store cookies between runs
- Mimics real user browsing multiple hotels
```

#### Strategy C: Smarter Element Detection
```python
# Currently missing:
1. Wait for price API calls to complete
2. Detect "loading" states
3. Handle dynamic content properly
4. Screenshot failed pages for debugging
```

---

### ⭐ Tier 3: INFRASTRUCTURE CHANGES

#### Option A: Residential Proxies
```python
# Use rotating residential proxies
- Avoid IP-based rate limiting
- Appear as real users from different locations
- Cost: ~$100-500/month for quality proxies

Services:
- Bright Data (expensive but reliable)
- Oxylabs
- SmartProxy
```

#### Option B: CAPTCHA Solving Services
```python
# If Agoda shows CAPTCHAs
- 2Captcha
- Anti-Captcha
- Cost: ~$1-3 per 1000 solves
```

#### Option C: Undetected ChromeDriver
```python
# Use undetected-chromedriver library
pip install undetected-chromedriver

# Better stealth than regular Selenium
import undetected_chromedriver as uc
driver = uc.Chrome()
```

---

### ⭐ Tier 4: ARCHITECTURAL CHANGES

#### Option A: Distributed Crawling
```python
# Split work across multiple machines/IPs
- Run on AWS Lambda với rotating IPs
- Use Scrapy Cloud
- Each worker handles subset of hotels
```

#### Option B: Time-Based Crawling
```python
# Spread crawling over time
- Crawl 50 hotels/day over 5 days
- More human-like behavior
- Lower detection risk
```

#### Option C: Browser Automation Cloud
```python
# Use services that handle stealth for you
- BrowserStack Automate
- LambdaTest
- Selenium Grid với stealth configs
```

---

## 🔧 Implementation Recommendations

### Immediate Actions (Next 24h):
1. ✅ **Run retry script** (`retry_na_cells.py`)
   - Should improve success rate to 60-70%
   - Takes ~2-3 hours for 1041 cells

2. ✅ **Analyze retry results**
   - If still >50% NA → Need Tier 3 solutions

### Short-term (This week):
3. **Implement undetected-chromedriver**
   ```bash
   pip install undetected-chromedriver
   ```

4. **Add screenshot debugging**
   ```python
   if price == "NA":
       driver.save_screenshot(f"debug/{hotel_name}_w{week}.png")
   ```

5. **Monitor which hotels consistently fail**
   - Some hotels might have different page structures
   - Create hotel-specific selectors

### Medium-term (If still needed):
6. **Consider proxy service** (if budget allows)
   - Residential proxies: ~$200/month
   - Should bring success rate to 90%+

7. **Implement caching strategy**
   ```python
   # Don't re-crawl successful cells
   # Focus only on NA cells in subsequent runs
   ```

---

## 📈 Success Rate Expectations

| Strategy | Expected Success | Time | Cost |
|----------|-----------------|------|------|
| Current (Stealth) | 24% | ⚡ Fast | Free |
| + Retry Script | 60-70% | 🐢 Slow | Free |
| + Undetected Chrome | 75-80% | 🐢 Slow | Free |
| + Residential Proxies | 90-95% | ⚡ Fast | $200/mo |
| + CAPTCHA Solving | 95-98% | ⚡ Fast | $300/mo |

---

## ⚠️ Legal & Ethical Considerations

### ✅ Generally OK:
- Crawling publicly visible prices
- Respecting rate limits
- Not overloading servers
- For personal/business intelligence use

### ❌ Risky:
- Circumventing CAPTCHA at scale
- Ignoring Terms of Service
- Reselling scraped data
- DDoS-like request volumes

### 📋 Recommendations:
1. **Check Agoda's Terms of Service**
2. **Use reasonable delays** (you're doing this ✅)
3. **Don't crawl during peak hours** (Asian evening)
4. **Consider contacting Agoda** for data partnership

---

## 🎯 My Recommendation for Your Use Case

Based on 229 hotels needing regular monitoring:

### Phase 1: FREE Solutions (Try First)
```bash
# 1. Run retry script
python3 retry_na_cells.py

# 2. Install undetected-chromedriver
pip install undetected-chromedriver

# 3. Update main crawler to use it
```

**Expected outcome**: 70-80% success rate

### Phase 2: IF Phase 1 Insufficient
```
# Invest in residential proxy service
# Cost: ~$200/month
# Expected: 90%+ success rate
```

### Phase 3: Long-term Solution
```
# Option A: Build relationship with Agoda for data access
# Option B: Use aggregator APIs (if available)
# Option C: Accept 80% success rate and manually fill gaps
```

---

## 🔍 Debugging Tips

### When NA occurs, check:
1. **Screenshot the page**: Does it load correctly?
2. **Check console logs**: Any JavaScript errors?
3. **Network tab**: Are price API calls failing?
4. **HTML structure**: Did Agoda change selectors?
5. **Geographic blocking**: Try VPN to Singapore/Thailand

### Common NA Causes:
- ❌ Price not loaded yet (increase waits)
- ❌ Room sold out (legitimate NA)
- ❌ Bot detection triggered (use stealth)
- ❌ Wrong selector (update CSS paths)
- ❌ CAPTCHA appeared (need solving)

---

## 📞 Need Help?

If retry script doesn't improve to 70%+:
1. Share screenshot of failed page
2. Check browser console for errors
3. Consider proxy solution
4. Alternative: Use booking.com or expedia if they have the same hotels
