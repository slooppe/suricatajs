import re
import os
import sqlite3
import hashlib
import requests
import datetime
import subprocess
import configparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from requests.auth import HTTPBasicAuth

# read config
config = configparser.ConfigParser()
config.read('./config/properties.ini')

http_proxy = ''

if config['CONFIG']['http_proxy']!='' and config['CONFIG']['port']!='':
    http_proxy = config['PROXY']['http_proxy']+config['PROXY']['port']

conn = sqlite3.connect('surikatajs.db')
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS jsmap (url text, javascript text)')
c.execute('CREATE TABLE IF NOT EXISTS jschecksum (javascript text, checksum text, date text)')
c.execute('CREATE TABLE IF NOT EXISTS alerts (javascript text, stored_checksum text, new_checksum, date text)')

javascript_set = set()

with open('targets.txt','r') as targets:
    for targeturl in targets:
        # Find all scripts in webpage
        html_resp = requests.get(targeturl).text
        soup2 = BeautifulSoup(html_resp,features='lxml')
        script_list = soup2.find_all('script')
        # Get src link for each javascript
        for script in script_list:
            try:
                if 'src' in str(script):
                    print(script)
                    script_url = urljoin(targeturl,script['src'])
                    # Add all scipts to set and map javascript to webpage
                    javascript_set.add(script_url)
                    c.execute('INSERT INTO jsmap SELECT ?,? WHERE NOT EXISTS (SELECT 1 FROM jsmap WHERE url=? AND javascript=?)', (targeturl, script_url, targeturl, script_url))
                    conn.commit()
            except KeyError:
                print("Error reading script source")

# For each of the detected scripts
for js in javascript_set:
    jssource = requests.get(js).text
    # Calculate the checksum
    new_checksum = hashlib.sha256(jssource.encode(encoding='utf-8')).hexdigest()

    # Check if checksum alrady exists in database
    stored_checksum_cur = c.execute('SELECT checksum FROM jschecksum WHERE javascript=?',(js,)).fetchone()

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    # If checksum already exists then compare with new checksum
    if stored_checksum_cur:
        print(stored_checksum_cur[0])
        stored_checksum=stored_checksum_cur[0]
        # If new and old checksum do not match then create alert
        if new_checksum != stored_checksum:
            print("creating alert for :"+js)
            c.execute('INSERT INTO alerts VALUES (?,?,?,?)', (js,stored_checksum,new_checksum,timestamp))
            conn.commit()
    # If checksum does not exist in database insert a new entry
    else:
        print("checksum insert for :"+js)
        c.execute('INSERT INTO jschecksum VALUES (?,?,?)',(str(js), new_checksum,timestamp))
        conn.commit()

conn.close()