#!/usr/bin/env python3

# Copyright (C) 2017-2021 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"Tests for the `btclib.script.script_pub_key` module."

import json
from os import path
from typing import List

import pytest

from btclib import b32, b58, var_bytes
from btclib.exceptions import BTClibValueError
from btclib.network import NETWORKS
from btclib.script.script import Command, Script, parse, serialize
from btclib.script.script_pub_key import (
    ScriptPubKey,
    address,
    assert_p2ms,
    assert_p2pk,
    assert_p2pkh,
    assert_p2sh,
    assert_p2wpkh,
    assert_p2wsh,
    has_segwit_prefix,
    is_nulldata,
    is_p2ms,
    type_and_payload,
)
from btclib.to_pub_key import Key
from btclib.utils import hash160, sha256


def test_has_segwit_prefix() -> None:
    addr = b"bc1q0hy024867ednvuhy9en4dggflt5w9unw4ztl5a"
    assert has_segwit_prefix(addr)
    assert has_segwit_prefix(addr.decode("ascii"))
    addr = b"1PMycacnJaSqwwJqjawXBErnLsZ7RkXUAs"
    assert not has_segwit_prefix(addr)
    assert not has_segwit_prefix(addr.decode("ascii"))


def test_nulldata() -> None:

    OP_RETURN = b"\x6a"  # pylint: disable=invalid-name

    # self-consistency
    string = "time-stamped data"
    payload = string.encode()
    script_pub_key = serialize(["OP_RETURN", payload])
    assert script_pub_key == ScriptPubKey.nulldata(string).script

    # to the script_pub_key in two steps (through payload)
    script_type = "nulldata"
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )

    # back from the script_pub_key to the payload
    assert (script_type, payload) == type_and_payload(script_pub_key)

    # data -> payload in this case is invertible (no hash functions)
    assert payload.decode("ascii") == string

    assert address(script_pub_key) == ""

    # documented test cases: https://learnmeabitcoin.com/guide/nulldata
    string = "hello world"
    payload = string.encode()
    assert payload.hex() == "68656c6c6f20776f726c64"  # pylint: disable=no-member
    script_pub_key = OP_RETURN + var_bytes.serialize(payload)
    assert script_pub_key == ScriptPubKey.nulldata(string).script
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )
    assert (script_type, payload) == type_and_payload(script_pub_key)

    # documented test cases: https://learnmeabitcoin.com/guide/nulldata
    string = "charley loves heidi"
    payload = string.encode()
    assert (
        payload.hex()  # pylint: disable=no-member
        == "636861726c6579206c6f766573206865696469"
    )
    script_pub_key = OP_RETURN + var_bytes.serialize(payload)
    assert script_pub_key == ScriptPubKey.nulldata(string).script
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )
    assert (script_type, payload) == type_and_payload(script_pub_key)

    # documented test cases: https://learnmeabitcoin.com/guide/nulldata
    string = "家族も友達もみんなが笑顔の毎日がほしい"
    payload = string.encode()
    assert (
        payload.hex()  # pylint: disable=no-member
        == "e5aeb6e6978fe38282e58f8be98194e38282e381bfe38293e381aae3818ce7ac91e9a194e381aee6af8ee697a5e3818ce381bbe38197e38184"
    )
    script_pub_key = OP_RETURN + var_bytes.serialize(payload)
    assert script_pub_key == ScriptPubKey.nulldata(string).script
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )
    assert (script_type, payload) == type_and_payload(script_pub_key)


def test_nulldata2() -> None:

    script_type = "nulldata"

    # max length case
    byte = b"\x00"
    for length in (0, 1, 16, 17, 74, 75, 76, 77, 78, 79, 80):
        payload = byte * length
        script_pub_key = serialize(["OP_RETURN", payload])
        assert (
            script_pub_key
            == ScriptPubKey.from_type_and_payload(script_type, payload).script
        )

        # back from the script_pub_key to the payload
        assert (script_type, payload) == type_and_payload(script_pub_key)


