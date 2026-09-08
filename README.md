# FEIN Pinterest Digest — Kurulum

Bu sistem, Pinterest board'larından pinleri çeker, FEIN içerik pillar'larına göre
gruplar (Product, Process, Space, People, Community, Brand, Culture/Lifestyle,
Educational) ve sana günlük/haftalık bir e-posta özeti gönderir.
Hiçbir veri diske/veritabanına kaydedilmez — her çalıştığında taze çeker (Pinterest'in
veri saklama kuralına uygun).

## 1. Pinterest tarafı

1. https://developers.pinterest.com adresinden geliştirici hesabı aç (zaten açtığını yazdın).
2. Bir app oluştur, **Trial access** ile başla — bu aşamada okuma (`boards:read`,
   `pins:read`) yeterli, yazma iznine gerek yok.
3. OAuth flow'unu tamamlayıp bir **access token** al. Trial token'lar kısa ömürlü
   olabilir; Standard access'e geçmek istersen Pinterest'in video-kayıtlı OAuth
   inceleme sürecinden geçmen gerekiyor (kendi hesabın için ise Trial genelde yeterli).
4. Takip etmek istediğin board'ların ID'lerini not al (API'den veya board URL'sinden).

## 2. Repo'yu hazırla

1. Bu klasörü bir GitHub repo'suna yükle (private repo önerilir).
2. Repo → Settings → Secrets and variables → Actions → **New repository secret**
   ile şunları ekle:

   | Secret adı | Açıklama |
   |---|---|
   | `PINTEREST_ACCESS_TOKEN` | Pinterest OAuth access token |
   | `PINTEREST_BOARD_IDS` | Virgülle ayrılmış board ID'leri (boş bırakılırsa tüm boardlar) |
   | `SMTP_HOST` | Örn. `smtp.gmail.com` |
   | `SMTP_PORT` | Örn. `587` |
   | `SMTP_USER` | Gönderen e-posta adresi |
   | `SMTP_PASSWORD` | Uygulama şifresi (Gmail kullanıyorsan "App Password" oluştur, normal şifre çalışmaz) |
   | `DIGEST_TO_EMAIL` | Özetin gideceği e-posta |
   | `DIGEST_FROM_EMAIL` | Genelde `SMTP_USER` ile aynı |

## 3. Zamanlama

`.github/workflows/pinterest-digest.yml` içinde:
- Her gün 07:00 UTC → günlük özet
- Her Pazartesi 07:00 UTC → haftalık özet (aynı saatte çakışan cron, script içinde
  gün kontrolüyle "weekly" moduna geçiyor)

UTC saatlerini kendi saat dilimine göre ayarlamak istersen `cron` satırlarındaki
saatleri değiştir (Türkiye UTC+3, yani TR saatiyle 10:00 için `0 7 * * *` doğru).

## 4. Test et

Repo'ya push ettikten sonra GitHub → Actions → "FEIN Pinterest Digest" →
**Run workflow** ile manuel tetikleyip e-postanın gelip gelmediğini kontrol et.

## Notlar / sınırlamalar

- Pillar sınıflandırması şu an basit anahtar kelime eşleştirmesiyle yapılıyor
  (`pinterest_digest.py` içindeki `PILLAR_KEYWORDS`). Pin başlık/açıklamaları
  İngilizce değilse veya boşsa çoğu pin "Culture / Lifestyle" varsayılanına düşer —
  gerekirse Türkçe anahtar kelimeler eklenmeli.
- Gmail SMTP günlük gönderim limitine takılırsa (çok düşük ihtimal, tek alıcıya
  günde/haftada 1 mail), alternatif olarak Resend/SendGrid gibi bir e-posta API'si
  entegre edilebilir.
- Trial-tier Pinterest token'lar süresi dolduğunda yenilenmesi gerekebilir —
  Standard access'e geçersen refresh token akışı otomatik olur, script'e
  refresh mantığı eklenmesi gerekir.
