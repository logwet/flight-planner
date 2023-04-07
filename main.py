import time

import selenium
from selenium import webdriver

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

NUMBER_OF_PEOPLE=4
TIME_BETWEEN_ACTIONS=0.1

driverOptions = Options()
# driverOptions.add_argument('--headless')
# driverOptions.add_argument("--window-size=1920,1080")

# Setup chromedriver
driver = webdriver.Chrome(options=driverOptions)

def _wait_for_element(name):
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, name)))
    WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, name)))

def click_thing(name):
    # _wait_for_element(name)
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, name))).click()
    # element = WebDriverWait(driver, 5).until(lambda x: x.find_element(By.XPATH, name))
    # actions = ActionChains(driver)
    # actions.move_to_element(element).click().perform()
    time.sleep(TIME_BETWEEN_ACTIONS)

def send_text(name, text):
    _wait_for_element(name)
    element = WebDriverWait(driver, 5).until(lambda x: x.find_element(By.XPATH, name))
    actions = ActionChains(driver)
    actions.move_to_element(element).send_keys(text).perform()
    WebDriverWait(driver, 5).until(lambda x: x.find_element(By.XPATH, name).get_attribute('value') == text)
    time.sleep(TIME_BETWEEN_ACTIONS)

def send_keys(name, keys):
    _wait_for_element(name)
    element = WebDriverWait(driver, 5).until(lambda x: x.find_element(By.XPATH, name))
    actions = ActionChains(driver)
    actions.move_to_element(element).send_keys(keys).perform()
    time.sleep(TIME_BETWEEN_ACTIONS)

# Open the page
driver.get("https://www.google.com/travel/flights")

# Click on type of flight
click_thing("//span[2]")

# Select one way
click_thing("//li[2]")
time.sleep(3)

# Click people
click_thing("//div[2]/div/div/div/button/span/span")

# Add num of people
for i in range(NUMBER_OF_PEOPLE-1):
    click_thing("//span[3]/button/div[3]")

# Click done
click_thing("//div[2]/button/div")

# Click on origin city input
click_thing("//input")

# Type in origin city
send_text("//div[2]/div[2]/div/div/input", "new")
send_keys("//div[2]/div[2]/div/div/input", Keys.ENTER)

# Click on destination city input
click_thing("//div[4]/div/div/div/div/div/input")

# Type in destination city
send_text("//div[2]/div[2]/div/div/input", "jak")
send_keys("//li/div[2]/div/div", Keys.ENTER)

# Click on departure date input
click_thing("//div[2]/div[2]/div/div/div/div/div/div/div/div/div/input")

# Type in departure date
send_text("//div[2]/div/div[2]/div/div/div/div/input", "Jan 2 2024")

# Enter departure date
send_keys("//div[2]/div/div[2]/div/div/div/div/input", Keys.ENTER)

# Save date
click_thing("//div[3]/div/button/div[3]")

time.sleep(1)

# Search flights
click_thing("//div[2]/div/div/div[2]/div/button/div")

time.sleep(1)

# Open price graph
click_thing("//div[2]/div/div/div[3]/button/div")

time.sleep(1)

WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "g[series-id='price graph']")))
element = WebDriverWait(driver, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, "g[series-id='price graph']"))
children = element.find_elements(By.CSS_SELECTOR, "*")
actions = ActionChains(driver)
for e in children:
    actions.move_to_element(e).click().perform()
    WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, "//span/div/div/div/div/div[3]/div")))
    t = WebDriverWait(driver, 5).until(lambda x: x.find_element(By.XPATH, "//span/div/div/div/div/div[3]/div"))
    print(t.text)


while True:
    ...

# # Close the browser
# driver.quit()