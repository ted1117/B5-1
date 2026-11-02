"""Mini Redis 저장 엔진.

HashMap(키→값), DoublyLinkedList(LRU 순서), MinHeap(TTL 만료 시간)을 조립해
In-Memory Key-Value 저장소의 핵심 동작을 제공한다. 네트워크/영속성/스레딩은 없다.
"""

from __future__ import annotations

import time
from typing import Callable, cast

from doubly_linked_list import DoublyLinkedList, Node
from hash_map import HashMap
from min_heap import MinHeap


class OutOfMemoryError(Exception):
    """단일 엔트리가 maxmemory를 초과해 저장할 수 없을 때 발생한다."""


class _Entry:
    """한 키에 대응하는 값, LRU 노드 핸들, 만료 시각을 함께 보관한다."""

    __slots__ = ("value", "lru_node", "expire_at")

    def __init__(self, value: str, lru_node: Node, expire_at: float | None) -> None:
        self.value = value
        # LRU 리스트에서 이 키를 가리키는 노드. O(1) 이동/제거에 사용한다.
        self.lru_node = lru_node
        # 만료 시각(초, 절대값). TTL이 없으면 None.
        self.expire_at = expire_at


def _bytelen(text: str) -> int:
    """문자열의 UTF-8 바이트 길이를 반환한다."""
    return len(text.encode("utf-8"))


