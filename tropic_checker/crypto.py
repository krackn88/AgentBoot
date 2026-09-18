"""AES password encryption used by the TSC mobile app."""

import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

AES_KEY = b"aesEncryptionTSC"
AES_IV = b"encryptionIntVec"


def aes_encrypt(plaintext: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.b64encode(ciphertext).decode()
