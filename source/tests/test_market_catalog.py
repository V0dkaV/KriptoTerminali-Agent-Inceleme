import json

import pytest

from engine.market import Exchange, fetch, BINANCE_PRODUCT_METADATA_URL


def binance(base='BTC', **kwargs):
    return dict(symbol=base+'USDT',baseAsset=base,quoteAsset='USDT',status='TRADING',
                isSpotTradingAllowed=True,**kwargs)


def bybit(base='BTC', **kwargs):
    return dict(symbol=base+'USDT',baseCoin=base,quoteCoin='USDT',status='Trading',**kwargs)


def metadata(rows):
    return dict(success=True,data=[dict(s=r['symbol'],b=r['baseAsset'],q=r['quoteAsset'],tags=[],etf=False) for r in rows])


def test_binance_spot_catalog_active_products_only_and_normalized(monkeypatch):
    e=Exchange('Binance');calls=[]
    rows=[binance(),binance('ETH'),binance('JUP'),binance('USDC'),binance('EUR'),
          binance('BTCUP'),binance('ETHDOWN'),binance('SOL3L'),binance('BTCBEAR'),
          binance('LEVTOKEN',permissions=['LEVERAGED']),binance('AAA',permissionSets=[['LEVERAGED']]),
          {**binance('HALT'),'status':'BREAK'}, {**binance('CLOSED'),'isSpotTradingAllowed':False},
          {**binance('BNB'),'symbol':'BNBBTC','quoteAsset':'BTC'},binance()]
    def public(path,params,market):
        calls.append((path,params,market));return dict(symbols=rows)
    monkeypatch.setattr(e,'public',public)
    monkeypatch.setattr('engine.market.fetch',lambda url:metadata(rows))
    result=e.catalog()
    assert [r['symbol'] for r in result]==['BTCUSDT','ETHUSDT','JUPUSDT']
    assert result[0]==dict(symbol='BTCUSDT',venue='Binance',market='spot',base='BTC',quote='USDT',status='TRADING')
    assert calls==[('/api/v3/exchangeInfo',dict(permissions='SPOT',symbolStatus='TRADING',showPermissionSets='false'),'spot')]


def test_binance_futures_excludes_expiry_non_usdt_margin_and_nontrading(monkeypatch):
    e=Exchange('Binance')
    rows=[binance('BTC',contractType='PERPETUAL',marginAsset='USDT'),
          binance('ETH',contractType='CURRENT_QUARTER',marginAsset='USDT'),
          binance('SOL',contractType='PERPETUAL',marginAsset='USDC'),
          binance('XRP',contractType='TRADIFI_PERPETUAL',marginAsset='USDT'),
          binance('AAPL',contractType='PERPETUAL',marginAsset='USDT',underlyingType='EQUITY'),
          binance('AMD',contractType='PERPETUAL',marginAsset='USDT',underlyingSubType=['TradFi']),
          {**binance('ADA',contractType='PERPETUAL',marginAsset='USDT'),'status':'PENDING_TRADING'}]
    monkeypatch.setattr(e,'public',lambda path,params,market:dict(symbols=rows))
    result=e.catalog('futures')
    assert len(result)==1 and result[0]['symbol']=='BTCUSDT' and result[0]['market']=='futures'


def test_bybit_spot_has_no_invalid_pagination_parameters(monkeypatch):
    e=Exchange('Bybit');calls=[]
    rows=[bybit(),bybit('JUP'),bybit('USDE'),bybit('ETH3S'),bybit('AAPLX',symbolType='xstocks'),
          {**bybit('SOL'),'status':'PreLaunch'}, {**bybit('USDC'),'quoteCoin':'BTC','symbol':'USDCBTC'}]
    def public(path,params,market):
        calls.append(params);return dict(result=dict(list=rows))
    monkeypatch.setattr(e,'public',public)
    assert [r['symbol'] for r in e.catalog()]==['BTCUSDT','JUPUSDT']
    assert calls==[dict(category='spot')]


def test_bybit_linear_cursor_dedupes_complete_pages(monkeypatch):
    e=Exchange('Bybit');calls=[]
    btc=bybit('BTC',contractType='LinearPerpetual',settleCoin='USDT')
    def public(path,params,market):
        calls.append(params.copy())
        if 'cursor' not in params:return dict(result=dict(list=[btc],nextPageCursor='next-1'))
        return dict(result=dict(list=[btc,bybit('SOL',contractType='LinearPerpetual',settleCoin='USDT'),
            bybit('ETH',contractType='LinearFutures',settleCoin='USDT'),
            bybit('XRP',contractType='LinearPerpetual',settleCoin='USDC')],nextPageCursor=''))
    monkeypatch.setattr(e,'public',public)
    assert [r['symbol'] for r in e.catalog('futures')]==['BTCUSDT','SOLUSDT']
    assert calls==[dict(category='linear',status='Trading',limit=1000),
                   dict(category='linear',status='Trading',limit=1000,cursor='next-1')]


@pytest.mark.parametrize('symbol_type',['stock','ETF','commodity','forex','xstocks','mstocks'])
def test_traditional_finance_products_not_treated_as_crypto(monkeypatch,symbol_type):
    e=Exchange('Bybit')
    rows=[bybit('BTC',contractType='LinearPerpetual',settleCoin='USDT'),
          bybit('TRADFI',contractType='LinearPerpetual',settleCoin='USDT',symbolType=symbol_type)]
    monkeypatch.setattr(e,'public',lambda *args:dict(result=dict(list=rows)))
    assert [r['symbol'] for r in e.catalog('futures')]==['BTCUSDT']


