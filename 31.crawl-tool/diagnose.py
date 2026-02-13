"""
Diagnostic tool: Mở 3 hotels (1 thành công, 1 partial, 1 all-NA)
và capture screenshots + network data + HTML để hiểu root cause
"""
import asyncio
import nest_asyncio
import pandas as pd
import os
import re
import json
import random
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

nest_asyncio.apply()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR = os.path.join(SCRIPT_DIR, "debug")
os.makedirs(DEBUG_DIR, exist_ok=True)

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = { runtime: {} };
"""

def update_url_checkin(url, checkin_date):
    new_date = checkin_date.strftime("%Y-%m-%d")
    if 'checkin=' in url.lower():
        url = re.sub(r'checkin=[\d-]+', f'checkin={new_date}', url, flags=re.IGNORECASE)
    else:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}checkin={new_date}"
    return url

async def diagnose_hotel(browser, hotel_name, hotel_url, room_type, label):
    print(f"\n{'='*60}", flush=True)
    print(f"🔍 DIAGNOSING: {hotel_name} [{label}]", flush=True)
    print(f"   Room: {room_type}", flush=True)
    print(f"{'='*60}", flush=True)

    # Track ALL network requests
    api_responses = []
    all_requests = []

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        locale="en-US",
    )
    page = await context.new_page()
    await page.add_init_script(STEALTH_SCRIPT)

    # Intercept network responses
    async def handle_response(response):
        url = response.url
        # Capture API calls related to pricing/rooms
        if any(kw in url.lower() for kw in ['graphql', 'pricing', 'room', 'property', 'search', 'availability']):
            try:
                body = await response.text()
                api_responses.append({
                    "url": url[:200],
                    "status": response.status,
                    "size": len(body),
                    "has_price": any(kw in body.lower() for kw in ['price', 'amount', 'rate', 'cost']),
                    "has_room": any(kw in body.lower() for kw in ['room', 'masterroom', 'roomtype']),
                })
            except:
                pass
        all_requests.append(url[:100])

    page.on("response", handle_response)

    checkin = datetime.today() + timedelta(days=7)
    url = update_url_checkin(hotel_url, checkin)

    safe_name = re.sub(r'[^\w]', '_', hotel_name)[:30]

    try:
        # Navigate - dùng domcontentloaded (networkidle KHÔNG work với Agoda!)
        print(f"\n1️⃣  Loading page...", flush=True)
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        # Wait cho room grid load
        try:
            await page.wait_for_selector("div#roomGrid", timeout=15000)
            print(f"   ✅ roomGrid loaded!", flush=True)
        except:
            print(f"   ⚠️  roomGrid not found within 15s, waiting more...", flush=True)
        await asyncio.sleep(5)

        # Screenshot - initial
        await page.screenshot(path=os.path.join(DEBUG_DIR, f"{safe_name}_1_initial.png"), full_page=False)
        print(f"   📸 Screenshot saved: {safe_name}_1_initial.png", flush=True)

        # Check for bot detection / CAPTCHA
        print(f"\n2️⃣  Checking for bot detection...", flush=True)
        page_text = await page.text_content("body")
        bot_signals = []
        if "captcha" in page_text.lower():
            bot_signals.append("CAPTCHA detected!")
        if "access denied" in page_text.lower():
            bot_signals.append("Access Denied!")
        if "cloudflare" in page_text.lower():
            bot_signals.append("Cloudflare protection!")
        if "please verify" in page_text.lower():
            bot_signals.append("Verification required!")
        if "robot" in page_text.lower():
            bot_signals.append("Robot check!")

        if bot_signals:
            print(f"   🚨 BOT DETECTION: {', '.join(bot_signals)}", flush=True)
        else:
            print(f"   ✅ No bot detection signals", flush=True)

        # Check page title
        title = await page.title()
        print(f"   📄 Page title: {title}", flush=True)

        # Scroll down
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(1)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

        # Screenshot - after scroll
        await page.screenshot(path=os.path.join(DEBUG_DIR, f"{safe_name}_2_scrolled.png"), full_page=False)

        # Check roomGrid
        print(f"\n3️⃣  Checking room grid...", flush=True)
        room_grid = page.locator("div#roomGrid")
        has_grid = await room_grid.count() > 0
        print(f"   div#roomGrid exists: {has_grid}", flush=True)

        if has_grid:
            grid_html_len = len(await room_grid.inner_html())
            print(f"   roomGrid HTML size: {grid_html_len:,} chars", flush=True)

        # Check MasterRoom cards
        room_cards = page.locator("div[data-selenium='MasterRoom']")
        card_count = await room_cards.count()
        print(f"   MasterRoom cards found: {card_count}", flush=True)

        # List ALL room names found
        print(f"\n4️⃣  Rooms found on page:", flush=True)
        found_target = False
        for idx in range(card_count):
            card = room_cards.nth(idx)
            try:
                name_el = card.locator("[data-selenium='masterroom-title-name']")
                name = (await name_el.text_content()).strip() if await name_el.count() > 0 else "(no name)"
            except:
                name = "(error)"

            try:
                price_el = card.locator("[data-selenium='PriceDisplay']")
                price = (await price_el.text_content()).strip() if await price_el.count() > 0 else "NO PRICE"
            except:
                price = "NO PRICE"

            match = "✅ MATCH" if name == room_type.strip() else ""
            if name == room_type.strip():
                found_target = True
            print(f"   [{idx}] '{name}' → {price} {match}", flush=True)

        if not found_target and card_count > 0:
            print(f"\n   ⚠️  TARGET ROOM '{room_type}' NOT FOUND in {card_count} rooms!", flush=True)
            print(f"   This explains the NA - room name doesn't match exactly", flush=True)

        # Network analysis
        print(f"\n5️⃣  Network analysis:", flush=True)
        print(f"   Total requests: {len(all_requests)}", flush=True)
        print(f"   API responses captured: {len(api_responses)}", flush=True)
        for api in api_responses[:5]:
            print(f"   - [{api['status']}] {api['url'][:80]}", flush=True)
            print(f"     has_price={api['has_price']}, has_room={api['has_room']}, size={api['size']:,}", flush=True)

        # Try alternative selectors
        print(f"\n6️⃣  Alternative selectors:", flush=True)
        alt_selectors = {
            "PriceDisplay": "[data-selenium='PriceDisplay']",
            "display-price": "[data-selenium='display-price']",
            "PropertyCardPrice": ".PropertyCardPrice__Value",
            "price-box": "[data-element-name='price-box']",
            "room-price": "[data-ppapi='room-price']",
            "ChildRoomsList-price": "[data-selenium='ChildRoomsList-price']",
        }
        for name, sel in alt_selectors.items():
            count = await page.locator(sel).count()
            if count > 0:
                sample = await page.locator(sel).first.text_content()
                print(f"   ✅ {name}: {count} elements (sample: '{sample[:50]}')", flush=True)
            else:
                print(f"   ❌ {name}: 0 elements", flush=True)

        # Save page HTML for analysis
        html = await page.content()
        html_path = os.path.join(DEBUG_DIR, f"{safe_name}_page.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\n   💾 Full HTML saved: {safe_name}_page.html ({len(html):,} chars)", flush=True)

    except Exception as e:
        print(f"   ❌ Error: {e}", flush=True)
        try:
            await page.screenshot(path=os.path.join(DEBUG_DIR, f"{safe_name}_error.png"))
        except:
            pass
    finally:
        await context.close()

async def main():
    print("🔍 AGODA CRAWLER DIAGNOSTIC TOOL", flush=True)
    print("="*60, flush=True)

    # Load data
    raw_df = pd.read_csv(os.path.join(SCRIPT_DIR, "raw.csv"))
    raw_df.columns = ['hotel_name', 'hotel_url', 'room_type']

    result_df = pd.read_csv(os.path.join(SCRIPT_DIR, "hotel_prices_20260213.csv"))
    weeks = ['price_w1', 'price_w2', 'price_w3', 'price_w4', 'price_w5', 'price_w6']

    # Pick 3 test cases
    test_cases = []

    # 1. Hotel with MOST success (to verify selectors work)
    best_idx = -1
    best_count = 0
    for idx, row in result_df.iterrows():
        count = sum(1 for c in weeks if pd.notna(row[c]) and str(row[c]).strip() not in ['', 'NA'])
        if count > best_count:
            best_count = count
            best_idx = idx
    if best_idx >= 0:
        r = result_df.iloc[best_idx]
        match = raw_df[raw_df['hotel_name'] == r['hotel_name']]
        if len(match) > 0:
            test_cases.append((r['hotel_name'], match.iloc[0]['hotel_url'], r['room_type'], f"BEST ({best_count}/6)"))

    # 2. Hotel with PARTIAL success
    for idx, row in result_df.iterrows():
        count = sum(1 for c in weeks if pd.notna(row[c]) and str(row[c]).strip() not in ['', 'NA'])
        if count == 3:
            match = raw_df[raw_df['hotel_name'] == row['hotel_name']]
            if len(match) > 0:
                test_cases.append((row['hotel_name'], match.iloc[0]['hotel_url'], row['room_type'], "PARTIAL (3/6)"))
                break

    # 3. Hotel with ALL NA
    for idx, row in result_df.iterrows():
        count = sum(1 for c in weeks if pd.notna(row[c]) and str(row[c]).strip() not in ['', 'NA'])
        if count == 0:
            match = raw_df[raw_df['hotel_name'] == row['hotel_name']]
            if len(match) > 0:
                test_cases.append((row['hotel_name'], match.iloc[0]['hotel_url'], row['room_type'], "ALL NA (0/6)"))
                break

    print(f"\n📋 Test cases ({len(test_cases)}):")
    for name, url, room, label in test_cases:
        print(f"   [{label}] {name} → {room}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )

        for name, url, room, label in test_cases:
            await diagnose_hotel(browser, name, url, room, label)

        await browser.close()

    print(f"\n{'='*60}", flush=True)
    print(f"📁 Debug files saved to: {DEBUG_DIR}/", flush=True)
    print(f"   Check screenshots and HTML files for visual analysis", flush=True)
    print(f"{'='*60}", flush=True)

asyncio.run(main())
