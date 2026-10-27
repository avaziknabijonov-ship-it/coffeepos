"""Short-lived, audience-scoped links to privacy-minimized non-fiscal receipts."""
import hashlib
import secrets
import time
from datetime import datetime
from html import escape

import jwt

from .security import secret_key
from .db import ReceiptLink, now_ms

AUDIENCE = 'coffeepos-public-receipt'
TTL = 15 * 60


def make_receipt_token(db, order):
    now = int(time.time())
    jti = secrets.token_hex(16)
    grant = ReceiptLink(id=hashlib.sha256(jti.encode()).hexdigest(),
                        company_id=order.company_id, order_id=order.id,
                        expires_at=(now + TTL) * 1000)
    db.add(grant)
    token = jwt.encode({'aud': AUDIENCE, 'purpose': 'receipt', 'oid': order.id,
                       'cid': order.company_id, 'iat': now, 'exp': now + TTL,
                       'jti': jti}, secret_key(db), algorithm='HS256')
    return token, grant


def read_receipt_token(db, token):
    if len(token) > 1024:
        return None
    try:
        claims = jwt.decode(token, secret_key(db), algorithms=['HS256'], audience=AUDIENCE,
                            options={'require': ['exp', 'iat', 'aud', 'jti', 'oid', 'cid', 'purpose']})
        if claims['purpose'] != 'receipt' or type(claims['oid']) is not int or type(claims['cid']) is not int:
            return None
        if not isinstance(claims['jti'], str):
            return None
        grant = db.get(ReceiptLink, hashlib.sha256(claims['jti'].encode()).hexdigest())
        if (grant is None or grant.revoked_at is not None or grant.expires_at <= now_ms()
                or grant.order_id != claims['oid'] or grant.company_id != claims['cid']):
            return None
        return claims
    except jwt.PyJWTError:
        return None


def receipt_html(order, company_name, refunded, lang, tz, fiscal=None):
    ru = lang == 'ru'
    title = 'Электронный чек' if ru else 'Elektron chek'
    warning = 'НЕ ФИСКАЛЬНЫЙ ЧЕК' if ru else 'FISKAL CHEK EMAS'
    fiscal_block = ''
    if fiscal is not None and fiscal.status == 'issued':
        warning = 'ФИСКАЛЬНЫЙ ЧЕК' if ru else 'FISKAL CHEK'
        fiscal_block = ('<p>ID: ' + escape(fiscal.provider_receipt_id) + '<br>' + escape(fiscal.fiscal_sign) +
                        '</p><p><a href="' + escape(fiscal.qr_payload, quote=True) + '">QR</a></p>')
    elif fiscal is not None and fiscal.status == 'sandbox':
        warning = ('ТЕСТОВЫЙ (SANDBOX) — НЕ ФИСКАЛЬНЫЙ ЧЕК' if ru else 'TEST (SANDBOX) — FISKAL CHEK EMAS')
    total = 'Итого' if ru else 'Jami'
    discount = 'Скидка' if ru else 'Chegirma'
    returned = 'Возвращено' if ru else 'Qaytarilgan'
    status = 'ОТМЕНЁН' if ru else 'BEKOR QILINGAN'
    amount = lambda value: f'{value:,}'.replace(',', ' ')
    lines = ''.join('<tr><td>' + escape(str(item.get('name', ''))) + ' ' + escape(str(item.get('size', ''))) +
                    '</td><td>' + escape(str(item['qty'])) + '</td><td>' +
                    amount(item['unitPrice'] * item['qty']) + '</td></tr>' for item in order.items)
    date = datetime.fromtimestamp(order.created_at / 1000, tz).strftime('%Y-%m-%d %H:%M')
    # Customer name/phone, staff names, ingredient recipes, cost and cancellation
    # reasons are intentionally never rendered. All user-controlled text is escaped.
    return f'''<!doctype html><html lang="{lang}"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font:16px system-ui;max-width:560px;margin:32px auto;padding:16px}}table{{width:100%;border-collapse:collapse}}td{{padding:8px;border-bottom:1px solid #ddd}}td:last-child{{text-align:right}}.notice{{padding:12px;border:2px solid #333;font-weight:bold}}</style>
<h1>{escape(company_name)}</h1><h2>{title} №{order.number}</h2><p>{date}</p>
<p class="notice">{warning}</p>{fiscal_block}{('<p>' + status + '</p>') if order.status == 'cancelled' else ''}
<table>{lines}</table><p>{discount}: {amount(order.discount)} UZS</p>
<h2>{total}: {amount(order.total)} UZS</h2><p>{returned}: {amount(refunded)} UZS</p></html>'''
