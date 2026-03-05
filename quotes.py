import webapp2
import base64
from xml.dom import minidom
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.api import memcache
import json
import logging

class Quotes(db.Model):
  #base = db.StringProperty(required=True)
  text = db.TextProperty(required=True)

def download_mtgox_api(base):
  url1 = "http://data.mtgox.com/api/2/BTC" + base + "/money/ticker"
  result = urlfetch.fetch(url1)
  if result.status_code != 200:
    raise InvalidURLError()
  logging.info( "content=" + result.content )
  js = json.loads(result.content)
  text = "\n"
  text += "BTC" + "," + unicode(1/float(js["data"]["avg"]["value"])) + "\n"
  return text

def download_yahoo_api(base):
  url1 = "http://download.finance.yahoo.com/d/quotes.csv?f=l1&s=" + base
  url2 = "=X"
  curr_list = ["CRC", "COP"]

  text = "\n"
  for curr in curr_list:
    result = urlfetch.fetch(url1 + curr + url2)
    if result.status_code != 200:
      raise InvalidURLError()
    val = float(result.content)
    text += curr + "," + unicode(val) + "\n"
  return text

def download_exhangerate_api(base):
  url1 = "http://www.exchangerate-api.com/" + base + "/"
  url2 = "/<censored>"
  curr_list = ["ARS", "AUD", "BSD", "BHD", "BBD", "XOF", "BRL", "XAF",
  "CAD", "CLP", "CNY", "HRK", "CZK", "DKK", "XCD", "EGP",
  "EEK", "EUR", "FJD", "HKD", "HUF", "ISK", "INR", "IDR", 
  "ILS", "JMD", "JPY", "KES", "KRW", "LVL", "LTL", "MYR", 
  "MXN", "MAD", "ANG", "NZD", "NOK", "OMR", "PKR", "PAB", 
  "PEN", "PHP", "PLN", "QAR", "RON", "RUB", "SAR", "RSD", 
  "SGD", "ZAR", "LKR", "SEK", "CHF", "TWD", "THB", "TTD",
  "TRY", "AED", "GBP", "USD", "VEF", "VND"]

  text = "\n"
  for curr in curr_list:
    result = urlfetch.fetch(url1 + curr + url2)
    if result.status_code != 200:
      raise InvalidURLError()
    val = float(result.content)/1048576
    text += curr + "," + unicode(val) + "\n"
  return text
  
def download_cbr(base):
  url = "http://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
  payload = """<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
  <GetLatestDateTime xmlns="http://web.cbr.ru/" />
  </soap12:Body>
</soap12:Envelope>"""

  result = urlfetch.fetch(url, payload,
    method=urlfetch.POST,
    headers={'Content-Type': 'application/soap+xml; charset=utf-8'})
  dom = minidom.parseString(result.content)
  last_date = None
  for node in dom.getElementsByTagName('GetLatestDateTimeResult'):
    last_date = node.firstChild.data
  if not last_date:
    raise InvalidURLError()

  url = "http://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
  payload = """<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <GetCursOnDateXML xmlns="http://web.cbr.ru/">
      <On_date>%s</On_date>
    </GetCursOnDateXML>
  </soap12:Body>
</soap12:Envelope>""" % last_date;

  result = urlfetch.fetch(url, payload,
    method=urlfetch.POST,
    headers={'Content-Type': 'application/soap+xml; charset=utf-8'})
  #logging.info( "CB courses=" + result.content )
  dom = minidom.parseString(result.content)
  curr_cbr_list = ["AZN", "AMD", "BYR", "BGN", "KZT", "KGS", "MDL", "XDR",
  "TJS", "TMT", "UZS", "UAH"];
  rub_usd = 0.0
  for node in dom.getElementsByTagName('ValuteCursOnDate'):
    curr = node.getElementsByTagName('VchCode')[0].firstChild.data
    sum = node.getElementsByTagName('Vnom')[0].firstChild.data
    curs = node.getElementsByTagName('Vcurs')[0].firstChild.data
    if curr == base:
      rub_usd = float(curs)/float(sum)
      break
  if not rub_usd:
    raise InvalidURLError()
  text = "\n"
  for node in dom.getElementsByTagName('ValuteCursOnDate'):
    curr = node.getElementsByTagName('VchCode')[0].firstChild.data
    sum = node.getElementsByTagName('Vnom')[0].firstChild.data
    curs = node.getElementsByTagName('Vcurs')[0].firstChild.data
    try:
      pos = curr_cbr_list.index(curr)
      rub_curr = float(curs)/float(sum)
      val = rub_usd / rub_curr
      text += curr + "," + unicode(val) + "\n"
    except ValueError:
      pass
  return text
  
def download_openexchangerate_api(base):
  text = ""
  if base != "USD":
    return text
  fetch_headers = {'Cache-Control':'no-cache,max-age=0', 'Pragma':'no-cache'}
  result = urlfetch.fetch("http://openexchangerates.org/api/latest.json?app_id=<censored>", headers=fetch_headers)
  
  logging.info( "Exchange rates status_code=" + unicode(result.status_code) )
  logging.info( "Exchange rates headers=" + unicode(result.headers) )
  logging.info( "Exchange rates content=" + result.content )
  js = json.loads(result.content)
  if js["base"] != "USD":
    return text
  for ra in js["rates"]:
    val = js["rates"][ra]
    text += ra + "," + unicode(val) + "\n"
  return text


def download_quotes(base):
  text = ""
  text += download_openexchangerate_api(base)
  #text += download_mtgox_api(base)
  #text += download_yahoo_api(base)
  #text += download_exhangerate_api(base)
  #text += download_cbr(base)
  quotes = Quotes.get_by_key_name(base)
  if not quotes:
    quotes = Quotes(key_name=base, text=text)
  quotes.text = text
  quotes.put()
  memcache.delete('quotes_' + base)
  #logging.info("cleared memcache")
  return text
  
def main(req):
  base = req.get("base", "")
  if req.path != "/quotes_cron.php":
    text = memcache.get('quotes_' + base)
    if not text is None:
      #logging.info("from memcache")
      return text
    quotes = Quotes.get_by_key_name(base)
    if not quotes:
      return "no quotes";
    #logging.info("add to memcache")
    memcache.add('quotes_' + base, quotes.text, 3600)
    return quotes.text
  return download_quotes(base)

class main_quotes(webapp2.RequestHandler):
  def post(self):
    self.response.headers['Content-Type'] = "text/plain; charset=UTF-8"
    self.response.out.write( "" )
    self.response.out.write( main(self.request) )
  def get(self):
      return self.post()


app = webapp2.WSGIApplication([('.*', main_quotes)],
                              debug=True)
