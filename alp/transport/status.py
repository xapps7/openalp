from __future__ import annotations

"""Execution status and error classification for ALP transports.

Defined by spec/transport-semantics-v0.2.md.
"""

# Non-terminal
ACCEPTED = "accepted"
RUNNING = "running"
RETRYING = "retrying"

# Terminal
SUCCEEDED = "succeeded"
FAILED = "failed"
REJECTED = "rejected"
EXPIRED = "expired"
DUPLICATE = "duplicate"

ALL_STATUSES = (
    ACCEPTED,
    RUNNING,
    RETRYING,
    SUCCEEDED,
    FAILED,
    REJECTED,
    EXPIRED,
    DUPLICATE,
)

TERMINAL_STATUSES = frozenset({SUCCEEDED, FAILED, REJECTED, EXPIRED, DUPLICATE})

# Error classes
TRANSIENT = "transient"
PERMANENT = "permanent"
PROTOCOL = "protocol"

ERROR_CLASSES = (TRANSIENT, PERMANENT, PROTOCOL)

RETRYABLE_ERROR_CLASSES = frozenset({TRANSIENT})


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def is_retryable(error_class: str) -> bool:
    return error_class in RETRYABLE_ERROR_CLASSES
