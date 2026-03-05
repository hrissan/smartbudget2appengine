import webapp2
import base64
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.api import memcache
import json
from Crypto import Random
import logging
import hashlib
import datetime as module_datetime

cut_off_date = module_datetime.datetime(2022,01,01,01,01,01)

class Receipt(db.Model):
  data = db.BlobProperty(required=True)
  platform = db.StringProperty(required=True) # iOS, Mac, Android, etc
  check = db.IntegerProperty(required=True) # 0 - bad, 1 - good, 2 - pending
  decoded = db.TextProperty(required=True)
  documents = db.ListProperty(db.Key)

class Document(db.Model):
  #a_token = db.StringProperty(required=True) #we use key now
  removed = db.BooleanProperty(required=True)
  last_change = db.IntegerProperty(required=True)
  last_change_datetime = db.DateTimeProperty(required=False)

class Change(db.Model):
  num = db.IntegerProperty(required=True)
  body = db.BlobProperty(required=True)
  datetime = db.DateTimeProperty(required=True, auto_now_add=True, indexed=False)

def insert_change(doc, client_last_change, body_by, delta):
  if doc.last_change != client_last_change:
    return None
  now = module_datetime.datetime.now()
  doc.last_change += delta
  doc.last_change_datetime = now
  cha = Change(parent=doc, num=doc.last_change, body=body_by, datetime=now)
  doc.put()
  cha.put()
  return cha

def destroy_doc(doc):
  delBatch = 400
  changes = Change.all(keys_only=True).ancestor(doc.key()).order("num").fetch(limit=delBatch, batch_size=delBatch)
  if len(changes) == 0:
      doc.delete()
      return 0
  db.delete(changes)
  doc.removed = True # prevent adding changes
  doc.put()
  return len(changes)

def create_doc(a_token, body_by, delta):
  now = module_datetime.datetime.now()
  doc = Document(key_name=a_token, removed=False, last_change=delta, last_change_datetime=now)
  doc.put()
  cha = Change(parent=doc, num=delta, body=body_by, datetime=now)
  cha.put()
  return doc

def verify_apple_receipt(data_by):
  payload = json.dumps( {"receipt-data":base64.b64encode(data_by)} )
  logging.info( "verify_apple_receipt=" + payload )
  result = urlfetch.fetch("https://buy.itunes.apple.com/verifyReceipt", payload,
    method=urlfetch.POST,
    headers={'Content-Type': 'application/javascript; charset=utf-8'}, validate_certificate=False)
  #logging.info( "Apple production content=" + result.content )
  js = json.loads(result.content)
  if js["status"] == 21007: # Sandbox receipt sent to production server
    result = urlfetch.fetch("https://sandbox.itunes.apple.com/verifyReceipt", payload,
      method=urlfetch.POST,
      headers={'Content-Type': 'application/javascript; charset=utf-8'}, validate_certificate=False)
    #logging.info( "Apple sandbox content=" + result.content )
    js = json.loads(result.content)
  if js["status"] != 0:
    return 0, result.content
  pid = js["receipt"]["product_id"]
  #logging.info( "pid=" + pid )
  if pid == "com.smartbudgetapp.sb2.full_version":
    return 1, result.content
  if pid == "com.smartbudgetapp.sb2.full_version_sale":
    return 1, result.content
  if pid == "com.gamepizza.Money.FullVersion": # TODO - remove after testing
    return 1, result.content
  return 0, result.content

def verify_any_receipt(platform, data_by):
  #logging.info( "verify_any_receipt platform=" + unicode(platform) + " data_by=" + data_by )
  if data_by == "MagicReceipt": # optimization
    return 0, "just magic"
  if platform == "iOS":
    check, decoded = verify_apple_receipt(data_by)
    return check, decoded
  return 0, "platform unknown"
  
