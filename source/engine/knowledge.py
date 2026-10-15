"""Reviewed research knowledge, not executable strategy definitions or model weights."""
from __future__ import annotations

import copy
import time

VERSION = '2026.10.15-1'
REVIEWED_AT = '2026-10-15'
SOURCES = [
    dict(id='tv-avwap', title='TradingView · Anchored VWAP', url='https://www.tradingview.com/support/solutions/43000669764-anchored-vwap-drawing-tool/'),
    dict(id='tv-profile', title='TradingView · Volume profile', url='https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/'),
    dict(id='tv-bb', title='TradingView · Bollinger Bands', url='https://www.tradingview.com/support/solutions/43000501840-bollinger-bands-bb/'),
    dict(id='tv-macd', title='TradingView · MACD', url='https://www.tradingview.com/support/solutions/43000502344-moving-average-convergence-divergence-macd-indicator/'),
    dict(id='aqr-trend', title='Moskowitz, Ooi, Pedersen · Time Series Momentum (2012)', url='https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum'),
    dict(id='bybit-oi', title='Bybit · Open interest API', url='https://bybit-exchange.github.io/docs/v5/market/open-interest'),
    dict(id='bybit-funding', title='Bybit · Funding history API', url='https://bybit-exchange.github.io/docs/v5/market/history-fund-rate'),
    dict(id='bybit-trades', title='Bybit · Public trade stream', url='https://bybit-exchange.github.io/docs/v5/websocket/public/trade'),
    dict(id='oi-quality', title='Giagkiozis, Said · Open interest data quality (2023)', url='https://arxiv.org/abs/2310.14973'),
    dict(id='sk-time', title='scikit-learn · TimeSeriesSplit', url='https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html'),
    dict(id='sk-calibration', title='scikit-learn · Probability calibration', url='https://scikit-learn.org/stable/modules/calibration.html'),
    dict(id='deflated-sharpe', title='Bailey, López de Prado · Deflated Sharpe Ratio (2014)', url='https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf'),
]


def card(id, name, family, status, method, data, limitation, validation, sources, brief):
    return dict(id=id, name=name, family=family, status=status, method=method, data=data,
                limitation=limitation, validation=validation, source_ids=sources,
                reviewed_at=REVIEWED_AT, ai_brief=brief)


