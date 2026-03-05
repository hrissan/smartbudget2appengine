import webapp2
import sys

class main_sbs(webapp2.RequestHandler):
  def post(self):
    body = self.request.get("body", "")
    if body == "":
      self.response.headers['Content-Type'] = "text/html; charset=UTF-8"
      self.response.out.write( "" )

      self.response.out.write( "<html><head><title>Smart Budget 2 cloud availability</title></head><body>" )
      self.response.out.write( "<p>If you see this page, the cloud is accessible to you now</p>" )
      if self.request.scheme == 'http':
        self.response.out.write( "<p>You are accessing it using HTTP connection.<br/>" )
        self.response.out.write( "<a href='https://smartbudgetapp2.appspot.com/check.php'>Check HTTPS connection</a></p>" )
      else:
        self.response.out.write( "<p>You are accessing it using HTTPS connection.<br/>" )
        self.response.out.write( "<a href='http://smartbudgetapp2.appspot.com/check.php'>Check HTTP connection</a></p>" )
  #       self.response.out.write( "<p>Your IP address:" )
  #       self.response.out.write( cgi.escape(os.environ.get('REMOTE_ADDR', 'Unknown')) )
  #       self.response.out.write( "</p>" )
        self.response.out.write( "</body></html>" )
    else:
      self.response.headers['Content-Type'] =  'text/plain; charset=UTF-8'
      self.response.out.write( '' )
      self.response.out.write( body )
  def get(self):
      return self.post()

app = webapp2.WSGIApplication([('.*', main_sbs)],
                              debug=True)
