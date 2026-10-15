# Farklı agentlar için ayrı inceleme görevleri

Her agenta aynı ZIP'i verebilirsin. Ortak çıktı biçimi AGENTA-VERILECEK-ISTEK.md içindedir. Aşağıdaki görevlerden birini ek mesaj olarak gönder.

## Agent 1 — Muhasebe, risk ve gerçekleşme

Öncelikle core.py, models.py, margin.py, exits.py, portfolio.py, operations.py, store.py ve state_transaction.py dosyalarını incele. Ücret/fonlama işaretleri, kısmi gerçekleşme, isolated tasfiye ve özsermaye, geç kayıtlar, eşzamanlı bütçe ve görev/hesap risk sınırları için hata ara. Muhasebe tutarlılığını örnek olayla yeniden üret. Model doğruluğu veya UI tasarımı yerine maddi hesap hatalarına odaklan.

## Agent 2 — Strateji, geçmiş test ve öğrenme

Öncelikle research.py, adaptive.py, training.py, agents.py, knowledge.py ve history.py dosyalarını incele. Gelecek veri sızıntısı, kapanmış mum zamanlaması, giriş/çıkış varsayımı, etiket/maliyet, kronolojik ayrım, örnek yeterliliği, terfi/geri alma ve model çalışma/çökme davranışını kontrol et. Eğitim sayısını başarı kanıtı kabul etme. Uygulanan yöntemle belgelerin uyumunu denetle.

## Agent 3 — Güvenilirlik, güvenlik ve emir tekrarı

Öncelikle main.py, server.py, electron/main.cjs/preload.cjs, chat.py, grounding.py, store.py ve operations.py dosyalarını incele. Süreç kaybı, yeniden açılış, ağ gecikmesi, idempotency/makbuz, onay kapsamı, durdurma sırasında bekleyen iş, IPC ve sırların korunması için somut açık ara. Gerçek kullanıcı hesabını bağlama; ayrı test ortamında yeniden üret.

## Agent 4 — Geniş piyasa taraması, performans ve UI

Öncelikle universe.py, market.py, stream.py, scanner_cache.py, core.py tarama akışları ile UniversePanel/ExecutionStatus/AdaptiveLearning/OperationsPanel dosyalarını incele. Binlerce sembolde adil tarama, doğru borsa-ürün eşleşmesi, eski/eksik veri, açık pozisyon önceliği, kuyruk/bellek/disk/API sınırları ve UI'da gerçek durumun gösterilmesini kontrol et. 1.205 coinlik UI fikstürü gerçek piyasa kanıtı değildir. Taşma ve sayfalama hatalarını örnekle.

## Bulguları birleştirirken

Aynı kök nedene ait bulguları tekleştir; farklı etkileri kanıtlarıyla ekle. Çelişen bulguları aynı sürüm üzerinde yeniden üret. Uygulama hatası, bağımlılık/ortam sorunu ve yeni özellik önerisini ayır. Üç öncelikli düzeltmeyi gerekçesi ve doğrulama adımıyla sun.
