"""Conservative output boundary for the local model's qualitative conversation.

Account facts, sizing and executable plans are rendered by deterministic services.
Matching a number from input would not prove its meaning, so conversation does not
reuse financial numbers at all. This is an output filter, not a truth guarantee.
"""
from __future__ import annotations

import re
import unicodedata


POLICY = 'qualitative-v1'
BLOCKED_ANSWER = (
    'Yerel modelin yanıtı doğrulanamayan sayısal bir iddia veya işlem önerisi '
    'içerdiği için gösterilmedi. Güncel bakiye, fiyat ve risk değerlerini hesap '
    'kayıtlarından; işlem kapsamını ve maliyetini onay kartından kontrol edebilirsin. '
    'İstersen bir yöntemin nasıl çalıştığını nitel olarak açıklayabilirim.'
)


def _normalized(value: str) -> str:
    value = value.translate(str.maketrans({'ı': 'i', 'İ': 'I'})).lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', value)
                   if not unicodedata.combining(c))


def conversation_grounding(answer: str, knowledge_ids=(), *, facts_at=None) -> dict:
    """Report only whether free prose respects the bounded qualitative policy.

    Sources are permitted as exact identifiers, never interpreted as validation of
    surrounding prose. No amount, percentage or probability is blessed by matching
    a value in the prompt. Unicode decimal digits are included in the rejection.
    """
    prose = answer
    for source_id in sorted(set(knowledge_ids), key=len, reverse=True):
        prose = re.sub(r'(?<!\w)' + re.escape(source_id) + r'(?!\w)', '', prose)
    # Product/model identities contain digits but make no financial claim.
    prose = re.sub(r'(?<!\w)Qwen\s*3(?:\s*[- ]?\s*4\s*B)?(?:\s+Q4_K_M)?(?!\w)',
                   '', prose, flags=re.IGNORECASE)
    text = _normalized(prose)
    reasons = []
    if any(c.isnumeric() for c in prose):
        reasons.append('numeric_claim')
    # Written numbers and allocations can bypass a digits-only check. "Bir" as an
    # article remains useful ("bir yöntem"); it is checked only with financial units.
    number = (r'(?:bir|iki|uc|dort|bes|alti|yedi|sekiz|dokuz|on|yirmi|otuz|kirk|'
              r'elli|altmis|yetmis|seksen|doksan|yuz|bin|milyon|one|two|three|four|'
              r'five|six|seven|eight|nine|ten|twenty|fifty|hundred|thousand)')
    unit = (r'(?:dolar(?:lik|la)?|usdt|usd|tl|lira(?:lik)?|euro|kat|kati|'
            r'kaldirac|percent|dollars?|times|leverage)')
    if (re.search(r'\b(?:yuzde|binde|percent|percentage)\b', text)
            or re.search(r'\b' + number + r'(?:\s+' + number + r')*\s+' + unit + r'\b', text)
            or re.search(r'\b(?:paranin|bakiyenin|butcenin|sermayenin|hesabinin|riskin|riskini)\s+'
                         r'(?:tamami|hepsi|yariya|yarisi|yarisini|ceyregi|ceyregini|'
                         r'onda bir\w*|yuzde bir\w*)\b', text)
            or re.search(r'\b(?:half|quarter|all)\s+(?:of\s+)?(?:your\s+)?'
                         r'(?:money|balance|capital|funds|budget)\b', text)
            or re.search(r'\b(?:tum|butun)\s+(?:parayla|bakiyeyle|sermayeyle|butceyle)\b', text)):
        reasons.append('quantified_financial_claim')
    if re.search(r'\b(?:kesin|garantili|risksiz)\s+(?:kar|kazanc|getiri|profit|return)\b|'
                 r'\b(?:guaranteed|risk[- ]?free)\s+(?:profit|return)\b|'
                 r'\b(?:kesinlikle|mutlaka)\s+(?:kazan|kar et)|'
                 r'\b(?:kar|kazanc)\s+garantisi\s+(?:var|veriyorum|veririm)\b', text):
        reasons.append('return_guarantee')
    # Concrete investment or risk-setting directives belong to reviewed plans.
    if re.search(r'\b(?:almalisin|satmalisin|almaliyiz|satmaliyiz|long ac|short ac|'
                 r'longa gir|shorta gir|pozisyon acmalisin|kaldiraci artir|riski artir|'
                 r'you should buy|you should sell|buy now|sell now)\b', text):
        reasons.append('investment_directive')
    elif (re.search(r'\b(?:almani|satmani|acmani)\s+(?:oneririm|tavsiye ederim)\b', text)
          or re.search(r'\b(?:kaldiraci|kaldiracini|riski|riskini)\s+'
                       r'(?:artir|arttir|yukselt)(?:malisin|mani oneririm|meni oneririm)?\b', text)
          or re.search(r'\b(?:BTC|ETH|SOL|BNB|XRP|DOGE|[A-Z]{2,12}USDT)\s+'
                       r'(?:al|sat|satın al)\b', prose)):
        reasons.append('investment_directive')
    if re.search(r'\b(?:actim|kapattim|durdurdum|baslattim|degistirdim|artirdim|'
                 r'azalttim|emri gonderdim|islemi yaptim|i placed|i executed)\b', text):
        reasons.append('action_claim')
    return dict(status='blocked' if reasons else 'qualitative', policy=POLICY,
                reasons=reasons, facts_at=facts_at)


def grounded_conversation(answer: str, knowledge_ids=(), *, facts_at=None) -> dict:
    grounding = conversation_grounding(answer, knowledge_ids, facts_at=facts_at)
    blocked = grounding['status'] == 'blocked'
    return dict(answer=BLOCKED_ANSWER if blocked else answer,
                knowledge_ids=[] if blocked else list(knowledge_ids), grounding=grounding)
