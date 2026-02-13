from bs4 import BeautifulSoup
import os
from pprint import pprint
import requests
import time
import traceback
#import chromedriver_binary
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import ysref.util

# Direct download using Selenium+Chromedriver
def seleniumDL(url, dir):
  options = webdriver.ChromeOptions()
  options.add_experimental_option('prefs', {
    "download.default_directory": dir,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    "plugins.always_open_pdf_externally": True,
  })
  driver = webdriver.Chrome(options=options)
  driver.get(url)
  time.sleep(10) # Loading

# PubMed => PMC ID
def getPMCID(refid):
  res = requests.get(ysref.util.base_urls['pmc_id'], {
    'tool': 'my_tool',
    'email': 'my_email@example.com',
    'ids': refid,
    'format': 'json'
    })
  ##
  if res.status_code == requests.codes.ok:
    info = res.json()
    if 'records' in info and 0 < len(info['records']) and 'pmcid' in info['records'][0]:
      return info['records'][0]['pmcid'].replace('PMC', '')
  return None

# Get PMC FTP URL
def getPMCLink(pmcid):
  res = requests.get(ysref.util.base_urls['pmc_ftp'], { 'id': pmcid })
  if res.status_code == requests.codes.ok:
    soup = BeautifulSoup(res.content, "xml")
    link = soup.find('link', {'format':'tgz'})
    if link and link.get('href'):
      return link.get('href')
  return None

# Download full-text article in PMC
def dlFromPMC(refid, outdir):
  ## Container
  result = {
    'status': None,
    'source': 'PMC',
    'url': None,
    'path': None
  }
  try:
    ## Get PMC ID
    pmcid = getPMCID(refid)
    if not pmcid:
      result['status'] = False
      return result
    result['pmcid'] = pmcid
    ## Get PMC link
    result['url'] = getPMCLink(pmcid)
    if result['url'] :
      result['path'] = os.path.join(outdir, os.path.split(result['url'])[1])
      # DL
      res = ysref.util.execCmd(f"curl -L -o '{result['path']}' '{result['url']}'")
      if res[0]:
        result['status'] = True
      else:
        result['status'] = False
        result['msg'] = f'{res[1]} {res[2]}'
    else:
      result['status'] = False
  except Exception as e:
    result['status'] = False
    result['msg'] = traceback.format_exception_only(type(e), e) 
  return result

# Download from Elsevier
def dlFromElsevier(url, doi, outdir, allow_direct=False):
  ## Container
  result = {
    'status': None,
    'source': 'Elsevier',
    'url': f"{ysref.util.base_urls['elsevier_doi']}{doi.replace('doi: ', '')}",
    'path': None,
    'log': []
  }
  ##
  try:
    res = requests.get(result['url'], { 'apiKey': {ysref.util.getAPIKey('ELSEVIER_KEY')}, 'view': 'FULL' })
    if res.status_code == requests.codes.ok and 'service-error' not in res.text:
      result['path'] = os.path.join(outdir, 'document.xml')
      with open(result['path'], 'w') as f:
        f.write(res.text)
      # Get suppl. materials
      soup = BeautifulSoup(res.text, 'xml')
      objs = soup.find("objects")
      if objs and objs.find("object", {"category" : "standard"}):
        nodes = objs.find_all("object", {"category" : "standard"})
        for node in nodes:
          ext = ysref.util.getExtFromMIME(node['mimetype'])
          supout = os.path.join(outdir, os.path.split(node['ref'])[-1])
          res2 = ysref.util.execCmd(f"curl -L -o {supout}.{ext} '{node.text}&apikey={ysref.util.getAPIKey('ELSEVIER_KEY')}'")
          if not res2[0]:
            result['log'].append(f"{res2[1]} {res2[2]}")
      result['status'] = True
      if 0 < len(result['log']):
        result['msg'] = '\n'.join(result['log'])
    else:
      result['status'] = False
      result['msg'] = res.reason
  except Exception as e:
    result['status'] = False
    result['msg'] = traceback.format_exception_only(type(e), e) 
  return result

