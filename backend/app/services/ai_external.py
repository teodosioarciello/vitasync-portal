"""
Sprint 6.1 - Client AI esterna opzionale.
Regole:
- default off gestito dall'endpoint;
- invia solo contenuto gia' pseudonimizzato;
- verifica che non contenga identificatori reali passati dal chiamante;
- non salva risposte;
- risponde sempre con disclaimer forte.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

ALLOWED_PROVIDERS = {"ollama", "openai", "anthropic", "mock"}

SYSTEM_PROMPT_IT = (
    "Sei un assistente sanitario prudenziale. Ricevi solo dati pseudonimizzati. "
    "Non formulare diagnosi. Non consigliare terapie, dosaggi, sospensioni o interruzioni. "
    "Non affermare rapporti di causa-effetto tra farmaci e valori. "
    "Non dire che va tutto bene. Descrivi solo cio' che emerge dai dati allegati e prepara domande da portare al medico. "
    "Se i dati sono insufficienti, dillo esplicitamente. Rispondi in italiano."
)

AI_DISCLAIMER_IT = (
    "Risposta generata da un modello AI esterno su dati pseudonimizzati. "
    "Non e' una diagnosi, non sostituisce il medico e non deve guidare decisioni terapeutiche."
)


def _mask(value: str) -> str:
    value = str(value)
    if len(value) <= 3:
        return "***"
    return value[:2] + "***"


def assert_no_identifiers(text: str, forbidden_values: list, label: str = "payload") -> None:
    """
    Solleva ValueError se nel testo e' presente uno degli identificatori reali forniti.
    Usato come ultima guardia prima di inviare dati a un provider esterno.
    """
    lowered = (text or "").lower()
    for value in forbidden_values or []:
        if value is None:
            continue
        s = str(value).strip()
        if len(s) < 3:
            continue
        if s.lower() in lowered:
            raise ValueError(f"{label}: identificatore reale trovato: {_mask(s)}")


def _truncate(text: str, max_chars: int | None) -> str:
    if not max_chars or max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Contenuto troncato per limite di sicurezza.]"


def build_ai_user_prompt(markdown_export: str) -> str:
    return (
        "Analizza esclusivamente il seguente export sanitario pseudonimizzato. "
        "Non inventare dati assenti. Non formulare diagnosi. "
        "Produci: 1) sintesi prudente, 2) possibili punti di attenzione basati solo sui dati, "
        "3) domande concrete da fare al medico, 4) limiti dell'analisi.\n\n"
        + markdown_export
    )


def _http_post_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} da provider AI: {err[:500]}")
    except Exception as exc:
        raise RuntimeError(f"Errore chiamata provider AI: {exc}")


def _mock_answer() -> str:
    return (
        "Risposta simulata (provider mock, nessuna AI esterna contattata).\n\n"
        "Questo mock serve solo a verificare il flusso tecnico di VitaSync. "
        "Non analizza i dati e non deve essere usato come parere clinico.\n\n"
        "Domande di esempio da portare al medico:\n"
        "- Quali valori dovrei monitorare nel tempo?\n"
        "- Ci sono esami da ripetere o approfondire?\n"
        "- Le terapie registrate sono coerenti con il quadro complessivo?\n\n"
        "Limiti: risposta deterministica di test, non diagnosi, non consiglio terapeutico."
    )


def call_external_ai(
    *,
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 30,
    max_prompt_chars: int | None = 12000,
) -> dict:
    provider = (provider or "").lower().strip()
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(f"Provider AI non consentito: {provider}")

    user_prompt = _truncate(user_prompt, max_prompt_chars)

    if provider == "mock":
        text = _mock_answer()
    else:
        if not base_url:
            raise ValueError("Base URL provider AI mancante")
        if provider in ("openai", "anthropic") and not api_key:
            raise ValueError("API key provider AI mancante")

        base = base_url.rstrip("/")

        if provider == "openai":
            url = base + "/chat/completions"
            payload = {
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = _http_post_json(url, payload, headers, timeout)
            text = (
                resp.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

        elif provider == "anthropic":
            url = base + "/messages"
            payload = {
                "model": model,
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            resp = _http_post_json(url, payload, headers, timeout)
            text = (
                resp.get("content", [{}])[0]
                .get("text", "")
            )

        else:  # ollama
            url = base + "/api/chat"
            payload = {
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            resp = _http_post_json(url, payload, {}, timeout)
            text = resp.get("message", {}).get("content", "")

    text = (text or "").strip()
    if not text:
        raise RuntimeError("Risposta vuota dal provider AI")

    return {
        "answer": text,
        "provider": provider,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": AI_DISCLAIMER_IT,
        "data_scope": "pseudonimizzato",
        "stored": False,
    }