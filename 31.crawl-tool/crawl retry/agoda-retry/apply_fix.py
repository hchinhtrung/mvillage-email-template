"""
Script to apply the EXTRACT_PRICES_JS fix to the notebook.
This script reads the notebook JSON, replaces the EXTRACT_PRICES_JS variable,
and writes the fixed notebook back.

Usage: python apply_fix.py
"""

import json
import re
import sys
import shutil

NOTEBOOK_PATH = "./Crawl Price AGODA - 3.ipynb"
BACKUP_PATH = "./Crawl Price AGODA - 3.BACKUP.ipynb"

# The new EXTRACT_PRICES_JS code (properly escaped for Python triple-quoted string inside notebook source)
NEW_EXTRACT_PRICES_JS_LINES = [
    "EXTRACT_PRICES_JS = \\\"\\\"\\\"(targetRoom) => {\\n",
    "    const results = [];\\n",
    "    // 2026-03: Agoda changed from data-selenium to data-testid\\n",
    "    let masterRooms = document.querySelectorAll(\\\"[data-testid='room-item']\\\");\\n",
    "    // Fallback to old selector for backward compatibility\\n",
    "    if (masterRooms.length === 0) {\\n",
    "        masterRooms = document.querySelectorAll(\\\"[data-selenium='MasterRoom']\\\");\\n",
    "    }\\n",
    "    const targetLower = targetRoom.toLowerCase().trim();\\n",
    "\\n",
    "    // Extract only the numeric price (with ₫ or VND), stripping all surrounding text\\n",
    "    // Handles Agoda variants:\\n",
    "    //   'Giá rẻ nhất từ trước đến nay!Nhanh lên! Phòng cuối cùng của chúng tôi!1.351.852₫Mỗi đêm, chưa có thuế'\\n",
    "    //   'Giá rẻ nhất từ trước đến nay!4 phòng cuối cùng của chúng tôi!4.590.370₫Mỗi đêm, chưa có thuế'\\n",
    "    //   'Giá rẻ nhất từ trước đến nay!-10%Số phòng có hạn900.000₫Mỗi đêm, chưa có thuế'\\n",
    "    //   'Số phòng có hạn2.383.333₫Mỗi đêm, chưa có thuế'\\n",
    "    function extractCleanPrice(text) {\\n",
    "        if (!text) return null;\\n",
    "        // Step 1: Strip known Agoda promotional/urgency prefixes & suffixes\\n",
    "        let cleaned = text;\\n",
    "        cleaned = cleaned.replace(/Giá rẻ nhất[^₫đ\\\\d]*/gi, '');\\n",
    "        cleaned = cleaned.replace(/Nhanh lên[!.]?/gi, '');\\n",
    "        cleaned = cleaned.replace(/\\\\d+\\\\s*phòng cuối cùng[^₫đ\\\\d]*/gi, '');\\n",
    "        cleaned = cleaned.replace(/Phòng cuối cùng[^₫đ\\\\d]*/gi, '');\\n",
    "        cleaned = cleaned.replace(/Số phòng có hạn/gi, '');\\n",
    "        cleaned = cleaned.replace(/-?\\\\d{1,3}%/g, '');\\n",
    "        cleaned = cleaned.replace(/Mỗi đêm[^₫đ]*/gi, '');\\n",
    "        cleaned = cleaned.replace(/chưa có thuế/gi, '');\\n",
    "        cleaned = cleaned.replace(/của chúng tôi[!.]?/gi, '');\\n",
    "        cleaned = cleaned.trim();\\n",
    "\\n",
    "        // Step 2: Try to extract price from cleaned text first, then fallback to original\\n",
    "        function tryExtract(s) {\\n",
    "            const m1 = s.match(/(\\\\d[\\\\d.,]*\\\\d)\\\\s*₫/);\\n",
    "            if (m1) return m1[1].replace(/\\\\s/g, '') + '₫';\\n",
    "            const m2 = s.match(/₫\\\\s*(\\\\d[\\\\d.,]*\\\\d)/);\\n",
    "            if (m2) return '₫' + m2[1].replace(/\\\\s/g, '');\\n",
    "            const m3 = s.match(/(\\\\d[\\\\d.,]*\\\\d)\\\\s*VND/i);\\n",
    "            if (m3) return m3[1].replace(/\\\\s/g, '') + ' VND';\\n",
    "            const m4 = s.match(/VND\\\\s*(\\\\d[\\\\d.,]*\\\\d)/i);\\n",
    "            if (m4) return 'VND ' + m4[1].replace(/\\\\s/g, '');\\n",
    "            const m5 = s.match(/(\\\\d[\\\\d.,]{3,}\\\\d)/);\\n",
    "            if (m5) return m5[1];\\n",
    "            return null;\\n",
    "        }\\n",
    "        return tryExtract(cleaned) || tryExtract(text);\\n",
    "    }\\n",
    "\\n",
    "    function findPriceInText(text) {\\n",
    "        return extractCleanPrice(text);\\n",
    "    }\\n",
    "\\n",
    "    // 2026-04 FIX: Detect struck-through (original) price elements\\n",
    "    // Agoda shows original price with line-through style or <s>/<del> tags\\n",
    "    function isStrikethroughElement(el) {\\n",
    "        if (!el) return false;\\n",
    "        const tag = el.tagName.toLowerCase();\\n",
    "        if (tag === 's' || tag === 'del') return true;\\n",
    "        // Check computed style for line-through\\n",
    "        try {\\n",
    "            const style = window.getComputedStyle(el);\\n",
    "            if (style.textDecorationLine.includes('line-through') || \\n",
    "                style.textDecoration.includes('line-through')) return true;\\n",
    "        } catch(e) {}\\n",
    "        // Check data-testid for original/strikethrough indicators\\n",
    "        const testId = (el.getAttribute('data-testid') || '').toLowerCase();\\n",
    "        if (testId.includes('original') || testId.includes('strike') || testId.includes('crossed')) return true;\\n",
    "        // Check parent for strikethrough (price text might be in a child of <s>)\\n",
    "        const parent = el.parentElement;\\n",
    "        if (parent) {\\n",
    "            const pTag = parent.tagName.toLowerCase();\\n",
    "            if (pTag === 's' || pTag === 'del') return true;\\n",
    "            try {\\n",
    "                const pStyle = window.getComputedStyle(parent);\\n",
    "                if (pStyle.textDecorationLine.includes('line-through') ||\\n",
    "                    pStyle.textDecoration.includes('line-through')) return true;\\n",
    "            } catch(e) {}\\n",
    "            const pTestId = (parent.getAttribute('data-testid') || '').toLowerCase();\\n",
    "            if (pTestId.includes('original') || pTestId.includes('strike') || pTestId.includes('crossed')) return true;\\n",
    "        }\\n",
    "        return false;\\n",
    "    }\\n",
    "\\n",
    "    const bodyText = document.body.innerText || '';\\n",
    "    const hotelSoldOut = /sold\\\\s*out[!.]?\\\\s*(our last room|all rooms)/i.test(bodyText);\\n",
    "    const noAvailability = /no\\\\s*(rooms?)?\\\\s*avail/i.test(bodyText) && masterRooms.length === 0;\\n",
    "\\n",
    "    if ((hotelSoldOut || noAvailability) && masterRooms.length === 0) {\\n",
    "        return {found: false, soldOut: true, soldOutType: 'hotel', allRooms: 0, pageTitle: document.title, bodySnippet: bodyText.substring(0, 300)};\\n",
    "    }\\n",
    "\\n",
    "    masterRooms.forEach(room => {\\n",
    "        // 2026-03: Try new selector first, fallback to old\\n",
    "        let nameEl = room.querySelector(\\\"[data-testid='room-name']\\\");\\n",
    "        if (!nameEl) nameEl = room.querySelector(\\\"[data-selenium='masterroom-title-name']\\\");\\n",
    "        const name = nameEl ? nameEl.textContent.trim() : '';\\n",
    "        const roomText = room.innerText || '';\\n",
    "\\n",
    "        // Check for sold-out via data-testid\\n",
    "        let soldOutPrice = null;\\n",
    "        const soldOutEl = room.querySelector(\\\"[data-testid='sold-out-urgency']\\\");\\n",
    "        if (soldOutEl) {\\n",
    "            const soPrice = extractCleanPrice(soldOutEl.textContent);\\n",
    "            if (soPrice) soldOutPrice = soPrice;\\n",
    "        }\\n",
    "        // Fallback: regex match\\n",
    "        if (!soldOutPrice) {\\n",
    "            const soldOutMatch = roomText.match(/sold\\\\s*out\\\\s*at\\\\s*([₫đ]\\\\s*[\\\\d,. ]+|[\\\\d,.]+\\\\s*[₫đ])/i);\\n",
    "            if (soldOutMatch) soldOutPrice = soldOutMatch[1].trim();\\n",
    "        }\\n",
    "        if (!soldOutPrice) {\\n",
    "            let parent = room.parentElement;\\n",
    "            for (let i = 0; i < 3 && parent; i++) {\\n",
    "                const parentMatch = (parent.innerText || '').match(/sold\\\\s*out\\\\s*at\\\\s*([₫đ]\\\\s*[\\\\d,. ]+|[\\\\d,.]+\\\\s*[₫đ])/i);\\n",
    "                if (parentMatch) { soldOutPrice = parentMatch[1].trim(); break; }\\n",
    "                parent = parent.parentElement;\\n",
    "            }\\n",
    "        }\\n",
    "\\n",
    "        let prices = [];\\n",
    "        // 2026-04 FIX: New strategy - separate actual prices from original (struck-through) prices\\n",
    "        // Agoda shows: [struck-through original price] [-75%] [actual discounted price]\\n",
    "        // We must skip the struck-through price and only take the actual price\\n",
    "        room.querySelectorAll(\\\"[data-testid='offer-price']\\\").forEach(p => {\\n",
    "            let actualPrices = [];\\n",
    "            let originalPrices = [];\\n",
    "            const children = p.querySelectorAll('span, div, strong, b');\\n",
    "            for (const child of children) {\\n",
    "                const ct = child.textContent.trim();\\n",
    "                // Look for elements that contain ONLY a price pattern\\n",
    "                if (/^[₫đ]?\\\\s*\\\\d[\\\\d.,\\\\s]*\\\\d\\\\s*[₫đ]?$/.test(ct)) {\\n",
    "                    const clean = extractCleanPrice(ct);\\n",
    "                    if (!clean) continue;\\n",
    "                    // 2026-04 FIX: Check if this element is struck-through (original price)\\n",
    "                    if (isStrikethroughElement(child)) {\\n",
    "                        originalPrices.push(clean);\\n",
    "                    } else {\\n",
    "                        actualPrices.push(clean);\\n",
    "                    }\\n",
    "                }\\n",
    "            }\\n",
    "            // Prefer actual prices over original prices\\n",
    "            if (actualPrices.length > 0) {\\n",
    "                prices.push(actualPrices[0]);\\n",
    "                return;\\n",
    "            }\\n",
    "\\n",
    "            // Fallback: extract from full text using regex (but try to get the LAST price,\\n",
    "            // which is typically the actual price in Agoda's layout)\\n",
    "            const text = p.textContent.trim();\\n",
    "            if (!text) return;\\n",
    "            \\n",
    "            // 2026-04 FIX: If we found original prices but no actual prices from children,\\n",
    "            // try to extract all prices from the full text and take the last one\\n",
    "            // (Agoda layout: original price first, then actual price)\\n",
    "            if (originalPrices.length > 0) {\\n",
    "                const allMatches = [];\\n",
    "                // Find all price patterns in the text\\n",
    "                const priceRegex = /([₫đ]\\\\s*\\\\d[\\\\d.,]*\\\\d|\\\\d[\\\\d.,]*\\\\d\\\\s*₫)/g;\\n",
    "                let m;\\n",
    "                while ((m = priceRegex.exec(text)) !== null) {\\n",
    "                    const clean = extractCleanPrice(m[0]);\\n",
    "                    if (clean && !originalPrices.includes(clean)) {\\n",
    "                        allMatches.push(clean);\\n",
    "                    }\\n",
    "                }\\n",
    "                if (allMatches.length > 0) {\\n",
    "                    prices.push(allMatches[allMatches.length - 1]);\\n",
    "                    return;\\n",
    "                }\\n",
    "            }\\n",
    "            \\n",
    "            const clean = extractCleanPrice(text);\\n",
    "            if (clean) { prices.push(clean); return; }\\n",
    "            // Last resort: push raw text (should rarely happen now)\\n",
    "            if (text) prices.push(text);\\n",
    "        });\\n",
    "        // Fallback: old selectors\\n",
    "        if (prices.length === 0) {\\n",
    "            room.querySelectorAll(\\\"[data-selenium='PriceDisplay']\\\").forEach(p => {\\n",
    "                const text = p.textContent.trim();\\n",
    "                if (text) {\\n",
    "                    const clean = extractCleanPrice(text);\\n",
    "                    prices.push(clean || text);\\n",
    "                }\\n",
    "            });\\n",
    "        }\\n",
    "        // Fallback: look for price in room-offer-price-info\\n",
    "        if (prices.length === 0) {\\n",
    "            room.querySelectorAll(\\\"[data-testid='room-offer-price-info']\\\").forEach(p => {\\n",
    "                const text = p.textContent.trim();\\n",
    "                if (!text) return;\\n",
    "                const clean = extractCleanPrice(text);\\n",
    "                if (clean) { prices.push(clean); return; }\\n",
    "            });\\n",
    "        }\\n",
    "        // Fallback: text walker (also skip struck-through elements)\\n",
    "        if (prices.length === 0) {\\n",
    "            const walker = document.createTreeWalker(room, NodeFilter.SHOW_TEXT);\\n",
    "            const actualWalkerPrices = [];\\n",
    "            const originalWalkerPrices = [];\\n",
    "            while (walker.nextNode()) {\\n",
    "                const price = extractCleanPrice(walker.currentNode.textContent.trim());\\n",
    "                if (price) {\\n",
    "                    if (isStrikethroughElement(walker.currentNode.parentElement)) {\\n",
    "                        originalWalkerPrices.push(price);\\n",
    "                    } else {\\n",
    "                        actualWalkerPrices.push(price);\\n",
    "                    }\\n",
    "                }\\n",
    "            }\\n",
    "            // Prefer actual prices\\n",
    "            if (actualWalkerPrices.length > 0) {\\n",
    "                prices = actualWalkerPrices;\\n",
    "            } else {\\n",
    "                prices = originalWalkerPrices;\\n",
    "            }\\n",
    "        }\\n",
    "\\n",
    "        results.push({\\n",
    "            name, nameLower: name.toLowerCase().trim(),\\n",
    "            prices: prices.slice(0, 5),\\n",
    "            matched: name.toLowerCase().trim() === targetLower,\\n",
    "            soldOutPrice\\n",
    "        });\\n",
    "    });\\n",
    "\\n",
    "    const target = results.find(r => r.matched);\\n",
    "    if (target) {\\n",
    "        if (target.prices.length > 0) return {found: true, price: target.prices[0], room: target.name, allRooms: results.length};\\n",
    "        if (target.soldOutPrice) return {found: false, soldOut: true, soldOutType: 'room', soldOutPrice: target.soldOutPrice, room: target.name, allRooms: results.length};\\n",
    "    }\\n",
    "    const partial = results.find(r => r.nameLower.includes(targetLower) || targetLower.includes(r.nameLower));\\n",
    "    if (partial) {\\n",
    "        if (partial.prices.length > 0) return {found: true, price: partial.prices[0], room: partial.name, allRooms: results.length, partial: true};\\n",
    "        if (partial.soldOutPrice) return {found: false, soldOut: true, soldOutType: 'room', soldOutPrice: partial.soldOutPrice, room: partial.name, allRooms: results.length, partial: true};\\n",
    "    }\\n",
    "    const allSoldOut = results.length > 0 && results.every(r => r.soldOutPrice && r.prices.length === 0);\\n",
    "    if (allSoldOut) {\\n",
    "        const rel = target || partial || results[0];\\n",
    "        return {found: false, soldOut: true, soldOutType: 'all_rooms', soldOutPrice: rel.soldOutPrice, allRooms: results.length};\\n",
    "    }\\n",
    "    return {found: false, soldOut: false, allRooms: results.length, roomNames: results.map(r => r.name), pageTitle: document.title, bodySnippet: (document.body.innerText || '').substring(0, 300)};\\n",
    "}\\\"\\\"\\\"\\n",
]

