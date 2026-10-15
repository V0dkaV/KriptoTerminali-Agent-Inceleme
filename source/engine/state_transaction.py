"""Rollback the in-memory configuration together with its SQLite transaction."""
from contextlib import contextmanager
import copy


@contextmanager
def state_transaction(engine):
    # Caller owns engine.lock. Orders have their own narrow transactions; this
    # envelope covers account/mode/configuration changes spanning multiple states.
    before={key:copy.deepcopy(getattr(engine,key)) for key in ('states','mode','settings','enabled','news')}
    try:
        with engine.store.atomic():
            yield
    except BaseException:
        for key,value in before.items():setattr(engine,key,value)
        raise
