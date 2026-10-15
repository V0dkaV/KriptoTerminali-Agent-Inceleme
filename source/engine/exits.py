"""Deterministic paper execution and immutable per-position exit rules.

These rules are hypotheses, not optimized results. They cannot issue real orders.
"""
from __future__ import annotations

from engine.margin import isolated_adjustment

SLIPPAGE = .0003
MIN_NOTIONAL = 10.


def executable_price(position, quote):
    side = 1 if position['side'] == 'long' else -1
    return quote['bid' if side == 1 else 'ask'] * (1 - side * SLIPPAGE)


def initialize(position, policy):
    position.update(exit_policy=policy, original_quantity=position['quantity'],
                    initial_planned_risk=position['planned_risk'],
                    initial_stop=position['stop'], initial_target=position['target'],
                    initial_stop_distance=abs(position['entry'] - position['stop']),
                    original_entry_fee=position['entry_fee'],
                    original_initial_margin=position.get('initial_margin', 0.),
                    partial_fills=[], partial_realized=0., remaining_risk=position['planned_risk'],
                    exit_status='İlk stop ve hedef izleniyor', breakeven_active=False,
                    trailing_active=False, favorable_price=position['entry'])


def remaining_net(position, price):
    side = 1 if position['side'] == 'long' else -1
    gross=(price-position['entry'])*position['quantity']*side
    exit_fee=price*position['quantity']*position['fee_rate']
    funding=position.get('funding',0)
    adjustment=0.
    if position['market']=='futures':
        margin=position.get('initial_margin',position['entry']*position['quantity']/position['leverage'])
        adjustment=isolated_adjustment(margin,funding,gross,exit_fee,'')
    return gross-position['entry_fee']-exit_fee+funding+adjustment


def adaptive_action(position, price):
    """Return one action. Call only after all full-position protective checks."""
    if position.get('exit_policy', 'fixed') != 'adaptive':
        return None
    side = 1 if position['side'] == 'long' else -1
    distance = position['initial_stop_distance']
    if not position.get('partial_fills'):
        if side*(price-position['entry']) < distance or remaining_net(position, price) <= 0:
            return None
        half = position['quantity']*.5
        if min(half*price, half*position['entry']) < MIN_NOTIONAL:
            position['exit_status'] = 'Kısmi çıkış minimum 10 USDT nedeniyle bekliyor; tam hedef korunuyor'
            return None
        return 'partial'
    return 'trail'


def tighten_stop(position, price):
    """Price and stop are executable-side levels; no second slippage deduction."""
    side = 1 if position['side'] == 'long' else -1
    previous = position['stop']
    # Solve side*q*(P-entry)-entry_fee-P*q*fee+signed_funding=0.
    breakeven = (side*position['entry'] +
                 (position['entry_fee']-position.get('funding', 0))/position['quantity'])/(side-position['fee_rate'])
    high = max(position.get('favorable_price', price), price) if side == 1 else min(position.get('favorable_price', price), price)
    trail = high-side*position['initial_stop_distance']
    candidate = max(previous, breakeven, trail) if side == 1 else min(previous, breakeven, trail)
    # A newly tightened trigger above the available fill is handled next tick,
    # never recorded as if the impossible stop price had actually executed.
    position.update(stop=max(.000000000001, candidate), favorable_price=high,
                    breakeven_active=True, trailing_active=True,
                    exit_status='Kısmi kâr alındı · maliyetli başabaş ve takip stopu etkin')
    return candidate != previous


def quantity_at(position, timestamp):
    original = position.get('original_quantity', position['quantity'])
    return max(0., original-sum(f['quantity'] for f in position.get('partial_fills', [])
                               if f['closed_at'] < timestamp))
