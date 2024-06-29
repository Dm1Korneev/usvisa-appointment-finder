import datetime
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from creds import username, password, facility_name, latest_notification_date, seconds_between_checks
from telegram import send_message, send_photo, send_debug_message, send_debug_photo
from urls import BASE_URL, SIGN_IN_URL, SCHEDULE_URL, APPOINTMENTS_URL


def log_in(driver, attempts):    
    if driver.current_url == APPOINTMENTS_URL:
        print('Logged in.')
        return
    
    if (attempts == 0):
        send_debug_message('Cant login')
        send_debug_photo(driver.get_screenshot_as_png())
        raise Exception('Cant login')

    print('Logging in.')

    # Clicking the OK button in the "You need to sign in or sign up before continuing" dialog
    ok_button = driver.find_element(By.XPATH, '/html/body/div[7]/div[3]/div/button')
    if ok_button:
        ok_button.click()

    # Filling the user and password
    user_box = driver.find_element(By.NAME, 'user[email]')
    user_box.send_keys(username)
    password_box = driver.find_element(By.NAME, 'user[password]')
    password_box.send_keys(password)

    # Clicking the checkbox
    driver.find_element(By.XPATH, '//*[@id="sign_in_form"]/div[3]/label/div').click()

    # Clicking 'Sign in'
    driver.find_element(By.XPATH, '//*[@id="sign_in_form"]/p[1]/input').click()

    time.sleep(2)
    attempts = attempts - 1

    log_in(driver, attempts)


def is_worth_notifying(year, month, days):
    first_available_date_object = datetime.datetime.strptime(f'{year}-{month}-{days[0]}', "%Y-%B-%d")
    latest_notification_date_object = datetime.datetime.strptime(latest_notification_date, '%Y-%m-%d')

    return first_available_date_object <= latest_notification_date_object

def rebook_day(year, month, days):
    for day in days:
        print(day)
        date = datetime.datetime.strptime(f'{year}-{month}-{day}', "%Y-%B-%d")
        forbidden = False
        for forbidden_period in get_forbidden_periods():
            if date >= forbidden_period[0] and date <= forbidden_period[1]:
                forbidden = True
                break
        if not forbidden:
            return day
    return False

def get_forbidden_periods():
    return [
        [datetime.datetime.strptime('2024-06-20', '%Y-%m-%d'), datetime.datetime.strptime('2024-07-30', '%Y-%m-%d')],
        [datetime.datetime.strptime('2024-09-01', '%Y-%m-%d'), datetime.datetime.strptime('2024-09-20', '%Y-%m-%d')]
    ]

def check_appointments(driver):
    driver.get(APPOINTMENTS_URL)
    # Waiting for the page to load.
    time.sleep(2)
    
    attempts = 3
    log_in(driver, attempts)

    # Clicking the Continue button in case of rescheduling multiple people to include all
    continue_button = driver.find_element(By.CLASS_NAME, 'primary')
    if continue_button and continue_button.get_property('value') == 'Continue':
        continue_button.click()

    time.sleep(3)

    # # Selecting the facility
    # facility_select = Select(driver.find_element(By.ID, 'appointments_consulate_appointment_facility_id'))
    # facility_select.select_by_visible_text(facility_name)
    # time.sleep(2)

    if driver.find_element(By.ID, 'consulate_date_time_not_available').is_displayed():
        print("No dates available")
        return

    time.sleep(3)

    # Click on "Date of Appointment" to display calendar
    driver.find_element(By.ID, 'appointments_consulate_appointment_date').click()

    while True:
        for date_picker in driver.find_elements(By.CLASS_NAME, 'ui-datepicker-group'):
            day_elements = date_picker.find_elements(By.TAG_NAME, 'td')
            available_days_elements = [day_element.find_element(By.TAG_NAME, 'a')
                              for day_element in day_elements if day_element.get_attribute("class") == ' undefined']

            available_days = list(map(lambda element: element.get_attribute("textContent"), available_days_elements))

            if available_days:
                month = date_picker.find_element(By.CLASS_NAME, 'ui-datepicker-month').get_attribute("textContent")
                year = date_picker.find_element(By.CLASS_NAME, 'ui-datepicker-year').get_attribute("textContent")
                message = f'Available days found in {month} {year}: {", ".join(available_days)}. Link: {SIGN_IN_URL}'
                print(message)

                if not is_worth_notifying(year, month, available_days):
                    print("Not worth notifying.")
                    return

                need_rebook = rebook_day(year, month, available_days)
                if (need_rebook is False):
                    return

                print(f'Rebooking {need_rebook}')
                day = list(filter(lambda element: element.get_attribute("textContent") == need_rebook, available_days_elements))
                day[0].click()

                time.sleep(2)

                time_select = Select(driver.find_element(By.ID, 'appointments_consulate_appointment_time'))
                options = time_select.options
                time_select.select_by_value(time_select.options[1].get_attribute("textContent"))

                driver.find_element(By.ID, 'appointments_submit').click()

                driver.find_element(By.XPATH, "//a[@class='button alert']").click()

                send_message(message)
                send_photo(driver.get_screenshot_as_png())

                return

        # Skipping two months since we processed both already
        driver.find_element(By.CLASS_NAME, 'ui-datepicker-next').click()
        driver.find_element(By.CLASS_NAME, 'ui-datepicker-next').click()


def main():
    chrome_options = Options()
    # chrome_options.add_argument("--headless")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    while True:
        current_time = time.strftime('%a, %d %b %Y %H:%M:%S', time.localtime())
        print(f'Starting a new check at {current_time}.')
        try:
            check_appointments(driver)
        except Exception as err:
            print(f'Exception: {err}')
            if 'disconnected' in f'{err}':
                print('Reconnecting...')
                driver.quit()
                driver = webdriver.Chrome(service=service, options=chrome_options)

        time.sleep(seconds_between_checks)


if __name__ == "__main__":
    main()
