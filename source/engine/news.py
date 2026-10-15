import hashlib
import re
import time
import xml.etree.ElementTree as ET
import html
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from engine.market import fetch, iso_now

SOURCES = [
    ('Federal Reserve', 'https://www.federalreserve.gov/feeds/press_monetary.xml'),
    ('SEC', 'https://www.sec.gov/news/pressreleases.rss'),
    ('Avrupa Merkez Bankası','https://www.ecb.europa.eu/rss/press.html'),
    ('Beyaz Saray','https://www.whitehouse.gov/feed/'),
    ('Avrupa Konseyi','https://www.consilium.europa.eu/en/press/press-releases/rss/'),
]


def collect_news(previous):
    seen = {n['id']: n for n in previous if not n.get('demo')}
    sources = []
    for name, url in SOURCES:
        try:
            root = ET.fromstring(fetch(url, raw=True))
            items = root.findall('.//item')
            for item in items[:25]:
                title = re.sub(r'\s+', ' ', item.findtext('title', '')).strip()
                link = item.findtext('link', '').strip()
                if not title or not link.startswith('https://'): continue
                identity = hashlib.sha256((name + re.sub(r'\W+', '', title.lower())).encode()).hexdigest()[:20]
                try:
                    published = parsedate_to_datetime(item.findtext('pubDate', '')).astimezone(timezone.utc).isoformat()
                except Exception:
                    published = ''
                content = title.lower()
                description=html.unescape(re.sub('<[^>]+>',' ',item.findtext('description','')))[:900]
                critical = any(word in content for word in ('exploit', 'hack', 'suspend trading', 'security incident'))
                assets = [coin for coin in ('BTC', 'ETH', 'USDT') if coin.lower() in content]
                if 'bitcoin' in content and 'BTC' not in assets: assets.append('BTC')
                if 'ethereum' in content and 'ETH' not in assets: assets.append('ETH')
                old = seen.get(identity, {})
                seen[identity] = dict(id=identity, title=title, source=name, url=link, published_at=published,
                                      description=description,
                                      first_seen_at=old.get('first_seen_at', iso_now()), severity='critical' if critical else 'info',
                                      verification='official', assets=assets, demo=False,
                                      restriction_until=old.get('restriction_until',0),
                                      action='Resmî kaynak; etki doğrulaması gerekiyor. Başlıktan yön tahmini yapılmaz.',
                                      candidate_restriction=critical)
            sources.append(dict(name=name, status='ok', count=len(items), observed=time.time()))
        except Exception:
            sources.append(dict(name=name, status='unavailable', count=0, observed=time.time()))
    try:
        text = fetch('https://www.bls.gov/schedule/news_release/bls.ics', raw=True).decode('utf-8', errors='replace')
        calendar = []
        for block in text.split('BEGIN:VEVENT')[1:]:
            title = re.search(r'\nSUMMARY:(.+)', block)
            date = re.search(r'\nDTSTART([^:]*):([^\r\n]+)', block)
            if not title or not date: continue
            raw = date.group(2).strip()
            try:
                value = datetime.strptime(raw.rstrip('Z'), '%Y%m%dT%H%M%S')
                value = value.replace(tzinfo=timezone.utc if raw.endswith('Z') else ZoneInfo('America/New_York'))
                stamp = value.timestamp()
            except ValueError:
                continue
            if stamp < time.time()-86400 or stamp > time.time()+14*86400: continue
            name = title.group(1).strip()
            important = any(word in name.lower() for word in ('consumer price', 'employment situation', 'producer price'))
            identity = hashlib.sha256(('BLS' + name + raw).encode()).hexdigest()[:20]
            seen[identity] = dict(id=identity, title=name, source='BLS takvimi', url='https://www.bls.gov/schedule/',
                                  published_at='', first_seen_at=seen.get(identity, {}).get('first_seen_at', iso_now()),
                                  severity='scheduled', verification='official', assets=['BTC', 'ETH'], demo=False,
                                  restriction_until=seen.get(identity,{}).get('restriction_until',0),
                                  scheduled_at=stamp, blackout=important,
                                  action='Açıklama öncesi 15dk / sonrası 30dk yeni giriş bekleme penceresi.' if important else 'Takvim bilgisi; giriş kısıtı yok.')
            calendar.append(identity)
        sources.append(dict(name='BLS takvimi', status='ok', count=len(calendar), observed=time.time()))
    except Exception:
        sources.append(dict(name='BLS takvimi', status='unavailable', count=0, observed=time.time()))
    events = sorted(seen.values(), key=lambda n: n.get('first_seen_at', ''), reverse=True)[:100]
    return events, sources


ARTICLE_HOSTS={'www.federalreserve.gov','www.sec.gov','www.ecb.europa.eu','www.whitehouse.gov','www.consilium.europa.eu'}


def article_excerpt(event):
    """Fetch only known primary-source hosts; never follow links supplied by AI."""
    url=event.get('url','')
    def valid(value):
        parsed=urllib.parse.urlparse(value)
        return parsed.scheme=='https' and parsed.hostname in ARTICLE_HOSTS
    if not valid(url):return event.get('description','')[:1000]
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not valid(newurl):raise ValueError('Kaynak dışına yönlendirme reddedildi.')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'KriptoTerminali/0.3 local-news-reader'})
        with urllib.request.build_opener(Redirect()).open(request,timeout=6) as response:
            body=response.read(2_000_000).decode('utf-8',errors='replace')
        body=re.sub(r'<(script|style|nav|footer)\b[^>]*>.*?</\1>',' ',body,flags=re.S|re.I)
        main=re.search(r'<(?:article|main)\b[^>]*>(.*?)</(?:article|main)>',body,flags=re.S|re.I)
        text=html.unescape(re.sub('<[^>]+>',' ',main.group(1) if main else body))
        return re.sub(r'\s+',' ',text).strip()[:1600]
    except Exception:return event.get('description','')[:1000]


def entry_restriction(events, symbol, now=None):
    now = time.time() if now is None else now
    for event in events:
        stamp = event.get('scheduled_at')
        if stamp and event.get('blackout') and stamp - 900 <= now <= stamp + 1800:
            return f"Ekonomik takvim bekleme penceresi: {event['title']}"
        # Headline keyword detection is NOT enough to freeze trading. Explicit human
        # confirmation supplies a bounded restriction through the local UI.
        if event.get('restriction_until', 0) > now:
            assets = event.get('assets', [])
            if not assets or any(symbol.startswith(a) for a in assets):
                return 'Doğrulanmış olay kısıtı: ' + event['title']
    return None
