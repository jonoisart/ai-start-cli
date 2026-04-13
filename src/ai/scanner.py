"""GGUF file discovery and binary header parsing."""
import re
import struct
from pathlib import Path

FILE_TYPE_NAMES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1",
    7: "Q8_0", 8: "Q5_0", 9: "Q5_1",
    10: "Q2_K", 11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L",
    14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M",
    18: "Q6_K", 19: "IQ2_XXS", 20: "IQ2_XS",
    21: "IQ2_M", 22: "IQ1_M", 23: "IQ4_K_S", 24: "IQ4_K_M",
    25: "IQ3_K_S", 26: "IQ3_K_M", 27: "IQ3_K_L",
    28: "IQ4_NL", 29: "IQ3_S", 30: "IQ3_M",
    31: "IQ1_S", 32: "IQ4_XS",
}

GGUF_MAGIC = b"GGUF"

# Scalar value type → (struct_fmt, byte_size)
_SCALAR_FMT = {
    0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2),
    4: ("<I", 4), 5: ("<i", 4), 6: ("<f", 4), 7: ("<B", 1),
    10: ("<Q", 8), 11: ("<q", 8), 12: ("<d", 8),
}


def _read_str(f, version: int) -> str:
    length = struct.unpack("<I" if version == 1 else "<Q", f.read(4 if version == 1 else 8))[0]
    return f.read(length).decode("utf-8", errors="replace")


def _skip_array(f, version: int) -> None:
    elem_type = struct.unpack("<I", f.read(4))[0]
    count = struct.unpack("<I" if version == 1 else "<Q", f.read(4 if version == 1 else 8))[0]
    if elem_type in _SCALAR_FMT:
        _, size = _SCALAR_FMT[elem_type]
        f.seek(count * size, 1)
    elif elem_type == 8:  # array of strings
        for _ in range(count):
            slen = struct.unpack("<I" if version == 1 else "<Q", f.read(4 if version == 1 else 8))[0]
            f.seek(slen, 1)
    # nested arrays (type 9) are extremely rare — outer except catches any failure


def _read_scalar(f, value_type: int, version: int):
    if value_type == 8:
        return _read_str(f, version)
    fmt, size = _SCALAR_FMT[value_type]
    return struct.unpack(fmt, f.read(size))[0]


def parse_gguf_header(path: Path) -> dict:
    """
    Read GGUF binary header and return {arch, quant, ctx, params}.
    Returns {} on any parse failure.
    """
    try:
        with open(path, "rb") as f:
            if f.read(4) != GGUF_MAGIC:
                return {}

            version = struct.unpack("<I", f.read(4))[0]
            int_fmt = "<I" if version == 1 else "<Q"
            int_size = 4 if version == 1 else 8

            f.read(int_size)  # tensor count — skip
            kv_count = struct.unpack(int_fmt, f.read(int_size))[0]

            result = {}

            for _ in range(kv_count):
                key = _read_str(f, version)
                value_type = struct.unpack("<I", f.read(4))[0]

                if value_type == 9:  # array — skip
                    _skip_array(f, version)
                    continue

                value = _read_scalar(f, value_type, version)

                if key == "general.architecture":
                    arch = value
                    result["arch"] = arch
                elif key == "general.file_type":
                    result["quant"] = FILE_TYPE_NAMES.get(value, f"type_{value}")
                elif key == "general.parameter_count":
                    result["params"] = _format_params(value)
                elif key.endswith(".context_length"):
                    result["ctx"] = value

                # Stop once we have all four fields
                if len(result) == 4:
                    break

        return result
    except Exception:
        return {}


def _format_params(count: int) -> str:
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.0f}B"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.0f}M"
    return str(count)


def nickname_from_filename(path: Path) -> str:
    stem = path.stem
    # Cut at quantization pattern (e.g. -Q8_0, _Q4_K_M)
    m = re.search(r"[-_][Ii][Qq][0-9]|[-_][Qq][0-9]", stem)
    if m:
        stem = stem[: m.start()]
    nick = re.sub(r"[^a-zA-Z0-9]+", "-", stem).lower().strip("-")
    return nick[:32]


DEFAULT_SCAN_PATHS = [
    "~/.cache/huggingface/hub",
    "~/.cache/llama.cpp",
    "~/Downloads",
    "/Volumes",
]


def find_ggufs(path: str, depth: int = 5) -> list:
    root = Path(path).expanduser()
    if not root.exists():
        return []
    return _walk(root, depth)


def _walk(directory: Path, depth: int) -> list:
    if depth < 0:
        return []
    results = []
    try:
        for entry in directory.iterdir():
            if entry.is_file() and entry.suffix.lower() == ".gguf":
                results.append(entry)
            elif entry.is_dir() and not entry.is_symlink():
                results.extend(_walk(entry, depth - 1))
    except PermissionError:
        pass
    return results


def is_registered(path: Path, registry: dict) -> bool:
    registered_paths = {m["path"] for m in registry.get("models", {}).values()}
    return str(path) in registered_paths
