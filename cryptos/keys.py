"""
Utilities to generate secret/public key pairs and Bitcoin address
(note: using "secret" instead of "private" so that sk and pk are
easy consistent shortcuts of the two without collision)
"""

import os
import time

from .sha256 import sha256
from .curves import Point
from .bitcoin import BITCOIN

# -----------------------------------------------------------------------------
# Secret key generation utilities

def random_bytes_os():
    """
    Use os provided entropy, e.g. on macs sourced from /dev/urandom, eg available as:
    $ head -c 32 /dev/urandom

    According to Apple Platform Security docs
    https://support.apple.com/en-ie/guide/security/seca0c73a75b/web
    the kernel CPRNG is a Fortuna-derived design targeting a 256-bit security level
    where the entropy is sourced from:
    - The Secure Enclave’s hardware RNG
    - Timing-based jitter collected during boot
    - Entropy collected from hardware interrupts
    - A seed file used to persist entropy across boots
    - Intel random instructions, i.e. RDSEED and RDRAND (macOS only)
    """
    return os.urandom(32)


def random_bytes_user():
    """
    Collect some entropy from time and user and generate a key with SHA-256
    """
    entropy = ''
    for i in range(5):
        s = input("Enter some word #%d/5: " % (i+1,))
        entropy += s + '|' + str(int(time.time() * 1000000)) + '|'
    return sha256(entropy.encode('ascii'))


def mastering_bitcoin_bytes():
    """
    The example from Mastering Bitcoin, Chapter 4
    https://github.com/bitcoinbook/bitcoinbook/blob/develop/ch04.asciidoc
    """
    sk = '3aba4162c7251c891207b747840551a71939b0de081f85c4e44cf7c13e41daa6'
    return bytes.fromhex(sk)


def gen_secret_key(n: int, source: str = 'os') -> int:
    """
    n is the upper bound on the key, typically the order of the elliptic curve
    we are using. The function will return a valid key, i.e. 1 <= key < n.
    """

    assert source in ['os', 'user', 'mastering'], "The source must be one of 'os' or 'user' or 'mastering'"
    bytes_fn = {
        'os': random_bytes_os,
        'user': random_bytes_user,
        'mastering': mastering_bitcoin_bytes,
    }[source]

    while True:
        key = int.from_bytes(bytes_fn(), 'big')
        if 1 <= key < n:
            break # the key is valid, break out

    return key

# -----------------------------------------------------------------------------
# Public key - specific functions, esp encoding / decoding

class PublicKey(Point):
    """
    The public key is just a Point on a Curve, but has some additional specific
    encoding / decoding functionality that this class implements.
    """

    @classmethod
    def from_point(cls, pt: Point):
        """ promote a Point to be a PublicKey """
        return cls(pt.curve, pt.x, pt.y)

    @classmethod
    def from_sk(cls, sk):
        """ sk can be an int or a hex string """
        assert isinstance(sk, (int, str))
        sk = int(sk, 16) if isinstance(sk, str) else sk
        pk = sk * BITCOIN.gen.G
        return cls.from_point(pk)

    @classmethod
    def decode(cls, b: bytes):
        """ decode from the SEC binary format """
        assert isinstance(b, bytes)

        # the uncompressed version is straight forward
        if b[0] == 4:
            x = int.from_bytes(b[1:33], 'big')
            y = int.from_bytes(b[33:65], 'big')
            return Point(BITCOIN.gen.G.curve, x, y)

        # for compressed version uncompress the full public key Point
        # first recover the y-evenness and the full x
        assert b[0] in [2, 3]
        is_even = b[0] == 2
        x = int.from_bytes(b[1:], 'big')

        # solve y^2 = x^3 + 7 for y, but mod p
        p = BITCOIN.gen.G.curve.p
        y2 = (pow(x, 3, p) + 7) % p
        y = pow(y2, (p + 1) // 4, p)
        y = y if ((y % 2 == 0) == is_even) else p - y # flip if needed to make the evenness agree
        return cls(BITCOIN.gen.G.curve, x, y)

    def encode(self, compressed=True):
        """ return the SEC bytes encoding of the public key Point """
        if compressed:
            prefix = b'\x02' if self.y % 2 == 0 else b'\x03'
            return prefix + self.x.to_bytes(32, 'big')
        else:
            return b'\x04' + self.x.to_bytes(32, 'big') + self.y.to_bytes(32, 'big')

# -----------------------------------------------------------------------------
# convenience functions

def gen_key_pair(source: str = 'os'):
    """ convenience function to quickly generate a secret/public keypair """
    sk = gen_secret_key(BITCOIN.gen.n, source)
    pk = PublicKey.from_sk(sk)
    return sk, pk
