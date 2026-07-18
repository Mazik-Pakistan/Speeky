"""
Namespaced key/value store used by the ported feature services (interview_coach,
session_memory, resume_jd). The incoming code was written against an in-memory
`app.core.store` with create/get/update/list_values; this backs that same interface
with the prisma KvEntry table so state now persists.

Values are arbitrary nested dicts that may contain datetime and (str) Enum members.
JSON can't hold datetimes, so _encode/_decode round-trip them through a tagged marker;
str-Enums are stored as their .value (they compare/hash equal to it, so the feature
code keeps working). Reads return fresh decoded copies — callers mutate the returned
dict then call update(), matching the original in-memory semantics.

`store` is a module-level singleton swapped for InMemoryKvStore in tests.
"""

import copy
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from prisma import Json

from lib.prisma_client import db

_DT_TAG = "__dt__"


def _encode(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return {_DT_TAG: obj.isoformat()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_encode(v) for v in obj]
    return obj


def _decode(obj: Any) -> Any:
    if isinstance(obj, dict):
        if len(obj) == 1 and _DT_TAG in obj:
            return datetime.fromisoformat(obj[_DT_TAG])
        return {k: _decode(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode(v) for v in obj]
    return obj


def _user_id_of(value: Dict) -> Optional[str]:
    if not isinstance(value, dict):
        return None
    return value.get("user_id") or value.get("userId")


class PrismaKvStore:
    """Persistent store backed by the KvEntry table."""

    async def create(self, namespace: str, key: str, value: Dict) -> Dict:
        await db.kventry.create(
            data={
                "namespace": namespace,
                "key": key,
                "userId": _user_id_of(value),
                "value": Json(_encode(value)),
            }
        )
        return value

    async def get(self, namespace: str, key: str) -> Optional[Dict]:
        row = await db.kventry.find_unique(
            where={"namespace_key": {"namespace": namespace, "key": key}}
        )
        return _decode(row.value) if row else None

    async def update(self, namespace: str, key: str, value: Dict) -> Dict:
        await db.kventry.update(
            where={"namespace_key": {"namespace": namespace, "key": key}},
            data={"userId": _user_id_of(value), "value": Json(_encode(value))},
        )
        return value

    async def list_values(self, namespace: str) -> List[Dict]:
        rows = await db.kventry.find_many(where={"namespace": namespace})
        return [_decode(r.value) for r in rows]


class InMemoryKvStore:
    """In-process store for tests. Mirrors PrismaKvStore's JSON round-trip (datetime
    marker + enum→value + decoupled copies) so tests exercise identical semantics."""

    def __init__(self):
        self._data: Dict[tuple, Any] = {}

    async def create(self, namespace: str, key: str, value: Dict) -> Dict:
        self._data[(namespace, key)] = _encode(value)
        return value

    async def get(self, namespace: str, key: str) -> Optional[Dict]:
        raw = self._data.get((namespace, key))
        return _decode(copy.deepcopy(raw)) if raw is not None else None

    async def update(self, namespace: str, key: str, value: Dict) -> Dict:
        self._data[(namespace, key)] = _encode(value)
        return value

    async def list_values(self, namespace: str) -> List[Dict]:
        return [
            _decode(copy.deepcopy(v)) for (ns, _k), v in self._data.items() if ns == namespace
        ]


# Default persistent store; tests reassign kv_store.store = InMemoryKvStore().
store: Any = PrismaKvStore()
