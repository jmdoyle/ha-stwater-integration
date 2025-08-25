from datetime import datetime
import logging
import os
import re
import time as time_module
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .const import LOGIN_PAGE, DEBUG_MODE, BROWSER_DEBUG

_LOGGER = logging.getLogger(__name__)

# Debug directory for screenshots
DEBUG_DIR = "/config/debug"

def ensure_debug_dir():
    """Ensure the debug directory exists"""
    try:
        if not os.path.exists(DEBUG_DIR):
            os.makedirs(DEBUG_DIR, exist_ok=True)
            _LOGGER.debug("Created debug directory: %s", DEBUG_DIR)
    except Exception as e:
        _LOGGER.warning("Failed to create debug directory: %s", e)


def extract_hourly_data(consumption_history):
    """
    Extract hourly water usage data from the current view.

    Args:
        consumption_history (WebElement): The parent element containing consumption data.

    Returns:
        dict: A dictionary with the date as the key and hourly usage data as the value.
    """
    # Extract the date
    period_dates = consumption_history.find_element(By.CLASS_NAME, "period-dates").text

    # Extract hourly usage data
    chart_surface = consumption_history.find_element(By.CLASS_NAME, "recharts-surface")
    usage_data_wrappers = chart_surface.find_elements(
        By.CLASS_NAME, "recharts-layer.recharts-customized-wrapper"
    )
    day_data = []

    for usage_data_wrapper in usage_data_wrappers:
        for usage_element in usage_data_wrapper.find_elements(By.TAG_NAME, "rect"):
            usage = usage_element.get_attribute("aria-label")
            if usage:  # Only add non-empty data
                day_data.append(usage)

    return {period_dates: day_data}


def parse_usage(usage_str):
    match = re.match(r"Usage on (\d+) (am|pm) was (\d+) Litres", usage_str)
    if not match:
        return None, None

    hour, meridiem, value = match.groups()
    hour = int(hour)

    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    return f"{hour:02d}:00", int(value)


def parse_date(date_str, year):
    dt = datetime.strptime(f"{date_str} {year}", "%A %d %B %Y")
    return dt.strftime("%Y-%m-%d")


def get_water_usage(username=None, password=None, selenium_url=None):
    """Get water usage data and return as dictionary.

    Args:
        username (str, optional): Username for login
        password (str, optional): Password for login
        selenium_url (str, optional): URL for Selenium remote webdriver

    Note: Currently returns empty data as placeholder until new usage graphs are available
    """
    if not username or not password or not selenium_url:
        username = os.getenv("WATER_USERNAME")
        password = os.getenv("WATER_PASSWORD")
        selenium_url = os.getenv("SELENIUM_URL")
    if not username or not password or not selenium_url:
        raise ValueError("No credentials or selenium URL provided")

    # Debug mode override - return mock data
    if DEBUG_MODE:
        _LOGGER.debug("Debug mode: returning mock data")
        return {
            "2025-08-24": {
                "00:00": 0,
                "01:00": 0,
                "02:00": 0
            }
        }

    start_time = time_module.time()
    _LOGGER.debug("Starting water usage fetch for user: %s", username[:3] + "***")
    _LOGGER.info("Note: New ST Water website detected - usage graphs not yet available, returning placeholder data")

    try:
        data = {}
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            driver = None
            try:
                _LOGGER.debug("Attempt %d", retry_count + 1)
                options = webdriver.ChromeOptions()
                if not BROWSER_DEBUG:  # Use BROWSER_DEBUG instead of DEBUG_MODE for headless control
                    options.add_argument("--headless")

                # Core stability options
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-web-security")
                options.add_argument("--disable-features=VizDisplayCompositor")
                options.add_argument("--disable-extensions")
                options.add_argument("--disable-plugins")
                options.add_argument("--disable-images")
                options.add_argument("--no-first-run")
                options.add_argument("--disable-default-apps")
                options.add_argument("--disable-background-timer-throttling")
                options.add_argument("--disable-renderer-backgrounding")
                options.add_argument("--disable-backgrounding-occluded-windows")

                # Memory management
                options.add_argument("--memory-pressure-off")
                options.add_argument("--max_old_space_size=4096")
                options.add_argument("--force-device-scale-factor=1")

                # Window management
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--start-maximized")

                # Disable logging and automation detection
                options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                options.add_argument("--disable-blink-features=AutomationControlled")

                # Set user agent to avoid detection
                options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")

                driver = webdriver.Remote(
                    command_executor=selenium_url,
                    options=options
                )

                # Set timeouts for the driver
                driver.set_page_load_timeout(60)
                driver.implicitly_wait(10)

                _LOGGER.debug("Getting usage page (new ST Water website)")
                driver.get(LOGIN_PAGE)
                _LOGGER.debug("Got usage page, current URL: %s", driver.current_url)

                # Take a screenshot for debugging
                if BROWSER_DEBUG:
                    try:
                        ensure_debug_dir()
                        driver.save_screenshot(f"{DEBUG_DIR}/debug_usage_page.png")
                        _LOGGER.debug("Saved screenshot: %s/debug_usage_page.png", DEBUG_DIR)
                    except Exception as e:
                        _LOGGER.warning("Failed to save screenshot: %s", e)

                # Wait a moment for the page to load completely
                time_module.sleep(3)

                # Check if we need to authenticate or if we're already on the usage page
                current_url = driver.current_url
                page_title = driver.title.lower()

                _LOGGER.debug("After navigation - URL: %s, Title: %s", current_url, page_title)

                # Check if we're redirected to a login page
                if "login" in current_url.lower() or "sign-in" in current_url.lower() or "auth" in current_url.lower():
                    _LOGGER.debug("Detected login page, attempting authentication")
                    success = handle_authentication(driver, username, password, start_time)
                    if not success:
                        raise ValueError("Authentication failed")
                elif "usage" in current_url.lower() or "account" in current_url.lower():
                    _LOGGER.debug("Already on usage/account page")
                else:
                    _LOGGER.warning("Unexpected page after navigation: %s", current_url)

                # Take screenshot after authentication/navigation
                if BROWSER_DEBUG:
                    try:
                        ensure_debug_dir()
                        driver.save_screenshot(f"{DEBUG_DIR}/debug_after_auth.png")
                        _LOGGER.debug("Saved screenshot: %s/debug_after_auth.png", DEBUG_DIR)
                    except Exception as e:
                        _LOGGER.warning("Failed to save screenshot: %s", e)

                # Verify we're on the usage page
                final_url = driver.current_url
                _LOGGER.debug("Final URL: %s", final_url)

                if "usage" in final_url.lower() or "account" in final_url.lower():
                    _LOGGER.info("Successfully reached usage page")

                    # TODO: Extract usage data when graphs become available
                    # For now, return placeholder data to indicate successful connection
                    _LOGGER.info("Usage graphs not yet available on new website - returning placeholder data")

                    # Return placeholder data with today's date
                    today = datetime.now().strftime("%Y-%m-%d")
                    data = {
                        today: {
                            "00:00": 0,  # Placeholder values
                            "12:00": 0,
                        }
                    }

                    return data
                else:
                    raise ValueError("Failed to reach usage page")

            except Exception as e:
                elapsed = time_module.time() - start_time
                _LOGGER.warning(
                    "Attempt %d failed after %.2f seconds: %s",
                    retry_count + 1,
                    elapsed,
                    str(e),
                )
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                time_module.sleep(5 * retry_count)

            finally:
                elapsed = time_module.time() - start_time
                _LOGGER.debug("Attempt completed in %.2f seconds", elapsed)
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception as e:
                        _LOGGER.warning("Error closing Chrome driver: %s", e)
                    finally:
                        driver = None

    except Exception as e:
        _LOGGER.error("All attempts failed: %s", str(e))
        raise