CARDS = [
    card('breakout', 'Kanal kırılımı', 'Trend', 'adaptive',
         'Önceki kapanmış mumların kanalını aşan hareket, üst zaman EMA eğilimiyle karşılaştırılır. Uygulamanın kendi kuralıdır.',
         'Kapanmış OHLCV, üst zaman mumları, güncel alış/satış.', 'Sahte kırılım, fiyat boşluğu ve maliyetler.',
         'Maliyetli kronolojik değerlendirme ve ileri dönem karşılaştırması; her coin için kâr kanıtı değildir.', ['aqr-trend'],
         'Implemented breakout: previous-bar channel + higher-timeframe EMA. False breakouts; costs and forward comparison required.'),
    card('momentum', 'MACD ve momentum', 'Momentum', 'adaptive',
         'MACD histogram kesişimi, RSI ve üst zaman trendi uygulamanın belirlenmiş koşullarıyla birlikte kullanılır.',
         'Kapanmış OHLCV ve yeterli hazırlık.', 'Gecikme ve yatay piyasada sık ters sinyal.',
         'Seçicinin maliyetli geçmiş ve ileri dönem karşılaştırması; MACD kaynağı bu birleşimin başarısını doğrulamaz.', ['tv-macd'],
         'Implemented momentum: MACD histogram crossing + RSI + trend. Lag/whipsaw risk; source defines indicator, not profitability.'),
    card('pullback', 'Trend içi geri çekilme', 'Trend', 'adaptive',
         'Üst zaman eğilimi yönünde EMA20 seviyesine dönüş ve yeniden geçiş araştırılır; bu, uygulamanın kuralıdır.',
         'Kapanmış OHLCV ve üst zaman EMA50/200.', 'Trend kırıldığında tekrar giriş kayıpları.',
         'Diğer dört aileyle aynı maliyet ve bağımsız ileri dönem koşulları.', ['aqr-trend'],
         'Implemented pullback: EMA20 recross in higher-timeframe trend. Trend failure risk; do not equate long-horizon research with this rule.'),
    card('reversion', 'Bollinger ortalamaya dönüş', 'Yatay piyasa', 'adaptive',
         'Bollinger bandına geri dönüş, RSI ve sınırlı trend gücüyle değerlendirilir.',
         'Kapanmış OHLCV, oynaklık ve trend ölçümleri.', 'Banda değmek tek başına al/sat nedeni değildir; güçlü trend sürdürülebilir.',
         'Trend ailelerine karşı maliyetli karşılaştırma ve ileri dönem izleme.', ['tv-bb'],
         'Implemented reversion: Bollinger re-entry + RSI in weak trend. Band touch alone is not an entry; trends can persist.'),
    card('squeeze', 'Volatilite sıkışması', 'Volatilite', 'adaptive',
         'Düşük Bollinger genişliği ardından kanal kırılımı ve üst zaman teyidi kullanılır.',
         'Kapanmış OHLCV ve geçmiş bant genişliği.', 'Sıkışma, kırılım yönünü veya başarısını tek başına belirlemez.',
         'Maliyetli geçmiş ve ileri dönem karşılaştırması; haber sıçramalarında kayma izlenir.', ['tv-bb'],
         'Implemented squeeze: low Bollinger width then confirmed channel break. Compression does not predict direction.'),
    card('anchored_vwap', 'Olaydan başlayan VWAP', 'Hacim', 'research',
         'Önceden tanımlanan bir olaydan başlayarak hacim ağırlıklı fiyat bağlamı oluşturma adayı.',
         'OHLCV ve zaman damgalı, önceden seçilmiş başlangıç olayı.', 'Sonucu gördükten sonra başlangıç seçmek yanlılık yaratır. Mumdan hesaplanan değer işlem bazlı ortalamanın yaklaşımıdır.',
         'Başlangıç kuralı sabitlenmeli; bağımsız dönemde maliyetli karşılaştırılmalı. Henüz hesaplanmıyor.', ['tv-avwap'],
         'Research only: anchored VWAP needs a prespecified anchor. Post-hoc anchors leak outcomes; no AVWAP values supplied.'),
    card('volume_profile', 'Hacim profili ve değer alanı', 'Hacim', 'research',
         'Fiyat seviyelerindeki hacim yoğunluğu, POC ve değer alanı için araştırma adayı.',
         'Alt zaman mumları veya işlem bazlı fiyat/hacim geçmişi.', 'Günlük mum hacmini seviyelere yaymak gerçek işlem dağılımını vermez. Yükselen mum hacmi alıcı agresör hacmi değildir.',
         'Veri çözünürlüğü ve hesap kuralı belirtilmeli; tarihsel ve ileri dönem sınanmalı. Henüz hesaplanmıyor.', ['tv-profile'],
         'Research only: volume profile needs lower-timeframe/trade data. Daily OHLCV cannot reveal true volume-at-price or aggressor delta.'),
    card('open_interest', 'Açık pozisyon ve fiyat bağlamı', 'Türev', 'research',
         'Fiyat, hacim ve açık pozisyon değişimini birlikte inceleme adayı; yön için bağımsız kanıt gerekir.',
         'Borsa/ürün bazlı zaman eşleşmiş açık pozisyon serisi ve birim dönüşümü.', 'Açık pozisyon long/short yönünü tek başına göstermez; birimler ve rapor kalitesi değişebilir.',
         'Veri akışı ve kalite kontrolleri henüz bağlı değil; eksik ölçümden sinyal üretilmez.', ['bybit-oi', 'oi-quality'],
         'Research only: OI is not directional. Feed/units vary and may be unreliable; no historical OI series is supplied.'),
    card('funding_basis', 'Fonlama ve baz farkı', 'Türev', 'research',
         'Spot–vadeli farkı ile gerçekleşmiş fonlamanın maliyet sonrası birlikte incelenmesi.',
         'Eşzamanlı spot/vadeli kitaplar, gerçek fonlama geçmişi ve iki bacağın ücretleri.', 'Fonlama işareti değişebilir; baz farkı kapanmayabilir. Mevcut muhasebe fonlamayı izler, bu aday işlem kuralı değildir.',
         'İki bacağın gerçekleşme/teminat riski ve maliyetli bağımsız test gerekir.', ['bybit-funding'],
         'Research only: funding/basis needs aligned two-leg execution and historical funding. Accounting support is not a tested carry strategy.'),
    card('order_flow', 'İşlem akışı ve CVD', 'Mikroyapı', 'research',
         'Gerçekleşen işlemlerin agresör yönüyle hacim farkı ve kümülatif farkını inceleme adayı.',
         'Sıralı işlem kimliği, zaman, miktar ve agresör yönü; kopuk akışta yeniden eşleme.', 'Alış/satış kotasyonu veya mum rengi gerçek agresör işlem akışının yerine geçmez.',
         'Kalıcı işlem akışı toplayıcısı henüz yok; geçmiş mumlarla CVD üretilmez.', ['bybit-trades'],
         'Research only: CVD requires deduplicated aggressor trades. Quotes/candle color are not CVD; no trade history collector is connected.'),
    card('long_trend', '6–12 aylık trend bağlamı', 'Uzun dönem', 'research',
         'Günlük trend, oynaklık ve düşüş bağlamıyla kısa dönem kararlarının karşılaştırılması için aday.',
         'Gerçek 6/12 aylık mumlar ve ayrıca 200 mum hazırlık. Grafikte istenen geçmişin özeti bulunur.', 'Uzun dönem araştırmasının sonuçları kriptoya veya 15 dakikalık kurala doğrudan aktarılamaz.',
         'Grafik özeti betimseldir; otomatik seçici bu uzun arşiv üzerinde yeniden eğitilmiş sayılmaz.', ['aqr-trend'],
         'Research context: requested 6/12m history summaries describe price, not portfolio returns. Adaptive training still uses its separate recent window.'),
    card('walk_forward', 'İlerleyen dönem doğrulaması', 'Doğrulama', 'methodology',
         'Geçmişte eğitip sonraki dönemde ölçme; üst üste binen hedef süreleri için ayrım aralığı kullanma ilkesi.',
         'Zaman sıralı veriler, hedef gerçekleşme zamanı ve denenen parametre kaydı.', 'Rastgele bölme veya gelecekte kapanan etiketleri eğitime almak veri sızıntısı yaratır.',
         'Mevcut seçici kronolojik ayırır ve ileri dönem karşılaştırır; kapsamlı 6/12 aylık yürüyen test henüz yok.', ['sk-time'],
         'Validation: chronological train/test, purge overlapping outcome horizons. Never tune on held-out results; year-chart access is not a year backtest.'),
    card('calibration', 'Model skoru ve kalibrasyon', 'Doğrulama', 'methodology',
         'Model skorlarının gerçekleşme sıklıklarıyla bağımsız dönemde karşılaştırılması.',
         'Yeterli bağımsız etiket, kalibrasyon eğrisi ve uygun kayıp ölçümleri.', 'Skor 80/100 ifadesi kanıtlanmış %80 kazanma olasılığı değildir.',
         'Kalibrasyon raporu henüz uygulanmadı; mevcut skor kesin olasılık diye sunulmaz.', ['sk-calibration'],
         'Validation: model score is not calibrated win probability. Calibration needs disjoint fitting/evaluation and enough independent outcomes.'),
    card('multiple_testing', 'Çoklu deneme yanlılığı', 'Doğrulama', 'methodology',
         'Çok sayıda stratejiden en iyisini seçmenin tesadüfi iyi sonuç üretme etkisini hesaba katma ilkesi.',
         'Başarısızlar dahil tüm denemeler, örnek uzunluğu ve getiri dağılımı.', 'En iyi geçmiş sonucu seçmek kalıcı üstünlük kanıtı değildir.',
         'Deneyler kaydedilir ve ileri dönem sınanır; Deflated Sharpe hesabı henüz uygulanmadı.', ['deflated-sharpe'],
         'Validation: log all trials, not only winners. Selection across many tests overstates results; Deflated Sharpe is not implemented.'),
]


