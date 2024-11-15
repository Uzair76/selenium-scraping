from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os
import time

# Set up Chrome options to ignore SSL certificate errors
chrome_options = Options()
chrome_options.add_argument("--ignore-certificate-errors")

# Initialize the Chrome driver with the specified options
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
driver.get("https://nz.ingrammicro.com/Site/Search#category%3aOther%20Marketing%20Services")

# Step 1: Create a directory to save product HTML pages
folder_name = 'other_marketing_services'
if not os.path.exists(folder_name):
    os.makedirs(folder_name)

# Step 2: Collect all product links by explicitly navigating through three pages
all_product_links = []

for page_number in range(1, 4):  # Explicitly iterate over the three pages
    try:
        # If not on the first page, navigate to the page number link
        if page_number > 1:
            page_link = driver.find_element(By.XPATH, f"//ul[@id='search-paging-container']//a[@href='#{page_number}']")
            driver.execute_script("arguments[0].click();", page_link)
            # Wait for the overlay to disappear after clicking the page link
            WebDriverWait(driver, 10).until(EC.invisibility_of_element_located((By.ID, "overlay")))

        # Wait for product containers to load on each page
        product_containers = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".container.product-separator.product_info_panel_lstView"))
        )

        # Extract product links from containers
        for container in product_containers:
            try:
                link_element = container.find_element(By.CLASS_NAME, 'js-adobe-tracking')
                product_link = link_element.get_attribute('href')
                all_product_links.append(product_link)
            except Exception as e:
                print(f"Error extracting link: {e}")

        print(f"Total product links found on page {page_number}: {len(product_containers)}")

    except Exception as e:
        print(f"Error navigating or scraping page {page_number}: {e}")
        break

print(f"Total product links collected: {len(all_product_links)}")

# Array to store links that fail to be scraped successfully
missing_urls = []

# Step 3: Visit each product link and save the HTML content
for index, test_link in enumerate(all_product_links):
    driver.get(test_link)
    try:
        # Wait for the main product detail section to load fully
        product_detail_section = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, 'productDetailMainSection'))
        )

        # Additional explicit waits for elements inside the detail section to ensure full loading
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#collapseZero"))  # Ensure description is loaded
        )
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#collapseOne"))   # Ensure technical specs are loaded
        )

        # Get only the main product detail section HTML
        product_detail_html = product_detail_section.get_attribute('outerHTML')

        # Locate the SKU input field to name the file
        sku_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'ProductDetail.Sku'))
        )
        sku_value = sku_element.get_attribute('value')

        # Define the filename for saving the product HTML
        filename = os.path.join(folder_name, f"{sku_value}.html")

        # Save the HTML content to a file
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(product_detail_html)

        print(f"Saved HTML file: {filename}")

    except Exception as e:
        print(f"Error occurred while fetching product details from {test_link}: {e}")
        missing_urls.append(test_link)  # Add link to missing_urls if an error occurs

# Print any missing URLs at the end
if missing_urls:
    print(f"Links that failed to scrape successfully: {len(missing_urls)}")
    for link in missing_urls:
        print(link)

# Close the browser
time.sleep(5)
driver.quit()
