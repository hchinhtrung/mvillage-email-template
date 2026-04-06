#!/usr/bin/env python3
"""Fix Agoda crawl notebooks: skip strikethrough prices, take last (final) price."""
import json
import os
import sys

# All notebook files to fix
NOTEBOOKS = [
    "/Users/hchinhtrung/Documents/GitHub/mvillage-email-template/31.crawl-tool/agoda/agoda1-check/Crawl Price AGODA - check.ipynb",
    "/Users/hchinhtrung/Documents/GitHub/mvillage-email-template/31.crawl-tool/agoda/agoda1/Crawl Price AGODA - 1.ipynb",
    "/Users/hchinhtrung/Documents/GitHub/mvillage-email-template/31.crawl-tool/agoda/agoda2/Crawl Price AGODA - 2.ipynb",
    "/Users/hchinhtrung/Documents/GitHub/mvillage-email-template/31.crawl-tool/agoda/agoda3/Crawl Price AGODA - 3.ipynb",
    "/Users/hchinhtrung/Documents/GitHub/mvillage-email-template/31.crawl-tool/agoda/agoda4/Crawl Price AGODA - 4.ipynb",
]

# Old code to find (the buggy offer-price extraction block)
OLD_CODE_LINES = [
    "        let prices = [];\n",
    "        // 2026-03: New Agoda selectors for price display\n",
    "        // Strategy: try to find price from individual child elements first (avoid concatenated text)\n",
    "        room.querySelectorAll(\\\"[data-testid='offer-price']\\\").forEach(p => {\n",
    "            // First, try to find price from direct child spans/divs (more precise)\n",
    "            let found = false;\n",
    "            const children = p.querySelectorAll('span, div, strong, b');\n",
    "            for (const child of children) {\n",
    "                const ct = child.textContent.trim();\n",
    "                // Look for elements that contain ONLY a price pattern\n",
    "                if (/^[₫đ]?\\\\s*\\\\d[\\\\d.,\\\\s]*\\\\d\\\\s*[₫đ]?$/.test(ct)) {\n",
    "                    const clean = extractCleanPrice(ct);\n",
    "                    if (clean) { prices.push(clean); found = true; break; }\n",
    "                }\n",
    "            }\n",
    "            if (found) return;\n",
    "\\n\",\n",
    "            // Fallback: extract from full text using regex\n",
    "            const text = p.textContent.trim();\n",
    "            if (!text) return;\n",
    "            const clean = extractCleanPrice(text);\n",
    "            if (clean) { prices.push(clean); return; }\n",
    "            // Last resort: push raw text (should rarely happen now)\n",
    "            if (text) prices.push(text);\n",
    "        });\n",
]

# The key markers to find the block
BLOCK_START = "        let prices = [];\\n"
BLOCK_END_MARKER = "        // Fallback: old selectors\\n"