def library_snapshot():
    cards = [{k: copy.deepcopy(v) for k, v in c.items() if k != 'ai_brief'} for c in CARDS]
    return dict(version=VERSION, reviewed_at=REVIEWED_AT, cards=cards,
                sources=[dict(**s, reviewed_at=REVIEWED_AT) for s in SOURCES],
                update_policy='Bu sürümde kaynaklar elle gözden geçirildi. Kütüphane kendiliğinden internetten güncellenmez.',
                learning='Kaynak kartları analiz bağlamına eklenir; dil modelinin ağırlıkları yeniden eğitilmez.')


def research_context(now=None):
    """Rotate bounded context so the local model can review the whole catalog over time."""
    cycle = int((time.time() if now is None else now) // 21600)
    runnable = [c for c in CARDS if c['status'] == 'adaptive']
    candidates = [c for c in CARDS if c['status'] == 'research']
    validation = [c for c in CARDS if c['status'] == 'methodology']
    chosen = ([runnable[(cycle+i) % len(runnable)] for i in range(2)] +
              [candidates[(cycle*2+i) % len(candidates)] for i in range(2)] +
              [validation[cycle % len(validation)]])
    return dict(version=VERSION, reviewed_at=REVIEWED_AT,
                cards=[dict(id=c['id'], status=c['status'], note=c['ai_brief'], sources=c['source_ids']) for c in chosen],
                rule='Only adaptive methods may be in executable experiments. Other cards are research/validation knowledge, never fabricated measurements.')


def history_context(service, now=None):
    """Only already requested real history; never download a universe for an AI prompt."""
    if service is None:
        return []
    now = time.time() if now is None else now
    records = []
    for item in list(reversed(service.latest_summaries()))[:2]:
        if item.get('source') != 'PAPER' or now-item.get('observed', 0) > 86400:
            continue
        summary = item['summary']
        records.append(dict(symbol=item['symbol'], venue=item['venue'], market=item['market'],
            months=item['months'], interval=item['interval'], coverage=item['coverage']['status'],
            observed=item['observed'], as_of=summary.get('as_of'), return_pct=summary.get('return_pct'),
            max_drawdown_pct=summary.get('max_drawdown_pct'), trend=summary.get('trend'),
            limitations=summary.get('limitations', [])[:2]))
    return records