def handle_authentication(driver, username, password, start_time):
    """Handle authentication on the new ST Water website"""
    try:
        # Look for various possible login form elements
        _LOGGER.debug("Looking for login form elements")

        # Wait for login form - try different possible selectors
        username_field = None
        password_field = None

        # Try common username field selectors
        for selector in ["#username", "#email", "[name='username']", "[name='email']", "[type='email']", "input[placeholder*='email' i]", "input[placeholder*='username' i]"]:
            try:
                username_field = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                _LOGGER.debug("Found username field with selector: %s", selector)
                break
            except:
                continue

        # Try common password field selectors
        for selector in ["#password", "[name='password']", "[type='password']", "input[placeholder*='password' i]"]:
            try:
                password_field = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                _LOGGER.debug("Found password field with selector: %s", selector)
                break
            except:
                continue

        if not username_field or not password_field:
            _LOGGER.error("Could not find login form fields")
            return False

        _LOGGER.debug("Found login form fields")

        # Clear fields first
        username_field.clear()
        password_field.clear()

        # Type credentials with explicit waits
        _LOGGER.debug("Entering credentials")
        _LOGGER.debug("username: %s", username[:3] + "*" * (len(username) - 3))
        _LOGGER.debug("password: %s", "*" * len(password))

        time_module.sleep(1)
        username_field.send_keys(username)
        time_module.sleep(1)
        password_field.send_keys(password)
        time_module.sleep(1)

        # Take screenshot before clicking login
        if BROWSER_DEBUG:
            try:
                ensure_debug_dir()
                driver.save_screenshot(f"{DEBUG_DIR}/debug_before_login.png")
                _LOGGER.debug("Saved screenshot: %s/debug_before_login.png", DEBUG_DIR)
            except Exception as e:
                _LOGGER.warning("Failed to save screenshot: %s", e)

        # Find and click the login button
        _LOGGER.debug("Looking for login button")
        login_button = None

        # Try common login button selectors
        for selector in ["button[type='submit']", "input[type='submit']", "button:contains('Sign in')", "button:contains('Login')", "button:contains('Log in')", ".login-btn", ".signin-btn"]:
            try:
                login_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                _LOGGER.debug("Found login button with selector: %s", selector)
                break
            except:
                continue

        if not login_button:
            _LOGGER.error("Could not find login button")
            return False

        _LOGGER.debug("Found login button: %s", login_button.text if hasattr(login_button, 'text') else 'N/A')
        login_button.click()
        _LOGGER.debug("Clicked login button")

        # Wait for authentication to complete
        _LOGGER.debug("Waiting for authentication to complete")
        time_module.sleep(5)

        # Check if authentication was successful
        current_url = driver.current_url
        _LOGGER.debug("After login attempt - URL: %s", current_url)

        # If we're no longer on a login page, assume success
        if not any(term in current_url.lower() for term in ["login", "sign-in", "auth"]):
            _LOGGER.debug("Authentication appears successful")
            return True
        else:
            _LOGGER.error("Authentication failed - still on login page")
            return False

    except Exception as e:
        _LOGGER.error("Authentication process failed: %s", str(e))
        return False
