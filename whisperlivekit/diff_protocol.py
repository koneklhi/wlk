"""Delta-based WebSocket output protocol for WhisperLiveKit.

Instead of sending the full FrontData state on every update, the DiffTracker
computes incremental diffs — only sending new/changed lines and volatile fields.
This is the **default** output protocol (``--ws-protocol delta``); clients that
cannot accumulate state can opt out with ``?mode=full``.

Protocol
--------
``ws://host:port/asr`` (default, or explicit ``?mode=delta``)

First message from server:
    ``{"type": "snapshot", "seq": 1, ...full state...}``

Subsequent messages:
    ``{"type": "diff", "seq": N, "n_lines": M, "new_lines": [...], ...}``

``new_lines`` is NOT an append-only tail
----------------------------------------
``new_lines`` is everything after the **common prefix** with the previously sent
state — i.e. the whole *tail* of the current line list. The backend may
retroactively rewrite recently emitted lines (reconciliation / silence-gate
re-open within ~8s), and when it does, those already-sent lines are re-included
in ``new_lines`` with their updated content. A client that blindly appends
``new_lines`` therefore **duplicates** lines. The correct operation is
**tail replacement**.

Client reconstruction algorithm
-------------------------------
1. On ``"snapshot"``: ``lines = msg["lines"]`` (replace all state, drop any
   previously accumulated lines).
2. On ``"diff"``:
   a. Prune the front:      ``if msg.get("lines_pruned"): del lines[:msg["lines_pruned"]]``
   b. Compute the common prefix length:
      ``common = msg["n_lines"] - len(msg.get("new_lines", []))``
   c. Replace the tail:     ``lines = lines[:common] + msg.get("new_lines", [])``
   d. Replace the volatile fields verbatim: ``buffer_transcription``,
      ``buffer_diarization``, ``buffer_translation``,
      ``remaining_time_transcription``, ``remaining_time_diarization``,
      ``status`` (and ``error`` when present).
   e. Verify sync: ``len(lines) == msg["n_lines"]``. A mismatch means the client
      lost a message or mis-applied a diff — reconnect to get a fresh snapshot.

Lines are identified by ``id`` (= ``round(start, 3)``, the stable segment key).
Use ``id`` **alone** for dedup / render keys — never a composite key with
``end``/``text``, which grow as a segment is extended.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from whisperlivekit.timed_objects import FrontData


@dataclass
class DiffTracker:
    """Tracks FrontData state and computes incremental diffs."""

    seq: int = 0
    _prev_lines: List[Dict[str, Any]] = field(default_factory=list)
    _sent_snapshot: bool = False

    def to_message(self, front_data: FrontData, session_start: Optional[float] = None) -> Dict[str, Any]:
        """Convert a FrontData into a diff or snapshot message.

        First call returns a full snapshot. Subsequent calls return diffs
        containing only changed/new data.
        """
        self.seq += 1
        full = front_data.to_dict(session_start)
        current_lines = full["lines"]

        if not self._sent_snapshot:
            self._sent_snapshot = True
            self._prev_lines = current_lines[:]
            return {"type": "snapshot", "seq": self.seq, **full}

        # Compute diff
        msg: Dict[str, Any] = {
            "type": "diff",
            "seq": self.seq,
            "status": full["status"],
            "n_lines": len(current_lines),
            "buffer_transcription": full["buffer_transcription"],
            "buffer_diarization": full["buffer_diarization"],
            "buffer_translation": full["buffer_translation"],
            "remaining_time_transcription": full["remaining_time_transcription"],
            "remaining_time_diarization": full["remaining_time_diarization"],
        }
        if full.get("error"):
            msg["error"] = full["error"]

        # Detect front-pruning: find where current[0] appears in prev
        prune_offset = 0
        if current_lines and self._prev_lines:
            first_current = current_lines[0]
            for i, prev_line in enumerate(self._prev_lines):
                if prev_line == first_current:
                    prune_offset = i
                    break
            else:
                # current[0] not found in prev — treat all prev as pruned
                prune_offset = len(self._prev_lines)
        elif not current_lines:
            prune_offset = len(self._prev_lines)

        if prune_offset > 0:
            msg["lines_pruned"] = prune_offset

        # Find common prefix starting after pruned lines
        common = 0
        remaining_prev = len(self._prev_lines) - prune_offset
        min_len = min(remaining_prev, len(current_lines))
        while common < min_len and self._prev_lines[prune_offset + common] == current_lines[common]:
            common += 1

        # New or changed lines after the common prefix
        new_lines = current_lines[common:]
        if new_lines:
            msg["new_lines"] = new_lines

        self._prev_lines = current_lines[:]
        return msg

    def reset(self) -> None:
        """Reset state so the next call produces a fresh snapshot."""
        self.seq = 0
        self._prev_lines = []
        self._sent_snapshot = False
