import os
import time
import logging
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
from webdriver_manager.chrome import ChromeDriverManager
import google.generativeai as genai

# Load environment variables
load_dotenv()
USERNAME = os.getenv("GITHUB_USERNAME")
PASSWORD = os.getenv("GITHUB_PASSWORD")

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Gemini setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(model_name="gemini-1.5-pro")

LOCATOR_MAP = {
    "username": ["login_field", "user_login", "username"],
    "password": ["password", "pass", "login_password"],
    "submit": ["commit", "login_button"]
}

def gemini_locator_suggestion(driver, error_message, element_type):
    prompt = f"""
    Selenium failed with error:
    {error_message}
    Trying to interact with '{element_type}' on GitHub login page.
    Suggest a working locator (CSS or XPath).
    """
    response = model.generate_content(prompt)
    for line in response.text.splitlines():
        if "By.CSS_SELECTOR" in line or "By.XPATH" in line:
            try:
                locator_type = By.CSS_SELECTOR if "CSS_SELECTOR" in line else By.XPATH
                locator_value = line.split('"')[1]
                return WebDriverWait(driver, 10).until(EC.element_to_be_clickable((locator_type, locator_value)))
            except Exception as e:
                logging.warning(f"Gemini suggestion failed: {e}")
    return None

def find_element(driver, by, locators, element_type):
    for locator in locators:
        try:
            element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((by, locator)))
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((by, locator)))
            return element
        except Exception:
            continue
    raise NoSuchElementException(f"All locators failed for {element_type}")

def login(driver, username, password):
    driver.get("https://github.com/login")
    try:
        username_input = find_element(driver, By.ID, LOCATOR_MAP["username"], "username")
        password_input = find_element(driver, By.ID, LOCATOR_MAP["password"], "password")
        submit_button = find_element(driver, By.NAME, LOCATOR_MAP["submit"], "submit")

        username_input.send_keys(username)
        password_input.send_keys(password)
        submit_button.click()

        time.sleep(3)
        if "Incorrect username or password." in driver.page_source:
            logging.error("Login failed: Incorrect credentials.")
            return False
        logging.info("Login successful.")
        return True

    except Exception as e:
        logging.warning(f"Locator error: {e}")
        for field in ["username", "password", "submit"]:
            fixed_element = gemini_locator_suggestion(driver, str(e), field)
            if fixed_element:
                try:
                    if field == "username":
                        fixed_element.send_keys(username)
                    elif field == "password":
                        fixed_element.send_keys(password)
                    elif field == "submit":
                        fixed_element.click()
                    time.sleep(3)
                    if "Incorrect username or password." in driver.page_source:
                        return False
                    return True
                except Exception as inner_e:
                    logging.error(f"Interaction failed: {inner_e}")
        return False

def run_test(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("window-size=1920x1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        if not login(driver, USERNAME, PASSWORD):
            logging.info("Retrying with correct credentials...")
            login(driver, os.getenv("CORRECT_USERNAME"), os.getenv("CORRECT_PASSWORD"))
    finally:
        driver.quit()

if __name__ == "__main__":
    run_test(headless=False)