@pytest.mark.parametrize('failure',['cycle','empty_page','malformed','page_cap','spot_cursor'])
def test_catalog_never_returns_partial_pages(monkeypatch,failure):
    e=Exchange('Bybit');counter=0
    def public(*args):
        nonlocal counter
        counter+=1
        if failure=='malformed':return dict(result=dict(list='truncated'))
        if failure=='empty_page':return dict(result=dict(list=[],nextPageCursor='next'))
        cursor=str(counter) if failure=='page_cap' else 'same'
        return dict(result=dict(list=[bybit('BTC',contractType='LinearPerpetual',settleCoin='USDT')],nextPageCursor=cursor))
    monkeypatch.setattr(e,'public',public)
    with pytest.raises(ValueError):e.catalog('spot' if failure=='spot_cursor' else 'futures')
    assert counter<=20


@pytest.mark.parametrize('payload',[{},dict(symbols={}),dict(symbols=[None]),dict(symbols=[{'symbol':'BTCUSDT'}])])
def test_bad_binance_catalog_rejected(monkeypatch,payload):
    e=Exchange('Binance');monkeypatch.setattr(e,'public',lambda *args:payload)
    monkeypatch.setattr('engine.market.fetch',lambda *args:dict(success=True,data=[]))
    with pytest.raises(ValueError):e.catalog()


def test_binance_metadata_excludes_tokenized_stocks_preserves_real_b_tokens(monkeypatch):
    e=Exchange('Binance')
    rows=[binance('SHIB'),binance('NVDAB'),binance('AAPLB'),binance('OTHERB'),binance('LEVB')]
    product=metadata(rows)
    product['data'][1]['tags']=['bStocks']
    product['data'][2]['an']='Apple (bStocks)'
    product['data'][4]['etf']=True
    monkeypatch.setattr(e,'public',lambda *args:dict(symbols=rows))
    def fetch_metadata(url):
        assert url==BINANCE_PRODUCT_METADATA_URL
        return product
    monkeypatch.setattr('engine.market.fetch',fetch_metadata)
    assert [r['symbol'] for r in e.catalog()]==['OTHERBUSDT','SHIBUSDT']


@pytest.mark.parametrize('failure',['missing','malformed','false_success','network','base_mismatch','invalid_tags'])
def test_incomplete_product_classification_rejects_entire_spot_catalog(monkeypatch,failure):
    e=Exchange('Binance');rows=[binance('BTC'),binance('NVDAB')]
    product=metadata(rows)
    if failure=='missing':product['data']=product['data'][:1]
    elif failure=='malformed':product['data']='truncated'
    elif failure=='false_success':product['success']=False
    elif failure=='base_mismatch':product['data'][1]['b']='NVDA'
    elif failure=='invalid_tags':product['data'][1]['tags']='bStocks'
    monkeypatch.setattr(e,'public',lambda *args:dict(symbols=rows))
    def fetch_metadata(url):
        if failure=='network':raise OSError('classification offline')
        return product
    monkeypatch.setattr('engine.market.fetch',fetch_metadata)
    with pytest.raises((ValueError,OSError)):e.catalog()


def test_later_network_failure_does_not_commit_first_page(monkeypatch):
    e=Exchange('Bybit')
    def public(path,params,market):
        if params.get('cursor'):raise OSError('offline')
        return dict(result=dict(list=[bybit('BTC',contractType='LinearPerpetual',settleCoin='USDT')],nextPageCursor='next'))
    monkeypatch.setattr(e,'public',public)
    with pytest.raises(OSError):e.catalog('futures')


@pytest.mark.parametrize('count',[1,20,21,1500])
def test_large_binance_spot_quote_universe_avoids_long_urls(monkeypatch,count):
    e=Exchange('Binance');calls=[]
    def public(path,params,market):
        calls.append((path,params));return []
    monkeypatch.setattr(e,'public',public)
    symbols=[f'T{i}USDT' for i in range(count)]
    assert e.quotes(symbols)==[]
    params=calls[0][1]
    if count<=20:assert sorted(json.loads(params['symbols']))==sorted(symbols)
    else:assert params=={}


def test_empty_quotes_does_not_fetch_full_exchange(monkeypatch):
    e=Exchange('Binance')
    monkeypatch.setattr(e,'public',lambda *args:pytest.fail('empty watchlist must not fetch'))
    assert e.quotes([])==[]


def test_oversized_response_fails_instead_of_accepting_truncation(monkeypatch):
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):
            assert limit==4_000_001
            return b' '*limit
    monkeypatch.setattr('engine.market.urllib.request.urlopen',lambda *args,**kwargs:Response())
    with pytest.raises(ValueError,match='boyutu'):fetch('https://api.binance.com/api/v3/exchangeInfo')


def test_nonfinite_batch_data_is_excluded(monkeypatch):
    e=Exchange('Bybit')
    rows=[dict(symbol='BTCUSDT',lastPrice='Infinity',bid1Price='100',ask1Price='101'),
          dict(symbol='ETHUSDT',lastPrice='100',bid1Price='99',ask1Price='101',turnover24h='NaN')]
    monkeypatch.setattr(e,'public',lambda *args:dict(result=dict(list=rows)))
    assert e.quotes(['BTCUSDT','ETHUSDT'])==[]