def apply_fix():
    # Read notebook
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    # Backup
    shutil.copy2(NOTEBOOK_PATH, BACKUP_PATH)
    print(f"✅ Backup saved: {BACKUP_PATH}")
    
    # Find the cell containing EXTRACT_PRICES_JS
    target_cell = None
    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
        source = ''.join(cell['source'])
        if 'EXTRACT_PRICES_JS' in source and 'targetRoom' in source:
            target_cell = cell
            break
    
    if not target_cell:
        print("❌ Không tìm thấy cell chứa EXTRACT_PRICES_JS!")
        sys.exit(1)
    
    # Find the start and end of EXTRACT_PRICES_JS in the source lines
    source_lines = target_cell['source']
    js_start = None
    js_end = None
    
    for i, line in enumerate(source_lines):
        if 'EXTRACT_PRICES_JS = """' in line or "EXTRACT_PRICES_JS = '''" in line:
            js_start = i
        if js_start is not None and (line.strip().endswith('"""') or line.strip().endswith("'''")):
            if i > js_start:  # Don't match the opening line
                js_end = i
                break
    
    if js_start is None or js_end is None:
        print("❌ Không tìm được vị trí EXTRACT_PRICES_JS trong cell!")
        print(f"   js_start={js_start}, js_end={js_end}")
        sys.exit(1)
    
    print(f"📍 Found EXTRACT_PRICES_JS at lines {js_start}-{js_end} in cell source")
    print(f"   Old: {js_end - js_start + 1} lines")
    print(f"   New: {len(NEW_EXTRACT_PRICES_JS_LINES)} lines")
    
    # Replace the lines
    new_source = source_lines[:js_start] + NEW_EXTRACT_PRICES_JS_LINES + source_lines[js_end + 1:]
    target_cell['source'] = new_source
    
    # Write back
    with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    
    print(f"✅ Fixed notebook saved: {NOTEBOOK_PATH}")
    print()
    print("Thay đổi chính:")
    print("  1. Thêm function isStrikethroughElement() để detect giá gốc bị gạch ngang")
    print("  2. Trong offer-price loop: tách actual prices vs original prices")
    print("  3. Ưu tiên actual prices (giá thực tế) over original prices (giá gốc)")
    print("  4. Tree walker fallback cũng skip struck-through elements")
    print()
    print("⚠️  NHỚ: Xóa file TEMP_agoda3.csv trước khi chạy lại crawler")
    print("         để crawl lại giá mới với logic đã fix!")

if __name__ == "__main__":
    apply_fix()