class MiniRedisStore:
    """세 자료구조를 조립한 Key-Value 저장 엔진."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        # 키 → _Entry 매핑.
        self._table = HashMap()
        # LRU 순서: front(head)가 가장 최근 사용, back(tail)이 가장 오래 사용.
        # 각 노드의 data에는 키 문자열을 저장한다.
        self._lru = DoublyLinkedList()
        # (expire_at, key) 최소 힙. Lazy/active deletion으로 만료를 관리한다.
        self._ttl_heap = MinHeap()

        self._maxmemory = 0  # 0은 무제한을 의미한다.
        self._used_memory = 0  # 살아있는 키의 Σ(utf8(key) + utf8(value)).
        self._evicted_keys = 0  # 메모리 초과로 제거된 키 누적 개수.

        # 테스트에서 시간을 주입할 수 있도록 clock을 분리한다.
        self._clock = clock

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------
    def _drop(self, key: str, entry: _Entry) -> None:
        """데이터·LRU·메모리에서 키를 함께 제거한다(evicted_keys는 증가시키지 않음)."""
        self._used_memory -= _bytelen(key) + _bytelen(entry.value)
        self._lru.remove_node(entry.lru_node)
        self._table.remove(key)

    def _purge_expired(self) -> None:
        """만료 시각이 지난 키를 힙에서 찾아 적극적으로 제거한다.

        모든 키 기반 명령 실행 전에 호출해, 만료된 키를 '없는 키'처럼 다룬다.
        힙에는 과거의 stale 항목이 남을 수 있으므로 entry.expire_at과 대조해 검증한다.
        """
        now = self._clock()
        while self._ttl_heap.size() > 0:
            top = self._ttl_heap.peek()
            assert top is not None
            expire_at, key = top
            if expire_at > now:
                break  # 가장 이른 만료도 아직 남았으면 더 볼 필요가 없다.

            self._ttl_heap.pop()
            entry = self._table.get(key)
            # 키가 아직 살아있고, 이 힙 항목이 현재 TTL과 일치할 때만 실제 만료.
            if entry is not None and entry.expire_at == expire_at:
                self._drop(key, entry)

    def _evict_if_needed(self) -> None:
        """maxmemory 초과 시 used_memory <= maxmemory가 될 때까지 LRU 키를 제거한다."""
        if self._maxmemory <= 0:
            return
        while self._used_memory > self._maxmemory and len(self._lru) > 0:
            tail = self._lru._tail
            if tail is None:
                break
            key = cast(str, tail.data)
            entry = cast("_Entry | None", self._table.get(key))
            if entry is None:
                break
            self._drop(key, entry)
            self._evicted_keys += 1

    # ------------------------------------------------------------------
    # String 타입 명령어
    # ------------------------------------------------------------------
    def set(self, key: str, value: str) -> None:
        """키에 값을 저장하고 LRU를 갱신한다. 메모리 초과 시 OOM 또는 LRU 제거."""
        self._purge_expired()

        entry_size = _bytelen(key) + _bytelen(value)
        # 단일 엔트리만으로 제한을 넘기면 저장하지 않고 OOM.
        if self._maxmemory > 0 and entry_size > self._maxmemory:
            raise OutOfMemoryError()

        existing = self._table.get(key)
        if existing is not None:
            # 덮어쓰기: 메모리 재계산, TTL 초기화, LRU front로 이동.
            self._used_memory -= _bytelen(key) + _bytelen(existing.value)
            existing.value = value
            existing.expire_at = None
            self._used_memory += entry_size
            self._lru.move_to_front(existing.lru_node)
        else:
            node = self._lru.insert_front(key)
            self._table.put(key, _Entry(value, node, None))
            self._used_memory += entry_size

        self._evict_if_needed()

    def get(self, key: str) -> str | None:
        """키의 값을 반환하고 LRU를 갱신한다. 없거나 만료면 None."""
        self._purge_expired()
        entry = self._table.get(key)
        if entry is None:
            return None
        self._lru.move_to_front(entry.lru_node)
        return entry.value

    def delete(self, key: str) -> int:
        """키를 삭제하면 1, 없으면 0을 반환한다. 데이터·TTL·LRU를 함께 정리한다."""
        self._purge_expired()
        entry = self._table.get(key)
        if entry is None:
            return 0
        self._drop(key, entry)  # 힙의 TTL 항목은 stale 처리되어 자연히 무시된다.
        return 1

    def exists(self, key: str) -> int:
        """키가 있으면 1, 없으면 0."""
        self._purge_expired()
        return 1 if self._table.contains(key) else 0

    def dbsize(self) -> int:
        """현재 저장된 키 개수."""
        self._purge_expired()
        return self._table.size()

    def keys(self) -> list[str]:
        """전체 키 목록(순서 보장 없음)."""
        self._purge_expired()
        return self._table.keys()

    # ------------------------------------------------------------------
    # 메모리 관리 명령어
    # ------------------------------------------------------------------
    def set_maxmemory(self, maxmemory: int) -> None:
        """최대 메모리 제한을 설정한다. 0은 무제한. 낮추면 즉시 LRU 제거를 적용한다."""
        self._maxmemory = maxmemory
        self._evict_if_needed()

    def info_memory(self) -> tuple[int, int, int]:
        """(used_memory, maxmemory, evicted_keys)를 반환한다."""
        self._purge_expired()
        return (self._used_memory, self._maxmemory, self._evicted_keys)

    # ------------------------------------------------------------------
    # TTL 관리 명령어
    # ------------------------------------------------------------------
    def expire(self, key: str, seconds: int) -> int:
        """만료 시간을 설정한다. 키가 없으면 0, 설정하면 1.

        seconds가 0 이하이면 키를 즉시 삭제하고 1을 반환한다.
        """
        self._purge_expired()
        entry = self._table.get(key)
        if entry is None:
            return 0

        if seconds <= 0:
            self._drop(key, entry)
            return 1

        expire_at = self._clock() + seconds
        entry.expire_at = expire_at
        self._ttl_heap.push((expire_at, key))
        return 1

    def ttl(self, key: str) -> int:
        """남은 TTL(초). 키 없음 -2, TTL 없음 -1, 있으면 남은 초(내림)."""
        self._purge_expired()
        entry = self._table.get(key)
        if entry is None:
            return -2
        if entry.expire_at is None:
            return -1
        remaining = entry.expire_at - self._clock()
        # _purge_expired 이후이므로 remaining > 0. 내림으로 남은 초를 반환한다.
        return int(remaining)
