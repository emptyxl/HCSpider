# -*- coding: UTF-8 -*-
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, Text, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from selenium.webdriver.chrome.options import Options
from seleniumrequests import Chrome as post_Chrome
from selenium import webdriver
from parse_sim_url import remove_sim_url
from urllib import parse
from lxml import etree
from concurrent.futures import ThreadPoolExecutor
import os
import re
import random
import time
import logging
import queue
import pybloomfilter
import threading
import json
import subprocess

MAX_RECURSION_DEPTH = 2
q = queue.Queue()

delay_time = [0, 2, 5, 10, 20, 60]
REG_DOMAIN = '^[]\s\S]*$'

# rm last BloomFilter
try:
    subprocess.check_output(['rm', 'url.bloom'])
except:
    pass

url_bloom = pybloomfilter.BloomFilter(100000, 0.01, 'url.bloom')

# set logger
logger = logging.getLogger('mylog')
handler = logging.FileHandler('spider.log')
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)-8s in %(module)s: %(message)s')
handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
handler.setLevel(logging.DEBUG)
console_handler.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

# set database
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

DB_CONNECT_STRING = 'mysql+mysqldb://root:@localhost/hcspider?charset=utf8'
db = create_engine(DB_CONNECT_STRING, max_overflow=50)
Base = declarative_base()
Session = sessionmaker(bind=db)
session = Session()


class SpiderItem(Base):

    __tablename__ = 'domain'

    id = Column(Integer, primary_key=True)
    method = Column(String(6), nullable=False)
    url = Column(Text, nullable=False)
    netloc = Column(String(255), nullable=False)
    data = Column(Text, nullable=True, default=None)
    deep = Column(Integer, nullable=False, default=0)
    has_params = Column(Boolean, nullable=False, default=False)
    def __str__(self):
        return 'Item [%s] %s' % (self.method, self.url)


def cookie2dict(cookie):
    cookies = dict([l.split("=", 1) for l in cookie.split("; ")])
    return cookies


def calc_url_uuid(method, url):
    u = parse.urlparse(url)
    parmas = parse.parse_qs(u.query)
    uuid = u.netloc + u.path
    sorted_parmas = sorted([x for x in parmas])
    uuid += '/' + '&'.join([x for x in sorted_parmas])
    return uuid


def rand_string(n):
    s = 'abcdefghijglmnopqrstuvwxyz1234567890._-()*@'
    res = random.sample(s[:26], 1)[0] + ''.join(random.sample(s, n))
    return res


def clean_up_path(url):
    q = parse.urlparse(url)
    if q.path == '':
        return parse.urlunparse((q.scheme, q.netloc, '/', q.params, q.query, ''))
    else:
        return parse.urlunparse(q)


def clean_up_url(orurl, current_url):
    if orurl is None:
        return None
    else:
        # https://a.b/c?d=e
        if re.match('^http[s]?://[\s\S]+\.[\s\S]+', orurl):
            return clean_up_path(orurl)
        # //a.b/c?d=e
        elif re.match('^//[^/][\s\S]*\.[\s\S]+', orurl):
            sch = parse.urlparse(current_url).scheme
            return clean_up_path(sch + ":" + orurl)
        # /a.b/c?d=e
        elif re.match('^/[^/][\s\S]*\.[\s\S]+', orurl):
            return clean_up_path(parse.urljoin(current_url, orurl[1:]))
        # javascript:;
        elif re.match('^javascript:[\s\S]+', orurl, re.IGNORECASE):
            return None
        # a.b/c?d=e
        elif re.match('^[^/]{2}[\s\S]+', orurl):
            return clean_up_path(parse.urljoin(current_url, orurl))
        else:
            return None


