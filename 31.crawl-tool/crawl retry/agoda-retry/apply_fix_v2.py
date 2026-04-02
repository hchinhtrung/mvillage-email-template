"""
Script to apply the EXTRACT_PRICES_JS fix to the notebook.
v2: Fixed escaping to match notebook's actual format.
"""

import json
import sys
import shutil

NOTEBOOK_PATH = "./Crawl Price AGODA - 3.ipynb"
BACKUP_PATH = "./Crawl Price AGODA - 3.BACKUP.ipynb"

def get_new_js_lines():
    """Return the new EXTRACT_PRICES_JS source lines with correct escaping.
    Each line is a Python string that, when json.dump'd, produces correct notebook JSON.
    The notebook stores source as list of strings where \\n in the string = newline in code.
    """
    lines = []
    # Build lines exactly like the original format: each line ends with \n
    # and uses single-escaped quotes for JS strings
    
    raw = r'''EXTRACT_PRICES_JS = """(targetRoom) => {
    const results = [];
    // 2026-03: Agoda changed from data-selenium to data-testid
    let masterRooms = document.querySelectorAll("[data-testid='room-item']");
    // Fallback to old selector for backward compatibility
    if (masterRooms.length === 0) {
        masterRooms = document.querySelectorAll("[data-selenium='MasterRoom']");
    }
    const targetLower = targetRoom.toLowerCase().trim();

    // Extract only the numeric price (with ₫ or VND), stripping all surrounding text
    // Handles Agoda variants:
    //   'Giá rẻ nhất từ trước đến nay!Nhanh lên! Phòng cuối cùng của chúng tôi!1.351.852₫Mỗi đêm, chưa có thuế'
    //   'Giá rẻ nhất từ trước đến nay!4 phòng cuối cùng của chúng tôi!4.590.370₫Mỗi đêm, chưa có thuế'
    //   'Giá rẻ nhất từ trước đến nay!-10%Số phòng có hạn900.000₫Mỗi đêm, chưa có thuế'
    //   'Số phòng có hạn2.383.333₫Mỗi đêm, chưa có thuế'
    function extractCleanPrice(text) {
        if (!text) return null;
        // Step 1: Strip known Agoda promotional/urgency prefixes & suffixes
        let cleaned = text;
        cleaned = cleaned.replace(/Giá rẻ nhất[^₫đ\\d]*/gi, '');
        cleaned = cleaned.replace(/Nhanh lên[!.]?/gi, '');
        cleaned = cleaned.replace(/\\d+\\s*phòng cuối cùng[^₫đ\\d]*/gi, '');
        cleaned = cleaned.replace(/Phòng cuối cùng[^₫đ\\d]*/gi, '');
        cleaned = cleaned.replace(/Số phòng có hạn/gi, '');
        cleaned = cleaned.replace(/-?\\d{1,3}%/g, '');
        cleaned = cleaned.replace(/Mỗi đêm[^₫đ]*/gi, '');
        cleaned = cleaned.replace(/chưa có thuế/gi, '');
        cleaned = cleaned.replace(/của chúng tôi[!.]?/gi, '');
        cleaned = cleaned.trim();

        // Step 2: Try to extract price from cleaned text first, then fallback to original
        function tryExtract(s) {
            const m1 = s.match(/(\\d[\\d.,]*\\d)\\s*₫/);
            if (m1) return m1[1].replace(/\\s/g, '') + '₫';
            const m2 = s.match(/₫\\s*(\\d[\\d.,]*\\d)/);
            if (m2) return '₫' + m2[1].replace(/\\s/g, '');
            const m3 = s.match(/(\\d[\\d.,]*\\d)\\s*VND/i);
            if (m3) return m3[1].replace(/\\s/g, '') + ' VND';
            const m4 = s.match(/VND\\s*(\\d[\\d.,]*\\d)/i);
            if (m4) return 'VND ' + m4[1].replace(/\\s/g, '');
            const m5 = s.match(/(\\d[\\d.,]{3,}\\d)/);
            if (m5) return m5[1];
            return null;
        }
        return tryExtract(cleaned) || tryExtract(text);
    }

    function findPriceInText(text) {
        return extractCleanPrice(text);
    }

    // 2026-04 FIX: Detect struck-through (original) price elements
    // Agoda shows original price with line-through style or <s>/<del> tags
    function isStrikethroughElement(el) {
        if (!el) return false;
        const tag = el.tagName.toLowerCase();
        if (tag === 's' || tag === 'del') return true;
        // Check computed style for line-through
        try {
            const style = window.getComputedStyle(el);
            if (style.textDecorationLine.includes('line-through') || 
                style.textDecoration.includes('line-through')) return true;
        } catch(e) {}
        // Check data-testid for original/strikethrough indicators
        const testId = (el.getAttribute('data-testid') || '').toLowerCase();
        if (testId.includes('original') || testId.includes('strike') || testId.includes('crossed')) return true;
        // Check parent for strikethrough (price text might be in a child of <s>)
        const parent = el.parentElement;
        if (parent) {
            const pTag = parent.tagName.toLowerCase();
            if (pTag === 's' || pTag === 'del') return true;
            try {
                const pStyle = window.getComputedStyle(parent);
                if (pStyle.textDecorationLine.includes('line-through') ||
                    pStyle.textDecoration.includes('line-through')) return true;
            } catch(e) {}
            const pTestId = (parent.getAttribute('data-testid') || '').toLowerCase();
            if (pTestId.includes('original') || pTestId.includes('strike') || pTestId.includes('crossed')) return true;
        }
        return false;
    }

    const bodyText = document.body.innerText || '';
    const hotelSoldOut = /sold\\s*out[!.]?\\s*(our last room|all rooms)/i.test(bodyText);
    const noAvailability = /no\\s*(rooms?)?\\s*avail/i.test(bodyText) && masterRooms.length === 0;

    if ((hotelSoldOut || noAvailability) && masterRooms.length === 0) {
        return {found: false, soldOut: true, soldOutType: 'hotel', allRooms: 0, pageTitle: document.title, bodySnippet: bodyText.substring(0, 300)};
    }

    masterRooms.forEach(room => {
        // 2026-03: Try new selector first, fallback to old
        let nameEl = room.querySelector("[data-testid='room-name']");
        if (!nameEl) nameEl = room.querySelector("[data-selenium='masterroom-title-name']");
        const name = nameEl ? nameEl.textContent.trim() : '';
        const roomText = room.innerText || '';

        // Check for sold-out via data-testid
        let soldOutPrice = null;
        const soldOutEl = room.querySelector("[data-testid='sold-out-urgency']");
        if (soldOutEl) {
            const soPrice = extractCleanPrice(soldOutEl.textContent);
            if (soPrice) soldOutPrice = soPrice;
        }
        // Fallback: regex match
        if (!soldOutPrice) {
            const soldOutMatch = roomText.match(/sold\\s*out\\s*at\\s*([₫đ]\\s*[\\d,. ]+|[\\d,.]+\\s*[₫đ])/i);
            if (soldOutMatch) soldOutPrice = soldOutMatch[1].trim();
        }
        if (!soldOutPrice) {
            let parent = room.parentElement;
            for (let i = 0; i < 3 && parent; i++) {
                const parentMatch = (parent.innerText || '').match(/sold\\s*out\\s*at\\s*([₫đ]\\s*[\\d,. ]+|[\\d,.]+\\s*[₫đ])/i);
                if (parentMatch) { soldOutPrice = parentMatch[1].trim(); break; }
                parent = parent.parentElement;
            }
        }

        let prices = [];
        // 2026-04 FIX: New strategy - separate actual prices from original (struck-through) prices
        // Agoda shows: [struck-through original price] [-75%] [actual discounted price]
        // We must skip the struck-through price and only take the actual price
        room.querySelectorAll("[data-testid='offer-price']").forEach(p => {
            let actualPrices = [];
            let originalPrices = [];
            const children = p.querySelectorAll('span, div, strong, b');
            for (const child of children) {
                const ct = child.textContent.trim();
                // Look for elements that contain ONLY a price pattern
                if (/^[₫đ]?\\s*\\d[\\d.,\\s]*\\d\\s*[₫đ]?$/.test(ct)) {
                    const clean = extractCleanPrice(ct);
                    if (!clean) continue;
                    // 2026-04 FIX: Check if this element is struck-through (original price)
                    if (isStrikethroughElement(child)) {
                        originalPrices.push(clean);
                    } else {
                        actualPrices.push(clean);
                    }
                }
            }
            // Prefer actual prices over original prices
            if (actualPrices.length > 0) {
                prices.push(actualPrices[0]);
                return;
            }

            // Fallback: extract from full text using regex
            const text = p.textContent.trim();
            if (!text) return;
            
            // 2026-04 FIX: If we found original prices but no actual prices from children,
            // try to extract all prices from the full text and take the last one
            // (Agoda layout: original price first, then actual price)
            if (originalPrices.length > 0) {
                const allMatches = [];
                const priceRegex = /([₫đ]\\s*\\d[\\d.,]*\\d|\\d[\\d.,]*\\d\\s*₫)/g;
                let m;
                while ((m = priceRegex.exec(text)) !== null) {
                    const clean = extractCleanPrice(m[0]);
                    if (clean && !originalPrices.includes(clean)) {
                        allMatches.push(clean);
                    }
                }
                if (allMatches.length > 0) {
                    prices.push(allMatches[allMatches.length - 1]);
                    return;
                }
            }
            
            const clean = extractCleanPrice(text);
            if (clean) { prices.push(clean); return; }
            if (text) prices.push(text);
        });
        // Fallback: old selectors
        if (prices.length === 0) {
            room.querySelectorAll("[data-selenium='PriceDisplay']").forEach(p => {
                const text = p.textContent.trim();
                if (text) {
                    const clean = extractCleanPrice(text);
                    prices.push(clean || text);
                }
            });
        }
        // Fallback: look for price in room-offer-price-info
        if (prices.length === 0) {
            room.querySelectorAll("[data-testid='room-offer-price-info']").forEach(p => {
                const text = p.textContent.trim();
                if (!text) return;
                const clean = extractCleanPrice(text);
                if (clean) { prices.push(clean); return; }
            });
        }
        // Fallback: text walker (also skip struck-through elements)
        if (prices.length === 0) {
            const walker = document.createTreeWalker(room, NodeFilter.SHOW_TEXT);
            const actualWalkerPrices = [];
            const originalWalkerPrices = [];
            while (walker.nextNode()) {
                const price = extractCleanPrice(walker.currentNode.textContent.trim());
                if (price) {
                    if (isStrikethroughElement(walker.currentNode.parentElement)) {
                        originalWalkerPrices.push(price);
                    } else {
                        actualWalkerPrices.push(price);
                    }
                }
            }
            if (actualWalkerPrices.length > 0) {
                prices = actualWalkerPrices;
            } else {
                prices = originalWalkerPrices;
            }
        }

        results.push({
            name, nameLower: name.toLowerCase().trim(),
            prices: prices.slice(0, 5),
            matched: name.toLowerCase().trim() === targetLower,
            soldOutPrice
        });
    });

    const target = results.find(r => r.matched);
    if (target) {
        if (target.prices.length > 0) return {found: true, price: target.prices[0], room: target.name, allRooms: results.length};
        if (target.soldOutPrice) return {found: false, soldOut: true, soldOutType: 'room', soldOutPrice: target.soldOutPrice, room: target.name, allRooms: results.length};
    }
    const partial = results.find(r => r.nameLower.includes(targetLower) || targetLower.includes(r.nameLower));
    if (partial) {
        if (partial.prices.length > 0) return {found: true, price: partial.prices[0], room: partial.name, allRooms: results.length, partial: true};
        if (partial.soldOutPrice) return {found: false, soldOut: true, soldOutType: 'room', soldOutPrice: partial.soldOutPrice, room: partial.name, allRooms: results.length, partial: true};
    }
    const allSoldOut = results.length > 0 && results.every(r => r.soldOutPrice && r.prices.length === 0);
    if (allSoldOut) {
        const rel = target || partial || results[0];
        return {found: false, soldOut: true, soldOutType: 'all_rooms', soldOutPrice: rel.soldOutPrice, allRooms: results.length};
    }
    return {found: false, soldOut: false, allRooms: results.length, roomNames: results.map(r => r.name), pageTitle: document.title, bodySnippet: (document.body.innerText || '').substring(0, 300)};
}"""
'''
    
    # Split into lines, each ending with \n (matching notebook format)
    for line in raw.split('\n'):
        lines.append(line + '\n')
    
    # Last line should not have trailing \n (it's the end of the cell content for this block)
    if lines and lines[-1] == '\n':
        lines[-1] = '\n'
    
    return lines


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
        if js_start is not None and i > js_start:
            if '"""' in line or "'''" in line:
                js_end = i
                break
    
    if js_start is None or js_end is None:
        print("❌ Không tìm được vị trí EXTRACT_PRICES_JS trong cell!")
        sys.exit(1)
    
    new_lines = get_new_js_lines()
    
    print(f"📍 Found EXTRACT_PRICES_JS at source lines {js_start}-{js_end}")
    print(f"   Old: {js_end - js_start + 1} lines")
    print(f"   New: {len(new_lines)} lines")
    
    # Verify escaping matches original format
    orig_line = repr(source_lines[js_start + 1])  # e.g., line after EXTRACT_PRICES_JS =
    new_line = repr(new_lines[1])
    print(f"   Original format sample: {orig_line[:80]}")
    print(f"   New format sample:      {new_line[:80]}")
    
    # Replace the lines
    new_source = source_lines[:js_start] + new_lines + source_lines[js_end + 1:]
    target_cell['source'] = new_source
    
    # Write back with same formatting
    with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    
    # Verify result
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb2 = json.load(f)
    for cell in nb2['cells']:
        if cell['cell_type'] != 'code':
            continue
        src = ''.join(cell['source'])
        if 'EXTRACT_PRICES_JS' in src and 'isStrikethroughElement' in src:
            print("✅ Verified: isStrikethroughElement found in fixed notebook")
            break
    else:
        print("❌ Verification failed!")
        sys.exit(1)
    
    print(f"\n✅ Fixed notebook saved: {NOTEBOOK_PATH}")
    print("\nThay đổi chính:")
    print("  1. Thêm function isStrikethroughElement() — detect giá gốc bị gạch ngang")
    print("  2. Trong offer-price loop: tách actual vs original prices")
    print("  3. Ưu tiên actual prices (giá thực tế) over original prices (giá gốc)")
    print("  4. Tree walker fallback cũng skip struck-through elements")
    print("\n⚠️  Xóa TEMP_agoda3.csv trước khi chạy lại crawler!")


if __name__ == "__main__":
    apply_fix()
