import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse


def generate_totp_secret(length=20):
    raw = secrets.token_bytes(length)
    return base64.b32encode(raw).decode("utf-8").replace("=", "")


def _normalize_secret(secret):
    normalized = (secret or "").strip().replace(" ", "").upper()
    missing_padding = len(normalized) % 8
    if missing_padding:
        normalized += "=" * (8 - missing_padding)
    return normalized


def _hotp(secret, counter, digits=6):
    key = base64.b32decode(_normalize_secret(secret), casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def current_totp_token(secret, time_step=30, at_time=None):
    timestamp = int(at_time if at_time is not None else time.time())
    counter = timestamp // time_step
    return _hotp(secret, counter)


def verify_totp(secret, token, time_step=30, window=1):
    cleaned = "".join(ch for ch in (token or "") if ch.isdigit())
    if len(cleaned) != 6:
        return False

    counter = int(time.time()) // time_step
    for shift in range(-window, window + 1):
        if _hotp(secret, counter + shift) == cleaned:
            return True
    return False


def build_otpauth_uri(secret, username, issuer="MUIV StudCouncil"):
    label = urllib.parse.quote(f"{issuer}:{username}")
    issuer_q = urllib.parse.quote(issuer)
    secret_q = urllib.parse.quote(secret)
    return f"otpauth://totp/{label}?secret={secret_q}&issuer={issuer_q}&digits=6&period=30"
