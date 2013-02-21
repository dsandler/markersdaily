#!/usr/bin/env python

DEBUG=True

import webapp2
import json

if DEBUG:
  import pprint

from google.appengine.api import memcache
from google.appengine.api import urlfetch

from apikey import API_KEY

MAX_RESULTS=64

SECONDS=1
MINUTES=60*SECONDS
HOURS=60*MINUTES
DAYS=24*HOURS
CACHE_TIMEOUT_SEC=2*MINUTES

MARKERSDAILY_GPLUS_QUERY = \
    "https://www.googleapis.com/plus/v1/activities?key=" \
    + API_KEY + "&query=markersdaily&maxResults=" \
    + str(min(MAX_RESULTS, 20))

class MainHandler(webapp2.RequestHandler):
  def get(self):
    record = memcache.get('results')
    results, etag = record if record else ([], '')
    if not results:
      token = ''
      while len(results) < MAX_RESULTS:
        response = urlfetch.fetch(
          url=MARKERSDAILY_GPLUS_QUERY + "&pageToken=" + token,
          headers={'If-None-Match': etag})
        if response.status_code != 200:
          break
        j = json.loads(response.content)
        if not j or 'nextPageToken' not in j:
          break
        etag = j['etag']
        token = j['nextPageToken']

        seen_urls=set()

        for post in j['items']:
          # try to skip reshares and find the root post
          obj = post['object']
          link = obj['url']
          is_a_reshare = (link != post['url'])
          if link in seen_urls:
            if is_a_reshare:
              continue
            else:
              for i in range(len(results)-1,-1,-1):
                post2 = results[i]
                if post2['object']['url'] == link:
                  del results[i]
          seen_urls.add(link)
          results.append(post)

      memcache.add('results', (results, etag), CACHE_TIMEOUT_SEC)

    self.response.write('''<html>
<head>
<title>#markersdaily</title>
<link rel="icon" type="image/png" href="/assets/img/markersdaily_favicon_32x32.png" />
<meta name="viewport" content="width=520" />
<link href='http://fonts.googleapis.com/css?family=Roboto+Condensed:400,700' rel='stylesheet' type='text/css'>
<style>
body {
  font-family: 'Roboto Condensed', sans-serif;
  background-image: url(/assets/img/checks.png);
  background-attachment:fixed;
  margin: 6px 0 0 6px;
}
.tile {
  display: inline-block;
  width: 250px;
  height: 250px;
  background-size: cover;
  background-repeat: no-repeat;
  background-position: center;
  position: relative;
  margin: 0 6px 6px 0;
}
.authorblock {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  display: block;
  background-color: rgba(0,0,0,0.33);
  color: #eee;
  font-size: 12px;
}
.authorblock>div {
  padding: 6px;
}
.authorblock h3 {
  font-size: 125%;
  margin: 0;
}
.plusone {
  float: right;
}
@media screen and (max-device-width: 480px) {
  html {
    max-width: 520px;
  }
  .authorblock h3 {
    font-size: 150%;
  }
}
</style>
</head>
<body>

''')

    self.response.write('<!-- cache was %s, etag for results: %s -->\n\n' \
      % ("hot" if record else "cold", etag))
    #self.response.write('Got %d items:<p>' % len(results))
    for post in results:
      obj=post['object']

      img=''
      if 'attachments' in obj:
        for att in obj['attachments']:
          if att['objectType'] == 'photo':
            img=att['image']['url']
          elif att['objectType'] == 'album':
            try:
              img=att['thumbnails'][0]['image']['url']
            except KeyError:
              pass
      if not img:
        img=str(post['actor']['image']['url'])
        img=img.replace("?sz=50","?sz=250")

      plusone=''
      if 'plusoners' in obj:
        count=obj['plusoners']['totalItems']
        if count > 0:
          plusone='+%d' % (count,)

      reshare=''
      if 'resharers' in obj:
        count=obj['resharers']['totalItems']
        if count > 0:
          reshare='&#10150;%d' % (count,)

      actor=obj.get('actor', post['actor'])

      who=actor['displayName']

      link=obj['url']

      self.response.write('''<a
        href="%(link)s"
        class="tile"
        style="background-image: url('%(img)s');">
        <div class="authorblock"><div>
        <h3>%(author)s
          <span class="plusone">%(reshare)s %(plusone)s</span>
        </h3>
        %(title)s
        </div></div>
      </a>''' % dict(
          link=link,
          author=who,
          img=img,
          title=post['title'],
          reshare=reshare,
          plusone=plusone,
        ))
      if DEBUG:
        self.response.write('<!-- ' + pprint.pformat(post) + ' -->');
    self.response.write('</body></html>')

app = webapp2.WSGIApplication([
  ('/', MainHandler)
], debug=True)
