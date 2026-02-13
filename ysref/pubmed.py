from bs4 import BeautifulSoup
import requests
import time
import ysref.util

# Get deteailed information for a specific PubMed ID
def getPMSummary(refid, key='env'):
  """
    Get summary information from PubMed database via Entrez API.
    NCBI API key should be provided by either env variable, keyring, or google.colab.userdata (For GoogleColab only).
    Please register your key with name 'NCBI_API' before use this script.
    ```shell
    # For env user
    $ export NCBI_API=xxxxxx 
    ```
    ```py
    # For keyring user
    import keyring
    keyring.set_password("system", "NCBI_API", "xxxxxx")
    ```
    ```
    # For Google Colab user
    # Set your key using webbrowser
    ```
    
    Args:
        refid (str): The PubMed ID.
        key (str): Either 'env', 'keyring', or 'colab'

    Returns:
        dict: Article information.
  """
  ## Container 
  ref = {
    'id' : refid,     ## PubMed ID
    'title': '',      ## Article title
    'author': [],     ## Author list
    'journal': '',    ## Journal name
    'type' : '',      ##  
    'volume' : '',    ## Volume
    'issue' : '',     ## issue
    'page' : '',      ## Page
    'date' : '',      ## Date
    'doi': '',        ## DOI
    'link': [],       ## Link to fulltext
    'file': '',       ## Path to downloaded file
    'attribute' : {}, ## Attribute
    'note': ''        ## Note
  }
  ## Call API
  response = requests.get(ysref.util.base_urls['pubmed_summary'], {
    "db":"pubmed",
    "id":refid,
    "retmode":"json",
    "api_key": ysref.util.getAPIKey(key, 'NCBI_API')
  })
  res = response.json()
  ## IF successed
  if 'result' in res:
    sum = res['result'][str(refid)]
    ref['title'] = sum['title']
    ref['title'] = ref['title'].replace('&lt;i&gt;', '')
    ref['title'] = ref['title'].replace('&lt;/i&gt;', '')
    ref['title'] = ref['title'].replace('&lt;sub&gt;', '')
    ref['title'] = ref['title'].replace('&lt;/sub&gt;', '')
    ref['title'] = ref['title'].replace('&lt;sup&gt;', '')
    ref['title'] = ref['title'].replace('&lt;/sup&gt;', '')
    for author in sum['authors']:
      ref['author'].append(author['name'])
    ref['journal'] = sum['fulljournalname']
    ref['type'] = ' '.join(sum['pubtype'])
    ref['volume'] = sum['volume']
    ref['issue'] = sum['issue']
    ref['page'] = sum['pages']
    ref['date'] = sum['pubdate']
    ref['doi'] = sum['elocationid']
  return ref

# Get PubMed ID list 
def getPMList(query, key='env', condition={},verbose=False):
  ## Container to store results
  reflist = {}
  ## Parameter
  params = {
    "term": query,
    "mindate": condition['period'][0],
    "maxdate": condition['period'][1],
    "retmode": "json",
    "api_key": ysref.util.getAPIKey(key, 'NCBI_API')
  }
  ## Total count of search results
  response = requests.get(ysref.util.base_urls['pubmed_search'], params={**params, **{"rettype":"count"}})
  total = response.json()['esearchresult']['count']
  ##
  if verbose:
    print(total, 'articles were found.')
  ##
  if (0 < int(total)):
    ### Request PubMed IDs
    response = requests.get(ysref.util.base_urls['pubmed_search'], params={**params, **{"retmax":str(total)}})
    refids = response.json()['esearchresult']['idlist']
    for refid in refids:
      #### Get information of each ID
      reflist[str(refid)] = getPMSummary(refid, key)
      time.sleep(0.25)
  return reflist

# Get abstract text from PubMed
def getPMAbstract(refid):
  ## Parameter
  params = {
    "db": "pubmed",
    "id": refid,
    "retmode": "xml",
    "rettype": "abstract"
  }
  ##
  response = requests.get(ysref.util.base_urls['pubmed_abstract'], params=params)
  xml_data = response.text
  ## Parse the XML response to extract the abstract
  soup = BeautifulSoup(xml_data, "xml")
  abstract_element = soup.find("AbstractText")
  if abstract_element is not None:
    return abstract_element.text.strip()
  else:
    return None