def test_nulldata3() -> None:

    err_msg = "invalid nulldata payload length: "
    with pytest.raises(BTClibValueError, match=err_msg):
        payload = "00" * 81
        ScriptPubKey.from_type_and_payload("nulldata", payload)

    # wrong data length: 32 in 35-bytes nulldata script;
    # it should have been 33
    script_pub_key = serialize(["OP_RETURN", b"\x00" * 33])
    script_pub_key = script_pub_key[:1] + b"\x20" + script_pub_key[2:]
    assert not is_nulldata(script_pub_key)

    # wrong data length: 32 in 83-bytes nulldata script;
    # it should have been 80
    script_pub_key = serialize(["OP_RETURN", b"\x00" * 80])
    script_pub_key = script_pub_key[:2] + b"\x20" + script_pub_key[3:]
    assert not is_nulldata(script_pub_key)

    # missing OP_PUSHDATA1 (0x4c) in 83-bytes nulldata script,
    # got 0x20 instead
    script_pub_key = serialize(["OP_RETURN", b"\x00" * 80])
    script_pub_key = script_pub_key[:1] + b"\x20" + script_pub_key[2:]
    assert not is_nulldata(script_pub_key)

    assert len(serialize(["OP_RETURN", b"\x00" * 75])) == 77
    assert len(serialize(["OP_RETURN", b"\x00" * 76])) == 79
    script_pub_key = serialize(["OP_RETURN", b"\x00" * 76])[:-1]
    assert not is_nulldata(script_pub_key)


def test_nulldata4() -> None:

    script_: List[Command] = [
        "OP_RETURN",
        "OP_RETURN",
        "OP_3",
        "OP_1",
        "OP_VERIF",
        "OP_0",
        "OP_3",
    ]
    # FIXME: serialization is not 0x6A{1 byte data-length}{data 6 bytes)}
    script_pub_key = serialize(script_)
    assert len(script_pub_key) == 7
    assert parse(script_pub_key) == script_
    script_type, _ = type_and_payload(script_pub_key)
    # FIXME: it should be "nulldata"
    assert script_type == "unknown"
    # assert is_nulldata(script_pub_key)


def test_p2pk() -> None:

    # self-consistency
    pub_key = "02 cc71eb30d653c0c3163990c47b976f3fb3f37cccdcbedb169a1dfef58bbfbfaf"
    script_pub_key = serialize([pub_key, "OP_CHECKSIG"])
    assert_p2pk(script_pub_key)
    assert script_pub_key == ScriptPubKey.p2pk(pub_key).script

    script_type = "p2pk"
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, pub_key).script
    )

    # back from the script_pub_key to the payload
    assert (script_type, bytes.fromhex(pub_key)) == type_and_payload(script_pub_key)

    assert address(script_pub_key) == ""

    err_msg = "invalid pub_key length marker: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2pk(b"\x31" + script_pub_key[1:])

    # documented test case: https://learnmeabitcoin.com/guide/p2pk
    pub_key = (
        "04"
        "ae1a62fe09c5f51b13905f07f06b99a2f7159b2225f374cd378d71302fa28414"
        "e7aab37397f554a7df5f142c21c1b7303b8a0626f1baded5c72a704f7e6cd84c"
    )
    script_pub_key = bytes.fromhex("41" + pub_key + "ac")
    assert_p2pk(script_pub_key)
    assert script_pub_key == ScriptPubKey.p2pk(pub_key).script

    err_msg = "missing final OP_CHECKSIG"
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2pk(script_pub_key[:-1] + b"\x00")

    err_msg = "invalid pub_key length marker: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2pk(b"\x31" + script_pub_key[1:])

    # invalid size: 34 bytes instead of (33, 65)
    pub_key = "03 ae1a62fe09c5f51b13905f07f06b99a2f7159b2225f374cd378d71302fa28414 14"
    err_msg = "not a private or public key: "
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.p2pk(pub_key)


