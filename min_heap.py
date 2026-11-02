class MinHeap:
    def __init__(self) -> None:
        self._heap: list[tuple[float, str]] = []

    def push(self, item: tuple[float, str]) -> None:
        """항목을 추가하고 부모와 비교하며 위로 이동한다."""
        self._heap.append(item)
        self._heapify_up(len(self._heap) - 1)

    def pop(self) -> tuple[float, str] | None:
        """가장 이른 항목을 제거해 반환한다. 비어 있으면 None을 반환한다."""
        if not self._heap:
            return None

        minimum = self._heap[0]
        last = self._heap.pop()

        if self._heap:
            self._heap[0] = last
            self._heapify_down(0)

        return minimum

    def peek(self) -> tuple[float, str] | None:
        """가장 이른 항목을 제거하지 않고 반환한다. 비어 있으면 None을 반환한다."""
        if not self._heap:
            return None
        return self._heap[0]

    def size(self) -> int:
        """저장된 항목 수를 반환한다."""
        return len(self._heap)

    def _heapify_up(self, index: int) -> None:
        """부모가 자식보다 크면 교환하며 힙 조건을 복구한다."""
        while index > 0:
            parent = (index - 1) // 2
            if self._heap[parent] <= self._heap[index]:
                break

            self._heap[parent], self._heap[index] = (
                self._heap[index],
                self._heap[parent],
            )
            index = parent

    def _heapify_down(self, index: int) -> None:
        """더 작은 자식과 교환하며 힙 조건을 복구한다."""
        size = len(self._heap)
        while True:
            left = 2 * index + 1
            right = 2 * index + 2
            smallest = index

            if left < size and self._heap[left] < self._heap[smallest]:
                smallest = left
            if right < size and self._heap[right] < self._heap[smallest]:
                smallest = right
            if smallest == index:
                break

            self._heap[index], self._heap[smallest] = (
                self._heap[smallest],
                self._heap[index],
            )
            index = smallest
