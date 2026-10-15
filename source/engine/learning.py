"""Local chronological learning observer. It cannot submit orders or change risk."""
from __future__ import annotations

import time
import hashlib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, brier_score_loss
from engine.research import features

HORIZON=4


def train_observer(rows,strategy,market):
    df=features(rows,strategy)
    side=np.where(df.fast>df.slow,1,-1)
    # Fixed transforms, no scaler fitted on a future evaluation period.
    x=np.column_stack([df.momentum*100,df.volatility*100,
                       np.log1p(df.volume_ratio.clip(0,20)),df.trend_strength*100,side])
    valid=np.isfinite(df.fast)&np.isfinite(df.slow)&np.isfinite(x).all(axis=1)
    cost=.0026 if market=='spot' else .0018
    future=(df.close.shift(-HORIZON)/df.close-1).to_numpy()*side
    resolved=valid&np.isfinite(future)
    indices=np.flatnonzero(resolved)
    if len(indices)<160: return dict(status='warming',samples=len(indices),note='Gerçek kapanmış mum birikiyor; en az 160 etiket gerekli.')
    split=int(len(indices)*.7)
    train=indices[:max(0,split-HORIZON)]
    holdout=indices[split:]
    y=(future>cost).astype(int)
    if len(np.unique(y[train]))<2 or len(np.unique(y[holdout]))<2:
        return dict(status='warming',samples=len(indices),note='Öğrenme için iki sonuç sınıfında da örnek gerekiyor.')
    model=LogisticRegression(C=.3,max_iter=500,random_state=73).fit(x[train],y[train])
    predicted=model.predict_proba(x[holdout])[:,1]
    score=float(model.predict_proba(x[-1:])[0,1])
    step=900 if strategy=='intraday' else 14400
    version=hashlib.sha256(model.coef_.tobytes()+model.intercept_.tobytes()).hexdigest()[:12]
    return dict(status='observing',samples=len(train),evaluation_samples=len(holdout),
                balanced_accuracy=float(balanced_accuracy_score(y[holdout],predicted>=.5)),
                brier=float(brier_score_loss(y[holdout],predicted)),score=score,
                positive_rate=float(y[holdout].mean()),version=version,
                trained_at=time.time(),training_end=int(df.iloc[train[-1]+HORIZON].time)+step,
                evaluation_start=int(df.iloc[holdout[0]].time)+step,
                candle_time=int(df.iloc[-1].time),horizon_seconds=HORIZON*step,
                coefficients=model.coef_[0].tolist(),intercept=float(model.intercept_[0]),
                note='Yerel gözlem modeli: 4 mum sonraki yön getirisinin tahmini maliyeti aşmasını öğrenir. Emir ve risk yetkisi yok; skor kalibre edilmiş olasılık değildir.')
