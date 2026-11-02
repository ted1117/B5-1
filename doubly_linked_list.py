class Node:
    """데이터와 앞뒤 노드의 연결을 보관한다."""

    def __init__(self, data: object = None) -> None:
        self.data = data
        self.prev: Node | None = None
        self.next: Node | None = None


class DoublyLinkedList:
    def __init__(self) -> None:
        self._head: Node | None = None
        self._tail: Node | None = None
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def is_empty(self) -> bool:
        """리스트가 비어 있는지 반환한다."""
        return self._size == 0

    def insert_front(self, data: object) -> Node:
        """맨 앞에 데이터를 삽입하고 생성한 노드를 반환한다."""
        node = Node(data)
        first = self._head
        node.next = first

        if first is None:
            self._tail = node
        else:
            first.prev = node

        self._head = node
        self._size += 1
        return node

    def insert_back(self, data: object) -> Node:
        """맨 뒤에 데이터를 삽입하고 생성한 노드를 반환한다."""
        node = Node(data)
        last = self._tail
        node.prev = last

        if last is None:
            self._head = node
        else:
            last.next = node

        self._tail = node
        self._size += 1
        return node

    def remove_front(self) -> Node | None:
        """맨 앞 노드를 제거해 반환한다. 비어 있으면 None을 반환한다."""
        target = self._head
        if target is None:
            return None
        return self.remove_node(target)

    def remove_back(self) -> Node | None:
        """맨 뒤 노드를 제거해 반환한다. 비어 있으면 None을 반환한다."""
        target = self._tail
        if target is None:
            return None
        return self.remove_node(target)

    def remove_node(self, node: Node) -> Node:
        """현재 이 리스트에 연결된 노드를 제거해 반환한다."""
        prev_node = node.prev
        next_node = node.next

        if prev_node is None:
            self._head = next_node
        else:
            prev_node.next = next_node

        if next_node is None:
            self._tail = prev_node
        else:
            next_node.prev = prev_node

        node.prev = None
        node.next = None
        self._size -= 1
        return node

    def move_to_front(self, node: Node) -> None:
        """현재 이 리스트에 연결된 노드를 맨 앞으로 이동한다."""
        if node is self._head:
            return

        self.remove_node(node)
        first = self._head
        node.next = first

        if first is None:
            self._tail = node
        else:
            first.prev = node

        self._head = node
        self._size += 1
