from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


# These are product exclusions, not liquidity/creditworthiness endorsements.
# Fiat and USD/EUR-pegged base assets add no independent crypto-direction signal.
CATALOG_EXCLUDED_BASES = frozenset('''
USDT USDC USDCV FDUSD BUSD TUSD USDP DAI USDE USD1 USDJ PYUSD FRAX USD0
GUSD USDD USDS USDTB LUSD SUSD USDB RLUSD GHO USDQ USDR USDG USDF USDU
USN MIM CUSD DOLA VAI EUR AEUR EURI EURC EURCV TRY BRL AUD GBP RUB UAH
BIDR IDRT NGN ARS ZAR PLN RON UST USTC USTB EURQ EURR CAD CHF JPY MXN
'''.split())
CATALOG_LEVERAGED_UNDERLYINGS = frozenset('''
BTC ETH BNB XRP LTC BCH EOS TRX ADA XLM XTZ LINK DOT YFI UNI AAVE SUSHI
FIL SOL DOGE AVAX MATIC ATOM NEAR ETC BSV DASH ZEC
'''.split())
CATALOG_EXCLUDED_TYPES = frozenset(('stock','ETF','commodity','forex','xstocks','mstocks'))
BINANCE_PRODUCT_METADATA_URL = 'https://www.binance.com/bapi/asset/v2/public/asset-service/product/get-products?includeEtf=true'


def _catalog_product_allowed(symbol, base, row):
    """Keep USDT crypto products; exclude known fiat/stables and leveraged tokens.

    Numeric 2/3/5L/S and BULL/BEAR suffixes identify leveraged token families.
    UP/DOWN is matched only for known underlyings, so JUP is never mistaken for UP.
    Exchange LEVERAGED permissions are also excluded when present.
    """
    if not re.fullmatch(r'[A-Z0-9]{1,16}USDT',symbol) or symbol!=base+'USDT':return False
    if base in CATALOG_EXCLUDED_BASES:return False
    if row.get('symbolType') in CATALOG_EXCLUDED_TYPES:return False
    if row.get('underlyingType','').upper() in ('EQUITY','COMMODITY','FOREX','ETF'):return False
    if any(str(tag).lower()=='tradfi' for tag in (row.get('underlyingSubType') or [])):return False
    if re.search(r'(?:[235][LS]|BULL|BEAR)$',base):return False
    if any(base==underlying+suffix for underlying in CATALOG_LEVERAGED_UNDERLYINGS for suffix in ('UP','DOWN')):return False
    if 'LEVERAGED' in (row.get('permissions') or []):return False
    if any('LEVERAGED' in group for group in (row.get('permissionSets') or [])):return False
    return True


