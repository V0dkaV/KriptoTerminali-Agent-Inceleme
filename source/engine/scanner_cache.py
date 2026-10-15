"""Keep broad-scan candle history on disk and bound its in-memory working set."""
import re
import uuid
from pathlib import Path


def cache_file(engine, key):
    _, venue, symbol, interval, market = key
    if not re.fullmatch(r'[A-Z0-9]{1,16}USDT', symbol):
        raise ValueError('Invalid scanner symbol')
    return Path(engine.store.path) / 'history' / 'scanner' / f'{venue}-{market}-{symbol}-{interval}.parquet'


def load(engine, key):
    import pandas as pd
    file = cache_file(engine, key)
    if not file.exists():return None
    try:
        rows = pd.read_parquet(file).to_dict('records')
        if rows:engine.history_bootstrapped.add(key)
        return (0, rows) if rows else None
    except Exception:return None


def save(engine, key, rows):
    import pandas as pd
    file = cache_file(engine, key)
    temporary = file.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(temporary, index=False)
        temporary.replace(file)
    finally:temporary.unlink(missing_ok=True)


def trim(engine, keep=192):
    if len(engine.cache) <= keep:return
    for key, _ in sorted(list(engine.cache.items()), key=lambda item: item[1][0])[:max(0, len(engine.cache)-keep)]:
        engine.cache.pop(key, None)
        engine.history_bootstrapped.discard(key)
