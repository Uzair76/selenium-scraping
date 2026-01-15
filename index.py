from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
import os
import time

# =========================
# Config
# =========================
START_URL = "https://nz.ingrammicro.com/Site/Search#category%3aCameras%20%26%20Scanners"
folder_name = "cameras_scanners"

ALL_LINKS_TXT = f"{folder_name}.txt"
MISSING_LINKS_TXT = f"{folder_name}_missing.txt"

PAGE_LOAD_TIMEOUT = 120
DETAIL_WAIT_TIMEOUT = 25
RETRIES = 3
DELAY_BETWEEN_PRODUCTS = 1.2

PRODUCT_CONTAINER_CSS = ".container.product-separator.product_info_panel_lstView"
TRACKING_LINK_CLASS = "js-adobe-tracking"

# =========================
# Setup Chrome
# =========================
chrome_options = Options()
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--disable-http2")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.page_load_strategy = "normal"

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

if not os.path.exists(folder_name):
    os.makedirs(folder_name)

# =========================
# Helpers
# =========================
def wait_dom_complete(timeout=60):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

def wait_overlay_gone(timeout=20):
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.ID, "overlay"))
        )
    except TimeoutException:
        pass

def safe_get(url: str, dom_timeout=60):
    try:
        driver.get(url)
    except TimeoutException:
        print(f"Timed out loading: {url} (continuing)")
    try:
        wait_dom_complete(timeout=dom_timeout)
    except TimeoutException:
        pass
    wait_overlay_gone(timeout=20)

def wait_products_present(timeout=60):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_CSS))
    )

def first_product_href():
    try:
        containers = driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_CSS)
        if not containers:
            return None
        a = containers[0].find_element(By.CLASS_NAME, TRACKING_LINK_CLASS)
        return a.get_attribute("href")
    except Exception:
        return None

def wait_products_stable(min_count=12, stable_seconds=1.2, timeout=30):
    """
    Wait until product list count is >= min_count and remains unchanged for stable_seconds.
    If last page has fewer than min_count, it will still proceed after timeout.
    """
    end = time.time() + timeout
    last_count = -1
    last_change = time.time()

    while time.time() < end:
        count = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_CSS))

        if count != last_count:
            last_count = count
            last_change = time.time()

        if count >= min_count and (time.time() - last_change) >= stable_seconds:
            return True

        time.sleep(0.25)

    return False

def get_last_page_number() -> int:
    """
    Reads <a id="lastPage" href="#8"> and returns 8 (fallback: 1)
    """
    try:
        last = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "lastPage")))
        href = (last.get_attribute("href") or "").strip()
        if "#" in href:
            return int(href.split("#")[-1])
    except Exception:
        pass
    return 1

def wait_active_page(page_num: int, timeout=20):
    """
    Wait until pagination shows the clicked page as active:
    <li class="page-item active"><a class="page-link">2</a></li>
    """
    def _active_is_correct(d):
        try:
            active = d.find_element(By.CSS_SELECTOR, "#search-paging-container li.page-item.active a.page-link")
            return active.text.strip() == str(page_num)
        except Exception:
            return False

    WebDriverWait(driver, timeout).until(_active_is_correct)

def go_to_page(page_num: int):
    """
    Click page link href="#N" then wait for:
    - active page marker becomes N
    - first product changes (if possible)
    - product list stabilizes
    """
    old_first = first_product_href()

    # click page number link
    link_css = f"#search-paging-container a.page-link[href='#{page_num}']"
    link = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, link_css)))
    driver.execute_script("arguments[0].click();", link)

    # wait overlay + active page marker
    wait_overlay_gone(timeout=20)
    wait_active_page(page_num, timeout=25)

    # wait for results change (first product link changes)
    def changed(_):
        try:
            new_first = first_product_href()
            return new_first is not None and new_first != old_first
        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(driver, 25).until(changed)
    except TimeoutException:
        # Sometimes first item doesn't change immediately; that's okay as long as list stabilizes
        pass

    # wait products list is present and stable
    wait_products_present(timeout=60)
    wait_products_stable(min_count=12, stable_seconds=1.2, timeout=30)
    time.sleep(0.4)

def collect_links_on_current_page():
    wait_products_present(timeout=60)
    wait_products_stable(min_count=12, stable_seconds=1.2, timeout=30)

    links = []
    for c in driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_CSS):
        try:
            a = c.find_element(By.CLASS_NAME, TRACKING_LINK_CLASS)
            href = a.get_attribute("href")
            if href:
                links.append(href)
        except Exception:
            pass
    return links

# =========================
# Step 0: Load search page fully
# =========================
safe_get(START_URL, dom_timeout=60)
wait_products_present(timeout=60)
wait_products_stable(min_count=12, stable_seconds=1.2, timeout=30)

# =========================
# Step 1: Collect ALL product links across ALL pages
# =========================
all_product_links = []

last_page = get_last_page_number()
print(f"Detected last page: {last_page}")

# Page 1
page_links = collect_links_on_current_page()
print(f"Total product links found on page 1: {len(page_links)}")
all_product_links.extend(page_links)

# Pages 2..last
for page_number in range(2, last_page + 1):
    go_to_page(page_number)
    page_links = collect_links_on_current_page()
    print(f"Total product links found on page {page_number}: {len(page_links)}")
    all_product_links.extend(page_links)

# Deduplicate links (keep order)
all_product_links = list(dict.fromkeys(all_product_links))

print(f"Total product links collected: {len(all_product_links)}")

with open(ALL_LINKS_TXT, "w", encoding="utf-8") as f:
    for link in all_product_links:
        f.write(link + "\n")
print(f"Saved all links to {ALL_LINKS_TXT}")

# =========================
# Step 2: Visit each product link & save HTML (wait for full load)
# =========================
missing_urls = []

def try_open_and_save(url: str, index: int) -> bool:
    for attempt in range(1, RETRIES + 1):
        try:
            safe_get(url, dom_timeout=60)

            # Wait for product section
            product_detail = WebDriverWait(driver, DETAIL_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.ID, "productDetailMainSection"))
            )

            # Wait for SKU field
            sku = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.NAME, "ProductDetail.Sku"))
            ).get_attribute("value") or f"unknown_{index}"

            filename = os.path.join(folder_name, f"{sku}.html")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(product_detail.get_attribute("outerHTML"))

            print(f"[{index}/{len(all_product_links)}] Saved: {filename}")
            return True

        except TimeoutException:
            print(f"[{index}] Attempt {attempt}/{RETRIES} timeout for: {url}")

        except WebDriverException as e:
            print(f"[{index}] Attempt {attempt}/{RETRIES} WebDriver error for: {url}")
            print(f"      {str(e).splitlines()[0]}")

        time.sleep(2 * attempt)

    return False

for idx, link in enumerate(all_product_links, start=1):
    ok = try_open_and_save(link, idx)
    if not ok:
        print(f"[{idx}/{len(all_product_links)}] Skipped: {link}")
        missing_urls.append(link)

    time.sleep(DELAY_BETWEEN_PRODUCTS)

with open(MISSING_LINKS_TXT, "w", encoding="utf-8") as f:
    for link in missing_urls:
        f.write(link + "\n")

print(f"Saved skipped links to {MISSING_LINKS_TXT} (count: {len(missing_urls)})")

time.sleep(2)
driver.quit()
