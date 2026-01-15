# generate_csv.py
# Reads saved product HTML files (from Selenium) and generates a CSV including images (comma-separated)

from bs4 import BeautifulSoup
import os
import pandas as pd

# =========================
# Config
# =========================
FOLDER_NAME = "cameras_scanners"  # <-- change this to your folder (same name you used in Selenium)
OUTPUT_CSV = f"{FOLDER_NAME}.csv"

product_data = []

for file in os.listdir(FOLDER_NAME):
    if not file.endswith(".html"):
        continue

    file_path = os.path.join(FOLDER_NAME, file)

    with open(file_path, encoding="utf-8") as f:
        html_doc = f.read()

    soup = BeautifulSoup(html_doc, "html.parser")

    # -------------------------
    # SKU (hidden input field)
    # In your HTML, SKU is: <input id="hsku" name="ProductDetail.Sku" ...>
    # -------------------------
    sku_tag = soup.find("input", {"id": "hsku", "name": "ProductDetail.Sku"})
    sku_value = sku_tag.get("value") if sku_tag else None

    # -------------------------
    # Title (clsProductFullDesc) - remove "Less" anchor etc
    # -------------------------
    title_tag = soup.find("div", class_="clsProductFullDesc")
    full_title = None
    if title_tag:
        for a_tag in title_tag.find_all("a"):
            a_tag.decompose()
        full_title = title_tag.get_text(" ", strip=True)

    # -------------------------
    # VPN (span contains "VPN:")
    # Example: <span ...><span class="bold">VPN: </span>942-000008</span>
    # -------------------------
    vpn = None
    # Find any element containing "VPN:"
    vpn_candidate = soup.find(string=lambda s: s and "VPN:" in s)
    if vpn_candidate:
        vpn = vpn_candidate.split("VPN:")[-1].strip()

    # If not found above, try the specific span pattern
    if not vpn:
        spans = soup.find_all("span", class_="margin-right-md color-font-black")
        for sp in spans:
            txt = sp.get_text(" ", strip=True)
            if "VPN:" in txt:
                vpn = txt.split("VPN:")[-1].strip()
                break

    # -------------------------
    # Price
    # <span id="pdpAddToCartMsrpPriceE">RRP: $ 130.39 EXCL TAX</span>
    # -------------------------
    price = None
    price_tag = soup.find("span", {"id": "pdpAddToCartMsrpPriceE"})
    if price_tag:
        price = price_tag.get_text(" ", strip=True)
        price = price.replace("RRP:", "").strip()

    # -------------------------
    # Description HTML (panel body under collapseZero)
    # -------------------------
    description = None
    desc_panel = soup.find("div", {"id": "collapseZero"})
    if desc_panel:
        desc_body = desc_panel.find("div", class_="panel-body")
        description = str(desc_body) if desc_body else None

    # -------------------------
    # Technical Specs HTML (panel body under collapseOne)
    # -------------------------
    technical_spec = None
    tech_panel = soup.find("div", {"id": "collapseOne"})
    if tech_panel:
        tech_body = tech_panel.find("div", class_="panel-body")
        technical_spec = str(tech_body) if tech_body else None

    # -------------------------
    # Brand (table row with "Brand Name")
    # In your HTML: <td>Brand Name</td><td>Logitech</td>
    # -------------------------
    brand = None
    brand_tag = soup.find(string=lambda s: s and s.strip() == "Brand Name")
    if brand_tag:
        brand_row = brand_tag.find_parent("tr")
        if brand_row:
            tds = brand_row.find_all("td")
            if len(tds) >= 2:
                brand = tds[1].get_text(" ", strip=True)

    # -------------------------
    # Images (comma-separated)
    # Collect all distinct image URLs from:
    # - #imgProductDetails (main image)
    # - any <img> inside product image/gallery area
    # -------------------------
    images = []

    # Main image
    main_img = soup.find("img", {"id": "imgProductDetails"})
    if main_img and main_img.get("src"):
        images.append(main_img["src"].strip())

    # Any other images on page (filter out blanks and duplicates)
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        src = src.strip()

        # Optional: Skip "no-image" placeholder if you want
        if "no-image" in src.lower():
            continue

        images.append(src)

    # Deduplicate while keeping order
    seen = set()
    images = [x for x in images if not (x in seen or seen.add(x))]

    images_csv = ",".join(images) if images else None

    # Append row
    product_data.append({
        "Product ID": sku_value,
        "Title": full_title,
        "Brand": brand,
        "VPN": vpn,
        "Price": price,
        "Product Description": description,
        "Technical Description": technical_spec,
        "Image URLs": images_csv,  # <-- last column: comma-separated image URLs
    })

# Create DataFrame + export
df = pd.DataFrame(product_data)
df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

print(f"Data saved to {OUTPUT_CSV} (rows: {len(df)})")
