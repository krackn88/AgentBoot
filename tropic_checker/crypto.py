"""AES encryption used by the TSC mobile app (passwords + gift card numbers)."""

import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

AES_KEY = b"aesEncryptionTSC"
AES_IV = b"encryptionIntVec"


def aes_encrypt(plaintext: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.b64encode(ciphertext).decode()


def aes_decrypt(ciphertext_b64: str) -> str | None:
    try:
        raw = base64.b64decode(ciphertext_b64)
        plaintext = unpad(AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(raw), 16)
        return plaintext.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
