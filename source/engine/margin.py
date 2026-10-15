"""Explicit conservative isolated USDT paper model, not an exchange liquidation quote."""
from __future__ import annotations


def isolated_adjustment(initial_margin, funding, gross, exit_fee, reason):
    """Cash correction for this slice's isolated collateral, including late funding."""
    limit = -(initial_margin + funding) - (gross - exit_fee)
    return limit if reason == 'Tahmini tasfiye' else max(0., limit)


def margin_status(position, mark):
    if position['market']!='futures': return {}
    qty, entry = position['quantity'], position['entry']
    sign=1 if position['side']=='long' else -1
    collateral=position.get('initial_margin',qty*entry/position['leverage'])
    # Funding is assigned to this position. No automatic wallet margin top-up.
    collateral+=position.get('funding',0)
    rate=position.get('maintenance_rate',0.01)
    fee=position['fee_rate']
    equity=collateral+sign*qty*(mark-entry)
    maintenance=qty*mark*(rate+fee)
    # Solve collateral + side*q*(P-entry) = q*P*(MMR+exit fee).
    denominator=qty*(sign-rate-fee)
    liq=max(0,(sign*qty*entry-collateral)/denominator) if denominator else 0
    return dict(initial_margin=position.get('initial_margin',qty*entry/position['leverage']),
                margin_equity=equity,maintenance_margin=maintenance,
                margin_ratio=maintenance/max(equity,1e-9)*100,
                liquidation_price=liq,liquidation_estimated=True,
                liquidation_buffer=max(0,sign*(mark-liq)/mark*100),
                liquidatable=equity<=maintenance,mark_price=mark,
                maintenance_rate=rate)
