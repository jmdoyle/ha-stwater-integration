from datetime import datetime
import logging
import os
import re
import time as time_module
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .const import LOGIN_PAGE, DEBUG_MODE

_LOGGER = logging.getLogger(__name__)


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
    """
    if not username or not password or not selenium_url:
        username = os.getenv("WATER_USERNAME")
        password = os.getenv("WATER_PASSWORD")
        selenium_url = os.getenv("SELENIUM_URL")
    if not username or not password or not selenium_url:
        raise ValueError("No credentials or selenium URL provided")
    start_time = time_module.time()
    _LOGGER.debug("Starting water usage fetch")

    try:
        data = {}
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                _LOGGER.debug("Attempt %d", retry_count + 1)
                options = webdriver.ChromeOptions()
                if not DEBUG_MODE:
                    options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-gpu")
                options.add_argument("--start-maximized")
                options.add_argument("--disable-dev-shm-usage")
                options.add_experimental_option("excludeSwitches", ["enable-logging"])
                driver = webdriver.Remote(command_executor=selenium_url, options=options)
                _LOGGER.debug("Getting log-in page")
                driver.get(LOGIN_PAGE)
                _LOGGER.debug("Got log-in page")

                # Wait for cookie popup with better error handling
                try:
                    _LOGGER.debug("Waiting for cookie popup")
                    cookie_popup = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable(
                            (By.CLASS_NAME, "cookie-request-container")
                        )
                    )
                    _LOGGER.debug("Found cookie popup, clicking")
                    cookie_popup.click()
                    _LOGGER.debug(
                        "Cookie popup handled at %.2f seconds",
                        time_module.time() - start_time,
                    )
                except Exception as e:
                    _LOGGER.warning("Cookie popup handling failed: %s", str(e))
                    # Continue anyway as the cookie popup might not appear

                # Wait for login form with explicit element checks
                _LOGGER.debug("Waiting for login form")
                username_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                password_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "password"))
                )

                # Clear fields first
                username_field.clear()
                password_field.clear()

                # Type credentials with explicit waits
                _LOGGER.debug("Entering credentials")
                _LOGGER.debug("username: %s", username)
                _LOGGER.debug("password: %s", "*" * len(password))
                time_module.sleep(1)  # Small delay before typing
                username_field.send_keys(username)
                time_module.sleep(1)  # Small delay between fields
                password_field.send_keys(password)
                time_module.sleep(1)  # Small delay before submit

                # Find and click the login button instead of using RETURN key
                _LOGGER.debug("Clicking login button")
                login_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
                )
                login_button.click()

                # Wait for successful login
                _LOGGER.debug("Waiting for login to complete")
                tracker_link = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.LINK_TEXT, "MY SMART TRACKER"))
                )

                _LOGGER.debug("Successfully logged in, clicking tracker link")
                tracker_link.click()

                # Switch to Day reporting
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "consumption-history")
                    )
                )
                consumption_history = driver.find_element(
                    By.CLASS_NAME, "consumption-history"
                )
                WebDriverWait(consumption_history, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "button-reset"))
                )
                _LOGGER.debug("Change to Day view")
                period_buttons = consumption_history.find_elements(
                    By.CLASS_NAME, "button-reset"
                )
                for period_button in period_buttons:
                    if period_button.text == "Day":
                        period_button.click()
                        break

                # Dictionary to store all days' data
                usage_data = {}

                while True:  # Loop until there's no more data
                    # Wait for the consumption history to load
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CLASS_NAME, "consumption-history")
                        )
                    )
                    _LOGGER.debug("Getting usage data")
                    consumption_history = driver.find_element(
                        By.CLASS_NAME, "consumption-history"
                    )

                    # Extract current date
                    current_date = consumption_history.find_element(
                        By.CLASS_NAME, "period-dates"
                    ).text

                    # Extract data for the current day
                    daily_data = extract_hourly_data(consumption_history)
                    usage_data.update(daily_data)

                    # Click "Next period range" button to go to the next day
                    next_button = consumption_history.find_element(
                        By.XPATH, "//button[@aria-label='Next period range']"
                    )

                    # Check if the button is disabled
                    if (
                        "disabled" in next_button.get_attribute("class")
                        or not next_button.is_enabled()
                    ):
                        _LOGGER.debug("No more data available. Exiting loop.")
                        break

                    # Click "Next period range" button
                    next_button.click()
                    _LOGGER.debug("Next day")
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.CLASS_NAME, "period-dates").text
                        != current_date
                    )

                for day, hours in usage_data.items():
                    # The date data from ST Water does not have a year. The day data is roughly from the last 8 days so it only matters near the start of a new year.
                    # If the month is January and the day is December, we need to subtract 1 from the year.
                    # This is a bit of a hack but it probably works for the current setup.
                    year = datetime.now().year
                    month = datetime.now().month
                    if month == 1 and "December" in day:
                        year -= 1
                    _LOGGER.debug("Usage for %s: %s", day, hours)
                    iso_date = parse_date(day, year)
                    time_data = {}
                    for usage in hours:
                        time, value = parse_usage(usage)
                        if time:
                            time_data[time] = value
                    data[iso_date] = time_data

                return data

            except Exception as e:
                raise

            finally:
                elapsed = time_module.time() - start_time
                _LOGGER.debug("Execution completed in %.2f seconds", elapsed)
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception as e:
                        _LOGGER.warning("Error closing Chrome driver: %s", e)
                    finally:
                        driver = None

    except Exception as e:
        retry_count += 1
        _LOGGER.warning(
            "Attempt %d failed after %.2f seconds: %s",
            retry_count,
            time_module.time() - start_time,
            str(e),
        )
        if retry_count >= max_retries:
            raise
        time_module.sleep(5 * retry_count)