# Download from Springer
def dlFromSpringer(url, doi, outdir, allow_direct=False):
  ## Container
  result = {
    'status': None,
    'source': 'Springer',
    'url': ysref.util.base_urls['springer_oa'],
    'path': None,
    'log': []
  }
  ## Call API
  try:
    res = requests.get(ysref.util.base_urls['springer_oa'], {
      'q': doi.replace(':', '%3A').replace(' ', '20'), 
      'api_key': ysref.util.getAPIKey('SPRINGER_KEY')
    })
    ###
    if res.status_code == requests.codes.ok:
      soup = BeautifulSoup(res.text, 'xml')
      count = int(soup.find('total').text)
      if 0 < count:
        result['path'] = os.path.join(outdir, 'document.xml')
        with open(result['path'], 'w') as f:
          f.write(res.text)
          # Get suppl. materials
          supps = soup.find_all('supplementary-material')
          for supp in supps:
            media = supp.find('media')
            if media:
              res2 = ysref.util.execCmd(f"curl -L -o '{os.path.join(outdir, os.path.split(media['xlink:href'])[-1])}' 'https://static-content.springer.com/esm/art%3A{doi.replace('doi: ', '').replace('/', '%2F')}/{media['xlink:href']}'")
              if not res2[0]:
                result['log'].append(f"{res2[1]} {res2[2]}")
        result['status'] = True
      elif allow_direct:
        result['url'] = url
        # Direct DL
        result['path'] = os.path.join(outdir, 'document.html')
        res2 = requests.get(url)
        with open(result['path'], 'w') as f:
          f.write(res2.text)
        # Get suppl. materials
        soup = BeautifulSoup(res2.text, 'html.parser')      
        links = soup.find_all('a', {'data-test': 'supp-info-link'})
        for link in links:
          if link.get('href').startswith('https://'):
            supout = os.path.join(outdir, os.path.split(link.get('href'))[-1])
            res3 = ysref.util.execCmd(f"curl -L -o '{supout}' '{link.get('href')}'")
            if not res3[0]:
              result['log'].append(f"{res3[1]} {res3[2]}")
    else:
      result['status'] = False
      result['msg'] = res.reason
        
  except Exception as e:
    result['status'] = False
    result['msg'] = traceback.format_exception_only(type(e), e) 
  return result

# Download from Atypon
def dlFromAtypon(url, doi, outdir, wdargs=[]):
  ## Container
  result = {
    'status': None,
    'source': 'Atypon',
    'url': url.replace(' ', '%20').replace('///', '//'),
    'path': os.path.join(outdir, 'document.html'),
    'log': []
  }
  ## 
  try:
    content = ysref.util.savePage(result['url'], result['path'], wdargs=wdargs)
    # PNAS
    if 'pnas.org' in url:
      result['source'] = 'PNAS' 
      soup = BeautifulSoup(content, 'html.parser')
      fl = soup.find('a', {'aria-label':"View PDF"})
      if fl:
        result['url'] = f"{fl.get('href').replace('/epdf/','/pdf/')}?download=true"
        result['path'] = os.path.join(outdir, 'document.pdf')
        ysref.util.savePage(result['url'], result['path'], wdargs=wdargs)
      result['return'] = True
    # Science
    elif 'www.science.org' in url:
      result['source'] = 'science'
      soup = BeautifulSoup(content, 'html.parser')
      sups = soup.find(id="supplementary-materials")
      if sups:
        all_links = sups.find_all('a')
        for li in all_links:
          if li.text == "Download":
            ysref.util.savePage(f"https://www.science.org{li['href']}", os.path.join(outdir, os.path.split(li['href'])[-1]), wdargs=wdargs)
      result['return'] = True
    else:
      result['return'] = True
  except Exception as e:
    result['status'] = False
    result['msg'] = traceback.format_exception_only(type(e), e)
  return result

