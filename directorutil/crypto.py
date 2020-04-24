# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors
# pylint: disable=broad-except

from typing import Any, Dict, Iterable, Optional, Tuple, Union, cast

import Crypto.Cipher.AES
import Crypto.Cipher.PKCS1_OAEP
import Crypto.Hash.SHA512
import Crypto.PublicKey.RSA
import Crypto.Random
import Crypto.Signature.pss


class DirectorCryptoError(Exception):
    pass


class DirectorCryptoVerifyError(DirectorCryptoError):
    pass


def import_rsa_key_from_file(fname: str) -> Crypto.PublicKey.RSA.RsaKey:
    with open(fname, "rb") as f_obj:
        return Crypto.PublicKey.RSA.import_key(f_obj.read())


def sign_message(
    *,
    msg: bytes,
    private_key: Crypto.PublicKey.RSA.RsaKey,
    hash_algo: Any = Crypto.Hash.SHA512,
    signature_algo: Any = Crypto.Signature.pss,
    signature_algo_kwargs: Optional[Dict[str, Any]] = None,
) -> bytes:
    if signature_algo_kwargs is None:
        signature_algo_kwargs = {}

    # Based on https://pycryptodome.readthedocs.io/en/latest/src/signature/dsa.html
    hash_obj = hash_algo.new(msg)
    signer = signature_algo.new(private_key, **signature_algo_kwargs)

    return cast(bytes, signer.sign(hash_obj))


def verify_signature(
    *,
    msg: bytes,
    signature: bytes,
    public_key: Crypto.PublicKey.RSA.RsaKey,
    hash_algo: Any = Crypto.Hash.SHA512,
    signature_algos: Optional[Iterable[Union[Any, Tuple[Any, Dict[str, Any]]]]] = None,
) -> None:
    """Raises DirectorCryptoVerifyError if signature is invalid"""
    verify_message_hash(
        msg_hash_obj=hash_algo.new(msg),
        signature=signature,
        public_key=public_key,
        signature_algos=signature_algos,
    )


def verify_message_hash(
    *,
    msg_hash_obj: Any,
    signature: bytes,
    public_key: Crypto.PublicKey.RSA.RsaKey,
    signature_algos: Optional[Iterable[Union[Any, Tuple[Any, Dict[str, Any]]]]] = None,
) -> None:
    """Raises DirectorCryptoVerifyError if signature is invalid."""

    if signature_algos is None:
        signature_algos = [Crypto.Signature.pss]

    verify_exc: Optional[Exception] = None

    # Based on https://pycryptodome.readthedocs.io/en/latest/src/signature/dsa.html

    for algo_info in signature_algos:
        if isinstance(algo_info, tuple):
            algo_cls, algo_kwargs = algo_info  # pylint: disable=unpacking-non-sequence
        else:
            algo_cls = algo_info
            algo_kwargs = {}

        try:
            verifier = algo_cls.new(public_key, **algo_kwargs)
        except Exception as ex:
            raise DirectorCryptoError("Error constructing signature object: {}".format(ex)) from ex

        try:
            verifier.verify(msg_hash_obj, signature)
        except ValueError as ex:
            verify_exc = ex
            continue
        except Exception as ex:
            raise DirectorCryptoError("Error verifying message signature: {}".format(ex)) from ex
        else:
            return

    if verify_exc is not None:
        raise DirectorCryptoVerifyError(
            "Error verifying message signature: {}".format(verify_exc)
        ) from verify_exc
    else:
        raise DirectorCryptoVerifyError("Error verifying message signature")


def encrypt_short_message_pkcs1(*, msg: bytes, public_key: Crypto.PublicKey.RSA.RsaKey) -> bytes:
    try:
        return Crypto.Cipher.PKCS1_OAEP.new(public_key).encrypt(msg)
    except Exception as ex:
        raise DirectorCryptoError("Error encrypting message: {}".format(ex)) from ex


def decrypt_short_message_pkcs1(*, msg: bytes, private_key: Crypto.PublicKey.RSA.RsaKey) -> bytes:
    try:
        return Crypto.Cipher.PKCS1_OAEP.new(private_key).decrypt(msg)
    except Exception as ex:
        raise DirectorCryptoError("Error decrypting message: {}".format(ex)) from ex


def encrypt_message(
    *,
    msg: bytes,
    public_key: Crypto.PublicKey.RSA.RsaKey,
    aes_session_key_length: int = 16,
    aes_nonce_length: int = 16,
    aes_tag_length: int = 16,
) -> bytes:
    # Based on https://pycryptodome.readthedocs.io/en/latest/src/examples.html#encrypt-data-with-rsa
    # Basically, we encrypt an AES session key with the RSA key, then we encrypt the message with
    # the session key.

    if aes_session_key_length < 16:
        raise ValueError("aes_session_key_length must be >= 16")

    if aes_nonce_length < 16:
        raise ValueError("aes_nonce_length must be >= 16")

    if aes_tag_length & 1 or aes_tag_length < 4 or aes_tag_length > 16:
        raise ValueError("aes_tag_length must an even number in the range [4, 16]")

    session_key = Crypto.Random.get_random_bytes(aes_session_key_length)
    nonce = Crypto.Random.get_random_bytes(aes_nonce_length)

    cipher_aes = Crypto.Cipher.AES.new(
        key=session_key, mode=Crypto.Cipher.AES.MODE_EAX, nonce=nonce, mac_len=aes_tag_length
    )

    ciphertext, tag = cipher_aes.encrypt_and_digest(msg)  # type: ignore

    return (
        encrypt_short_message_pkcs1(msg=session_key, public_key=public_key)
        + nonce
        + tag
        + ciphertext
    )


def decrypt_message(
    *,
    msg: bytes,
    private_key: Crypto.PublicKey.RSA.RsaKey,
    aes_nonce_length: int = 16,
    aes_tag_length: int = 16,
) -> bytes:
    encoded_session_key, msg = (
        msg[: private_key.size_in_bytes()],
        msg[private_key.size_in_bytes():],
    )
    nonce, msg = msg[:aes_nonce_length], msg[aes_nonce_length:]
    tag, msg = msg[:aes_tag_length], msg[aes_tag_length:]

    session_key = decrypt_short_message_pkcs1(msg=encoded_session_key, private_key=private_key)

    try:
        cipher_aes = Crypto.Cipher.AES.new(session_key, Crypto.Cipher.AES.MODE_EAX, nonce)

        return cipher_aes.decrypt_and_verify(msg, tag)  # type: ignore
    except Exception as ex:
        raise DirectorCryptoError("Error decrypting message: {}".format(ex)) from ex