def get_good_receipt(doc, r_token, data_by, platform):
  if len(r_token) == 0:
    return None
  rec = Receipt.get_by_key_name(r_token)
  if rec is None:
    check, decoded = 2, "unknown"
    #logging.info( "check=" + unicode(check) + " decoded=" + decoded )
    try:
      check, decoded = verify_any_receipt(platform, data_by)
      #logging.info( "check=" + unicode(check) + " decoded=" + decoded )
    except:
      pass
    if check == 0:
      return None
    rec = Receipt(key_name=r_token, data=data_by, platform=platform, check = check, decoded = decoded)
    if not doc is None:
      rec.documents.append(doc.key())
    rec.put()
    return rec
  if rec.check == 2:
    try:
      check, decoded = verify_any_receipt(rec.platform, rec.data)
      rec.check = check
      rec.decoded = decoded
      rec.put()
    except:
      pass
  if rec.check == 0:
    return None
  max_documents = 10 # max documents synced with 1 receipt
  if doc is None:
    if len(rec.documents) >= max_documents:
      return None
    return rec
  if rec.documents.count(doc.key()) != 0:
    return rec
  if len(rec.documents) >= max_documents:
    return None
  rec.documents.append(doc.key())
  rec.put()
  return rec
  
magic_r_token = hashlib.sha1("MagicReceipt").hexdigest()

def is_good(rec, last_change, r_token):
  if not rec is None: # have receipt, good
    return True
  if r_token == magic_r_token: # magic receipt, good
    return True
  if len(r_token) != 0: # and rec is None obviously
    return False
  return last_change <= 200 #max_free_changes


def main(req):
  if req.path == "/sbs_upgrade.php":
    batch = int(req.get("batch", "4"))
    result = {}
    documents = Document.all()
    documents_cursor = memcache.get('sbs_upgrade_cursor')
    if documents_cursor:
      documents.with_cursor(start_cursor=documents_cursor)
    totalDocs = 0
    totalNotFound = 0
    lastKey = ""
    for doc in documents:
#       print(doc.key(), doc.last_change)
      found = False
      for change in Change.gql("WHERE ANCESTOR IS :1 AND num >= :2 ORDER BY num", doc.key(), doc.last_change).run(limit=1):
#         print(change.key(), change.datetime)
        doc.last_change_datetime = change.datetime
        found = True
      if not found:
#         doc.removed = True
        totalNotFound += 1
      doc.put()
      totalDocs += 1
      lastKey = doc.key().id_or_name()
      if totalDocs >= batch:
        break
    documents_cursor = documents.cursor()
    memcache.set('sbs_upgrade_cursor', documents_cursor)
    return {"result":"ok", "processed":totalDocs, "not_found":totalNotFound, "last_key":lastKey}

  if req.path == "/sbs_destroy.php":
    batch = int(req.get("batch", "4"))
    result = {}
    totalDocs = 0
    totalDestroyed = 0
    maxKey = ""
    maxChanges = 0
    lastDate = ""
    for doc in Document.gql("WHERE last_change_datetime < :1 ORDER BY last_change_datetime", cut_off_date).run(limit=batch):
      lastDate = doc.last_change_datetime.isoformat()
