import re
import time
import brotli
import random
import requests
import itertools
from bs4 import BeautifulSoup
from tqdm import tqdm_notebook as tqdm

#Requests settings
BASE_HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;' + \
               'q=0.9,image/webp,image/apng,*/*;' + \
               'q=0.8,application/signed-exchange;v=b3',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'en-US,en;q=0.9',
    'cookie': '',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' + \
                  'AppleWebKit/537.36 (KHTML, like Gecko) ' + \
                  'Chrome/76.0.3809.100 Safari/537.36'
}
BASE_URL = 'https://www.pathofexile.com/forum/'
THREAD_URL = 'view-thread/'
FORUM_URL = 'view-forum/'
PAGE_URL = '/page/'

#Class settings
CLASS_URL_TAGS = {
    'Marauder': ('23', ['Juggernaut', 'Chieftan', 'Berserker']),
    'Duelist': ('40', ['Slayer', 'Gladiator', 'Champion']),
    'Ranger': ('24', ['Deadeye', 'Raider', 'Pathfinder']),
    'Scion': ('436', ['Ascendant']),
    'Shadow': ('303', ['Assassin', 'Saboteur', 'Trickster']),
    'Templar': ('41', ['Inquisitor', 'Hierophant', 'Guardian']),
    'Witch': ('22', ['Necromancer', 'Occultist', 'Elementalist'])
}

class BuildSearcher():
    '''Build a dataset of forum ID keys of build guides'''
    
    def __init__(self, filename, num_pages_per_class, delay_mean_sec=1):
        self.num_pages_per_class = num_pages_per_class
        self.delay_mean_sec = delay_mean_sec
        self.filename = filename
        
    def crawl_forum(self, classes=CLASS_URL_TAGS.keys()):
        #Create randomly sorted list of all forum thread lists we must crawl
        pool = list(itertools.product(classes, 
                                 range(1, self.num_pages_per_class + 1)))
        random.shuffle(pool)
        #Pool now looks like: [('Marauder', 400), ('Scion', 29), ('Shadow', 999)...]
        
        for page in tqdm(pool):
            self.write_page(*page)
            delay = self.delay_mean_sec
            delay = delay + (random.random() * self.delay_mean_sec)
            delay = delay - (random.random() * self.delay_mean_sec)
            time.sleep(delay)
        
    def write_page(self, base_class, page_number):
        with open(self.filename, 'a', encoding='utf-8') as f:
            results = self.get_page(base_class, page_number)
            for page in results:
                f.write('{} - {}\n'.format(page[1], page[0]))
    
    def get_page(self, base_class, page_number):
        forum = CLASS_URL_TAGS[base_class][0]
        #If page_number is 1, filter the class's build list ("Duelist Build List")
        start = 1 if page_number == 1 else 0
        return self._parse_page(self._request_page(forum, page_number), start=start)
    
    def _request_page(self, forum, page_number):
        url = BASE_URL + FORUM_URL + str(forum) + PAGE_URL + str(page_number)
        return requests.get(url, headers=BASE_HEADERS).content.decode('utf-8')
    
    def _parse_page(self, response, start=0):
        soup = BeautifulSoup(response, 'html.parser')
        thread_links = soup.find_all('div', class_='thread_title')
        thread_links = [div.find('div', class_='title').find('a') for div in thread_links]
        encode_str = lambda x: x.encode('utf-8') if type(x) == bytes or x.startswith("b'") else x
        thread_links = [(encode_str(a.get_text().strip()), 
                         encode_str(self._parse_href(a.get('href')))) for a in thread_links]
        return thread_links[start:]
    
    def _parse_href(self, href):
        return href.split('/')[-1]

class Build():
    
    def __init__(self, thread_number):
        self.thread_number = thread_number
        
    def get(self):
        return self._parse(self._request())
    
    def write(self, filename):
        self._write_page(filename, '\n'.join(list(self.get())))
        
    def _request(self):
        url = BASE_URL + THREAD_URL + str(self.thread_number)
        return BrotliPage(url).request()
    
    def _parse(self, response):
        soup = BeautifulSoup(response, 'html.parser')
        title = soup.find('h1', class_='layoutBoxTitle').get_text()
        body = soup.find('table', class_='forumTable').find('tr').find('div', class_='content')
        body = self._filter_content(body.get_text())
        return title, body
    
    def _write_page(self, filename, text):
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)
    
    def _filter_content(self, content):
        '''Replace text inputs which cannot be modeled (-------) or html tags (Spoiler)'''
        #Filter URLs
        content = re.sub(r'http\S+', '<link>', content)
        
        #Filter horizontal lines
        content = re.sub(r'[-=]+[-=]+[-=]+', '-----', content)
        
        #Filter Spoiler
        content = re.sub('Spoiler', '', content)
        
        return content

class BrotliPage():
    '''Pathofexile.com pages are encoded with the brotli algorithm'''
    def __init__(self, url):
        self.url = url
    
    def request(self):
        r = requests.get(self.url, headers=BASE_HEADERS)
        r.raise_for_status()
        assert r.ok
        content = r.content
        try:
            content = brotli.decompress(r.content)
        except Exception as e:
            print(e)
        return content.decode('utf-8')