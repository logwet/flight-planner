import copy
import datetime
import re
import shelve
import sys
import time
import urllib.parse
from ast import literal_eval
from itertools import permutations, starmap
from multiprocessing import Pool
from pathlib import Path
from typing import Generator, Callable

if not sys.version_info >= (3, 9):
    print("Python 3.9 or higher is required to run this script.")
    exit(1)


def td(x) -> datetime.timedelta:
    return datetime.timedelta(days=x)


NUMBER_OF_PEOPLE = 4
# TIME_BETWEEN_ACTIONS = 0.1
START_DATE = datetime.date(2023, 11, 18)
END_DATE = datetime.date(2024, 1, 21)
SEARCH_DATE = START_DATE + td(7)
LATEST_LEAVE_DELAY = 7
PARALLELISATION = 16
DRIVER_TIMEOUT = 25
OLD_DATA = 72

MASTER_ORIGIN_CITY = "Melbourne"
DESTINATION_CITIES = {"Colombo": (7, 14), "Kuala Lumpur": (7, 14), "Bangkok": (5, 7), "Singapore": (5, 7)}


class FlightData:
    def __init__(self, timestamp: datetime.datetime, flights: dict[datetime.date, int]):
        self.timestamp: datetime.datetime = timestamp
        self.flights: dict[datetime.date, int] = flights

    def is_old(self):
        return datetime.datetime.now() - self.timestamp > datetime.timedelta(hours=OLD_DATA)

    def get_flights(self) -> dict[datetime.date, int]:
        return self.flights

    def get_flight(self, date: datetime.date) -> int:
        return self.flights.get(date, default=None)

    def __len__(self):
        return len(self.flights)

    def items(self):
        return self.flights.items()


class FlightDatabase:
    def __init__(self, shelf: shelve.Shelf):
        self.shelf: shelve.Shelf = shelf

    def get_flight(self, origin: str, destination: str) -> FlightData:
        return self.shelf.get(repr((origin, destination)), default=FlightData(datetime.datetime.min, {}))

    def set_flight(self, origin: str, destination: str, flights: dict[datetime.date, int]):
        self.shelf[repr((origin, destination))] = FlightData(datetime.datetime.now(), flights)

    def read_state(self) -> dict[tuple[str, str], dict[datetime.date, int]]:
        return {literal_eval(k): copy.deepcopy(v.get_flights()) for k, v in self.shelf.items()}


def urlify(s: str) -> str:
    return urllib.parse.quote(s.encode('utf8'))


def _get_search_url(origin: str, destination: str) -> str:
    return "https://www.google.com/travel/flights?q=" + urlify(
        f"one way flights for {NUMBER_OF_PEOPLE} people from {origin} to {destination} on {SEARCH_DATE.strftime('%d/%m/%Y')}")


def scrape_price_graph(origin: str, destination: str) -> tuple[tuple[str, str], dict[datetime.date, int]]:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.wait import WebDriverWait
    from selenium.common.exceptions import TimeoutException

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
        time.sleep(max(DRIVER_TIMEOUT, 5))
        children = element.find_elements(By.CLASS_NAME, "ZMv3u")

        for e in children:
            try:
                actions.move_to_element(e).click().perform()
                WebDriverWait(driver, DRIVER_TIMEOUT).until(
                    EC.visibility_of_element_located((By.XPATH, "//span/div/div/div/div/div[3]/div")))
                WebDriverWait(driver, DRIVER_TIMEOUT).until(
                    EC.visibility_of_element_located((By.XPATH, "//div[3]/div[2]/span")))
                date_element = WebDriverWait(driver, DRIVER_TIMEOUT).until(
                    lambda x: x.find_element(By.XPATH, "//span/div/div/div/div/div[3]/div"))
                price_element = WebDriverWait(driver, DRIVER_TIMEOUT).until(
                    lambda x: x.find_element(By.XPATH, "//div[3]/div[2]/span"))

                if date_element.text:
                    date = datetime.datetime.strptime(date_element.text, "%a, %b %d").date()
                    if date.month <= datetime.datetime.now().month:
                        date = date.replace(year=datetime.datetime.now().year + 1)
                    else:
                        date = date.replace(year=datetime.datetime.now().year)

                    if date < START_DATE or date > END_DATE or date in data:
                        continue

                    raw_cost = re.sub('\D', '', price_element.text)

                    if raw_cost and (cost := int(raw_cost)) > 0:
                        data[date] = cost
            except Exception as e:
                print("Error scraping date in price graph", e)
                continue

    try:
        driver.get(_get_search_url(origin, destination))

        time.sleep(3)

        actions = ActionChains(driver)

        try:
            element = WebDriverWait(driver, min(DRIVER_TIMEOUT, 5)).until(
                EC.element_to_be_clickable((By.XPATH, "//div[2]/div/div/div[3]/button/div")))
        except TimeoutException:
            element = WebDriverWait(driver, min(DRIVER_TIMEOUT, 5)).until(
                EC.element_to_be_clickable((By.XPATH, "//div[2]/div[2]/div/div/div[2]/button/div")))

        actions.move_to_element(element).click().perform()

        time.sleep(3)

        _scrape()

        element = WebDriverWait(driver, DRIVER_TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, "//span/div/div[2]/button/div[3]")))
        actions.move_to_element(element).click().perform()

        _scrape()
    except Exception as e:
        print("Error scraping", origin, destination, e)
    finally:
        driver.quit()

    data = dict(sorted(reversed(data.items()), key=lambda x: x[1]))

    if (len(data) > 0):
        return (origin, destination), data
    return (None, None), None