def test_p2pkh() -> None:

    # self-consistency
    pub_key = (
        "04 "
        "cc71eb30d653c0c3163990c47b976f3fb3f37cccdcbedb169a1dfef58bbfbfaf"
        "f7d8a473e7e2e6d317b87bafe8bde97e3cf8f065dec022b51d11fcdd0d348ac4"
    )
    payload = hash160(pub_key)
    script_pub_key = serialize(
        ["OP_DUP", "OP_HASH160", payload, "OP_EQUALVERIFY", "OP_CHECKSIG"]
    )
    assert_p2pkh(script_pub_key)
    assert script_pub_key == ScriptPubKey.p2pkh(pub_key).script

    # to the script_pub_key in two steps (through payload)
    script_type = "p2pkh"
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )

    # back from the script_pub_key to the payload
    assert (script_type, payload) == type_and_payload(script_pub_key)

    # base58 address
    network = "mainnet"
    addr = b58.p2pkh(pub_key, network)
    assert addr == address(script_pub_key, network)
    prefix = NETWORKS[network].p2pkh
    assert addr == b58.address_from_h160(prefix, payload, network)

    # back from the address to the script_pub_key
    assert script_pub_key == ScriptPubKey.from_address(addr).script
    assert network == ScriptPubKey.from_address(addr).network

    # documented test case: https://learnmeabitcoin.com/guide/p2pkh
    payload = bytes.fromhex("12ab8dc588ca9d5787dde7eb29569da63c3a238c")
    script_pub_key = bytes.fromhex("76a914") + payload + bytes.fromhex("88ac")
    assert_p2pkh(script_pub_key)
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )
    addr = "12higDjoCCNXSA95xZMWUdPvXNmkAduhWv"
    assert addr == address(script_pub_key, network)
    assert script_pub_key == ScriptPubKey.from_address(addr).script
    assert network == ScriptPubKey.from_address(addr).network

    err_msg = "missing final OP_EQUALVERIFY, OP_CHECKSIG"
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2pkh(script_pub_key[:-2] + b"\x40\x40")

    err_msg = "missing leading OP_DUP, OP_HASH160"
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2pkh(b"\x40\x40" + script_pub_key[2:])

    err_msg = "invalid pub_key hash length marker: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2pkh(script_pub_key[:2] + b"\x40" + script_pub_key[3:])

    # invalid size: 11 bytes instead of 20
    err_msg = "invalid size: "
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.from_type_and_payload(script_type, "00" * 11)


def test_p2wpkh() -> None:

    # self-consistency
    pub_key = "02 cc71eb30d653c0c3163990c47b976f3fb3f37cccdcbedb169a1dfef58bbfbfaf"
    payload = hash160(pub_key)
    script_pub_key = serialize(["OP_0", payload])
    assert_p2wpkh(script_pub_key)
    assert script_pub_key == ScriptPubKey.p2wpkh(pub_key).script

    # to the script_pub_key in two steps (through payload)
    script_type = "p2wpkh"
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )

    # back from the script_pub_key to the payload
    assert (script_type, payload) == type_and_payload(script_pub_key)

    # bech32 address
    network = "mainnet"
    addr = b32.p2wpkh(pub_key, network)
    assert addr == address(script_pub_key, network)
    wit_ver = 0
    assert addr == b32.address_from_witness(wit_ver, payload, network)

    # back from the address to the script_pub_key
    assert script_pub_key == ScriptPubKey.from_address(addr).script
    assert network == ScriptPubKey.from_address(addr).network

    # p2sh-wrapped base58 address
    addr = b58.p2wpkh_p2sh(pub_key, network)
    assert addr == b58.address_from_v0_witness_program(payload, network)

    err_msg = "invalid witness version: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2wpkh(b"\x33" + script_pub_key[1:])

    err_msg = "invalid pub_key hash length marker: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2wpkh(script_pub_key[:1] + b"\x00" + script_pub_key[2:])