def parse_form_input(type, name, value):
    if name is None or name == '':
        return None
    if type == 'submit':
        return None
    if type == 'hidden':
        if value is None:
            return (name, rand_string(random.randint(10, 15)))
        else:
            return (name, value)

    if value is not None and value != '':
        return (name, value)
    else:
        # set different value
        if type == 'number':
            return (name, 7923476589)
        elif type == 'date':
            return (name, time.strftime("%Y-%m-%d"))
        elif type == 'datetime':
            return (name, time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            return (name, rand_string(random.randint(10, 15)))

    return None


def parse_page(tree, current_url, delay, deep, br, domain):
    tmp = []
    global q, url_bloom, session
    # get url in href
    for link in tree.xpath("//@href"):
        curl = clean_up_url(link, current_url)
        if (curl is not None) and not re.match(r'[\s\S]*(\.png|\.jpg|\.css|\.gif|\.js|\.ico|\.xml|\.svg|\.pdf)$', parse.urlparse(curl).path) and not re.match(r'[\s\S]*(\.png|\.jpg|\.css|\.gif|\.js|\.ico|\.xml|\.svg|\.pdf)$', curl):
            uuid = calc_url_uuid('get', curl)
            if uuid not in url_bloom:
                # each item in queue consists of (method, url, data, delay, deep)
                # store in tmp array to parse sim
                tmp.append(('get', curl, None, delay, deep + 1))
            url_bloom.add(uuid)

    # get url in form
    all_form = br.find_elements_by_xpath('//form')
    for form in all_form:
        form_url = clean_up_url(form.get_attribute('action'), br.current_url)
        if form_url is None:
            continue
        method = form.get_attribute('method')
        if method is None or method.lower() not in ['get', 'post']:
            continue
        else:
            method = method.lower()
        all_input = form.find_elements_by_xpath('.//input')
        post_data = {}
        for input_element in all_input:
            type = input_element.get_attribute('type')
            name = input_element.get_attribute('name')
            value = input_element.get_attribute('value')
            item_data = parse_form_input(type, name, value)
            if item_data is not None:
                post_data[item_data[0]] = item_data[1]

        # Add to corresponding list
        if method == 'get':
            gurl = parse.urlunparse((parse.urlparse(form_url).scheme, parse.urlparse(form_url).netloc,
                                     parse.urlparse(form_url).path, '', parse.urlencode(post_data), ''))
            uuid = calc_url_uuid('get', gurl)
            if uuid not in url_bloom:
                tmp.append(('get', gurl, None, delay, deep + 1))
            url_bloom.add(uuid)

        elif method == 'post':
            uuid = 'post/' + \
                parse.urlparse(form_url).netloc + \
                parse.urlparse(form_url).path
            uuid += '/' + '&'.join(sorted([_ for _ in post_data]))
            if uuid not in url_bloom and re.match(domain, form_url):
                q.put(('post', form_url, post_data, delay, deep + 1))
                session.add(SpiderItem(method=method, url=form_url, netloc=parse.urlparse(
                    form_url).netloc, data=json.dumps(post_data), deep=deep + 1,  has_params=True))
                session.commit()
                logger.info('add item: [%s] %s' % (method, form_url))
            url_bloom.add(uuid)

    url_list = [_[1] for _ in tmp]
    sim_list = remove_sim_url(url_list)
    for item in tmp:
        if item[1] in sim_list and re.match(domain, parse.urlparse(item[1]).netloc):
            q.put(item)
            h = (parse.urlparse(item[1]).query=='')
            session.add(SpiderItem(method=item[0], url=item[1], netloc=parse.urlparse(
                item[1]).netloc, data=item[2], deep=item[4], has_params=h))
            session.commit()
            logger.info('add item: [%s] %s' % (item[0], item[1]))


def get_url_hc(cookie, ThreadId, domain):
    logger.debug('start Thread [%s]' % ThreadId)
    global q, url_bloom
    try:
        RETRY = 0
        while RETRY < 5:
            if q.qsize() > 0:
                try:
                    item = q.get(timeout=3)
                except:
                    RETRY += 1
                    continue
            else:
                time.sleep(5)
                RETRY += 1
                continue
            # each item in queue consists of (method, url, data, delay, deep)
            method, url, data, delay, deep = item[0], item[1], item[2], item[3], item[4]
            if deep >= MAX_RECURSION_DEPTH:
                continue
            time.sleep(delay)
            logger.debug('[Thread %d] start to parse : %s' % (ThreadId, url))
            # set config
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument('window-size=1200x600')

            # get data
            if method == 'get':
                browser = webdriver.Chrome(
                    chrome_options=chrome_options, executable_path="./chromedriver")
                browser.set_page_load_timeout(15)
                browser.set_script_timeout(15)
                browser.implicitly_wait(10)
                RETRY = 0
                Flag = False
                while RETRY < 3 and not Flag:
                    try:
                        browser.get(url)
                        Flag = True
                    except:
                        logger.error('get %s timeout' % url)
                        RETRY += 1

                if not Flag:
                    continue

                if cookie is not None:
                    browser.delete_all_cookies()
                    Cookies = cookie2dict(cookie)
                    for key in Cookies:
                        browser.add_cookie(
                            {'name': key, 'value': Cookies[key]})
                        try:
                            browser.refresh()
                        except:
                            logger.error('get %s timeout' % url)
                            continue

                try:
                    html = browser.page_source
                    tree = etree.HTML(html)
                except:
                    continue

                parse_page(tree, url, delay, deep, browser, domain)

            elif method == 'post':
                browser = post_Chrome(
                    chrome_options=chrome_options, executable_path="./chromedriver")
                browser.set_page_load_timeout(15)
                browser.set_script_timeout(15)
                browser.implicitly_wait(10)

                if cookie is not None:
                    browser.delete_all_cookies()
                    Cookies = cookie2dict(cookie)
                    for key in Cookies:
                        browser.add_cookie(
                            {'name': key, 'value': Cookies[key]})

                while RETRY < 3 and not Flag:
                    try:
                        response = browser.request('POST', url, data=data)
                        tree = etree.HTML(response.text)
                        Flag = True
                    except:
                        logger.error('post %s timeout' % url)
                        RETRY += 1
                if not Flag:
                    continue

                parse_page(tree, url, delay, deep, browser, domain)
            # browser.save_screenshot('main.png')
            browser.quit()
    except Exception as e:
        print(e)


def start_spider(surl, domain=REG_DOMAIN, deep=0, delay_level=0, method='get', data=None, cookie=None):
    """
    surl        strat url: "https://www.baidu.com/?a=1&b=2" / scheme is required
    domain      domain scope      [default = *]
    deep        recursion depth   [default = 0]
    delay_level delay crawl level [default = 0] / scope:0-5
    method      support get/post in lowercase [default = get]
    data        post method parmas [default = None]
    cookie      you can copy the chrome cookies field directly, we will parse it [default = None]

    each item in queue consists of (method, url, data, delay, deep)
    """
    global q, url_bloom, session

    # create database
    Base.metadata.create_all(db)

    start_url = surl
    delay = delay_time[delay_level]
    # create start item
    q.put((method, start_url, data, delay, deep))
    url_bloom.add(calc_url_uuid('get', start_url))

    session.add(SpiderItem(method=method, url=start_url,
                           netloc=parse.urlparse(start_url).netloc, data=data, deep=deep))
    session.commit()
    logger.info('add item: [%s] %s' % (method, start_url))
    # get_url_hc(cookie)
    # DEFAULT_THREAD_NUMBER = (os.cpu_count() or 1) * 5
    DEFAULT_THREAD_NUMBER = os.cpu_count() or 1
    params = [cookie] * DEFAULT_THREAD_NUMBER
    ThreadId = [_ for _ in range(DEFAULT_THREAD_NUMBER)]
    DOMAIN_SCOPE = [domain] * DEFAULT_THREAD_NUMBER
    with ThreadPoolExecutor(max_workers=DEFAULT_THREAD_NUMBER) as executor:
        executor.map(get_url_hc, params, ThreadId, DOMAIN_SCOPE)

    print('crawl completed')


if __name__ == '__main__':
    start_spider('https://v.qq.com/', delay_level=2, domain='[\s\S]*qq.com/?$')