# New code to replace
NEW_CODE_LINES = [
    "        let prices = [];\\n",
    "\\n",
    "        // 2026-04: Helper to detect strikethrough/original price elements\\n",
    "        // Agoda shows: ~~original price~~ → discounted price → final price after cashback\\n",
    "        // We must SKIP the strikethrough price and take the FINAL price\\n",
    "        function isStrikethrough(el) {\\n",
    "            let node = el;\\n",
    "            for (let i = 0; i < 5 && node && node !== room; i++) {\\n",
    "                const style = window.getComputedStyle(node);\\n",
    "                if (style.textDecoration.includes('line-through') ||\\n",
    "                    style.textDecorationLine.includes('line-through')) return true;\\n",
    "                if (node.tagName === 'DEL' || node.tagName === 'S') return true;\\n",
    "                node = node.parentElement;\\n",
    "            }\\n",
    "            return false;\\n",
    "        }\\n",
    "\\n",
    "        // 2026-04: New strategy — collect ALL non-strikethrough prices, take the LAST one\\n",
    "        // On Agoda: last price = \\\"Price after Cashback\\\" = the actual price\\n",
    "        room.querySelectorAll(\\\"[data-testid='offer-price']\\\").forEach(p => {\\n",
    "            let offerPrices = [];\\n",
    "            const children = p.querySelectorAll('span, div, strong, b');\\n",
    "            for (const child of children) {\\n",
    "                // SKIP strikethrough (original/gach ngang) prices\\n",
    "                if (isStrikethrough(child)) continue;\\n",
    "                const ct = child.textContent.trim();\\n",
    "                // Look for elements that contain ONLY a price pattern\\n",
    "                if (/^[₫đ]?\\\\s*\\\\d[\\\\d.,\\\\s]*\\\\d\\\\s*[₫đ]?$/.test(ct)) {\\n",
    "                    const clean = extractCleanPrice(ct);\\n",
    "                    if (clean) offerPrices.push(clean);\\n",
    "                }\\n",
    "            }\\n",
    "            // Take the LAST non-strikethrough price (= final price after cashback)\\n",
    "            if (offerPrices.length > 0) {\\n",
    "                prices.push(offerPrices[offerPrices.length - 1]);\\n",
    "                return;\\n",
    "            }\\n",
    "\\n",
    "            // Fallback: extract from full text using regex\\n",
    "            const text = p.textContent.trim();\\n",
    "            if (!text) return;\\n",
    "            const clean = extractCleanPrice(text);\\n",
    "            if (clean) { prices.push(clean); return; }\\n",
    "            // Last resort: push raw text (should rarely happen now)\\n",
    "            if (text) prices.push(text);\\n",
    "        });\\n",
]


def fix_notebook(path):
    """Fix a single notebook file."""
    if not os.path.exists(path):
        print(f"  ⚠️  SKIP: File not found: {os.path.basename(path)}")
        return False
    
    with open(path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    fixed = False
    for cell_idx, cell in enumerate(nb.get('cells', [])):
        if cell.get('cell_type') != 'code':
            continue
        
        source = cell.get('source', [])
        # Join all source lines to search
        full_source = ''.join(source)
        
        if "let prices = [];" not in full_source:
            continue
        if "offer-price" not in full_source:
            continue
        
        # Find the block to replace
        # Strategy: find start marker, find end marker, replace between them
        start_idx = None
        end_idx = None
        
        for i, line in enumerate(source):
            if "let prices = [];" in line and start_idx is None:
                start_idx = i
            if start_idx is not None and "// Fallback: old selectors" in line:
                end_idx = i
                break
        
        if start_idx is None or end_idx is None:
            print(f"  ⚠️  Could not find block markers in cell {cell_idx}")
            continue
        
        # Check if already fixed
        block = ''.join(source[start_idx:end_idx])
        if "isStrikethrough" in block:
            print(f"  ✅ Already fixed: {os.path.basename(path)}")
            return True
        
        # Build new source lines
        new_source = source[:start_idx] + NEW_CODE_LINES + source[end_idx:]
        cell['source'] = new_source
        fixed = True
        break
    
    if fixed:
        # Clear outputs
        for cell in nb.get('cells', []):
            if cell.get('cell_type') == 'code':
                cell['outputs'] = []
                cell['execution_count'] = None
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)
        print(f"  ✅ FIXED: {os.path.basename(path)}")
        return True
    else:
        print(f"  ❌ Could not find target block in: {os.path.basename(path)}")
        return False


def main():
    print("🔧 Fixing Agoda crawl notebooks — skip strikethrough prices")
    print("=" * 60)
    
    success = 0
    for nb_path in NOTEBOOKS:
        print(f"\n📄 {os.path.basename(nb_path)}")
        if fix_notebook(nb_path):
            success += 1
    
    print(f"\n{'=' * 60}")
    print(f"✅ Fixed {success}/{len(NOTEBOOKS)} notebooks")
    
    if success > 0:
        print("\n💡 Next steps:")
        print("   1. Open notebook in VS Code / Jupyter")
        print("   2. Run the crawl on a few hotels to verify prices")
        print("   3. Compare with Agoda website directly")
    
    return 0 if success == len(NOTEBOOKS) else 1


if __name__ == "__main__":
    sys.exit(main())
