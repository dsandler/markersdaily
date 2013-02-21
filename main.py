#!/usr/bin/env python

DEBUG=True

import webapp2
import json
import urllib

if DEBUG:
  import pprint

from google.appengine.api import memcache

from apikey import API_KEY

MAX_RESULTS=100
MARKERSDAILY_GPLUS_QUERY = \
    "https://www.googleapis.com/plus/v1/activities?key=" \
    + API_KEY + "&query=markersdaily&maxResults=" \
    + str(min(MAX_RESULTS, 20))

class MainHandler(webapp2.RequestHandler):
  def get(self):
    results = memcache.get('results')

    if not results:
      token = ''
      results = []
      while len(results) < MAX_RESULTS:
        page = urllib.urlopen(MARKERSDAILY_GPLUS_QUERY + "&pageToken=" + token)
        j = json.load(page)
        if not j or 'nextPageToken' not in j:
          break
        token = j['nextPageToken']
        for item in j['items']:
          results.append(item)
      memcache.add('results', results, 120)

    self.response.write('''<html>
<head>
<title>#markersdaily</title>
<link rel="icon" type="image/png" href="/assets/img/markersdaily_favicon_32x32.png" />
<link href='http://fonts.googleapis.com/css?family=Roboto+Condensed:400,700' rel='stylesheet' type='text/css'>
<style>
body {
  font-family: 'Roboto Condensed', sans-serif;
  background-image: url(/assets/img/checks.png);
  background-attachment:fixed;
}
.tile {
  display: inline-block;
  width: 250px;
  height: 250px;
  background-size: cover;
  background-repeat: no-repeat;
  background-position: center;
  position: relative;
}
.author {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 238px;
  display: block;
  background-color: rgba(0,0,0,0.33);
  color: #eee;
  padding: 6px;
  font-size: 12px;
}
.author>h3 {
  font-size: 15px;
  margin: 0;
}
.plusone {
  float: right;
}
</style>
</head>
<body>
    ''')

    #self.response.write('Got %d items:<p>' % len(results))
    seen_urls=set()
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
        img=post['actor']['image']['url']

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

      if link in seen_urls: continue

      seen_urls.add(link)

      self.response.write('''
      <a href="%(link)s"
        class="tile"
        style="background-image: url('%(img)s');">
        <span class="author">
        <h3>%(author)s
          <span class="plusone">%(reshare)s %(plusone)s</span>
        </h3>
        %(title)s
        </span>
      </a>
        ''' % dict(
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
