# Flight Planner
# Copyright (C) 2023 logwet
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import copy
import datetime
import re
import shelve
import signal
import subprocess
import sys
import time
import urllib.parse
from ast import literal_eval
from itertools import permutations
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Iterator

if not sys.version_info >= (3, 9):
    print("Python 3.9 or higher is required to run this script.")
    exit(1)


def td(x) -> datetime.timedelta:
    return datetime.timedelta(days=x)


# ------ START CONFIGURATION SECTION ------

# How many people are travelling
NUMBER_OF_PEOPLE: int = 4

# What date is the earliest you can fly out from your initial departure city
# YYYY, MM, DD
START_DATE: datetime.date = datetime.date(2023, 11, 18)

# What date is the latest you can fly to your final destination on (ie. when do you need to return home by)
# YYYY, MM, DD
END_DATE: datetime.date = datetime.date(2024, 1, 21)

# How late can you leave from your initial departure city?
# By default this is right up until you want to get home
LATEST_LEAVE_DELAY: int = (END_DATE - START_DATE).days

# Number of hours to keep cached data for
OLD_DATA: int = 24 * 7

# What city are you departing from at the start of your trip
MASTER_ORIGIN_CITY: str = "Melbourne"

# What city are you ending up in at the end of your trip
MASTER_DESTINATION_CITY: str = "Melbourne"

# What cities are you visiting on the way, with the minimum and maximum number of days you want to spend in each city
# "City Name": (minimum days, maximum days)
DESTINATION_CITIES: dict[str, tuple[int, int]] = {
    "Colombo": (7, 14),
    "Kuala Lumpur": (7, 14),  # I want to spend at least a week in KL, but 2 is pushing it
    "Bangkok": (5, 14),
    "Singapore": (5, 14)
}

# ------ END CONFIGURATION SECTION ------

# Only fiddle with these if you know what you're doing
SEARCH_DATE = START_DATE + td(7)
DRIVER_TIMEOUT = 25
PARALLELISATION = max(cpu_count(), 16)


