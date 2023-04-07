import datetime
import time
import urllib.parse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from typing import List, Tuple, Dict
import re

from itertools import permutations

NUMBER_OF_PEOPLE = 4
TIME_BETWEEN_ACTIONS = 0.1
START_DATE = datetime.date(2023, 11, 18)
LATEST_LEAVE_DELAY = 21

driverOptions = Options()
# driverOptions.add_argument('--headless')

driver = webdriver.Chrome(options=driverOptions)
driver.maximize_window()

price_database: Dict[Tuple[str], List[Tuple[datetime.date, int]]] = {}

def urlify(s: str) -> str:
    return urllib.parse.quote(s.encode('utf8'))

def _get_search_url(origin: str, destination: str, date: datetime.date) -> str:
    return "https://www.google.com/travel/flights?q=" + urlify(
        f"one way flights for {NUMBER_OF_PEOPLE} people from {origin} to {destination} on {date.strftime('%d/%m/%Y')}")

def open_page(url):
    driver.get(url)

def td(x) -> datetime.timedelta:
    return datetime.timedelta(days=x)

def scrape_price_graph() -> List[Tuple[datetime.date, int]]:
    actions = ActionChains(driver)

    element = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//div[2]/div[2]/div/div/div[2]/button/div")))
    actions.move_to_element(element).click().perform()

    WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "g[series-id='price graph']")))
    element = WebDriverWait(driver, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, "g[series-id='price graph']"))

    WebDriverWait(driver, 5).until(lambda x: len(x.find_elements(By.CLASS_NAME, "ZMv3u")) > 10)
    time.sleep(5)
    children = element.find_elements(By.CLASS_NAME, "ZMv3u")

    data = []

    for e in children:
        actions.move_to_element(e).click().perform()
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, "//span/div/div/div/div/div[3]/div")))
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, "//div[3]/div[2]/span")))
        date_element = WebDriverWait(driver, 5).until(lambda x: x.find_element(By.XPATH, "//span/div/div/div/div/div[3]/div"))
        price_element = WebDriverWait(driver, 5).until(lambda x: x.find_element(By.XPATH, "//div[3]/div[2]/span"))

        date = datetime.datetime.strptime(date_element.text, "%a, %b %d").date()
        if date.month <= datetime.datetime.now().month:
            date = date.replace(year=datetime.datetime.now().year + 1)
        else:
            date = date.replace(year=datetime.datetime.now().year)

        # if date < START_DATE:
        #     continue

        cost = int(re.sub('\D', '', price_element.text))

        data.append((date, cost))

    return data

def get_prices(origin: str, destination: str, date: datetime.date) -> List[Tuple[datetime.date, int]]:
    if (origin, destination) not in price_database:
        open_page(_get_search_url(origin, destination, date))
        price_database[(origin, destination)] = scrape_price_graph()
    return price_database[(origin, destination)]

origin_city = "Melbourne"
destination_cities = {"Colombo": (5, 14), "Kuala Lumpur": (5, 14), "Bangkok": (3, 7)}
routes = (tuple([origin_city] + list(x) + [origin_city]) for x in permutations(destination_cities.keys(), 3))

for route in routes:
    earliest_date = START_DATE
    for origin, destination in zip(route, route[1:]):
        print("Looking at airfares for ", origin, "to", destination)
        all_costs: List[Tuple[datetime.date, int]] = get_prices(origin, destination, earliest_date)
        print(all_costs)

        if origin_city in destination_cities:
            latest_date = earliest_date + td(destination_cities[origin_city][1])
            earliest_date = earliest_date + td(destination_cities[origin_city][0])
        else:
            latest_date = earliest_date + td(LATEST_LEAVE_DELAY)

        flights_in_date_range = [(date, cost) for date, cost in all_costs if (date >= earliest_date and date <= latest_date)]
        print(flights_in_date_range)

driver.quit()
