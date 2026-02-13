import json
import sqlite3
import ysref.util

# Reference database
class RefDB():
  def __init__(self, path):
    self.dbpath = None
    self.connection = None
    self.cursor = None
    self.colnames = [
        'id', 
        'label', 
        'title', 
        'author', 
        'journal', 
        'type', 
        'volume', 
        'issue', 
        'page', 
        'date',
        'doi',
        'link',
        'file',
        'attribute',
        'note' 
    ]
    self.coltypes = {
      'id': 'numeric',
      'label': 'str', 
      'title': 'str', 
      'author': 'json', 
      'journal': 'str', 
      'type': 'str', 
      'volume': 'str', 
      'issue': 'str', 
      'page': 'str', 
      'date': 'str',
      'doi': 'str',
      'link': 'json',
      'file': 'str',
      'attribute': 'json',
      'note': 'str' 
    }
    self.open(path)

  # Connect DB
  def open(self, path):
    self.dbpath = path
    self.connection = sqlite3.connect(path)
    self.cursor = self.connection.cursor()
    self.cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' and name='reference'")
    res = self.cursor.fetchone()[0]
    if res == 0:
      self.cursor.execute("CREATE TABLE reference(id INTEGER PRIMARY KEY, label TEXT, title TEXT, author TEXT, journal TEXT, type TEXT, volume TEXT, issue TEXT, page TEXT, date TEXT, doi TEXT, link TEXT, file TEXT, attribute TEXT, note TEXT)")
      self.connection.commit()

  # Disconnect
  def close(self):
    self.connection.close()

  # Get reference IDs from DB
  def getRefIDs(self, conditions=None, orders=None, limit=None):
    ids = []
    sql = f"SELECT id FROM reference {f'WHERE {conditions}' if conditions else ''} {f'ORDER BY {orders}' if orders else ''} {f'LIMIT {str(limit)}' if limit else ''}"
    self.cursor.execute(sql.strip())
    res = self.cursor.fetchall()
    for row in res:
      ids.append(row[0])
    return ids

  # Get reference info.
  def getRefSummary(self, refid):
    info = {}
    sql = f"SELECT id,title,author,journal,volume,issue,page,date,doi,note FROM reference WHERE id={refid}"
    self.cursor.execute(sql)
    res = self.cursor.fetchone()
    info['id'] = res[0]
    info['title'] = res[1]
    info['author'] = json.loads(res[2])
    info['journal'] = res[3]
    info['volume'] = res[4]
    info['issue'] = res[5]
    info['page'] = res[6]
    info['date'] = res[7]
    info['doi'] = res[8]
    info['note'] = res[9]
    return info

  # Check if the reference is in the database
  def checkRefID(self, refid):
    sql = f'SELECT count(*) FROM reference WHERE id={refid}'
    self.cursor.execute(sql)
    ## True IF NOT registered, False IF registered
    return self.cursor.fetchone()[0] == 0
  
  # Insert record to DB
  def registerRefDB(self, refs, label, verbose=False):
    sql = f"INSERT INTO reference({','.join(self.colnames)}) VALUES ({'?,' * (len(self.colnames)-1) + '?'})"
    count = 0
    dataset = []
    for refid in refs:
      if self.checkRefID(refid):
        count += 1
        info = refs[refid]
        data = (refid, 
              label,
              info['title'],
              json.dumps(info['author']),
              info['journal'],
              info['type'],
              info['volume'],
              info['issue'],
              info['page'],
              info['date'],
              ysref.util.formDOI(info['doi']),
              json.dumps(info['link']),
              info['file'],
              json.dumps(info['attribute']),
              info['note'])
        dataset.append(data)
    self.cursor.executemany(sql, dataset)
    self.connection.commit()
    if verbose:
      print(f'{count}/{len(refs)} records are inserted. {len(refs)-count} records are already exist in the database.')

  # Select records
  def getRecord(self, refid, columns=['*']):
    sql = f"SELECT {','.join(columns)} FROM reference WHERE id={refid}"
    self.cursor.execute(sql)
    return self.cursor.fetchone()

  # Update record information
  def updateRecord(self, refid, columns, values, append=False):
    update = []
    if append:
      sql = f"SELECT {','.join(columns)} FROM reference WHERE id={refid}"
      self.cursor.execute(sql)
      record = self.cursor.fetchone()
      for idx,key,val in enumerate(zip(columns, values)):
        if self.coltypes[key] == 'numeric':
          update.append(f"{key}={val}")
        elif self.coltypes[key] == 'json':
          if isinstance(record[idx], list):
            if isinstance(val, list):
              record[idx].extend(val)
            else:
              record[idx].append(val)
          if isinstance(record[idx], dict):
            if isinstance(val, dict):
              record[idx].update(val)
          update.append(f"{key}='{json.dumps(record[idx]).replace("'", "''")}'")
        else:
          update.append(f"{key}='{record[idx]} {val.replace("'", "''")}'")
    else:
      for key,val in zip(columns, values):
        if self.coltypes[key] == 'numeric':
          update.append(f"{key}={val}")
        elif self.coltypes[key] == 'json':
          update.append(f"{key}='{json.dumps(val).replace("'", "''")}'")
        else:
          update.append(f"{key}='{val.replace("'", "''")}'")
    self.cursor.execute(f"UPDATE reference SET {','.join(update)} WHERE id={refid}")
    self.connection.commit()

  # Export records
  def export(self, output, style="bib", conditions=None, orders=None, limit=None):
    recordIds = self.getRefIDs(conditions, orders, limit)
    lines = []
    for pmid in recordIds:
      lines.append(f"@article{{pmid{pmid},")
      record = self.getRefSummary(pmid)
      lines.append(f"  title = {{{record['title']}}},")
      lines.append(f"  author = {{{','.join(record['author'])}}},")
      lines.append(f"  year = {{{record['date'][0:4]}}},")
      lines.append(f"  journal = {{{record['journal']}}},")
      lines.append(f"  volume = {{{record['volume']}}},")
      lines.append(f"  number = {{{record['issue']}}},")
      lines.append(f"  pages = {{{record['page']}}},")
      lines.append(f"  doi = {{{record['doi'].replace('doi: ', '').strip()}}},")
      lines.append(f"  pmid = {{{record['id']}}},")
      ## Finalize
      if 0 < len(lines) and lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
      lines.append("}")
    ## Export
    if style=='bib' and not output.endswith('.bib'):
      output += '.bib'
    with open(output, 'w') as f:
      f.write("\n".join(lines))
