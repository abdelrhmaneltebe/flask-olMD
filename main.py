from flask import Flask, request, render_template, send_file, jsonify
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import pandas as pd
import time
from io import BytesIO


# Initialize Flask app
app = Flask(__name__)

def click_load_more_if_available(driver):
    """
    Clicks 'Load more results' if available.
    """
    while True:
        try:
            load_more_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, '//button[span[contains(text(), "Load more results")]]'))
            )
            load_more_button.click()
            print("Clicked 'Load more results' button.")
            time.sleep(2)
        except Exception:
            print("No 'Load more results' button found.")
            break


def close_sign_in_popup(driver):
    """
    Closes the sign-in popup if it appears.
    """
    try:
        popup_close_button = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Dismiss sign-in info."]'))
        )
        popup_close_button.click()
        print("Sign-in popup dismissed.")
    except Exception:
        print("No sign-in popup to close.")


def set_currency_to_usd(driver):
    """
    Sets the currency to USD.
    """
    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="header-currency-picker-trigger"]'))
        ).click()
        print("Currency picker opened.")

        usd_option = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, '//span[contains(text(), "U.S. Dollar")]/ancestor::button'))
        )
        usd_option.click()
        print("USD selected.")
        time.sleep(1)
    except Exception as e:
        print("Error setting currency:", e)


def apply_free_cancellation_filter(driver):
    """
    Applies the 'Free cancellation' filter.
    """
    try:
        free_cancellation_filter = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//div[@data-filters-group="fc"]//input[@type="checkbox" and @value="2"]/following-sibling::span'))
        )
        free_cancellation_filter.click()
        print("Free cancellation filter applied.")
        time.sleep(2)
    except Exception as e:
        print("Error applying 'Free cancellation' filter:", e)


def get_full_page_html_with_scrolling(driver, url):
    """
    Ensures all content is loaded by scrolling and handling lazy loading.
    """
    driver.get(url)
    time.sleep(5)

    close_sign_in_popup(driver)
    set_currency_to_usd(driver)
    apply_free_cancellation_filter(driver)

    last_height = None
    while True:
        try:
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("No more content to load.")
                break
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            last_height = new_height
            click_load_more_if_available(driver)
        except Exception as e:
            print(f"Error during scrolling: {e}")
            break

    return driver.page_source


def extract_room_data(html_content):
    """
    Extracts room data and ensures all rows are captured.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    property_cards = soup.find_all('div', {'data-testid': 'property-card'})

    room_data = []
    for card in property_cards:
        url_element = card.find('a', {'data-testid': 'property-card-desktop-single-image'})
        room_url = url_element['href'] if url_element else "Not available"
        room_url = f"https://www.booking.com{room_url}" if room_url and not room_url.startswith("http") else room_url

        hotel_name = card.find('div', {'data-testid': 'title'})
        hotel_name = hotel_name.get_text(strip=True) if hotel_name else "Hotel name not available"

        price_element = card.find('span', {'data-testid': 'price-and-discounted-price'})
        room_price = price_element.get_text(strip=True) if price_element else "Price not available"

        room_data.append({
            'Hotel Name': hotel_name,
            'Room URL': room_url,
            'Room Price': room_price
        })

    print(f"Extracted {len(room_data)} rows.")  # Log the number of rows extracted
    return room_data


def scrape_booking_data(url):
    """
    Orchestrates the scraping process.
    """
    start_time = time.time()
    driver = uc.Chrome()
    try:
        html_content = get_full_page_html_with_scrolling(driver, url)
        room_data = extract_room_data(html_content)

        # Save to in-memory Excel file
        output_buffer = BytesIO()
        pd.DataFrame(room_data).to_excel(output_buffer, index=False)
        output_buffer.seek(0)
        print(f"Scraping completed. Total rows: {len(room_data)}")
        return output_buffer
    finally:
        driver.quit()
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Total time taken: {elapsed_time:.2f} seconds.")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/Booking_scrape', methods=['POST'])
def scrape():
    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        excel_file = scrape_booking_data(url)
        return send_file(excel_file, as_attachment=True, download_name='room_data_usd.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
