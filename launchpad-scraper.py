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
from io import StringIO, BytesIO
from collections import defaultdict

LAUNCHPAD_URL = "https://bugs.launchpad.net/"
LAUNCHPAD_URL_OPTIONS = "field.searchtext=&field.status%3Alist=NEW&field.status%3Alist=OPINION&field.status%3Alist=INVALID&field.status%3Alist=WONTFIX&field.status%3Alist=EXPIRED&field.status%3Alist=CONFIRMED&field.status%3Alist=TRIAGED&field.status%3Alist=INPROGRESS&field.status%3Alist=FIXCOMMITTED&field.status%3Alist=FIXRELEASED&field.status%3Alist=INCOMPLETE_WITH_RESPONSE&field.status%3Alist=INCOMPLETE_WITHOUT_RESPONSE&field.importance%3Alist=CRITICAL&field.importance%3Alist=HIGH&field.importance%3Alist=MEDIUM&field.information_type%3Alist=PUBLIC&field.information_type%3Alist=PUBLICSECURITY&field.information_type%3Alist=PRIVATESECURITY&field.information_type%3Alist=USERDATA&assignee_option=any&field.assignee=&field.bug_reporter=&field.bug_commenter=&field.subscriber=&field.structural_subscriber=&field.tag=&field.tags_combinator=ANY&field.has_cve.used=&field.omit_dupes.used=&field.omit_dupes=on&field.affects_me.used=&field.has_patch.used=&field.has_branches.used=&field.has_branches=on&field.has_no_branches.used=&field.has_no_branches=on&field.has_blueprints.used=&field.has_blueprints=on&field.has_no_blueprints.used=&field.has_no_blueprints=on&search=Search"

def parse_bug_age(age):

    age = age.replace("\n", "")
    numeric = int(re.findall('\d+', age)[0])

    if "year" in age:
        return -(numeric * 365 * 24)
    if "day" in age:
        return -(numeric * 24)
    else:
        return -(numeric)

def cleanup(string):
    return string.replace("\n", "").replace(" ", "")

def parse_bug_list(webpage):

    # set a 'human-like' user-agent header: not setting this may block http 
    # requests from the scraper
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:27.0) Gecko/20100101 Firefox/27.0'
    }

    # get the webpage
    page = requests.get(webpage, headers=headers)
    # parse the page
    root = html.fromstring(page.content)
    # the bug list can be fetched directly from a json encoded variable in  
    # the webpage (in <script id='json-cache-script'>). we extract it, encode it
    # as json and return it.
    # https://classic.scraperwiki.com/docs/python/python_css_guide/
    bugs = root.cssselect("script#json-cache-script")[0]

    return json.loads(bugs.text.split("= ", 1)[1].rstrip(";"))

def main():
    
    usage = """launchpad-scraper.py [options]

web scraper for launchpad.net lists

Examples:

'./launchpad-scraper.py --target openstack --pages 5 --order-by datecreated --output-file bugs-openstack.csv'
"""

    fmt = optparse.IndentedHelpFormatter(max_help_position=50, width=100)
    parser = optparse.OptionParser(usage=usage, formatter=fmt)

    group = optparse.OptionGroup(parser, 'launchpad search query arguments',
                                 'These options define search query arguments and parameters.')

    "https://bugs.launchpad.net/neutron/+bugs?orderby=-importance&start=0"

    group.add_option('-t', '--target', metavar='TARGET', default=None,
                     help="target (e.g. 'openstack', 'nova', 'neutron')")
    group.add_option('-p', '--pages', metavar='PAGES', default=1,
                     help="nr. of pages to fetch")
    group.add_option('--tags', metavar='TAGS', default=None,
                     help="launchpad.net tags, separated by '+'. e.g. '--tags ops+security'.")
    group.add_option('-f', '--output-file', metavar='OUTPUT_FILE', default='bugs.csv',
                     help="output .csv file")
    group.add_option('--order-by', metavar='ORDER', default='importance',
                     help="parameter to sort results (e.g. 'importance'")
    group.add_option('-o', '--offset', type='int', default=None,
                     help='staring nr. for the search result list. default is 0.')
    parser.add_option_group(group)

    options, _ = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        return 1

    if not options.target:
        sys.stderr.write("""launchpad-scraper.py : [ERROR] must specify a target. aborting.\n""") 
        parser.print_help()
        return 1

    # build the launchpad url
    launchpad_url = launchpad_url = LAUNCHPAD_URL + options.target + "/+bugs?" + LAUNCHPAD_URL_OPTIONS + "&orderby=-" + options.order_by
    if options.tags:
        launchpad_url += "&field.tag=" + options.tags

    print launchpad_url

    # query and extract the bug list
    first_row = False
    bugline = dict()
    with open(options.output_file, 'wb') as csv_file:
        for i in xrange(int(options.pages)):

            # update the launchpad url with the correct start offset (based on 
            # nr. of pages, 75 results per page)
            bugs_json = parse_bug_list(launchpad_url + "&start=" + str(i * 75))
            # use a csv writer to create the .csv file which stores the bugs
            writer = csv.writer(csv_file)

            for item in bugs_json['mustache_model']['items']:
                # ... transform the age field a bit
                item['age'] = parse_bug_age(str(item['age']))

                try:

                    bugline['id']           = str(item['id'])
                    bugline['project']      = str(item['bugtarget'])
                    bugline['importance']   = str(item['importance'])
                    bugline['status']       = str(item['status'])
                    bugline['title']        = str(item['title'])
                    bugline['age']          = int(item['age'])
                    bugline['heat']         = html.fromstring(str(item['bug_heat_html'])).cssselect("span.sprite.flame")[0].text
                    bugline['link']         = str(item['bug_url'])

                    # 1st row has the keys
                    if not first_row:
                        writer.writerow(bugline.keys())
                        first_row = True
                    writer.writerow(bugline.values())

                except:
                    print("launchpad-scraper.py::main() : [ERROR] unknown error parsing JSON")

if __name__ == "__main__":
    sys.exit(main())
