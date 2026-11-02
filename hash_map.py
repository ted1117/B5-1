from typing import cast

from doubly_linked_list import DoublyLinkedList, Node


class HashMap:
    """문자열 키를 직접 해싱하고 이중 연결리스트로 충돌을 처리한다."""

    def __init__(self) -> None:
        # 각 버킷의 노드에는 (키, 값) 튜플을 저장한다.
        self._buckets = [DoublyLinkedList() for _ in range(16)]
        self._size = 0

    def _hash(self, key: str) -> int:
        """문자마다 31을 곱해 누적한 해시를 버킷 인덱스로 변환한다."""
        value = 0
        for character in key:
            # 긴 키에서도 정수 크기가 계속 커지지 않도록 제한한다.
            value = (value * 31 + ord(character)) & 0xFFFFFFFF
        return value % len(self._buckets)

    def _find_node(self, key: str) -> Node | None:
        """키가 속한 버킷의 체인에서 노드를 찾는다."""
        node = self._buckets[self._hash(key)]._head
        while node is not None:
            stored_key, _ = cast(tuple[str, object], node.data)
            if stored_key == key:
                return node
            node = node.next
        return None

    def _resize(self) -> None:
        """버킷을 두 배로 늘리고 모든 항목의 위치를 다시 계산한다."""
        old_buckets = self._buckets
        self._buckets = [DoublyLinkedList() for _ in range(len(old_buckets) * 2)]

        for bucket in old_buckets:
            node = bucket._head
            while node is not None:
                key, _ = cast(tuple[str, object], node.data)
                self._buckets[self._hash(key)].insert_back(node.data)
                node = node.next

    def put(self, key: str, value: object) -> None:
        """값을 저장한다. 기존 키는 덮어쓰며 키 개수는 유지한다."""
        node = self._find_node(key)
        if node is not None:
            node.data = (key, value)
            return

        self._buckets[self._hash(key)].insert_back((key, value))
        self._size += 1

        if self._size / len(self._buckets) > 0.75:
            self._resize()

    def get(self, key: str) -> object | None:
        """키의 값을 반환한다. 키가 없으면 None을 반환한다."""
        node = self._find_node(key)
        if node is None:
            return None
        _, value = cast(tuple[str, object], node.data)
        return value

    def remove(self, key: str) -> bool:
        """키를 삭제한다. 삭제했으면 True, 키가 없으면 False를 반환한다."""
        node = self._find_node(key)
        if node is None:
            return False

        self._buckets[self._hash(key)].remove_node(node)
        self._size -= 1
        return True

    def contains(self, key: str) -> bool:
        """값이 None인 경우를 포함해 키의 존재 여부를 반환한다."""
        return self._find_node(key) is not None

    def keys(self) -> list[str]:
        """저장된 모든 키를 반환한다. 순서는 보장하지 않는다."""
        result: list[str] = []
        for bucket in self._buckets:
            node = bucket._head
            while node is not None:
                key, _ = cast(tuple[str, object], node.data)
                result.append(key)
                node = node.next
        return result

    def size(self) -> int:
        """저장된 키 개수를 반환한다."""
        return self._size
