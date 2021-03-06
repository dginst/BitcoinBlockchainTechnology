#!/usr/bin/env python3

# Copyright (C) 2017-2021 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"Tests for the `btclib.b58` module."

from typing import List, Tuple

import pytest

from btclib import b32, b58
from btclib.base58 import b58encode
from btclib.bip32 import bip32, slip132
from btclib.ecc.curve import secp256k1
from btclib.ecc.sec_point import bytes_from_point, point_from_octets
from btclib.exceptions import BTClibValueError
from btclib.hashes import hash160_from_key
from btclib.network import NETWORKS
from btclib.script import script
from btclib.to_prv_key import prv_keyinfo_from_prv_key
from btclib.to_pub_key import pub_keyinfo_from_prv_key
from btclib.utils import hash160, sha256

ec = secp256k1


def test_wif_from_prv_key() -> None:
    prv_key = "0C28FCA386C7A227600B2FE50B7CAE11EC86D3BF1FBE471BE89827E19D72AA1D"
    test_vectors: List[Tuple[str, str, bool]] = [
        ("KwdMAjGmerYanjeui5SHS7JkmpZvVipYvB2LJGU1ZxJwYvP98617", "mainnet", True),
        ("cMzLdeGd5vEqxB8B6VFQoRopQ3sLAAvEzDAoQgvX54xwofSWj1fx", "testnet", True),
        ("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ", "mainnet", False),
        ("91gGn1HgSap6CbU12F6z3pJri26xzp7Ay1VW6NHCoEayNXwRpu2", "testnet", False),
        (" KwdMAjGmerYanjeui5SHS7JkmpZvVipYvB2LJGU1ZxJwYvP98617", "mainnet", True),
        ("KwdMAjGmerYanjeui5SHS7JkmpZvVipYvB2LJGU1ZxJwYvP98617 ", "mainnet", True),
    ]
    for v in test_vectors:
        assert v[0].strip() == b58.wif_from_prv_key(prv_key, v[1], v[2])
        q, network, compressed = prv_keyinfo_from_prv_key(v[0])
        assert q == int(prv_key, 16)
        assert network == v[1]
        assert compressed == v[2]

    bad_q = ec.n.to_bytes(ec.n_size, byteorder="big", signed=False)
    with pytest.raises(BTClibValueError, match="private key not in 1..n-1: "):
        b58.wif_from_prv_key(bad_q, "mainnet", True)

    payload = b"\x80" + bad_q
    badwif = b58encode(payload)
    with pytest.raises(BTClibValueError, match="not a private key: "):
        prv_keyinfo_from_prv_key(badwif)

    # not a private key: 33 bytes
    bad_q = 33 * b"\x02"
    with pytest.raises(BTClibValueError, match="not a private key: "):
        b58.wif_from_prv_key(bad_q, "mainnet", True)
    payload = b"\x80" + bad_q
    badwif = b58encode(payload)
    with pytest.raises(BTClibValueError, match="not a private key: "):
        prv_keyinfo_from_prv_key(badwif)

    # Not a WIF: missing leading 0x80
    good_q = 32 * b"\x02"
    payload = b"\x81" + good_q
    badwif = b58encode(payload)
    with pytest.raises(BTClibValueError, match="not a private key: "):
        prv_keyinfo_from_prv_key(badwif)

    # Not a compressed WIF: missing trailing 0x01
    payload = b"\x80" + good_q + b"\x00"
    badwif = b58encode(payload)
    with pytest.raises(BTClibValueError, match="not a private key: "):
        prv_keyinfo_from_prv_key(badwif)

    # Not a WIF: wrong size (35)
    payload = b"\x80" + good_q + b"\x01\x00"
    badwif = b58encode(payload)
    with pytest.raises(BTClibValueError, match="not a private key: "):
        prv_keyinfo_from_prv_key(badwif)


