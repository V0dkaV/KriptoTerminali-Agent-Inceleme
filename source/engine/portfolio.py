"""Explicit paper risk profiles and conservative concentration budgets."""
import math

DEFAULT_SYMBOLS = [s+'USDT' for s in (
    'BTC','ETH','SOL','BNB','XRP','DOGE','ADA','AVAX','LINK','DOT','LTC','BCH',
    'TRX','SUI','ICP','NEAR','APT','ARB','OP','ATOM','UNI','AAVE','FIL','INJ')]

PROFILES = {
    'safe': dict(name='Korumacı',trade_risk=.25,total_risk=1.,daily_loss=1.,drawdown=6.,leverage=2,max_positions=4,symbol_risk=.5,correlated_risk=.75),
    'balanced': dict(name='Dengeli',trade_risk=.5,total_risk=2.,daily_loss=2.,drawdown=10.,leverage=3,max_positions=8,symbol_risk=1.,correlated_risk=1.25),
    'aggressive': dict(name='Atak',trade_risk=.75,total_risk=4.,daily_loss=3.,drawdown=15.,leverage=5,max_positions=12,symbol_risk=1.5,correlated_risk=2.5),
    'mixed': dict(name='Otomatik karma',trade_risk=.75,total_risk=2.,daily_loss=2.,drawdown=10.,leverage=3,max_positions=8,symbol_risk=1.,correlated_risk=1.25),
}


def style(settings, signal, actual):
    """A model's confidence alone never earns the largest mixed risk allocation."""
    if settings.risk_profile != 'mixed':
        return settings.risk_profile, 1.
    recent = [t for t in actual if t.get('method')==signal.method][-10:]
    if len(recent) >= 5 and sum(t.get('r',0) for t in recent)>0 and (signal.model_score or 0)>=.65 and signal.risk_multiplier>=1:
        return 'aggressive', 1.
    if signal.risk_multiplier < 1 or (signal.model_score or 0)<.5:
        return 'safe', 1/3
    return 'balanced', 2/3


def returns(rows):
    return {b['time']:math.log(b['close']/a['close']) for a,b in zip(rows,rows[1:])
            if b['time']-a['time']==900 and a['close']>0 and b['close']>0}


def correlation(a,b):
    keys=sorted(set(a)&set(b))[-192:]
    if len(keys)<48:return None
    x=[a[k] for k in keys];y=[b[k] for k in keys]
    mx=sum(x)/len(x);my=sum(y)/len(y)
    num=sum((v-mx)*(w-my) for v,w in zip(x,y))
    den=(sum((v-mx)**2 for v in x)*sum((w-my)**2 for w in y))**.5
    return num/den if den>1e-15 else None


def concentration(settings, signal, positions, equity, histories, aliases=None):
    """Across venues/products. Unknown correlation consumes a shared budget.

    Absolute correlation is conservative for opposite-direction pairs too: no
    unverified hedge credit or directional netting releases risk reservations.
    """
    aliases=aliases or {}
    canonical=lambda symbol:aliases.get(symbol,symbol)
    own=sum(p['planned_risk'] for p in positions if canonical(p['symbol'])==canonical(signal.symbol))
    group=0.;unknown=0
    base=histories.get(signal.symbol,{})
    for p in positions:
        if canonical(p['symbol'])==canonical(signal.symbol): group+=p['planned_risk'];continue
        corr=correlation(base,histories.get(p['symbol'],{}))
        if corr is None:unknown+=1
        if corr is None or abs(corr)>=.85:group+=p['planned_risk']
    remaining=min(settings.symbol_risk-own/max(equity,1)*100,
                  settings.correlated_risk-group/max(equity,1)*100)
    return max(0,remaining),dict(symbol_used=own,correlated_used=group,unknown=unknown)
