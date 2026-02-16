# Overview
This module provides functions to construct a workflow for literature search, full-text acquisition, and keyword mining.  

It enables programmatic PubMed searches via the NCBI API and stores retrieved data in a local SQLite3 database for structured and reproducible literature management. Search results can be exported in BibTeX format for direct use with reference managers and manuscript preparation.  

When appropriate API keys or tokens are configured (e.g., Elsevier API, Springer API, Wiley TDM token), the module can automatically download available full texts from PMC and other open-access sources. Supported file formats include PDF, DOCX, XLSX, HTML and (N)XML.  

Downloaded documents can be scanned using customizable regular-expression queries to extract keywords, phrases, or structured information. Extracted results can then be appended or merged into the SQLite3 database, allowing iterative enrichment and continuous updating of the literature dataset.  

# Installation
Install via pip command.

```py
pip install git+https://github.com/YujiSue/ysref.git
```

# API keys
This module requires at least an NCBI API key. If you do not already have one, please follow the instructions below to obtain the API key and configure it so that it is accessible.  
  
In addition, API keys or tokens from Elsevier, Springer, and Wiley can be used to enable full-text download.  
Please check your institution’s subscription agreements and, if necessary, obtain these keys/tokens and configure them in the same way as the NCBI API key.  

## How to obtain API keys/tokens 
### NCBI
1. Create an NCBI account
First, you need an account with NCBI.  
Go to the [NCBI homepage](https://www.ncbi.nlm.nih.gov/) and click "Log in" at the top right.  
Registration is free.  

2. Create an API key
After logging in, open your  [account settings](https://account.ncbi.nlm.nih.gov/settings/).  
Scroll down to API Key Management and click "Create an API key".  

### Elsevier
Obtain an API key by following the instructions in the [official document](https://dev.elsevier.com/).

### Springer
Obtain an API key by following the instructions in the [official document](https://dev.springernature.com/docs/quick-start/api-access/).  
  
### Wiley
Obtain a text and data mining token by following the [official document](https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining).

## How to use API keys/tokens
There are three ways to use the API. Please configure your platform by either of these methods so that the required keys can be used.  

### Environmental variables (env)
Please set the obtained key/token as environmental variables before running your program as shown in the examples below.  

* Linux/Unix/Mac
  ```sh
  export NCBI_API=xxxxxxx
  --- Option ---
  export ELSEVIER_API=xxxxxx
  export SPRINGER_API=xxxxxx
  export WILEY_API=xxxxxx
  ```

* Windows
  ```powershell
  $env:NCBI_API="xxxxxxx"
  --- Option ---
  $env:ELSEVIER_API="xxxxxx"
  $env:SPRINGER_API="xxxxxx"
  $env:WILEY_API="xxxxxx"
  ```

### keyring
Please set the obtained keys/tokens using [keyring](https://pypi.org/project/keyring/).  
If you run the following code once as a standalone Python script, you will not need to include keys or saving process in each individual program thereafter.  

  ```py
  import keyring

  keyring.set_password("NCBI_API", "default", "xxxxxx")
  ### Option ###
  keyring.set_password("ELSEVIER_API", "default", "xxxxxx")
  keyring.set_password("SPRINGER_API", "default", "xxxxxx")
  keyring.set_password("WILEY_API", "default", "xxxxxx")
  ```

### GoogleColab Secrets
  Google Colab Secrets are briefly introduced on the [official X account](https://x.com/GoogleColab/status/1719798406195867814/photo/1).  
<div><img src="https://pbs.twimg.com/media/F93zfjHWQAA1DB1?format=jpg&name=medium" width="480"/></div>
  

1. Open the left navigation panel in GoogleColab and select the key icon.
  
2. Add the Name and Value as below, and switch Access to ON.

  |Name|Value|
  |--|--|
  |NCBI_API|xxxxxx|
  |ELSEVIER_API|xxxxxx|
  |SPRINGER_API|xxxxxx|
  |WILEY_API|xxxxxx|

# Sample
## Search for PubMed and get metadata
```py
# Set query key word for PubMed search
query = 'xxxxx'
# Set period to search
start_date = '2000/01/01'
end_date = '2000/01/31'
# Get result of PubMed search
references = getPMList(query, key='env', # Use environmental varialbles to load API keys 
                        condition={'period': [start_date, end_date]})
```

## Save the records to SQlite3 database
```py
# Connect DB
dbpath = 'path-to-database'
db = RefDB(dbpath)

# Save the records with some label
label = '2000_Jan'
db.registerRefDB(references, label)

```

## Try to donwload the full-text of recorded articles 
```py

# Get reference IDs to full-text downlaod. If 'file' is already registered, ignore the record. 
refids = db.getRefIDs(conditions=f"file=''")

# Try downloading for each article
for refid in refids:
  ## Get DOI 
  refinfo = db.getRefSummary(refid)
  ## Try to download full-text
  outdir = 'path-to-save-files'
  result = getFullText(refid, refinfo['doi'], outdir)
  ## IF successed
  if result['status']:
    ### Update URL, file and logs
    db.updateRecord(refid, ['link','file','attribute'], [
        result['fulltexts'],
        os.path.split(result['path'])[1],
        {k:v for k,v in result.items() if k not in ['status', 'msg', 'path', 'fulltexts']}
    ])
  ## IF failed
  else:
    ### Save the error log
    db.updateRecord(refid, ['link','attribute'], [
        result['fulltexts'],
        {'error':result['msg']}
    ])

```

## Text-mining
```py
# Set keyword(s) in regex format
keywords = '[a-zA-Z0-9]+'

# Get reference IDs to analyze. If 'file' is NOT registered, ignore the record. 
refids = db.getRefIDs(conditions=f"file!=''")

# Try mining for each article
for refid in refids:
  ## Init. container
  result = {}
  ## Call recursive function
  outdir = 'path-to-output'
  mineWordFrom(result, keywords, outdir)
  ## If keywords are found
  if 0 < len(result):
    note = f"Text mining: {','.join(result.keys())}"
    db.updateRecord(refid, ['note'], [note])

```

## Export as bibtex
```py
# Set path to save
bibpath = 'path-to-save'
# Export as a bibtex (.bib) file.
db.export(bibpath)

```