def test_p2sh() -> None:

    # self-consistency
    pub_key = "02 cc71eb30d653c0c3163990c47b976f3fb3f37cccdcbedb169a1dfef58bbfbfaf"
    pub_key_hash = hash160(pub_key)
    redeem_script = ScriptPubKey.from_type_and_payload("p2pkh", pub_key_hash).script
    payload = hash160(redeem_script)
    script_pub_key = serialize(["OP_HASH160", payload, "OP_EQUAL"])
    assert_p2sh(script_pub_key)
    assert script_pub_key == ScriptPubKey.p2sh(redeem_script).script

    # to the script_pub_key in two steps (through payload)
    script_type = "p2sh"
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )

    # back from the script_pub_key to the payload
    assert (script_type, payload) == type_and_payload(script_pub_key)

    # base58 address
    network = "mainnet"
    addr = b58.p2sh(redeem_script, network)
    assert addr == address(script_pub_key, network)
    prefix = NETWORKS[network].p2sh
    assert addr == b58.address_from_h160(prefix, payload, network)

    # back from the address to the script_pub_key
    assert script_pub_key == ScriptPubKey.from_address(addr).script
    assert network == ScriptPubKey.from_address(addr).network

    # documented test case: https://learnmeabitcoin.com/guide/p2sh
    payload = bytes.fromhex("748284390f9e263a4b766a75d0633c50426eb875")
    script_pub_key = bytes.fromhex("a914") + payload + bytes.fromhex("87")
    assert_p2sh(script_pub_key)
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )
    addr = "3CK4fEwbMP7heJarmU4eqA3sMbVJyEnU3V"
    assert addr == address(script_pub_key, network)
    assert script_pub_key == ScriptPubKey.from_address(addr).script
    assert network == ScriptPubKey.from_address(addr).network

    err_msg = "missing final OP_EQUAL"
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2sh(script_pub_key[:-1] + b"\x40")

    err_msg = "missing leading OP_HASH160"
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2sh(b"\x40" + script_pub_key[1:])

    err_msg = "invalid redeem script hash length marker: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2sh(script_pub_key[:1] + b"\x40" + script_pub_key[2:])

    # invalid size: 21 bytes instead of 20
    err_msg = "invalid size: "
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.from_type_and_payload(script_type, "00" * 21)


def test_p2wsh() -> None:

    # self-consistency
    pub_key = "02 cc71eb30d653c0c3163990c47b976f3fb3f37cccdcbedb169a1dfef58bbfbfaf"
    pub_key_hash = hash160(pub_key)
    redeem_script = ScriptPubKey.from_type_and_payload("p2pkh", pub_key_hash).script
    payload = sha256(redeem_script)
    script_pub_key = serialize(["OP_0", payload])
    assert_p2wsh(script_pub_key)
    assert script_pub_key == ScriptPubKey.p2wsh(redeem_script).script

    script_type = "p2wsh"
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload(script_type, payload).script
    )

    # back from the script_pub_key to the payload
    assert (script_type, payload) == type_and_payload(script_pub_key)

    # bech32 address
    network = "mainnet"
    addr = b32.p2wsh(redeem_script, network)
    assert addr == address(script_pub_key, network)
    wit_ver = 0
    assert addr == b32.address_from_witness(wit_ver, payload, network)

    # back from the address to the script_pub_key
    assert script_pub_key == ScriptPubKey.from_address(addr).script
    assert network == ScriptPubKey.from_address(addr).network

    # p2sh-wrapped base58 address
    addr = b58.p2wsh_p2sh(redeem_script, network)
    assert addr == b58.address_from_v0_witness_program(payload, network)

    err_msg = "invalid witness version: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2wsh(b"\x33" + script_pub_key[1:])

    err_msg = "invalid redeem script hash length marker: "
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2wsh(script_pub_key[:1] + b"\x00" + script_pub_key[2:])