def test_address_from_h160() -> None:
    address = "1PMycacnJaSqwwJqjawXBErnLsZ7RkXUAs"
    prefix, payload, network, _ = b58.h160_from_address(address)
    assert address == b58.address_from_h160(prefix, payload, network)

    address = "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM"
    prefix, payload, network, _ = b58.h160_from_address(address)
    assert address == b58.address_from_h160(prefix, payload, network)

    address = "37k7toV1Nv4DfmQbmZ8KuZDQCYK9x5KpzP"
    prefix, payload, network, _ = b58.h160_from_address(address)
    assert address == b58.address_from_h160(prefix, payload, network)

    err_msg = "invalid mainnet base58 address prefix: "
    with pytest.raises(BTClibValueError, match=err_msg):
        b58.address_from_h160(b"\xbb", payload, network)


def test_p2pkh_from_wif() -> None:
    seed = b"\x00" * 32  # better be a documented test case
    rxprv = bip32.rootxprv_from_seed(seed)
    path = "m/0h/0h/12"
    xprv = bip32.derive(rxprv, path)
    wif = b58.wif_from_prv_key(xprv)
    assert wif == "L2L1dqRmkmVtwStNf5wg8nnGaRn3buoQr721XShM4VwDbTcn9bpm"
    pub_key, _ = pub_keyinfo_from_prv_key(wif)
    address = b58.p2pkh(pub_key)
    xpub = bip32.xpub_from_xprv(xprv)
    assert address == slip132.address_from_xpub(xpub)

    err_msg = "not a private key: "
    with pytest.raises(BTClibValueError, match=err_msg):
        b58.wif_from_prv_key(xpub)


def test_p2pkh_from_pub_key() -> None:
    # https://en.bitcoin.it/wiki/Technical_background_of_version_1_Bitcoin_addresses
    pub_key = "02 50863ad64a87ae8a2fe83c1af1a8403cb53f53e486d8511dad8a04887e5b2352"
    address = "1PMycacnJaSqwwJqjawXBErnLsZ7RkXUAs"
    assert address == b58.p2pkh(pub_key)
    assert address == b58.p2pkh(pub_key, compressed=True)
    _, h160, _, _ = b58.h160_from_address(address)
    assert h160 == hash160(pub_key)

    # trailing/leading spaces in address string
    assert address == b58.p2pkh(" " + pub_key)
    assert h160 == hash160(" " + pub_key)
    assert address == b58.p2pkh(pub_key + " ")
    assert h160 == hash160(pub_key + " ")

    uncompr_pub_key = bytes_from_point(point_from_octets(pub_key), compressed=False)
    uncompr_address = "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM"
    assert uncompr_address == b58.p2pkh(uncompr_pub_key, compressed=False)
    assert uncompr_address == b58.p2pkh(uncompr_pub_key)
    _, uncompr_h160, _, _ = b58.h160_from_address(uncompr_address)
    assert uncompr_h160 == hash160(uncompr_pub_key)

    err_msg = "not a private or uncompressed public key: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert uncompr_address == b58.p2pkh(pub_key, compressed=False)

    err_msg = "not a private or compressed public key: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert address == b58.p2pkh(uncompr_pub_key, compressed=True)


def test_p2sh() -> None:
    # https://medium.com/@darosior/bitcoin-raw-transactions-part-2-p2sh-94df206fee8d
    network = "mainnet"
    address = "37k7toV1Nv4DfmQbmZ8KuZDQCYK9x5KpzP"
    script_pub_key = script.serialize(
        [
            "OP_2DUP",
            "OP_EQUAL",
            "OP_NOT",
            "OP_VERIFY",
            "OP_SHA1",
            "OP_SWAP",
            "OP_SHA1",
            "OP_EQUAL",
        ]
    )

    assert script_pub_key.hex() == "6e879169a77ca787"
    assert address == b58.p2sh(script_pub_key, network)

    script_hash = hash160(script_pub_key)
    prefix = NETWORKS[network].p2sh
    assert (prefix, script_hash, network, True) == b58.h160_from_address(address)
    assert (prefix, script_hash, network, True) == b58.h160_from_address(
        " " + address + " "  # address with trailing/leading spaces
    )

    assert script_hash.hex() == "4266fc6f2c2861d7fe229b279a79803afca7ba34"
    script_sig: List[script.Command] = ["OP_HASH160", script_hash.hex(), "OP_EQUAL"]
    script.serialize(script_sig)


