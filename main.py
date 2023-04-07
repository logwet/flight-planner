import datetime
import re
import time
import urllib.parse
from itertools import permutations
from typing import Tuple, Dict

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


def td(x) -> datetime.timedelta:
    return datetime.timedelta(days=x)


NUMBER_OF_PEOPLE = 4
# TIME_BETWEEN_ACTIONS = 0.1
START_DATE = datetime.date(2023, 11, 18)
END_DATE = datetime.date(2024, 1, 21)
SEARCH_DATE = START_DATE + td(7)
LATEST_LEAVE_DELAY = 21

driverOptions = Options()
driverOptions.add_argument('--headless')

driver = webdriver.Chrome(options=driverOptions)
driver.maximize_window()

price_database: Dict[Tuple[str], Dict[datetime.date, int]] = {}


def urlify(s: str) -> str:
    return urllib.parse.quote(s.encode('utf8'))


def _get_search_url(origin: str, destination: str) -> str:
    return "https://www.google.com/travel/flights?q=" + urlify(
        f"one way flights for {NUMBER_OF_PEOPLE} people from {origin} to {destination} on {SEARCH_DATE.strftime('%d/%m/%Y')}")


def open_page(url):
    driver.get(url)


def scrape_price_graph() -> Dict[datetime.date, int]:
    actions = ActionChains(driver)

    element = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//div[2]/div[2]/div/div/div[2]/button/div")))
    actions.move_to_element(element).click().perform()

    data: Dict[datetime.date, int] = {}

    def _scrape_graph():
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "g[series-id='price graph']")))
        element = WebDriverWait(driver, 5).until(
            lambda x: x.find_element(By.CSS_SELECTOR, "g[series-id='price graph']"))

        WebDriverWait(driver, 5).until(lambda x: len(x.find_elements(By.CLASS_NAME, "ZMv3u")) > 10)
        time.sleep(5)
        children = element.find_elements(By.CLASS_NAME, "ZMv3u")

        for e in children:
            actions.move_to_element(e).click().perform()
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, "//span/div/div/div/div/div[3]/div")))
            WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, "//div[3]/div[2]/span")))
            date_element = WebDriverWait(driver, 5).until(
                lambda x: x.find_element(By.XPATH, "//span/div/div/div/div/div[3]/div"))
            price_element = WebDriverWait(driver, 5).until(lambda x: x.find_element(By.XPATH, "//div[3]/div[2]/span"))

            date = datetime.datetime.strptime(date_element.text, "%a, %b %d").date()
            if date.month <= datetime.datetime.now().month:
                date = date.replace(year=datetime.datetime.now().year + 1)
            else:
                date = date.replace(year=datetime.datetime.now().year)

            if date < START_DATE or date > END_DATE or date in data:
                continue

            cost = int(re.sub('\D', '', price_element.text))

            data[date] = cost

    _scrape_graph()

    element = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//span/div/div[2]/button/div[3]")))
    actions.move_to_element(element).click().perform()

    _scrape_graph()

    return data


def get_prices(origin: str, destination: str) -> Dict[datetime.date, int]:
    if (origin, destination) not in price_database:
        open_page(_get_search_url(origin, destination))
        price_database[(origin, destination)] = scrape_price_graph()
    return price_database[(origin, destination)]


master_origin_city = "Melbourne"
destination_cities = {"Colombo": (5, 14), "Kuala Lumpur": (5, 14), "Bangkok": (3, 7)}
routes = (tuple([master_origin_city] + list(x) + [master_origin_city]) for x in permutations(destination_cities.keys(), 3))

route_costs: Dict[Tuple[str], int] = {}

for route in routes:
    earliest_date = START_DATE
    total_cost = 0

    for origin, destination in zip(route, route[1:]):
        all_costs: Dict[datetime.date, int] = get_prices(origin, destination)

        if origin in destination_cities:
            latest_date = earliest_date + td(destination_cities[origin][1])
            earliest_date = earliest_date + td(destination_cities[origin][0])
        else:
            latest_date = earliest_date + td(LATEST_LEAVE_DELAY)

        flights_in_date_range = {date: cost for date, cost in all_costs.items() if
                                 (date >= earliest_date and date <= latest_date)}

        cheapest_date = min(flights_in_date_range, key=flights_in_date_range.get)
        cheapest_cost = flights_in_date_range[cheapest_date]

        print("Cheapest flight from", origin, "to", destination, "is on", cheapest_date.strftime("%d/%m/%Y"), "for",
              cheapest_cost, "AUD")

        earliest_date = cheapest_date
        total_cost += cheapest_cost

    route_costs[route] = total_cost
    print("Total cost for", route, "route is", total_cost, "AUD")

driver.quit()

cheapest_route = min(route_costs, key=route_costs.get)
cheapest_route_cost = route_costs[cheapest_route]

print("Cheapest route is", cheapest_route, "for", cheapest_route_cost, "AUD")