def test_unknown() -> None:

    script_pub_key = serialize(["OP_16", 20 * b"\x00"])
    assert address(script_pub_key) == ""
    assert type_and_payload(script_pub_key) == ("unknown", script_pub_key)


def test_exceptions() -> None:

    # invalid size: 11 bytes instead of 20
    err_msg = "invalid size: "
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.from_type_and_payload("p2wpkh", "00" * 11)

    # invalid size: 33 bytes instead of 32
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.from_type_and_payload("p2wsh", "00" * 33)

    err_msg = "unknown ScriptPubKey type: "
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.from_type_and_payload("p2unkn", "00" * 32)

    # Unhandled witness version (16)
    err_msg = "unmanaged witness version: "
    addr = b32.address_from_witness(16, 20 * b"\x00")
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.from_address(addr)


def test_p2ms_1() -> None:

    # self-consistency
    pub_key0 = "04 cc71eb30d653c0c3163990c47b976f3fb3f37cccdcbedb169a1dfef58bbfbfaf f7d8a473e7e2e6d317b87bafe8bde97e3cf8f065dec022b51d11fcdd0d348ac4"
    pub_key1 = "04 61cbdcc5409fb4b4d42b51d33381354d80e550078cb532a34bfa2fcfdeb7d765 19aecc62770f5b0e4ef8551946d8a540911abe3e7854a26f39f58b25c15342af"

    # documented test case: https://learnmeabitcoin.com/guide/p2ms
    script_pub_key = bytes.fromhex(  # fmt: off
        "51"  # OP_1
        "41"  # canonical 65-bytes push
        + pub_key0
        + "41"  # noqa E148  # canonical 65-bytes push
        + pub_key1
        + "52"  # noqa E148  # OP_2
        "ae"  # OP_CHECKMULTISIG
    )  # fmt: on
    assert is_p2ms(script_pub_key)
    assert address(script_pub_key) == ""
    script_type, payload = type_and_payload(script_pub_key)
    assert script_type == "p2ms"
    assert payload == script_pub_key[:-1]
    assert script_pub_key == ScriptPubKey.from_type_and_payload("p2ms", payload).script

    err_msg = "invalid p2ms payload"
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.from_type_and_payload("p2ms", script_pub_key)

    pub_keys: List[Key] = [pub_key0, pub_key1]
    err_msg = "invalid m in m-of-n: "
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.p2ms(4, pub_keys)
    err_msg = "invalid n in m-of-n: "
    with pytest.raises(BTClibValueError, match=err_msg):
        # pylance cannot grok the following line
        ScriptPubKey.p2ms(4, [pub_key0] * 17)  # type: ignore
    err_msg = "invalid m in m-of-n: "
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.p2ms(0, pub_keys)
    err_msg = "invalid m in m-of-n: "
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.p2ms(17, pub_keys)

    err_msg = "not a private or public key: "
    with pytest.raises(BTClibValueError, match=err_msg):
        ScriptPubKey.p2ms(1, [pub_key0 + "00", pub_key1])

    script_: List[Command] = [
        "OP_1",
        pub_key0 + "00",
        pub_key1,
        "OP_2",
        "OP_CHECKMULTISIG",
    ]
    script_pub_key = serialize(script_)
    assert not is_p2ms(script_pub_key)

    err_msg = "invalid key in p2ms"
    script_pub_key = serialize(["OP_1", pub_key0, "00", "OP_2", "OP_CHECKMULTISIG"])
    assert not is_p2ms(script_pub_key)

    script_pub_key = serialize(["OP_1", pub_key0, pub_key1, "OP_2", "OP_CHECKMULTISIG"])
    assert is_p2ms(script_pub_key)

    script_pub_key = serialize(["OP_2", pub_key0, pub_key1, "OP_2", "OP_CHECKMULTISIG"])
    assert is_p2ms(script_pub_key)

    script_pub_key = serialize(["OP_0", pub_key0, pub_key1, "OP_2", "OP_CHECKMULTISIG"])
    assert not is_p2ms(script_pub_key)

    script_pub_key = serialize(["OP_3", pub_key0, pub_key1, "OP_2", "OP_CHECKMULTISIG"])
    assert not is_p2ms(script_pub_key)

    script_pub_key = serialize(["OP_1", "OP_2", "OP_CHECKMULTISIG"])
    assert not is_p2ms(script_pub_key)

    script_pub_key = serialize(["OP_1", pub_key0, "OP_2", "OP_CHECKMULTISIG"])
    assert not is_p2ms(script_pub_key)

    script_pub_key = serialize(["OP_1", pub_key0, pub_key1, "OP_3", "OP_CHECKMULTISIG"])
    assert not is_p2ms(script_pub_key)

    pub_key2 = "04 79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798 483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8"
    script_pub_key = serialize(
        ["OP_1", pub_key0, pub_key1, pub_key2, "OP_3", "OP_CHECKMULTISIG"]
    )
    assert_p2ms(script_pub_key)

    err_msg = "invalid p2ms script_pub_key size"
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2ms(script_pub_key[:133] + b"\x40" + script_pub_key[134:])
    with pytest.raises(BTClibValueError, match=err_msg):
        assert_p2ms(script_pub_key[:-2] + b"\x00" + script_pub_key[-2:])