#       print(lastKey, doc.last_change, doc.last_change_datetime)
      changes = db.run_in_transaction(destroy_doc, doc)
      if changes > maxChanges:
        maxChanges = changes
        maxKey = doc.key().id_or_name()
      if changes == 0:
        totalDestroyed += 1
      totalDocs += 1
    return {"result":"ok", "processed":totalDocs, "destroyed":totalDestroyed, "max_key":maxKey, "max_changes":maxChanges, "last_date":lastDate}

  cmd = req.get("cmd", "")
  receipt_data = req.get("receipt_data", "")
  r_token = req.get("r_token", "")
  receipt_platform = req.get("receipt_platform", "")
  receipt_data_by = base64.urlsafe_b64decode(receipt_data.encode('ascii'))
  send_r_token = False
  if len(r_token) == 0 and len(receipt_data_by) != 0:
    r_token = hashlib.sha1(receipt_data_by).hexdigest()
    send_r_token = True

  result = {}

  if cmd == "create_doc":
    body = req.get("body", "")
    delta = int(req.get("delta", ""))
    body_by = base64.urlsafe_b64decode(body.encode('ascii'))
    if len(body_by) == 0 or delta <= 0:
      return {"result":"bad_cmd"}
    rec = get_good_receipt(None, r_token, receipt_data_by, receipt_platform)
    if not is_good(rec, delta, r_token):
      return {"result":"bad_receipt"}
    if not rec is None and send_r_token:
      result["r_token"] = rec.key().name()
    a_token_by = Random.get_random_bytes(24)
    a_token = base64.urlsafe_b64encode(a_token_by) # overwrite
    # logging.info( "md5_e_key=" + md5_e_key )
    # logging.info( "body=" + body )
    # logging.info( "a_token=" + a_token )
    doc = db.run_in_transaction(create_doc, a_token, body_by, delta)
    if not rec is None:
      rec.documents.append(doc.key())
      rec.put()
  
    result["last_change"] = delta
    result["a_token"] = a_token
    result["result"] = "create_doc"
    return result
  a_token = req.get("a_token", "")
  if len(a_token) == 0:
    return {"result":"bad_cmd"}
  doc = Document.get_by_key_name(a_token)

  if not doc:
    return {"result":"auth_failed"}
  if doc.removed:
    return {"result":"auth_failed", "removed":"1"}
    
  if cmd == "remove_doc":
    doc.removed = True
    doc.put()
    return {"result":"remove_doc"}
  elif cmd == "sync":
    body = req.get("body", "")
    body_by = base64.urlsafe_b64decode(body.encode('ascii'))
    last_change = int(req.get("last_change", ""))
    #print "body=" + body
    #print "last_change=" + unicode(last_change)
    changes = []
    inserted_change = None
    if body != "":
      delta = int(req.get("delta", ""))
      if delta <= 0:
        return {"result":"bad_cmd"}
      rec = get_good_receipt(doc, r_token, receipt_data_by, receipt_platform)
      if not is_good(rec, doc.last_change + delta, r_token):
        return {"result":"bad_receipt"}
      if not rec is None and send_r_token:
        result["r_token"] = rec.key().name()
      inserted_change = db.run_in_transaction(insert_change, doc, last_change, body_by, delta)
    result["changes"] = []
    if inserted_change:
      result["result"] = "commited"
      changes = [inserted_change]
      str = base64.b64encode(inserted_change.body)
      result["changes"].append( {"id":inserted_change.num, "datetime":unicode(inserted_change.datetime), "body":str} )
    else:
      changes_counter = 0
      total_len = 0
      max_changes = 400
      # do not send too much changes at once
      logging.info( "last_change=" + unicode(last_change) )
      for change in Change.gql("WHERE ANCESTOR IS :1 AND num >= :2 ORDER BY num", doc.key(), last_change).run(limit=max_changes):
        logging.info( "change.num=" + unicode(change.num) )
        changes_counter += 1
        if change.num != last_change:
          str = base64.b64encode(change.body)
          str_len = len(str) + 512 # even empty string is surrounded by stuff
          if total_len != 0 and total_len + str_len > 200000: #write at least 1 change, but not too long total
            result["more"] = "1"
            break
          total_len += str_len
          result["changes"].append( {"id":change.num, "datetime":unicode(change.datetime), "body":str} )
      if changes_counter == 0:
        return {"result":"bad"}
      if changes_counter == max_changes:
        result["more"] = "1";
      result["result"] = "update"
  else:
    return {"result":"bad_cmd"}
  return result

class main_sbs(webapp2.RequestHandler):
  def post(self):
    self.response.headers['Content-Type'] = "text/javascript"
    self.response.out.write( "" )
    self.response.out.write( json.dumps( main(self.request) ) )
  def get(self):
      return self.post()


app = webapp2.WSGIApplication([('.*', main_sbs)], debug=True)
