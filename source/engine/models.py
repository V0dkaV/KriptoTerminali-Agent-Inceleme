from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from engine.portfolio import DEFAULT_SYMBOLS


class RiskSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    risk_profile: Literal['safe','balanced','aggressive','mixed','custom'] = 'mixed'
    trade_risk: float = Field(default=0.75, gt=0, le=0.75)
    total_risk: float = Field(default=2.0, gt=0, le=4.0)
    daily_loss: float = Field(default=2.0, gt=0, le=3.0)
    drawdown: float = Field(default=10.0, gt=0, le=15.0)
    leverage: int = Field(default=3, ge=1, le=5)
    max_positions: int = Field(default=8, ge=1, le=12)
    exit_policy: Literal['fixed','adaptive'] = 'adaptive'
    symbol_risk: float = Field(default=1.,gt=0,le=1.5)
    correlated_risk: float = Field(default=1.25,gt=0,le=2.5)
    paper_balance: float = Field(default=10000, ge=100, le=10000000)
    telegram_enabled: bool = False
    local_ai_enabled: bool = True
    local_ai_news_controls: bool = True
    local_ai_research: bool = True
    telegram_chat_id: str = ''
    ai_enabled: bool = False
    ai_model: str = ''
    ai_daily_budget: float = Field(default=0, ge=0, le=100)
    ai_monthly_budget: float = Field(default=0, ge=0, le=1000)
    ai_input_price: float = Field(default=0, ge=0, le=1000)
    ai_output_price: float = Field(default=0, ge=0, le=5000)
    auto_universe: bool = True
    allowlist: list[str] = Field(default_factory=lambda: DEFAULT_SYMBOLS.copy(), min_length=1, max_length=1500)

    @field_validator('allowlist')
    @classmethod
    def symbols(cls,values):
        import re
        if any(not re.fullmatch(r'[A-Z0-9]{1,16}USDT',v) for v in values):raise ValueError('Geçersiz USDT paritesi')
        return list(dict.fromkeys(values))


class Signal(BaseModel):
    strategy: str
    symbol: str
    venue: str
    market: Literal['spot', 'futures']
    side: Literal['long', 'short']
    price: float = Field(gt=0)
    stop: float = Field(gt=0)
    target: float = Field(gt=0)
    reason: str
    candle_time: int
    method: Literal['breakout','momentum','pullback','reversion','squeeze','manual'] = 'breakout'
    model_version: str = ''
    model_score: float | None = Field(default=None,ge=0,le=1)
    risk_multiplier: float = Field(default=1,ge=.25,le=1)
    features: list[float] = Field(default_factory=list,max_length=19)


class RiskDecision(BaseModel):
    accepted: bool
    reason: str
    quantity: float = 0
    planned_risk: float = 0


class OrderIntent(BaseModel):
    client_id: str
    group_id: str | None = None
    signal: Signal
    quantity: float
    status: str = 'pending'


class Fill(BaseModel):
    execution_id: str
    client_id: str
    quantity: float
    price: float
    fee: float
    fee_asset: str = 'USDT'


class NewsEvent(BaseModel):
    id: str
    title: str
    source: str
    url: str
    published_at: str
    first_seen_at: str
    severity: str = 'info'
    verification: str = 'official'
    assets: list[str] = Field(default_factory=list)
    action: str = 'İzleniyor; yön tahmini üretilmedi.'
    demo: bool = False


def net_pnl(gross: float, fees: float, funding: float = 0.0) -> float:
    """Funding is signed cash flow; execution prices already include slippage."""
    return float(Decimal(str(gross)) - Decimal(str(fees)) + Decimal(str(funding)))


def position_size(equity: float, entry: float, stop: float, rate: float,
                  fee_rate: float, available: float, leverage: int = 1,
                  step: str = '0.00001') -> tuple[float, float]:
    d = lambda v: Decimal(str(v))
    distance = abs(d(entry) - d(stop)) + d(entry) * d(fee_rate) * 2
    if equity <= 0 or available <= 0 or entry <= 0 or distance <= 0:
        return 0.0, 0.0
    budget = d(equity) * d(rate) / 100
    # Entry commission is payable in addition to initial margin.
    capacity = d(available) / (d(entry) / d(leverage) + d(entry) * d(fee_rate))
    qty = min(budget / distance, capacity)
    quantum = d(step)
    qty = (qty / quantum).to_integral_value(rounding=ROUND_DOWN) * quantum
    return float(qty), float(qty * distance)


