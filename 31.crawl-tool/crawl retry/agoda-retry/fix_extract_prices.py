"""
FIX: Giá crawl Agoda bị lệch vì lấy giá gốc (struck-through) thay vì giá thực tế.

Chạy script này để xem đoạn EXTRACT_PRICES_JS đã được fix.
Copy đoạn code mới vào notebook cell thay thế đoạn cũ.

Thay đổi chính:
1. Thêm helper function `isStrikethroughElement()` để detect giá gốc bị gạch ngang
2. Trong vòng loop children của `[data-testid='offer-price']`:
   - Tách actual prices (không bị gạch) vs original prices (bị gạch)
   - Ưu tiên actual prices trước
3. Thêm fallback qua tree walker cũng skip struck-through elements
"""

EXTRACT_PRICES_JS_FIXED = """(targetRoom) => {
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

            // Fallback: extract from full text using regex (but try to get the LAST price,
            // which is typically the actual price in Agoda's layout)
            const text = p.textContent.trim();
            if (!text) return;
            
            // 2026-04 FIX: If we found original prices but no actual prices from children,
            // try to extract all prices from the full text and take the last one
            // (Agoda layout: original price first, then actual price)
            if (originalPrices.length > 0) {
                const allMatches = [];
                // Find all price patterns in the text
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
            // Last resort: push raw text (should rarely happen now)
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
            // Prefer actual prices
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

if __name__ == "__main__":
    print("=" * 60)
    print("EXTRACT_PRICES_JS - FIXED VERSION")
    print("=" * 60)
    print()
    print("Copy đoạn code dưới đây vào notebook cell thay thế")
    print("biến EXTRACT_PRICES_JS hiện tại:")
    print()
    print("-" * 60)
    
    # Format for notebook (with proper escaping)
    notebook_version = EXTRACT_PRICES_JS_FIXED.replace('\\', '\\\\')
    print(f'EXTRACT_PRICES_JS = """{EXTRACT_PRICES_JS_FIXED}"""')
    
    print("-" * 60)
    print()
    print("Thay đổi chính:")
    print("1. Thêm function isStrikethroughElement() để detect giá gốc bị gạch ngang")
    print("2. Tách actual prices vs original prices trong offer-price loop") 
    print("3. Ưu tiên actual prices, chỉ dùng original prices khi không có actual")
    print("4. Tree walker fallback cũng skip struck-through elements")
