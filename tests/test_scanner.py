import struct
import pytest
from pathlib import Path
from ai import scanner


# --- helpers ---

def gguf_v3(metadata: list) -> bytes:
    """
    Build a minimal valid GGUF v3 byte sequence.
    metadata: list of (key, value_type, value)
      value_type 4=uint32, 8=string, 10=uint64
    """
    buf = b"GGUF"
    buf += struct.pack("<I", 3)               # version 3
    buf += struct.pack("<Q", 0)               # tensor count
    buf += struct.pack("<Q", len(metadata))   # kv count
    for key, vtype, value in metadata:
        key_b = key.encode()
        buf += struct.pack("<Q", len(key_b)) + key_b
        buf += struct.pack("<I", vtype)
        if vtype == 8:
            val_b = value.encode()
            buf += struct.pack("<Q", len(val_b)) + val_b
        elif vtype == 4:
            buf += struct.pack("<I", value)
        elif vtype == 10:
            buf += struct.pack("<Q", value)
    return buf


# --- parse_gguf_header ---

def test_parse_returns_empty_for_non_gguf(tmp_path):
    f = tmp_path / "fake.gguf"
    f.write_bytes(b"NOT_GGUF_DATA")
    assert scanner.parse_gguf_header(f) == {}


def test_parse_returns_empty_for_missing_file(tmp_path):
    assert scanner.parse_gguf_header(tmp_path / "nope.gguf") == {}


def test_parse_extracts_arch(tmp_path):
    data = gguf_v3([("general.architecture", 8, "qwen2")])
    f = tmp_path / "model.gguf"
    f.write_bytes(data)
    result = scanner.parse_gguf_header(f)
    assert result["arch"] == "qwen2"


def test_parse_extracts_quant(tmp_path):
    # general.file_type = 7 → Q8_0
    data = gguf_v3([
        ("general.architecture", 8, "llama"),
        ("general.file_type", 4, 7),
    ])
    f = tmp_path / "model.gguf"
    f.write_bytes(data)
    result = scanner.parse_gguf_header(f)
    assert result["quant"] == "Q8_0"


def test_parse_extracts_ctx(tmp_path):
    data = gguf_v3([
        ("general.architecture", 8, "qwen2"),
        ("qwen2.context_length", 4, 131072),
    ])
    f = tmp_path / "model.gguf"
    f.write_bytes(data)
    result = scanner.parse_gguf_header(f)
    assert result["ctx"] == 131072


def test_parse_extracts_params(tmp_path):
    data = gguf_v3([
        ("general.architecture", 8, "llama"),
        ("general.parameter_count", 10, 7_000_000_000),
    ])
    f = tmp_path / "model.gguf"
    f.write_bytes(data)
    result = scanner.parse_gguf_header(f)
    assert result["params"] == "7B"


def test_parse_skips_array_values(tmp_path):
    # Array of uint32 followed by a real key we care about
    array_block = struct.pack("<I", 4)   # elem type uint32
    array_block += struct.pack("<Q", 3)  # 3 elements
    array_block += struct.pack("<III", 1, 2, 3)

    buf = b"GGUF"
    buf += struct.pack("<I", 3)   # version
    buf += struct.pack("<Q", 0)   # tensor count
    buf += struct.pack("<Q", 2)   # 2 kv entries

    # Entry 1: array
    key = b"some.array"
    buf += struct.pack("<Q", len(key)) + key
    buf += struct.pack("<I", 9)   # array type
    buf += array_block

    # Entry 2: real key
    key2 = b"general.architecture"
    buf += struct.pack("<Q", len(key2)) + key2
    buf += struct.pack("<I", 8)   # string type
    arch = b"gemma3"
    buf += struct.pack("<Q", len(arch)) + arch

    f = tmp_path / "model.gguf"
    f.write_bytes(buf)
    result = scanner.parse_gguf_header(f)
    assert result["arch"] == "gemma3"


# --- nickname_from_filename ---

def test_nickname_strips_quant_suffix():
    p = Path("Qwen3.5-9B-Uncensored-Q8_0.gguf")
    nick = scanner.nickname_from_filename(p)
    assert "q8" not in nick.lower()
    assert nick.startswith("qwen")


def test_nickname_is_lowercase_hyphenated():
    p = Path("Mistral_7B_Instruct_Q4_K_M.gguf")
    nick = scanner.nickname_from_filename(p)
    assert nick == nick.lower()
    assert "_" not in nick


def test_nickname_max_32_chars():
    p = Path("very-long-model-name-that-exceeds-normal-length-Q4_K_M.gguf")
    nick = scanner.nickname_from_filename(p)
    assert len(nick) <= 32
