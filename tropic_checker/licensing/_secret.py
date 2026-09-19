"""Build-time license PUBLIC key placeholder — replaced by prepare_customer_secret.py.

Only the Ed25519 *public* key is ever embedded in the shipped client. The
private signing key stays on the vendor's license server / build machine, so a
reverse-engineered client cannot forge license keys.
"""

# Ed25519 public key as 64-char hex (32 bytes). Empty in dev builds; the customer
# build injects the real public key derived from the vendor's private secret.
_LICENSE_PUBLIC_KEY_HEX = ""