# Download from Wiley
def dlFromWiley(url, doi, outdir, allow_direct=False, wdargs=[]):
  ## Container
  result = {
    'status': None,
    'source': 'Wiley',
    'url': None,
    'path': None,
    'log': []
  }
  ##
  try:
    result['url'] = f"{ysref.util.base_urls['wiley_doi']}{doi.replace('doi: ','').replace('/', '%2F')}"
    result['path'] = os.path.join(outdir, 'document.pdf')
    cmd = f"curl -L -H \"Wiley-TDM-Client-Token: {ysref.util.getAPIKey('WILEY_KEY')}\" -D 'header.txt' -o '{result['path']}' '{result['url']}'"
    ysref.util.execCmd(cmd)
    ###
    fsz = os.path.getsize(result['path'])
    if fsz == 0:
      if allow_direct:
        result['url'] = ysref.util.checkRedirect(url)
        result['path'] = os.path.join(outdir, 'document.html')
        ysref.util.savePage(result['url'], result['path'], wdargs=wdargs)
        result['status'] = True
      else:
        result['status'] = False
        result['msg'] = 'Not available API.'
  except Exception as e:
    result['status'] = False
    result['msg'] = traceback.format_exception_only(type(e), e)
  return result

# Download from PLOS
def dlFromPLOS(url, doi, outdir, wdargs=[]):
  ## Container
  result = {
    'status': None,
    'source': 'PLOS',
    'url': None,
    'path': None,
    'log': []
  }
  ##
  try:
    result['url'] = ysref.util.base_urls['plos_doi']
    result['path'] = os.path.join(outdir, 'jats.xml')
    # Call API
    content = requests.get(result['url'], {
       'id': doi.replace('doi: ', ''),
       'type': 'manuscript'
    })
    with open(result['path'] ,'w') as f:
      f.write(content.text)
    # Get suppl. materials
    soup = BeautifulSoup(content.text, 'xml')
    body = soup.find("body")
    if not body:
      result['status'] = False
      result['msg'] = 'Not available.'
    else:
      sups = body.find("sec", {"sec-type" : "supplementary-material"})
      if sups:
        nodes = sups.find_all("supplementary-material")
        if nodes:
          for node in nodes:
            ext = ysref.util.getExtFromMIME(node['mimetype'])
            cmd = f"curl -L -o '{os.path.join(outdir, node.get('id'))}.{ext}' 'https://www.doi.org/{node['xlink:href'].replace('info:doi','')}'"
            ysref.util.execCmd(cmd)
    result['return'] = True
  except Exception as e:
    result['status'] = False
    result['msg'] = traceback.format_exception_only(type(e), e)
  return result

# Download from CSH
def dlFromCSH(url, doi, outdir, wdargs=[]):
  ## Container
  result = {
    'status': None,
    'source': '',
    'url': url,
    'path': None,
    'log': []
  }
  ##
  try:
    res = requests.get(url)
    if 'biorxiv' in str(res.headers):
      ### biorxiv
      result['source'] = 'biorxiv'
      # biorxiv api
      res = requests.get(ysref.util.base_urls['biorxiv'].replace('<DOI>', doi.replace('doi: ', '')))
      if res.status_code == requests.codes.ok:
        content = res.json()
        if 'collection' in content and 0 < len(content['collection']) and 'jatsxml' in content['collection'][0]:
          result['url'] = content['collection'][0]['jatsxml'].replace('\\/', '/')
          result['path'] = os.path.jin(outdir, 'jats.xml')
          ysref.util.savePage(result['url'], result['path'], wdargs=wdargs)
        else:
          result['status'] = False
          result['msg'] = "Collection was not found."
      else:
        result['status'] = False
        result['msg'] = res.reason
    else:
      result['source'] = 'Cold Spring Harbor'
      result['url'] = ysref.util.checkRedirect(result['url'])
      result['path'] = os.path.join(outdir, "document.html")
      ysref.util.savePage(result['url'], result['path'], wdargs=wdargs)
    result['status'] = True
  except Exception as e:
    result['status'] = False
    result['msg'] = traceback.format_exception_only(type(e), e)
  return result

