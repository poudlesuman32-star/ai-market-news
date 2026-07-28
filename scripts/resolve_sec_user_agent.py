from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

APPLICATION_NAME = "PPI Universe Research"
EMAIL = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.IGNORECASE,
)
REJECTED_DOMAIN_SUFFIXES = (
    "example.com",
    "example.org",
    "example.net",
    "localhost",
    "noreply.github.com",
    "users.noreply.github.com",
)


class ResolverError(RuntimeError):
    pass


def normalize(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def rejected_domain(domain: str) -> bool:
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in REJECTED_DOMAIN_SUFFIXES)


def validate_email(value: object) -> str:
    email = normalize(value).lower()
    if not email or len(email) > 254 or not EMAIL.fullmatch(email):
        raise ResolverError("SEC contact email is missing or invalid")
    local, domain = email.rsplit("@", 1)
    if local in {"noreply", "no-reply", "donotreply", "do-not-reply"}:
        raise ResolverError("SEC contact email must be monitored")
    if rejected_domain(domain) or domain.endswith(".invalid") or domain.endswith(".example"):
        raise ResolverError("SEC contact email uses a non-contact domain")
    return email


def read_owner_email(path: Path) -> str | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("email") is None:
        return None
    try:
        return validate_email(value["email"])
    except ResolverError:
        return None


def resolve(configured_email: str, owner_json: Path) -> dict:
    email = None
    source = None
    if normalize(configured_email):
        email = validate_email(configured_email)
        source = "repository_contact_variable"
    else:
        email = read_owner_email(owner_json)
        if email:
            source = "github_public_profile"

    if not email:
        return {
            "status": "blocked",
            "resolved": False,
            "source": None,
            "reason": (
                "No validated SEC contact email was available from PPI_SEC_CONTACT_EMAIL "
                "or the repository owner's public GitHub profile"
            ),
        }

    user_agent = f"{APPLICATION_NAME} {email}"
    if any(character in user_agent for character in "\r\n") or len(user_agent) > 512:
        raise ResolverError("Resolved SEC user agent is unsafe")
    return {
        "status": "resolved",
        "resolved": True,
        "source": source,
        "application_name": APPLICATION_NAME,
        "contact_email_sha256": digest(email),
        "user_agent_sha256": digest(user_agent),
        "user_agent": user_agent,
    }


def append_environment(path: Path, key: str, value: str) -> None:
    if any(character in value for character in "\r\n"):
        raise ResolverError("Environment value must be one line")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def append_outputs(path: Path | None, values: dict[str, object]) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            text = str(value).lower() if isinstance(value, bool) else str(value or "")
            if any(character in text for character in "\r\n"):
                raise ResolverError("GitHub output value must be one line")
            handle.write(f"{key}={text}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configured-email", default="")
    parser.add_argument("--owner-json", type=Path, required=True)
    parser.add_argument("--github-env", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    result = resolve(args.configured_email, args.owner_json)
    append_environment(
        args.github_env,
        "PPI_SEC_USER_AGENT",
        str(result.get("user_agent") or ""),
    )
    append_outputs(
        args.github_output,
        {
            "resolved": result["resolved"],
            "source": result.get("source") or "none",
            "reason": result.get("reason") or "",
            "user_agent_sha256": result.get("user_agent_sha256") or "",
        },
    )
    print(json.dumps({key: value for key, value in result.items() if key != "user_agent"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