class FlightData:
    def __init__(self, timestamp: datetime.datetime, num_people: int, flights: dict[datetime.date, int]):
        self.timestamp: datetime.datetime = timestamp
        self.num_people = num_people
        self.flights: dict[datetime.date, int] = flights

    def should_be_rescraped(self):
        return (
            not self.flights) or self.num_people != NUMBER_OF_PEOPLE or datetime.datetime.now() - self.timestamp > datetime.timedelta(
            hours=OLD_DATA)

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
        return self.shelf.get(repr((origin, destination)),
                              default=FlightData(datetime.datetime.min, NUMBER_OF_PEOPLE, {}))

    def set_flight(self, origin: str, destination: str, flights: dict[datetime.date, int]):
        self.shelf[repr((origin, destination))] = FlightData(datetime.datetime.now(), NUMBER_OF_PEOPLE, flights)

    def read_state(self) -> dict[tuple[str, str], dict[datetime.date, int]]:
        return {literal_eval(k): copy.deepcopy(v.get_flights()) for k, v in self.shelf.items()}

    def del_flight(self, origin: str, destination: str):
        try:
            del self.shelf[repr((origin, destination))]
        except KeyError:
            pass


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

    print("Scraping for", origin, "to", destination)

    driver_options = Options()
    driver_options.add_argument("--headless=new")
    driver = webdriver.Remote(
        command_executor='http://127.0.0.1:4444/wd/hub',
        # Edit this if you want to use a browser besides chrome
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

    return (origin, destination), data


def find_cheapest_flights_for_route(flight_db: dict[tuple[str, str], dict[datetime.date, int]],
                                    route: tuple[str, ...]) -> \
        dict[tuple[str, str], tuple[datetime.date, int]]:
    class FlightException(Exception):
        ...

    class FinishedRouteException(FlightException):
        def __init__(self, total_cost):
            self.total_cost = total_cost

        def __str__(self):
            return f"Finished route with cost {self.total_cost}"

    class NoFlightsFoundException(FlightException):
        def __init__(self, leg: tuple[str, str]):
            self.leg = leg

        def __str__(self):
            return f"No flights found for leg {self.leg}"

    flights: dict[tuple[str, str], tuple[datetime.date, int]] = {}

    legs = tuple(zip(route, route[1:]))
    num_legs = len(legs)
    first_leg = legs[0]
    leg_indexes = {leg: i for i, leg in enumerate(legs)}

    flight_db = {k: v for k, v in flight_db.items() if k in legs}

    # noinspection PyTypeChecker
    flight_db[first_leg] = dict(sorted(reversed(flight_db[first_leg].items()), key=lambda x: x[1]))

    def _flights_in_range_iterator(leg: tuple[str, str], start_date: datetime.date,
                                   end_date: datetime.date) -> Iterator[tuple[datetime.date, int]]:
        # noinspection PyTypeChecker
        return filter(lambda flight: start_date <= flight[0] <= end_date, flight_db[leg].items())

    cost_of_cheapest_route_so_far: int = 2 ** 63 - 1

    def _step(leg: tuple[str, str], start_date: datetime.date, total_cost: int):
        o, d = leg
        next_leg_index = leg_indexes[leg] + 1

        if leg == first_leg:
            end_date = start_date + td(LATEST_LEAVE_DELAY)
        else:
            end_date = start_date + td(DESTINATION_CITIES[o][1])
            start_date = start_date + td(DESTINATION_CITIES[o][0])

        iterator = _flights_in_range_iterator(leg, start_date, end_date)

        for date, cost in iterator:
            new_total_cost = total_cost + cost

            if next_leg_index < num_legs:
                try:
                    _step(legs[next_leg_index], date, new_total_cost)
                except NoFlightsFoundException:
                    continue
                except FinishedRouteException:
                    flights[leg] = (date, cost)
                    raise FinishedRouteException(new_total_cost)
            else:
                nonlocal cost_of_cheapest_route_so_far
                if new_total_cost < cost_of_cheapest_route_so_far:
                    cost_of_cheapest_route_so_far = new_total_cost
                    flights[leg] = (date, cost)
                    raise FinishedRouteException(new_total_cost)
                continue

        raise NoFlightsFoundException(leg)

    i = 0
    while True:
        try:
            _step(first_leg, START_DATE + td(i), 0)
        except NoFlightsFoundException:
            break
        except FinishedRouteException:
            i += 1

    # noinspection PyTypeChecker
    return dict(reversed(flights.items()))


def main():
    Path("data").mkdir(parents=True, exist_ok=True)
    with shelve.open("data/cached_flight_data", "c") as shelf:
        flight_db = FlightDatabase(shelf)

        unscraped_flights = set(
            i for i in permutations(list(DESTINATION_CITIES.keys()) + [MASTER_ORIGIN_CITY, MASTER_DESTINATION_CITY], 2)
            if
            i not in ((MASTER_ORIGIN_CITY, MASTER_DESTINATION_CITY), (MASTER_DESTINATION_CITY, MASTER_ORIGIN_CITY)) and
            flight_db.get_flight(*i).should_be_rescraped())

        if (len(unscraped_flights) > 0):
            print("Unscraped flights:", unscraped_flights)

            global selenium_server
            selenium_server = subprocess.Popen(["java", "-jar", "bin/selenium-server-4.8.3.jar", "standalone"])
            time.sleep(1)

            with Pool(PARALLELISATION) as pool:
                results = pool.starmap(scrape_price_graph, unscraped_flights)
                pool.close()
                pool.join()

            selenium_server.send_signal(signal.SIGINT)

            for (origin, destination), result in results:
                flight_db.set_flight(origin, destination, result)

        flight_db_state = flight_db.read_state()

    routes = [tuple([MASTER_ORIGIN_CITY] + list(x) + [MASTER_DESTINATION_CITY]) for x in
              permutations(DESTINATION_CITIES.keys())]

    with Pool(PARALLELISATION) as pool:
        cheap_flights: dict[tuple[str, ...], dict[tuple[str, str], tuple[datetime.date, int]]] = dict(
            zip(routes, pool.starmap(find_cheapest_flights_for_route, [(flight_db_state, x) for x in routes])))
        pool.close()
        pool.join()

    def cost_of_route(x: dict[tuple[str, str], tuple[datetime.date, int]]):
        return sum(y[1] for y in x.values())

    def print_info(route: tuple[str, ...], flights: dict[tuple[str, str], tuple[datetime.date, int]], s=True):
        if s: print("Route", route, "for", cost_of_route(flights))
        for (o, d), (date, cost) in flights.items():
            print(o, "->", d, "on", date, "for", cost)
        print()

    for route, flights in cheap_flights.items():
        print_info(route, flights)

    cheapest_route: tuple[str, ...]
    cheapest_flights: dict[tuple[str, str], tuple[datetime.date, int]]
    cheapest_route, cheapest_flights = min(cheap_flights.items(), key=lambda x: cost_of_route(x[1]))

    print("Cheapest route is", cheapest_route, "for", cost_of_route(cheapest_flights))
    print_info(cheapest_route, cheap_flights[cheapest_route], False)


if __name__ == '__main__':
    selenium_server: subprocess.Popen = None
    try:
        main()
    finally:
        if selenium_server is not None:
            print("Closing Selenium Server")
            selenium_server.send_signal(signal.SIGINT)