class FinishedRouteException(Exception):
    ...


def find_cheapest_flights_for_route(flight_db: dict[tuple[str, str], dict[datetime.date, int]],
                                    route: tuple[str, ...]) -> \
        dict[tuple[str, str], tuple[datetime.date, int]]:
    flights: dict[tuple[str, str], tuple[datetime.date, int]] = {}

    # noinspection PyTypeChecker
    get_legs: Callable[[], Generator[tuple[str, str], None, None]] = lambda: zip(route, route[1:])

    first_leg = next(get_legs())

    # noinspection PyTypeChecker
    flight_db[first_leg] = dict(sorted(reversed(flight_db[first_leg].items()), key=lambda x: x[1]))

    flight_generators: dict[tuple[str, str], Generator[(datetime.date, int), None, None]] = {
        i: ((dc) for dc in flight_db[i].items()) for i in get_legs()}

    def step(leg_generator: Generator[tuple[str, str], None, None], start_date: datetime.date) -> bool:
        try:
            i = next(leg_generator)
        except StopIteration:
            raise FinishedRouteException

        o, d = i

        if o in DESTINATION_CITIES:
            end_date = start_date + td(DESTINATION_CITIES[o][1])
            start_date = start_date + td(DESTINATION_CITIES[o][0])
        else:
            end_date = start_date + td(LATEST_LEAVE_DELAY)

        try:
            while (flight := next(flight_generators[i]))[0] < start_date or flight[0] > end_date:
                pass
        except StopIteration:
            return False

        if flight[0] < start_date or flight[0] > end_date:
            return False

        start_date = flight[0]

        flights[i] = flight

        while not step(leg_generator, start_date):
            pass

        return True

    try:
        # noinspection PyTypeChecker
        step(get_legs(), START_DATE)
    except FinishedRouteException:
        pass

    return flights


def main():
    Path("data").mkdir(parents=True, exist_ok=True)
    with shelve.open("data/cached_flight_data", "c") as shelf:
        flight_db = FlightDatabase(shelf)

        unscraped_flights = set(
            i for i in permutations(list(DESTINATION_CITIES.keys()) + [MASTER_ORIGIN_CITY], 2) if
            flight_db.get_flight(*i).is_old())

        print("Unscraped flights:", unscraped_flights)

        with Pool(PARALLELISATION) as pool:
            results = pool.starmap(scrape_price_graph, unscraped_flights)
            pool.close()
            pool.join()

        for (origin, destination), result in results:
            if result is None: continue
            flight_db.set_flight(origin, destination, result)

        flight_db_state = flight_db.read_state()

    routes = [tuple([MASTER_ORIGIN_CITY] + list(x) + [MASTER_ORIGIN_CITY]) for x in
              permutations(DESTINATION_CITIES.keys())]

    cheap_flights: dict[tuple[str, ...], dict[tuple[str, str], tuple[datetime.date, int]]] = dict(
        zip(routes, starmap(find_cheapest_flights_for_route, [(flight_db_state, x) for x in routes])))

    def cost_of_route(x: dict[tuple[str, str], tuple[datetime.date, int]]):
        return sum(y[1] for y in x.values())

    for route, flights in cheap_flights.items():
        print("Route", route, "for", cost_of_route(flights), "AUD")
        for (o, d), (date, cost) in flights.items():
            print(o, "->", d, "on", date, "for", cost, "AUD")
        print()

    cheapest_route, cheapest_flights = min(cheap_flights.items(), key=lambda x: cost_of_route(x[1]))

    print("Cheapest route is", cheapest_route, "for", cost_of_route(cheapest_flights), "AUD")


if __name__ == '__main__':
    main()
