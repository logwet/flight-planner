# Flight Planner

Python Script that scrapes [Google Flights](https://www.google.com/travel/flights) and runs a basic algorithm to determine an optimal (cheap) route between any number of destinations.

## Configuration

Edit the parameters at the top of `main.py`

## Instructions

See the [Requirements Section](#requirements)

`python main.py`

## Algorithm

1. We have the origin city we are flying out of, a list of destinations we want to visit along the way, and a final destination city we want to end up in at the end of our trip (most likely the origin city).
2. What are all possible routes between the origin and final destination that visits all of our destinations?
3. For each of these routes, find all possible flights between the initial departure city (origin) and the first destination - the first leg of our trip
4. Find the flight to the next destination that is the cheapest (our priority!), latest (gives you the most time in the previous city) yet gives you the desired amount of time in that city (not too little, not too much)
5. Repeat until all destinations have been visited and we are at the final destination, which for most people will be back at home (origin)
6. Go back to Step (4) and repeat for the next flight from Step (3) until we have exhausted all possible first leg flights.
7. Of those sets of flights for this particular route, which one was cheapest? This is our optimal strategy for this route.
8. Repeat for all routes from Step (2), which route was cheapest overall?

## Disclaimers

- I put this together to plan a trip and so it has been designed and validated to work for my very specific use case.
- It has only been tested in Australia and may very well not work in other countries. 
- Scraping Google Flights takes a LONG time! Be prepared to wait a while.
- The algorithm is not perfect, there is probably a cheaper route that exists. It is sufficient for my needs.
- Because of ^, flights are cached after being scraped for up to 3 days (configurable). This means your first run of the script should be the longest but subsequent runs wont take as long.
- If you want to force a rescrape of cached data, delete the contents of `data/`
- By default this script will launch as many parallel instances of chrome as you have CPU cores (capped to 16 so I don't DDOS Google), which will put considerable load on your internet connection and your RAM.
- Currency is whatever currency Google Flights chooses to display in your locale

## Requirements

`>= Python 3.9` and the following Python Packages: `selenium` `psutil`. `pip install selenium psutil`

`Java` (to run the bundled `Selenium Server`). If you don't trust the bundled version (which you shouldn't), you can download it from [here](https://www.selenium.dev/downloads/)

A working installation of a `Selenium Driver` for your browser of choice.
The driver must be in the PATH. This script is set up to default to [chromedriver](https://chromedriver.chromium.org/downloads) and you will have to modify it if you wish to use another browser.
