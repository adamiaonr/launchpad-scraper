#!/usr/bin/env python

import os
import sys
import optparse
import urllib
import requests
import js2xml
import re
import json
import pandas as pd 
import csv

from BeautifulSoup import BeautifulSoup
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from cStringIO import StringIO
# for webpage parsing
from lxml import html
from lxml import etree
from io import StringIO, BytesIO
from collections import defaultdict

GOOGLE_APS_URL_PREFIX = "http://play.google.com"
GOOGLE_APS_URL_APP_COLLECTION = "/collection/topselling_free"
GOOGLE_APS_URL_APP_DETAILS = "/details?id="

# interesting categories
GOOGLE_APS_CATS = [
    "AUTO_AND_VEHICLES",
    "EVENTS",
    "FOOD_AND_DRINK",
    "MAPS_AND_NAVIGATION"
]

# set a 'human-like' user-agent header: not setting this may block http 
# requests from the scraper
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:27.0) Gecko/20100101 Firefox/27.0'
}

def parse_app(title, url):

    app = dict()

    # extract the app page from Google Play
    url = GOOGLE_APS_URL_PREFIX + url + "&hl=en"
    page = requests.get(url, headers=headers)
    # extract the html for further parsing
    html_app = html.fromstring(page.content)

    # cycle through each app, save a dict() for each
    app['title'] = title.encode('utf-8')
    app['link'] = url.encode('utf-8')

    for e in html_app.xpath("//div[@itemprop='description']/div/text()"):
        app['description'] = e.encode('utf-8')
    for e in html_app.xpath("//div[@itemprop='numDownloads']/text()"):
        ll, ul = e.split("-", 1)
        app['lower-limit'] = int(ll.replace(",","").replace(" ", "").encode('utf-8'))
        app['upper-limit'] = int(ul.replace(",","").replace(" ", "").encode('utf-8'))

    return app

def main():
    
    usage = """google-apps-scraper.py [options]

web scraper for google apps lists

Examples:
"""

    fmt = optparse.IndentedHelpFormatter(max_help_position=50, width=100)
    parser = optparse.OptionParser(usage=usage, formatter=fmt)

    group = optparse.OptionGroup(parser, 'Google apps query arguments',
                                 'e.g. categories to search for, path of output .csv file')
    group.add_option('-c', '--category', metavar='CATEGORY', default=None,
                     help="category of app (e.g. 'AUTO_AND_VEHICLES'). fetches all categories by default.")
    group.add_option('-f', '--output-file', metavar='OUTPUT_FILE', default='apps.csv',
                     help="output .csv file")
    parser.add_option_group(group)

    options, _ = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        return 1

    # crawl all categories, save results in .csv file
    with open(options.output_file, 'wb') as csv_file:

        writer = csv.writer(csv_file)
        first_row = False
        category_list = []

        # if a category is specified, stick to it, otherwise fetch all of them
        if options.category:
            category_list.append(options.category)
        else:
            category_list = GOOGLE_APS_CATS

        for cat in category_list:
            # build the url for the category
            url = GOOGLE_APS_URL_PREFIX + "/store/apps/category/" + cat + GOOGLE_APS_URL_APP_COLLECTION + "?hl=en"
            # get the webpage
            page = requests.get(url, headers=headers)
            # extract the raw html text into an object which can be parsed
            html_code = html.fromstring(page.content)
            # cycle through each app
            for app in html_code.cssselect("div.details a.title"):
                app = parse_app(app.attrib['title'], app.attrib['href'])
                app['category'] = cat

                try:
                    # write a row of keys first
                    if not first_row:
                        writer.writerow(app.keys())
                        first_row = True
                    writer.writerow(app.values())
                except:
                    print("launchpad-scraper.py::main() : [ERROR] unknown error parsing JSON")

if __name__ == "__main__":
    sys.exit(main())
