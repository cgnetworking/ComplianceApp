from __future__ import annotations

import os
from pathlib import Path


def _decode_env_value(raw_value: str) -> str:
    if len(raw_value) < 2:
        return raw_value

    quote = raw_value[0]
    if quote not in {"'", '"'} or raw_value[-1] != quote:
        return raw_value

    inner = raw_value[1:-1]
    if quote == "'":
        return inner

    decoded = []
    idx = 0
    while idx < len(inner):
        char = inner[idx]
        if char == "\\" and idx + 1 < len(inner):
            escaped = inner[idx + 1]
            if escaped in {'\\', '"', '$', '`'}:
                decoded.append(escaped)
                idx += 2
                continue
        decoded.append(char)
        idx += 1
    return "".join(decoded)


def load_dotenv(dotenv_path: Path | None = None) -> None:
    env_path = dotenv_path or Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        value = _decode_env_value(value)

        os.environ[key] = value