# Download from HTML body
def simpleDL(publisher, url, outdir, wdargs=[]):
  ## Container
  result = {
    'status': None,
    'source': publisher,
    'url': url,
    'path': os.path.join(outdir, "document.html"),
    'log': []
  }
  ##
  try:
    ysref.util.savePage(url, result['path'], wdargs)
    result['status'] = True
  except Exception as e:
    result['status'] = False
    result['msg'] = traceback.format_exception_only(type(e), e)
  ##
  return result

# Get full-text links
def getDLLinks(source):
  links = {}
  # full-text-links-listの<a>タグを全取得
  soup = BeautifulSoup(source, 'html.parser')
  node = soup.find('div', attrs={ 'class': 'full-text-links-list' })
  if node:
    hrefs = node.find_all('a')
    for href in hrefs:
      if 'at ' in href['title']:
        tag = href['title'][href['title'].find('at ')+3:]
        links[tag] = href['href']
      else:
        links[href['title']] = href['href']
  return links

# Download Full Text
def getFullText(refid, doi, dest, allow_direct=False, max_trial=3, wdargs=['--no-sandbox', '--headless'], verbose=False):
  ## Container
  result = { 
    'status': None,
    'msg': None,
    'fulltexts': None
    }

  ## Set output directory
  outdir = os.path.join(dest, str(refid))
  os.makedirs(outdir, exist_ok=True)
  
  ## Get full-text link(s)
  trial = 1
  while (True):
    try:
      ### Open PubMed website
      res = requests.get(f'https://pubmed.ncbi.nlm.nih.gov/{refid}/', 
                         headers=requests.utils.default_headers())
      if res.status_code == requests.codes.ok:
        result['fulltexts'] = getDLLinks(res.content)
        break
    except Exception as e:
      trial += 1
      if (trial == max_trial):
        result['status'] = False
        result['msg'] = traceback.format_exception_only(type(e), e)
        break
  ## 
  if result['fulltexts']:
    if verbose:
      print('Full-text links:')
      for pub in result['fulltexts']:
        print(' >', pub, ':', result['fulltexts'][pub])
    try:
      # PMC
      if 'PubMed Central' in result['fulltexts']:
        res = dlFromPMC(refid, outdir)
        if verbose and not res['status']:
          print('PMC downlaod failed.')
          pprint(res)
        result.update(res)
      # Other
      if not result['status']:                
        for publisher in result['fulltexts']:
          if 'PubMed Central' in publisher:
            continue
          # Elsevier group
          if 'Elsevier' in publisher:
            result.update(dlFromElsevier(result['fulltexts'][publisher], doi, outdir))
          # Springer group 
          elif 'Springer' in publisher or 'Nature Publishing Group' in publisher:
            result.update(dlFromSpringer(result['fulltexts'][publisher], doi, outdir, allow_direct=allow_direct))
          # Atypon group
          elif 'Atypon' in publisher:
            result.update(dlFromAtypon(result['fulltexts'][publisher], doi, outdir))
          # Wiley group
          elif 'Wiley' in publisher:
            result.update(dlFromWiley(result['fulltexts'][publisher], doi, outdir))
          # PLOS group
          elif 'Public Library of Science' in publisher:
            result.update(dlFromPLOS(result['fulltexts'][publisher], doi, outdir))
          # CSH
          elif 'Cold Spring Harbor' in publisher:
            result.update(dlFromCSH(result['fulltexts'][publisher], doi, outdir))
          else:
            result.update(simpleDL(publisher, result['fulltexts'][publisher], outdir, wdargs=wdargs))
          if result['status']:
            break
    except Exception as e:
      result['status'] = False
      result['msg'] = traceback.format_exception_only(type(e), e)
  else:
    result['status'] = False
    result['msg'] = 'Full text is not available in this institution.'  
  return result
