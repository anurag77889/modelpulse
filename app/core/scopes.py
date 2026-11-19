"""
OAuth 2.0 scopes understood by this API.

User logins receive every scope. Machine clients (client credentials
grant) receive only the scopes they were registered with, so an ML
pipeline can be limited to e.g. predictions:write.
"""

SCOPES: dict[str, str] = {
    "models:read": "Read models and model summaries",
    "models:write": "Create, update and delete models",
    "predictions:read": "Read predictions and prediction stats",
    "predictions:write": "Log predictions and attach ground-truth labels",
    "alerts:read": "Read alerts and alert stats",
    "alerts:write": "Resolve alerts",
}

ALL_SCOPES: frozenset[str] = frozenset(SCOPES)


def parse_scope(scope: str | None) -> set[str]:
    """Split an RFC 6749 space-delimited scope string into a set."""
    return set(scope.split()) if scope else set()


def format_scope(scopes: set[str] | frozenset[str]) -> str:
    """Join scopes into a stable, space-delimited string."""
    return " ".join(sorted(scopes))