def test_p2w_p2sh() -> None:

    pub_key = "03 a1af804ac108a8a51782198c2d034b28bf90c8803f5a53f76276fa69a4eae77f"
    witness_program, network = hash160_from_key(pub_key)
    b58addr = b58.p2wpkh_p2sh(pub_key, network)
    assert b58addr == b58.address_from_v0_witness_program(witness_program, network)

    script_pub_key = script.serialize(
        [
            "OP_DUP",
            "OP_HASH160",
            witness_program,
            "OP_EQUALVERIFY",
            "OP_CHECKSIG",
        ]
    )
    witness_program = sha256(script_pub_key)
    b58addr = b58.p2wsh_p2sh(script_pub_key, network)
    assert b58addr == b58.address_from_v0_witness_program(witness_program, network)

    err_msg = "invalid witness program length for witness v0: "
    with pytest.raises(BTClibValueError, match=err_msg):
        b58.address_from_v0_witness_program(witness_program[:-1], network)


def test_address_from_wif() -> None:

    q = 0x19E14A7B6A307F426A94F8114701E7C8E774E7F9A47E2C2035DB29A206321725

    test_cases: List[Tuple[bool, str, str, str]] = [
        (
            False,
            "mainnet",
            "5J1geo9kcAUSM6GJJmhYRX1eZEjvos9nFyWwPstVziTVueRJYvW",
            "1LPM8SZ4RQDMZymUmVSiSSvrDfj1UZY9ig",
        ),
        (
            True,
            "mainnet",
            "Kx621phdUCp6sgEXPSHwhDTrmHeUVrMkm6T95ycJyjyxbDXkr162",
            "1HJC7kFvXHepkSzdc8RX6khQKkAyntdfkB",
        ),
        (
            False,
            "testnet",
            "91nKEXyJCPYaK9maw7bTJ7ZcCu6dy2gybvNtUWF1LTCYggzhZgy",
            "mzuJRVe3ERecM6F6V4R6GN9B5fKiPC9HxF",
        ),
        (
            True,
            "testnet",
            "cNT1UjhUuGWN37hnmr754XxvPWwtAJTSq8bcCQ4pUrdxqxbA1iU1",
            "mwp9QoLuLK65XZUFKhPtvfujBjmgkZnmPx",
        ),
    ]
    for compressed, network, wif, address in test_cases:
        assert wif == b58.wif_from_prv_key(q, network, compressed)
        assert prv_keyinfo_from_prv_key(wif) == (q, network, compressed)
        assert address == b58.p2pkh(wif)
        _, payload, net, is_script_hash = b58.h160_from_address(address)
        assert net == network
        assert not is_script_hash
        if compressed:
            b32_address = b32.p2wpkh(wif)
            assert (
                0,
                payload,
                network,
                False,  # is_script_hash
            ) == b32.witness_from_address(b32_address)

            b58_address = b58.p2wpkh_p2sh(wif)
            assert (
                NETWORKS[network].p2sh,
                hash160(b"\x00\x14" + payload),
                network,
                True,  # is_script_hash
            ) == b58.h160_from_address(b58_address)

        else:
            err_msg = "not a private or compressed public key: "
            with pytest.raises(BTClibValueError, match=err_msg):
                b32.p2wpkh(wif)  # type: ignore
            with pytest.raises(BTClibValueError, match=err_msg):
                b58.p2wpkh_p2sh(wif)  # type: ignore


def test_exceptions() -> None:

    pub_key = "02 50863ad64a87ae8a2fe83c1af1a8403cb53f53e486d8511dad8a04887e5b2352"
    payload = b"\xf5" + hash160(pub_key)
    invalid_address = b58encode(payload)
    with pytest.raises(BTClibValueError, match="invalid base58 address prefix: "):
        b58.h160_from_address(invalid_address)

    with pytest.raises(BTClibValueError, match="not a private or public key: "):
        b58.p2pkh(pub_key + "00")
