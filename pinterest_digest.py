"""
FEIN Coffee Co. — Pinterest Reference Digest
Pinterest API v5'ten pinleri çeker, FEIN içerik pillar'larına göre gruplar,
bir HTML e-posta özeti hazırlayıp gönderir.

Gereken ortam değişkenleri (GitHub Actions Secrets üzerinden set edilir):
  PINTEREST_ACCESS_TOKEN   -> Pinterest API v5 OAuth access token
  PINTEREST_BOARD_IDS      -> virgülle ayrılmış board ID listesi (boş bırakılırsa tüm boardlar taranır)
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD  -> e-posta gönderimi için
  DIGEST_TO_EMAIL          -> özetin gideceği adres
  DIGEST_FROM_EMAIL        -> gönderen adres (genelde SMTP_USER ile aynı)
  DIGEST_MODE               -> "daily" veya "weekly" (varsayılan: daily)

Not: Pinterest kuralları API verisinin kalıcı cache'lenmesini yasaklıyor.
Bu script hiçbir pin verisini diske/db'ye yazmaz — her çalıştığında taze çeker,
e-postayı gönderir ve biter.
"""

import os
import sys
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta

PINTEREST_API_BASE = "https://api.pinterest.com/v5"

# FEIN content pillar anahtar kelime eşleştirmesi.
# Pin başlığı/açıklaması veya board adında bu kelimeler geçerse ilgili pillar'a atanır.
PILLAR_KEYWORDS = {
    "Product": ["product", "drink", "matcha", "coffee", "beverage", "cup", "flatlay"],
    "Process": ["pour", "pouring", "whisk", "extraction", "asmr", "process", "brewing"],
    "Space": ["interior", "cafe", "architecture", "space", "mekan", "berlin", "brutalist"],
    "People": ["portrait", "hands", "candid", "people", "person"],
    "Community": ["run", "event", "community", "group"],
    "Brand": ["packaging", "merch", "typography", "logo", "branding"],
    "Culture / Lifestyle": ["lifestyle", "editorial", "fashion", "street", "music", "design"],
    "Educational": ["how to", "diy", "recipe", "guide", "tutorial"],
}
DEFAULT_PILLAR = "Culture / Lifestyle"


def get_headers():
    token = os.environ["PINTEREST_ACCESS_TOKEN"]
    return {"Authorization": f"Bearer {token}"}


def fetch_board_ids():
    raw = os.environ.get("PINTEREST_BOARD_IDS", "").strip()
    if raw:
        return [b.strip() for b in raw.split(",") if b.strip()]
    # Board ID verilmediyse hesaptaki tüm boardları çek
    boards = []
    url = f"{PINTEREST_API_BASE}/boards"
    params = {"page_size": 100}
    while url:
        resp = requests.get(url, headers=get_headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        boards.extend(data.get("items", []))
        bookmark = data.get("bookmark")
        if bookmark:
            params = {"page_size": 100, "bookmark": bookmark}
        else:
            url = None
    return [b["id"] for b in boards]


def fetch_pins_for_board(board_id, since):
    pins = []
    url = f"{PINTEREST_API_BASE}/boards/{board_id}/pins"
    params = {"page_size": 100}
    while url:
        resp = requests.get(url, headers=get_headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for pin in data.get("items", []):
            created = pin.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if created_dt.replace(tzinfo=None) < since:
                        continue
                except ValueError:
                    pass
            pins.append(pin)
        bookmark = data.get("bookmark")
        if bookmark:
            params = {"page_size": 100, "bookmark": bookmark}
        else:
            url = None
    return pins


def classify_pillar(pin):
    text = " ".join(filter(None, [pin.get("title", ""), pin.get("description", "")])).lower()
    for pillar, keywords in PILLAR_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return pillar
    return DEFAULT_PILLAR


def build_html(pins_by_pillar, mode):
    period_label = "Günlük" if mode == "daily" else "Haftalık"
    today = datetime.now().strftime("%d.%m.%Y")
    sections = []
    for pillar, pins in pins_by_pillar.items():
        if not pins:
            continue
        rows = ""
        for pin in pins[:8]:  # pillar başına en fazla 8 pin
            image_url = (
                pin.get("media", {}).get("images", {}).get("600x", {}).get("url", "")
            )
            link = pin.get("link") or f"https://www.pinterest.com/pin/{pin.get('id','')}/"
            title = pin.get("title") or "(başlıksız pin)"
            rows += f"""
              <td style="padding:8px;vertical-align:top;width:33%;">
                <a href="{link}" style="text-decoration:none;color:#111;">
                  <img src="{image_url}" style="width:100%;border-radius:4px;display:block;margin-bottom:6px;" />
                  <div style="font-size:12px;line-height:1.3;">{title}</div>
                </a>
              </td>
            """
        # 3'erli satırlara böl
        cells = rows.split("</td>")
        cells = [c + "</td>" for c in cells if c.strip()]
        table_rows = ""
        for i in range(0, len(cells), 3):
            table_rows += "<tr>" + "".join(cells[i:i + 3]) + "</tr>"

        sections.append(f"""
          <h2 style="font-family:Helvetica,Arial,sans-serif;font-size:16px;
                     border-bottom:1px solid #eee;padding-bottom:6px;margin-top:28px;">
            {pillar}
          </h2>
          <table style="width:100%;border-collapse:collapse;">{table_rows}</table>
        """)

    body = "".join(sections) or "<p>Bu dönemde yeni pin bulunamadı.</p>"

    return f"""
    <html>
      <body style="font-family:Helvetica,Arial,sans-serif;background:#faf9f6;padding:24px;">
        <div style="max-width:640px;margin:0 auto;background:#fff;padding:24px;border-radius:6px;">
          <div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#888;">
            FEIN Coffee Co. — Pinterest Referans Özeti
          </div>
          <h1 style="font-size:22px;margin:6px 0 2px;">{period_label} Özet — {today}</h1>
          {body}
        </div>
      </body>
    </html>
    """


def send_email(html):
    mode = os.environ.get("DIGEST_MODE", "daily")
    subject_period = "Günlük" if mode == "daily" else "Haftalık"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"FEIN — {subject_period} Pinterest Referans Özeti — {datetime.now().strftime('%d.%m.%Y')}"
    msg["From"] = os.environ["DIGEST_FROM_EMAIL"]
    msg["To"] = os.environ["DIGEST_TO_EMAIL"]
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        server.sendmail(msg["From"], [msg["To"]], msg.as_string())


def main():
    mode = os.environ.get("DIGEST_MODE", "daily")
    since = datetime.now() - (timedelta(days=1) if mode == "daily" else timedelta(days=7))

    board_ids = fetch_board_ids()
    if not board_ids:
        print("Hiç board bulunamadı, çıkılıyor.")
        sys.exit(0)

    pins_by_pillar = {p: [] for p in PILLAR_KEYWORDS}
    pins_by_pillar[DEFAULT_PILLAR] = pins_by_pillar.get(DEFAULT_PILLAR, [])

    for board_id in board_ids:
        pins = fetch_pins_for_board(board_id, since)
        for pin in pins:
            pillar = classify_pillar(pin)
            pins_by_pillar.setdefault(pillar, []).append(pin)

    html = build_html(pins_by_pillar, mode)
    send_email(html)
    print("Özet e-postası gönderildi.")


if __name__ == "__main__":
    main()
