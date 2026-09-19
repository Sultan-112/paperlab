"""Low-cardinality, secret-free events for local monitoring and log collectors."""

import json
import logging
from datetime import datetime, timezone

from libs.metrics import SECURITY_EVENTS

logger = logging.getLogger("paperlab.security")


def security_event(kind: str, outcome: str, **details):
    """Only fixed event names and explicit non-sensitive details belong here."""
    SECURITY_EVENTS.labels(kind, outcome).inc()
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "component": "paperlab-api",
        "category": "security",
        "event": kind,
        "outcome": outcome,
        **details,
    }
    logger.warning(json.dumps(record, separators=(",", ":")))
