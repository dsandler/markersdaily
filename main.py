#!/usr/bin/env python

import webapp2
import json
import pprint

from google.appengine.api import memcache
from google.appengine.api import urlfetch

from apikey import API_KEY

MAX_RESULTS=64

USE_ETAG=True

SECONDS=1
MINUTES=60*SECONDS
HOURS=60*MINUTES
DAYS=24*HOURS
CACHE_TIMEOUT_SEC=2*MINUTES
ETAG_TIMEOUT_SEC=15*MINUTES

SEARCH_TERM='%23markersdaily'
MARKERSDAILY_GPLUS_QUERY = \
    "https://www.googleapis.com/plus/v1/activities?key=" \
    + API_KEY + "&query="+SEARCH_TERM+"&orderBy=recent&maxResults=" \
    + str(min(MAX_RESULTS, 20))

class MainHandler(webapp2.RequestHandler):
  def get(self):
    global DEBUG, NOCACHE, USE_ETAG

    DEBUG = 'debug' in self.request.GET and self.request.GET['debug']
    NOCACHE = 'nocache' in self.request.GET and self.request.GET['nocache']
    if 'noetag' in self.request.GET and self.request.get['noetag']:
      USE_ETAG=False

    self.response.write('''<html>
<head>
<title>#markersdaily</title>
<link rel="icon" type="image/png" href="/assets/img/markersdaily_favicon_32x32.png" />
<meta name="viewport" content="width=520" />
<link href='http://fonts.googleapis.com/css?family=Roboto+Condensed:400,700' rel='stylesheet' type='text/css'>
<link href='/assets/css/main.css' rel='stylesheet' type='text/css'>
<style>
</style>
</head>
<body>

''')

    results = memcache.get('results') if not NOCACHE else None
    etag = memcache.get('etag')
    cachecold = not results

    if cachecold:
      if DEBUG:
        self.response.write('<!-- QUERY: '+MARKERSDAILY_GPLUS_QUERY+'\n')
        self.response.write('     last ETag: '+str(etag)+'\n')
        self.response.write('     USE_ETAG='+str(USE_ETAG)+'\n')
        if NOCACHE: self.response.write('     NOCACHE=1\n')

      seen_urls=set()

      token = ''
      results = []
      new_etag = None
      while len(results) < MAX_RESULTS:
        headers=dict()
        if USE_ETAG:
          headers['If-None-Match'] = etag
        response = urlfetch.fetch(
          url=MARKERSDAILY_GPLUS_QUERY + "&pageToken=" + token,
          headers=headers)
        if response.status_code != 200:
          break
        j = json.loads(response.content)
        if not j or 'nextPageToken' not in j:
          break
        if not new_etag:
          new_etag = j['etag']
        token = j['nextPageToken']

        if (DEBUG):
          self.response.write('\n* got %d items:\n' % len(j['items']))

        for post in j['items']:
          if (DEBUG):
            self.response.write('     post url: ' + post['url'] + '\n')

          # try to skip reshares and find the root post
          obj = post['object']
          link = obj['url']
          is_a_reshare = (link != post['url'])

          if is_a_reshare and DEBUG:
            self.response.write('       - reshare of ' + link + '\n')

          if link in seen_urls:
            if is_a_reshare:
              if DEBUG:
                self.response.write('       - SKIPPING\n')
              continue
            else:
              for i in range(len(results)-1,-1,-1):
                post2 = results[i]
                if post2['object']['url'] == link:
                  del results[i]
                  if DEBUG:
                    self.response.write('       - deleting previous post: '
                      +post2['url']+'\n')
          seen_urls.add(link)
          results.append(post)

      if DEBUG: self.response.write('-->\n\n')
      memcache.add('results', results, CACHE_TIMEOUT_SEC)
      etag = new_etag
      memcache.add('etag', etag, ETAG_TIMEOUT_SEC)

    if DEBUG:
      self.response.write('<!-- cache was %s, etag for results: %s -->\n\n' \
        % ("cold" if cachecold else "hot", etag))

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