def fetch(url, headers=None, timeout=8, raw=False):
    req = urllib.request.Request(url, headers={'User-Agent': 'KriptoTerminali/0.1 local-research', **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read(4_000_001)
        if len(body) > 4_000_000:
            raise ValueError('Yanıt boyutu sınırı aşıldı')
    return body if raw else json.loads(body)


class Exchange:
    def __init__(self, venue, key='', secret='', testnet=False):
        if venue not in ('Binance', 'Bybit'):
            raise ValueError('Desteklenmeyen borsa')
        self.venue, self.key, self.secret, self.testnet = venue, key, secret, testnet

    def _base(self, market='spot'):
        if self.venue == 'Binance':
            if self.testnet:
                return 'https://testnet.binance.vision' if market == 'spot' else 'https://demo-fapi.binance.com'
            return 'https://api.binance.com' if market == 'spot' else 'https://fapi.binance.com'
        return 'https://api-testnet.bybit.com' if self.testnet else 'https://api.bybit.com'

    def public(self, path, params=None, market='spot'):
        query = urllib.parse.urlencode(params or {})
        data = fetch(self._base(market) + path + ('?' + query if query else ''))
        if self.venue == 'Bybit' and data.get('retCode', 0):
            raise ValueError('Bybit veri isteği reddedildi: ' + str(data['retCode']))
        return data

    def signed(self, path, params=None, market='spot', method='GET'):
        if not self.key or not self.secret:
            raise ValueError('API anahtarı yapılandırılmadı')
        params = dict(params or {})
        stamp = str(int(time.time() * 1000))
        if self.venue == 'Binance':
            params.update(timestamp=stamp, recvWindow=5000)
            query = urllib.parse.urlencode(params)
            signature = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            url = self._base(market) + path + '?' + query + '&signature=' + signature
            headers = {'X-MBX-APIKEY': self.key}
            payload = None
        else:
            query = urllib.parse.urlencode(sorted(params.items())) if method == 'GET' else json.dumps(params, separators=(',', ':'))
            signature = hmac.new(self.secret.encode(), (stamp + self.key + '5000' + query).encode(), hashlib.sha256).hexdigest()
            headers = {'X-BAPI-API-KEY': self.key, 'X-BAPI-SIGN': signature, 'X-BAPI-TIMESTAMP': stamp,
                       'X-BAPI-RECV-WINDOW': '5000', 'Content-Type': 'application/json'}
            url = self._base(market) + path + (('?' + query) if method == 'GET' else '')
            payload = None if method == 'GET' else query.encode()
        req = urllib.request.Request(url, data=payload, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read(4_000_000))
        if self.venue == 'Bybit' and result.get('retCode', 0):
            raise ValueError('Hesap isteği reddedildi: ' + str(result['retCode']))
        return result

    def quote(self, symbol='BTCUSDT', market='spot'):
        requested=time.time()
        if self.venue == 'Binance':
            prefix = '/api/v3' if market == 'spot' else '/fapi/v1'
            r = self.public(prefix + '/ticker/24hr', {'symbol': symbol}, market)
            book = self.public(prefix + '/ticker/bookTicker', {'symbol': symbol}, market)
            mark=self.public('/fapi/v1/premiumIndex',{'symbol':symbol},market) if market=='futures' else {}
            return dict(symbol=symbol, venue=self.venue, market=market, price=float(r['lastPrice']),
                        change=float(r['priceChangePercent']), volume=float(r['quoteVolume']),
                        bid=float(book['bidPrice']), ask=float(book['askPrice']), observed=requested,
                        price_observed=requested,bid_observed=requested,ask_observed=requested,
                        bid_size=float(book.get('bidQty',0)),ask_size=float(book.get('askQty',0)),transport='rest',
                        mark_price=float(mark.get('markPrice') or 0),mark_price_observed=requested if mark else 0,
                        funding=float(mark.get('lastFundingRate') or 0))
        r = self.public('/v5/market/tickers', {'category': 'spot' if market == 'spot' else 'linear', 'symbol': symbol}, market)['result']['list'][0]
        return dict(symbol=symbol, venue=self.venue, market=market, price=float(r['lastPrice']),
                    change=float(r.get('price24hPcnt', 0)) * 100, volume=float(r.get('turnover24h', 0)),
                    bid=float(r['bid1Price']), ask=float(r['ask1Price']), observed=requested,
                    price_observed=requested,bid_observed=requested,ask_observed=requested,
                    bid_size=float(r.get('bid1Size') or 0),ask_size=float(r.get('ask1Size') or 0),transport='rest',
                    mark_price=float(r.get('markPrice') or 0),mark_price_observed=requested if market=='futures' else 0,
                    funding=float(r.get('fundingRate', 0)), next_funding=r.get('nextFundingTime'))

    def quotes(self, symbols, market='spot'):
        """One bounded batch per venue/product, independent of watchlist length."""
        requested=time.time()
        wanted=set(symbols)
        if not wanted:return []
        if self.venue=='Bybit':
            rows=self.public('/v5/market/tickers',{'category':'spot' if market=='spot' else 'linear'},market)['result']['list']
            books={};marks={}
        else:
            prefix='/api/v3' if market=='spot' else '/fapi/v1'
            # Keep the cheap <=20-symbol request; large catalogs use all-symbol
            # tickers instead of an unbounded symbols query string.
            params={'symbols':json.dumps(sorted(wanted),separators=(',',':'))} if market=='spot' and len(wanted)<=20 else {}
            try: rows=self.public(prefix+'/ticker/24hr',params,market)
            except Exception: rows=self.public(prefix+'/ticker/24hr',{},market)
            books={r['symbol']:r for r in self.public(prefix+'/ticker/bookTicker',{},market)}
            marks={r['symbol']:r for r in self.public('/fapi/v1/premiumIndex',{},market)} if market=='futures' else {}
        result=[]
        for r in rows:
            symbol=r.get('symbol')
            if symbol not in wanted:continue
            try:
                bybit=self.venue=='Bybit';book=r if bybit else books[symbol];mark=r if bybit else marks.get(symbol,{})
                q=dict(symbol=symbol,venue=self.venue,market=market,price=float(r['lastPrice']),
                       bid=float(book['bid1Price' if bybit else 'bidPrice']),ask=float(book['ask1Price' if bybit else 'askPrice']),
                       bid_size=float(book.get('bid1Size' if bybit else 'bidQty') or 0),
                       ask_size=float(book.get('ask1Size' if bybit else 'askQty') or 0),
                       volume=float(r.get('turnover24h' if bybit else 'quoteVolume') or 0),
                       change=float(r.get('price24hPcnt' if bybit else 'priceChangePercent') or 0)*(100 if bybit else 1),
                       mark_price=float(mark.get('markPrice') or 0),funding=float(mark.get('fundingRate' if bybit else 'lastFundingRate') or 0),
                       observed=requested,transport='rest',price_transport='rest')
                if not all(math.isfinite(v) for v in q.values() if isinstance(v,(float,int))):continue
                if not all(q[k]>0 for k in ('price','bid','ask')) or q['ask']<q['bid']:continue
                q.update({k+'_observed':requested for k in ('price','bid','ask')})
                q['mark_price_observed']=requested if market=='futures' and q['mark_price']>0 else 0
                result.append(q)
            except (KeyError,ValueError,TypeError):continue
        return result

    def catalog(self, market='spot'):
        """Complete public list of active USDT spot or USDT-settled perpetuals.

        Fiat/stable bases, recognized leveraged tokens and unsupported symbols
        are excluded explicitly. A discovery request either returns every page
        or raises; a truncated/cyclic/oversized result is never a full catalog.
        No account or private API permissions are needed.
        """
        if market not in ('spot','futures'):raise ValueError('Desteklenmeyen katalog piyasası')
        if self.venue=='Binance':
            params=dict(permissions='SPOT',symbolStatus='TRADING',showPermissionSets='false') if market=='spot' else {}
            payload=self.public('/api/v3/exchangeInfo' if market=='spot' else '/fapi/v1/exchangeInfo',params,market)
            if not isinstance(payload,dict) or not isinstance(payload.get('symbols'),list):
                raise ValueError('Borsa kataloğu biçimi doğrulanamadı')
            rows=payload['symbols']
            if market=='spot':
                # exchangeInfo exposes no bStocks classification. Binance's own
                # public product metadata identifies bStocks explicitly; never
                # guess from ticker suffix B (which would also remove SHIB).
                metadata=fetch(BINANCE_PRODUCT_METADATA_URL)
                products=metadata.get('data') if isinstance(metadata,dict) else None
                if not isinstance(products,list) or metadata.get('success') is not True:
                    raise ValueError('Spot ürün sınıflandırması alınamadı; katalog tamamlanmadı')
                classified={}
                for product in products:
                    if not isinstance(product,dict) or not all(isinstance(product.get(k),str) for k in ('s','b','q')):
                        raise ValueError('Spot ürün sınıflandırması doğrulanamadı')
                    tags=product.get('tags') or []
                    if not isinstance(tags,list) or any(not isinstance(tag,str) for tag in tags):
                        raise ValueError('Spot ürün etiketleri doğrulanamadı')
                    excluded=bool(product.get('etf')) or any(tag.lower() in ('bstocks','stocks','stock','xstocks','mstocks','etf') for tag in tags)
                    excluded=excluded or '(bstocks)' in str(product.get('an','')).lower()
                    classified[product['s']]=(product['b'],product['q'],excluded)
                filtered=[]
                for row in rows:
                    if not isinstance(row,dict):raise ValueError('Spot katalog kaydı doğrulanamadı')
                    if row.get('quoteAsset')=='USDT' and row.get('status')=='TRADING' and row.get('isSpotTradingAllowed') is True:
                        product=classified.get(row.get('symbol'))
                        if not product or product[:2]!=(row.get('baseAsset'),row.get('quoteAsset')):
                            raise ValueError('Spot ürün sınıflandırması eksik; katalog tamamlanmadı')
                        if product[2]:continue
                    filtered.append(row)
                rows=filtered
        else:
            rows=[];cursor='';seen=set()
            for _ in range(20):
                params=dict(category='spot' if market=='spot' else 'linear')
                if market=='futures':
                    params.update(status='Trading',limit=1000)
                    if cursor:params['cursor']=cursor
                payload=self.public('/v5/market/instruments-info',params,market)
                result=payload.get('result') if isinstance(payload,dict) else None
                if not isinstance(result,dict) or not isinstance(result.get('list'),list):
                    raise ValueError('Borsa katalog sayfası doğrulanamadı')
                page=result['list']
                next_cursor=result.get('nextPageCursor','') or ''
                if not isinstance(next_cursor,str) or len(next_cursor)>4096:
                    raise ValueError('Borsa katalog sayfalama işareti geçersiz')
                if next_cursor and (not page or next_cursor in seen or market=='spot'):
                    raise ValueError('Borsa kataloğu eksik veya sayfalama tekrar ediyor')
                rows.extend(page)
                if len(rows)>20000:raise ValueError('Borsa katalog kayıt sınırı aşıldı; sonuç tamamlanmadı')
                if not next_cursor:break
                seen.add(next_cursor);cursor=next_cursor
            else:raise ValueError('Borsa katalog sayfa sınırı aşıldı; sonuç tamamlanmadı')
        if len(rows)>20000:raise ValueError('Borsa katalog kayıt sınırı aşıldı')
        found={}
        for row in rows:
            if not isinstance(row,dict):raise ValueError('Borsa katalog kaydı doğrulanamadı')
            bybit=self.venue=='Bybit'
            fields=('symbol','baseCoin','quoteCoin','status') if bybit else ('symbol','baseAsset','quoteAsset','status')
            if any(not isinstance(row.get(k),str) or not row[k] for k in fields):
                raise ValueError('Borsa katalog alanları eksik; sonuç tamamlanmadı')
            symbol,base,quote,status=(row[k] for k in fields)
            if status!=('Trading' if bybit else 'TRADING') or quote!='USDT':continue
            if market=='spot' and not bybit and row.get('isSpotTradingAllowed') is not True:continue
            if market=='futures':
                if row.get('contractType')!=('LinearPerpetual' if bybit else 'PERPETUAL'):continue
                if row.get('settleCoin' if bybit else 'marginAsset')!='USDT':continue
            if not _catalog_product_allowed(symbol,base,row):continue
            found[symbol]=dict(symbol=symbol,venue=self.venue,market=market,base=base,quote='USDT',status='TRADING')
        return [found[symbol] for symbol in sorted(found)]

    def candles(self, symbol, interval='15m', market='spot', limit=1000, start=None, end=None):
        seconds = {'15m': 900, '1h': 3600, '4h': 14400, '1d': 86400}[interval]
        if self.venue == 'Binance':
            p = dict(symbol=symbol, interval=interval, limit=min(limit, 1000))
            if start is not None: p['startTime'] = int(start * 1000)
            if end is not None: p['endTime'] = int(end * 1000)
            rows = self.public(('/api/v3' if market == 'spot' else '/fapi/v1') + '/klines', p, market)
            result = [dict(time=int(int(r[0]) / (1_000_000 if int(r[0]) > 10**14 else 1000)),
                           open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]), volume=float(r[5])) for r in rows]
        else:
            p = dict(category='spot' if market == 'spot' else 'linear', symbol=symbol,
                     interval={'15m': '15', '1h': '60', '4h': '240', '1d': 'D'}[interval], limit=min(limit, 1000))
            if start is not None: p['start'] = int(start * 1000)
            if end is not None: p['end'] = int(end * 1000)
            rows = self.public('/v5/market/kline', p, market)['result']['list']
            result = [dict(time=int(r[0]) // 1000, open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]), volume=float(r[5])) for r in rows]
        return sorted([r for r in result if r['time'] + seconds <= time.time()], key=lambda r: r['time'])

    def instruments(self, symbol, market='spot'):
        if self.venue == 'Binance':
            p = {'symbol': symbol} if market == 'spot' else {}
            result = self.public(('/api/v3' if market == 'spot' else '/fapi/v1') + '/exchangeInfo', p, market)
            return next(s for s in result['symbols'] if s['symbol'] == symbol)
        return self.public('/v5/market/instruments-info', dict(category='spot' if market == 'spot' else 'linear', symbol=symbol), market)['result']['list'][0]

    def funding_events(self,symbol):
        if self.venue=='Binance':
            rows=self.public('/fapi/v1/fundingRate',dict(symbol=symbol,limit=10),'futures')
            return [dict(time=int(r['fundingTime'])/1000,rate=float(r['fundingRate']),
                         mark=float(r.get('markPrice') or 0)) for r in rows]
        rows=self.public('/v5/market/funding/history',dict(category='linear',symbol=symbol,limit=10),'futures')['result']['list']
        return [dict(time=int(r['fundingRateTimestamp'])/1000,rate=float(r['fundingRate']),mark=0) for r in rows]

    def fee_rates(self, symbol, market='spot'):
        if self.venue == 'Binance':
            if market == 'spot':
                return self.signed('/api/v3/account/commission', {'symbol': symbol})
            return self.signed('/fapi/v1/commissionRate', {'symbol': symbol}, market)
        return self.signed('/v5/account/fee-rate', dict(category='spot' if market == 'spot' else 'linear', symbol=symbol), market)

    def account(self):
        if self.venue == 'Binance':
            r = self.signed('/api/v3/account', {'omitZeroBalances': 'true'})
            return {'can_trade': r.get('canTrade', False), 'balances': r.get('balances', [])}
        r = self.signed('/v5/account/wallet-balance', {'accountType': 'UNIFIED'})
        return {'can_trade': True, 'balances': r.get('result', {}).get('list', [])}

    def executions(self, symbol, market='spot'):
        if self.venue == 'Binance':
            return self.signed('/api/v3/myTrades' if market == 'spot' else '/fapi/v1/userTrades', {'symbol': symbol, 'limit': 100}, market)
        return self.signed('/v5/execution/list', {'category': 'spot' if market == 'spot' else 'linear', 'symbol': symbol, 'limit': 100}, market)


def iso_now():
    return datetime.now(timezone.utc).isoformat()
