import datetime
import re
import time
import urllib.parse
from datetime import date
from itertools import permutations
from multiprocessing import Pool

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
LATEST_LEAVE_DELAY = 60
PARALLELISATION = 16
DRIVER_TIMEOUT = 25

MASTER_ORIGIN_CITY = "Melbourne"
DESTINATION_CITIES = {"Colombo": (7, 14), "Kuala Lumpur": (7, 14), "Bangkok": (5, 7)}

def urlify(s: str) -> str:
    return urllib.parse.quote(s.encode('utf8'))


def _get_search_url(origin: str, destination: str) -> str:
    return "https://www.google.com/travel/flights?q=" + urlify(
        f"one way flights for {NUMBER_OF_PEOPLE} people from {origin} to {destination} on {SEARCH_DATE.strftime('%d/%m/%Y')}")


def scrape_price_graph(origin: str, destination: str) -> tuple[tuple[str, str], dict[date, int]]:
    print("Scraping for ", origin, "to", destination)

    driver_options = Options()
    driver_options.add_argument("--headless=new")
    driver = webdriver.Remote(
        command_executor='http://127.0.0.1:4444/wd/hub',
        desired_capabilities={'browserName': 'chrome', 'javascriptEnabled': True},
        options=driver_options)
    driver.maximize_window()

    data: dict[datetime.date, int] = {}

    def _scrape():
        WebDriverWait(driver, DRIVER_TIMEOUT).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "g[series-id='price graph']")))
        element = WebDriverWait(driver, DRIVER_TIMEOUT).until(
            lambda x: x.find_element(By.CSS_SELECTOR, "g[series-id='price graph']"))

        WebDriverWait(driver, DRIVER_TIMEOUT).until(lambda x: len(x.find_elements(By.CLASS_NAME, "ZMv3u")) > 10)
        time.sleep(max(DRIVER_TIMEOUT, 10))
        children = element.find_elements(By.CLASS_NAME, "ZMv3u")

        for e in children:
            actions.move_to_element(e).click().perform()
            WebDriverWait(driver, DRIVER_TIMEOUT).until(
                EC.visibility_of_element_located((By.XPATH, "//span/div/div/div/div/div[3]/div")))
            WebDriverWait(driver, DRIVER_TIMEOUT).until(
                EC.visibility_of_element_located((By.XPATH, "//div[3]/div[2]/span")))
            date_element = WebDriverWait(driver, DRIVER_TIMEOUT).until(
                lambda x: x.find_element(By.XPATH, "//span/div/div/div/div/div[3]/div"))
            price_element = WebDriverWait(driver, DRIVER_TIMEOUT).until(
                lambda x: x.find_element(By.XPATH, "//div[3]/div[2]/span"))

            date = datetime.datetime.strptime(date_element.text, "%a, %b %d").date()
            if date.month <= datetime.datetime.now().month:
                date = date.replace(year=datetime.datetime.now().year + 1)
            else:
                date = date.replace(year=datetime.datetime.now().year)

            if date < START_DATE or date > END_DATE or date in data:
                continue

            cost = int(re.sub('\D', '', price_element.text))

            data[date] = cost

    try:
        driver.get(_get_search_url(origin, destination))

        actions = ActionChains(driver)

        element = WebDriverWait(driver, DRIVER_TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, "//div[2]/div[2]/div/div/div[2]/button/div")))
        actions.move_to_element(element).click().perform()

        _scrape()

        element = WebDriverWait(driver, DRIVER_TIMEOUT).until(EC.element_to_be_clickable((By.XPATH, "//span/div/div[2]/button/div[3]")))
        actions.move_to_element(element).click().perform()

        _scrape()
    except Exception as e:
        print(origin, destination, e)
    finally:
        driver.quit()

    return (origin, destination), data


if __name__ == '__main__':
    price_database: dict[tuple[str, str], dict[datetime.date, int]] = {}


    def get_prices(origin: str, destination: str) -> dict[datetime.date, int]:
        return price_database[(origin, destination)]

    routes = (tuple([MASTER_ORIGIN_CITY] + list(x) + [MASTER_ORIGIN_CITY]) for x in
              permutations(DESTINATION_CITIES.keys(), 3))

    with Pool(PARALLELISATION) as p:
        results = p.starmap(scrape_price_graph,
                            set(permutations(list(DESTINATION_CITIES.keys()) + [MASTER_ORIGIN_CITY], 2)))
        p.close()
        p.join()
        for identifier, results in results:
            price_database[identifier] = results

    route_costs: dict[tuple[str], int] = {}

    for route in routes:
        earliest_date = START_DATE
        total_cost = 0

        for origin, destination in zip(route, route[1:]):
            all_costs: dict[datetime.date, int] = get_prices(origin, destination)

            if len(all_costs) < 1:
                print("No flights found for", origin, "->", destination)
                continue

            if origin in DESTINATION_CITIES:
                latest_date = earliest_date + td(DESTINATION_CITIES[origin][1])
                earliest_date = earliest_date + td(DESTINATION_CITIES[origin][0])
            else:
                latest_date = earliest_date + td(LATEST_LEAVE_DELAY)

            flights_in_date_range = {date: cost for date, cost in all_costs.items() if
                                     (earliest_date <= date <= latest_date)}

            if len(flights_in_date_range) < 1:
                print("No flights in date range for", origin, "->", destination)
                continue

            cheapest_date = min(flights_in_date_range.__reversed__(), key=flights_in_date_range.get)
            cheapest_cost = flights_in_date_range[cheapest_date]

            print(origin, "->", destination, "at", cheapest_date.strftime("%d/%m/%Y"), "for",
                  cheapest_cost, "AUD")

            earliest_date = cheapest_date
            total_cost += cheapest_cost

        route_costs[route] = total_cost
        print("Total cost for", route, "route is", total_cost, "AUD")

    cheapest_route = min(route_costs, key=route_costs.get)
    cheapest_route_cost = route_costs[cheapest_route]

    print("Cheapest route is", cheapest_route, "for", cheapest_route_cost, "AUD")