def test_p2ms_2() -> None:

    m = 1

    # all uncompressed
    pub_key0 = "04 cc71eb30d653c0c3163990c47b976f3fb3f37cccdcbedb169a1dfef58bbfbfaf f7d8a473e7e2e6d317b87bafe8bde97e3cf8f065dec022b51d11fcdd0d348ac4"
    pub_key1 = "04 61cbdcc5409fb4b4d42b51d33381354d80e550078cb532a34bfa2fcfdeb7d765 19aecc62770f5b0e4ef8551946d8a540911abe3e7854a26f39f58b25c15342af"
    pub_key2 = "04 79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798 483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8"
    uncompressed_pub_keys: List[Key] = [pub_key0, pub_key1, pub_key2]
    # mixed compressed / uncompressed public keys
    pub_key0 = "04 cc71eb30d653c0c3163990c47b976f3fb3f37cccdcbedb169a1dfef58bbfbfaf f7d8a473e7e2e6d317b87bafe8bde97e3cf8f065dec022b51d11fcdd0d348ac4"
    pub_key1 = "03 61cbdcc5409fb4b4d42b51d33381354d80e550078cb532a34bfa2fcfdeb7d765"
    pub_key2 = "02 79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
    mixed_pub_keys: List[Key] = [pub_key0, pub_key1, pub_key2]

    for pub_keys in (uncompressed_pub_keys, mixed_pub_keys):
        for lexi_sort in (True, False):
            script_pub_key = ScriptPubKey.p2ms(m, pub_keys, lexi_sort=lexi_sort).script
            assert is_p2ms(script_pub_key)
            assert address(script_pub_key) == ""
            script_type, payload = type_and_payload(script_pub_key)
            assert script_type == "p2ms"
            assert payload == script_pub_key[:-1]
            assert (
                script_pub_key
                == ScriptPubKey.from_type_and_payload("p2ms", payload).script
            )