CATALOG = [
    dict(id='intraday', name='Öğrenen gün içi seçici', family='Beş yöntem ailesi', status='paper', timeframe='15 dakika',
         description='Sanal modda kırılım, momentum, geri çekilme, ortalamaya dönüş ve sıkışma öğrenilen sonuçlarla seçilir. ATR(14) × 2 stop, 2R hedef, 16 mum süre sınırı. Demo/laboratuvar temel kırılım şablonunu kullanır.',
         data='15dk ve 1s kapanmış mumlar; en az 200 saat hazırlık.', risk='Yatay piyasada art arda yanlış kırılım. Ücret ve kayma riski.'),
    dict(id='swing', name='Öğrenen swing seçici', family='Beş yöntem ailesi', status='paper', timeframe='4 saat',
         description='Sanal modda beş yöntem ailesi ve günlük trend bağlamı birlikte öğrenilir. ATR(14) × 3 stop, 2R hedef, 42 mum süre sınırı. Demo/laboratuvar temel kırılım şablonunu kullanır.',
         data='4s ve günlük kapanmış mumlar; en az 200 günlük hazırlık.', risk='Gecelik hareketler, uzun süreli fonlama ve fiyat boşlukları.'),
    dict(id='momentum', name='Momentum', family='Momentum ve kırılım', status='adaptive', timeframe='15dk / 4s',
         description='EMA trendi, MACD histogram sıfır kesişimi ve RSI yön teyidi. Öğrenen seçici tarafından karşılaştırılır.',
         data='Kapanmış OHLCV, hacim ve spread geçmişi.', risk='Gecikmiş giriş ve ani ters dönüş. Sanal hesapta seçici yönetir.'),
    dict(id='reversion', name='Ortalamaya dönüş', family='Ortalamaya dönüş', status='adaptive', timeframe='15dk / 4s',
         description='Sınırlı trend gücünde Bollinger z-skorunun ±2 bandına geri dönmesi ve RSI koşulu. Öğrenen seçici yönetir.',
         data='OHLCV ve rejim etiketleri.', risk='Güçlü trendde ortalamaya dönüş gerçekleşmeyebilir.'),
    dict(id='grid', name='Grid / planlı alım', family='Grid ve planlı alım', status='research', timeframe='Aralık',
         description='Sabit toplam bütçe, belirlenmiş fiyat bandı ve envanter tavanı.',
         data='Emir defteri geçmişi, işlem adımları ve ücretler.', risk='Tek taraflı birikim. Martingale ve sınırsız ek alım desteklenmez.'),
    dict(id='statistical', name='İstatistiksel çiftler', family='İstatistiksel yöntemler', status='research', timeframe='1s–4s',
         description='Göreli fiyat ilişkisi, durağanlık ve ilişki bozulması testleri.',
         data='Zamanı eşleşmiş fiyatlar, fonlama ve maliyetler.', risk='İlişkinin kalıcı kırılması ve eşleşmeyen gerçekleşmeler.'),
    dict(id='spot_perp', name='Spot–vadeli denge', family='Spot-vadeli', status='simulation', timeframe='Olay bazlı',
         description='Spot long ve vadeli short için fiyat farkı, fonlama ve kapanış maliyetinin birlikte değerlendirilmesi.',
         data='İki emir defteri, fonlama, hesap komisyonları ve teminat.', risk='Fonlama değişimi, baz farkı, tasfiye ve bacak riski.'),
    dict(id='cross_spot', name='Borsalar arası arbitraj', family='Borsalar arası arbitraj', status='simulation', timeframe='Olay bazlı',
         description='Binance ve Bybit arasında önceden ayrılmış coin/USDT envanteriyle iki taraflı işlem.',
         data='Eşzamanlı emir defterleri ve önceden mevcut spot envanteri.', risk='Eski fiyat, kısmi gerçekleşme ve envanter dengesizliği.'),
    dict(id='market_making', name='Piyasa yapıcılığı', family='Piyasa yapıcılığı', status='research', timeframe='Emir defteri',
         description='Çift taraflı kotasyon, envanter dengesi ve gerçekleşme olasılığı araştırması.',
         data='Sıralı emir defteri, işlem akışı ve gecikme ölçümleri.', risk='Ters seçim ve envanter riski. Mum testi yeterli değildir.')
]
CATALOG.extend([
    dict(id='pullback',name='Trend içi geri çekilme',family='Trend takibi',status='adaptive',timeframe='15dk / 4s',
         description='Üst zaman trendiyle aynı yönde EMA20 üzerine/altına yeniden geçiş.',data='Kapanmış mumlar, üst zaman EMA50/200.',
         risk='Trendin bozulması ve tekrarlayan yanlış giriş. Seçici öğrenilen maliyetli sonuçlarla sınırlar.'),
    dict(id='squeeze',name='Sıkışma kırılımı',family='Volatilite ve kırılım',status='adaptive',timeframe='15dk / 4s',
         description='Düşük Bollinger genişliği sonrası 10 mum kanal kırılımı ve trend teyidi.',data='Kapanmış mumlar ve oynaklık dağılımı.',
         risk='Sahte kırılım ve spread genişlemesi. Öğrenen seçicinin sanal risk sınırları uygulanır.')
])


class GroupMachine:
    """Execution IDs are idempotent. Unknown orders retain their reservations."""
    def __init__(self, group_id: str, quantity: float):
        self.id = group_id
        self.quantity = quantity
        self.legs = {name: {'filled': 0.0, 'status': 'reserved'} for name in ('buy', 'sell')}
        self.executions: set[str] = set()

    def fill(self, leg: str, execution_id: str, qty: float):
        if execution_id in self.executions:
            return
        if leg not in self.legs or qty <= 0 or qty + self.legs[leg]['filled'] > self.quantity + 1e-9:
            raise ValueError('Geçersiz gerçekleşme miktarı')
        self.executions.add(execution_id)
        item = self.legs[leg]
        item['filled'] += qty
        item['status'] = 'filled' if abs(item['filled'] - self.quantity) < 1e-9 else 'partial'

    def unknown(self, leg: str):
        self.legs[leg]['status'] = 'unknown'

    def cancel(self, leg: str):
        if self.legs[leg]['status'] != 'filled':
            self.legs[leg]['status'] = 'cancelled'

    @property
    def state(self):
        if any(v['status'] == 'unknown' for v in self.legs.values()):
            return 'reconciling'
        if all(v['status'] == 'filled' for v in self.legs.values()):
            return 'hedged'
        if abs(self.legs['buy']['filled'] - self.legs['sell']['filled']) > 1e-9:
            return 'exposed'
        return 'reserved'

    @property
    def can_release(self):
        return all(v['status'] in ('filled', 'cancelled') for v in self.legs.values())
