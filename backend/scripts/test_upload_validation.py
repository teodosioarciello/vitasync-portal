"""
Test deterministico Sprint C-media Step 1.
Verifica magic-byte e limiti upload senza passare dal browser.

Da eseguire dentro il container backend:
    docker compose exec backend python scripts/test_upload_validation.py
"""

import io
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import HTTPException

from app.services.upload_validation import validate_upload_stream

failures: list[str] = []


def expect_ok(name: str, data: bytes, expected_mime: str) -> None:
    try:
        got = validate_upload_stream(io.BytesIO(data))
    except HTTPException as exc:
        failures.append(f"{name}: atteso OK, ricevuto HTTP {exc.status_code} - {exc.detail}")
        print(f"KO {name}: HTTP {exc.status_code} - {exc.detail}")
        return
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{name}: eccezione inattesa {exc!r}")
        print(f"KO {name}: eccezione inattesa {exc!r}")
        return

    if got != expected_mime:
        failures.append(f"{name}: atteso {expected_mime}, ricevuto {got}")
        print(f"KO {name}: atteso {expected_mime}, ricevuto {got}")
    else:
        print(f"OK {name}: {got}")


def expect_http_error(
    name: str,
    data: bytes,
    expected_status: int,
    max_bytes: int | None = None,
) -> None:
    try:
        kwargs = {}
        if max_bytes is not None:
            kwargs["max_bytes"] = max_bytes
        got = validate_upload_stream(io.BytesIO(data), **kwargs)
    except HTTPException as exc:
        if exc.status_code != expected_status:
            failures.append(
                f"{name}: atteso HTTP {expected_status}, ricevuto {exc.status_code} - {exc.detail}"
            )
            print(f"KO {name}: atteso HTTP {expected_status}, ricevuto {exc.status_code} - {exc.detail}")
        else:
            print(f"OK {name}: HTTP {exc.status_code} - {exc.detail}")
        return
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{name}: eccezione inattesa {exc!r}")
        print(f"KO {name}: eccezione inattesa {exc!r}")
        return

    failures.append(f"{name}: atteso errore HTTP {expected_status}, invece accettato come {got}")
    print(f"KO {name}: atteso errore HTTP {expected_status}, invece accettato come {got}")


def main() -> int:
    pdf = b"%PDF-1.4\n% fake synthetic pdf for tests\n" + b"x" * 200
    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"y" * 200
    png = b"\x89PNG\r\n\x1a\n" + b"z" * 200
    text = b"Questo non e un PDF valido, e solo testo."
    empty = b""
    large_pdf = b"%PDF-1.4" + b"a" * 100

    expect_ok("PDF valido", pdf, "application/pdf")
    expect_ok("JPEG valido", jpeg, "image/jpeg")
    expect_ok("PNG valido", png, "image/png")

    expect_http_error("Testo rinominato PDF", text, 415)
    expect_http_error("File vuoto", empty, 400)
    expect_http_error("File troppo grande", large_pdf, 413, max_bytes=10)

    print()
    if failures:
        print("TEST FALLITI:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("Tutti i test di validazione upload sono passati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())