def test_p2ms_3() -> None:
    # tx_id 33ac2af1a6f894276713b59ed09ce1a20fed5b36d169f20a3fe831dc45564d57
    # output n 0
    keys: List[Command] = [
        "036D568125A969DC78B963B494FA7ED5F20EE9C2F2FC2C57F86C5DF63089F2ED3A",
        "03FE4E6231D614D159741DF8371FA3B31AB93B3D28A7495CDAA0CD63A2097015C7",
    ]
    cmds: List[Command] = ["OP_1", *keys, "OP_2", "OP_CHECKMULTISIG"]
    script_pub_key = ScriptPubKey(serialize(cmds))
    assert script_pub_key == ScriptPubKey.p2ms(1, keys)

    pub_keys = script_pub_key.addresses
    exp_pub_keys = [
        "1Ng4YU2e2H3E86syX2qrsmD9opBHZ42vCF",
        "14XufxyGiY6ZBJsFYHJm6awdzpJdtsP1i3",
    ]
    for pub_key, key, exp_pub_key in zip(pub_keys, keys, exp_pub_keys):
        assert pub_key == b58.p2pkh(key)
        assert pub_key == exp_pub_key

    # tx 56214420a7c4dcc4832944298d169a75e93acf9721f00656b2ee0e4d194f9970
    # input n 1
    cmds_sig: List[Command] = [
        "OP_0",
        "3045022100dba1e9b1c8477fd364edcc1f81845928202daf465a1e2d92904c13c88761cbd002200add6af863dfdb7efb95f334baec041e90811ae9d81624f9f87f33a56761f29401",
    ]
    script_sig = Script(serialize(cmds_sig))
    script = script_sig + script_pub_key
    # parse(serialize(*)) is to enforce same string case convention
    assert script.asm == parse(serialize(cmds_sig + cmds))

    # TODO: evaluate


def test_bip67() -> None:
    "BIP67 test vectors https://en.bitcoin.it/wiki/BIP_0067"

    data_folder = path.join(path.dirname(__file__), "_data")
    filename = path.join(data_folder, "bip67_test_vectors.json")
    with open(filename, "r") as file_:
        # json.dump(test_vectors, f, indent=4)
        test_vectors = json.load(file_)

    m = 2
    for i in test_vectors:
        keys, addr = test_vectors[i]

        script_pub_key = ScriptPubKey.p2ms(m, keys, lexi_sort=True).script
        assert is_p2ms(script_pub_key)
        assert address(script_pub_key) == ""
        script_type, payload = type_and_payload(script_pub_key)
        assert script_type == "p2ms"
        assert payload == script_pub_key[:-1]
        assert (
            script_pub_key == ScriptPubKey.from_type_and_payload("p2ms", payload).script
        )

        errmsg = f"Test vector #{i}"
        assert addr == b58.p2sh(script_pub_key), errmsg


def test_non_standard_script_in_p2wsh() -> None:

    network = "mainnet"

    fed_pub_keys: List[Command] = ["00" * 33, "11" * 33, "22" * 33]
    rec_pub_keys: List[Command] = ["77" * 33, "88" * 33, "99" * 33]
    # fmt: off
    redeem_script_cmds: List[Command] = [
        "OP_IF",
            "OP_2", *fed_pub_keys, "OP_3", "OP_CHECKMULTISIG",  # noqa E131
        "OP_ELSE",
            500, "OP_CHECKLOCKTIMEVERIFY", "OP_DROP",  # noqa E131
            "OP_2", *rec_pub_keys, "OP_3", "OP_CHECKMULTISIG",  # noqa E131
        "OP_ENDIF",
    ]
    # fmt: on
    redeem_script = serialize(redeem_script_cmds)
    assert redeem_script_cmds == parse(redeem_script)
    payload = sha256(redeem_script)
    script_pub_key = (
        "00207b5310339c6001f75614daa5083839fa54d46165f6c56025cc54d397a85a5708"
    )
    assert script_pub_key == ScriptPubKey.p2wsh(redeem_script).script.hex()
    assert (
        script_pub_key
        == ScriptPubKey.from_type_and_payload("p2wsh", payload).script.hex()
    )

    addr = "bc1q0df3qvuuvqqlw4s5m2jsswpelf2dgct97mzkqfwv2nfe02z62uyq7n4zjj"
    assert addr == address(script_pub_key, network)
    assert addr == b32.address_from_witness(0, payload, network)
