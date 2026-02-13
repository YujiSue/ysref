import subprocess
import re
import requests
import time
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


# Base API URLs
base_urls = {
  'pubmed_search': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
  'pubmed_summary': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
  'pubmed_abstract': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
  'pmc_id': 'https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/',
  'pmc_ftp': 'https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi',
  'elsevier_doi': 'https://api.elsevier.com/content/article/doi/',
  'springer_oa': 'https://api.springernature.com/openaccess/jats',
  'wiley_doi': 'https://api.wiley.com/onlinelibrary/tdm/v1/articles/',
  'plos_doi': 'http://journals.plos.org/plosone/article/file',
  'biorxiv': 'https://api.biorxiv.org/details/biorxiv/<DOI>/na/json'
}

#
def execCmd(cmd):
  proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
  ret = proc.communicate()
  return [proc.returncode==0, ret[0].strip() if ret[0] else None, ret[1].strip() if ret[1] else None]

# 
def formDOI(doi):
  if not doi.startswith('doi: '):
    if 'doi: ' in doi:
      doi = doi[doi.find('doi: '):]
    else:
      doi = 'doi: ' + doi
  return doi

# Identify MIME type
def getExtFromMIME(mime):
  if re.match('image/[a-z]+', mime) or re.match('img/[a-z]+', mime):
    if 'tif' in mime:
      return 'tif'
    elif 'jp' in mime:
      return 'jpeg'
    elif 'png' in mime:
      return 'png'
    elif 'webp' in mime:
      return 'webp'
  elif re.match('application/[a-z.]+', mime):
    if 'pdf' in mime:
      return 'pdf'
    elif 'zip' in mime:
      return 'zip'
    elif 'word' in mime:
      return 'docx'
    elif ('openxml' in mime and 'sheet' in mime) or 'excel' in mime:
      return 'xlsx'
  return 'txt'

# Check redirect
def checkRedirect(url):
  response = requests.get(url)
  if (response.headers.get('Link') != None):
    beg = response.headers['Link'].find('http')
    end = response.headers['Link'].find('>', beg+1)
    if (end != -1):
      return response.headers['Link'][beg:end]
    else:
      return response.headers['Link']
  else:
    return url

# Save HTML body
def savePage(url, path, wdargs=[]):
  options = webdriver.ChromeOptions()
  for a in wdargs:
    options.add_argument(a)
  driver = webdriver.Chrome(options=options)
  ##
  driver.get(url)
  time.sleep(10) # Wait loading
  with open(path, 'w') as f:
    f.write(driver.page_source)
  return driver.page_source

# Get api key
def getAPIKey(key, tag):
  if key == 'env':
    import os
    return os.environ[tag]
  elif key == 'keyring':
    import keyring
    return keyring.get_password('system', tag)
  elif key == 'colab':
    from google.colab import userdata
    return userdata.get(tag)


