"""Mini Redis 스모크 테스트.

PRD의 '실행 예시', '에러 출력 예시' 흐름을 재현해 출력이 스펙과 일치하는지 검증한다.
TTL은 주입한 가짜 시계로 '3초 경과'를 시뮬레이션하고, 별도로 실제 time 기반
카운트다운도 짧게 확인한다.
"""

from __future__ import annotations

import time

from cli import run_line
from store import MiniRedisStore


class FakeClock:
    """테스트에서 시간을 임의로 진행시키는 가짜 시계."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def expect(store: MiniRedisStore, line: str, want: str) -> None:
    """한 줄을 실행하고 출력이 기대값과 같은지 단언한다."""
    got = run_line(store, line)
    assert got == want, f"\n입력:  {line}\n기대:  {want!r}\n실제:  {got!r}"
    print(f"mini-redis> {line}\n{got}\n")


def test_prd_execution_example() -> None:
    """PRD '실행 예시'의 전체 흐름을 재현한다."""
    clock = FakeClock()
    store = MiniRedisStore(clock=clock)

    expect(store, "CONFIG SET maxmemory 30", "OK")
    expect(store, 'SET user:1 "Alice"', "OK")
    expect(store, 'SET user:2 "Bob"', "OK")
    # user:3 저장 시 maxmemory(30) 초과 -> LRU(user:1) 제거.
    expect(store, 'SET user:3 "Charlie"', "OK")

    expect(store, "GET user:1", "(nil)")
    expect(store, "INFO memory", "used_memory:22\nmaxmemory:30\nevicted_keys:1")
    # KEYS 순서는 보장되지 않으므로 집합적으로 확인한다.
    keys_output = run_line(store, "KEYS")
    assert keys_output is not None and keys_output.count("\n") == 1
    assert '"user:2"' in keys_output and '"user:3"' in keys_output
    print(f"mini-redis> KEYS\n{keys_output}\n")

    expect(store, "EXPIRE user:2 3", "(integer) 1")
    # EXPIRE 직후 약간의 시간이 흐른 상황을 흉내 내 TTL=2 를 재현한다.
    clock.advance(0.5)
    expect(store, "TTL user:2", "(integer) 2")

    # 3초 경과.
    clock.advance(3)
    expect(store, "GET user:2", "(nil)")
    expect(store, "TTL user:2", "(integer) -2")


def test_prd_error_examples() -> None:
    """PRD '에러 출력 예시'를 재현한다."""
    store = MiniRedisStore()
    expect(
        store,
        "CONFIG SET maxmemory abc",
        "(error) ERR value is not an integer or out of range",
    )
    expect(
        store,
        "GET",
        "(error) ERR wrong number of arguments for 'GET' command",
    )
    expect(store, "HELLO", "(error) ERR unknown command 'HELLO'")


def test_basic_commands() -> None:
    """기본 String 명령과 덮어쓰기/TTL 초기화 동작을 확인한다."""
    store = MiniRedisStore()
    expect(store, "DBSIZE", "(integer) 0")
    expect(store, "KEYS", "(empty array)")
    expect(store, "EXISTS foo", "(integer) 0")
    expect(store, "SET foo bar", "OK")  # 따옴표 없는 값도 지원.
    expect(store, "GET foo", '"bar"')
    expect(store, "EXISTS foo", "(integer) 1")
    expect(store, "DBSIZE", "(integer) 1")
    expect(store, "DEL foo", "(integer) 1")
    expect(store, "DEL foo", "(integer) 0")
    expect(store, "GET foo", "(nil)")

    # 명령 이름 대소문자 무시, 키는 대소문자 구분.
    expect(store, "set Key Value", "OK")
    expect(store, "get Key", '"Value"')
    expect(store, "get key", "(nil)")

    # 따옴표로 공백 포함 값 저장.
    expect(store, 'SET msg "hello world"', "OK")
    expect(store, "GET msg", '"hello world"')

    # TTL 없음/있음/초기화.
    expect(store, "TTL Key", "(integer) -1")
    expect(store, "EXPIRE Key 100", "(integer) 1")
    ttl_out = run_line(store, "TTL Key")
    assert ttl_out in ("(integer) 100", "(integer) 99"), ttl_out
    # SET으로 덮어쓰면 TTL 초기화.
    expect(store, "set Key NewValue", "OK")
    expect(store, "TTL Key", "(integer) -1")

    # 존재하지 않는 키 EXPIRE.
    expect(store, "EXPIRE missing 10", "(integer) 0")
    # seconds<=0 이면 즉시 삭제.
    expect(store, "EXPIRE Key 0", "(integer) 1")
    expect(store, "EXISTS Key", "(integer) 0")


def test_oom_single_entry() -> None:
    """단일 엔트리가 maxmemory를 초과하면 저장하지 않고 OOM."""
    store = MiniRedisStore()
    run_line(store, "CONFIG SET maxmemory 5")
    expect(
        store,
        "SET longkey longvalue",
        "(error) OOM command not allowed when used_memory > 'maxmemory'",
    )
    expect(store, "EXISTS longkey", "(integer) 0")
    # maxmemory 0 = 무제한.
    run_line(store, "CONFIG SET maxmemory 0")
    expect(store, "SET longkey longvalue", "OK")


def test_lru_order_on_get() -> None:
    """GET으로 최근 사용된 키는 제거 대상에서 밀려난다."""
    store = MiniRedisStore()
    # 각 엔트리 "x"+"1" = 2바이트. 제한 5바이트면 세 개(6바이트)는 못 담는다.
    run_line(store, "CONFIG SET maxmemory 5")
    run_line(store, "SET a 1")
    run_line(store, "SET b 1")
    run_line(store, "GET a")  # a를 최근 사용으로 끌어올림.
    run_line(store, "SET c 1")  # 6바이트 초과 -> 가장 오래된 b 제거.
    assert run_line(store, "GET a") == '"1"'
    assert run_line(store, "GET b") == "(nil)"
    assert run_line(store, "GET c") == '"1"'
    print("LRU 순서 확인: GET으로 승격된 a는 유지, b가 제거됨\n")


def test_real_ttl_countdown() -> None:
    """실제 시계 기반 TTL 카운트다운이 동작하는지 짧게 확인한다."""
    store = MiniRedisStore()  # 기본 time.time 사용.
    run_line(store, "SET temp hi")
    run_line(store, "EXPIRE temp 1")
    assert run_line(store, "TTL temp") == "(integer) 0"  # 1초 미만 남음 -> 내림 0.
    assert run_line(store, "GET temp") == '"hi"'
    time.sleep(1.1)
    assert run_line(store, "GET temp") == "(nil)"
    assert run_line(store, "TTL temp") == "(integer) -2"
    print("실제 TTL 카운트다운 확인: 1.1초 후 만료\n")


def test_heap_remove() -> None:
    """MinHeap.remove는 임의 위치 항목을 지우고 힙 순서를 유지한다."""
    from min_heap import MinHeap

    heap = MinHeap()
    for item in [(5.0, "e"), (1.0, "a"), (3.0, "c"), (2.0, "b"), (4.0, "d"), (6.0, "f")]:
        heap.push(item)

    assert heap.remove((3.0, "c")) is True
    assert heap.remove((99.0, "zz")) is False
    assert heap.size() == 5

    popped = []
    while heap.size() > 0:
        popped.append(heap.pop())
    assert popped == [(1.0, "a"), (2.0, "b"), (4.0, "d"), (5.0, "e"), (6.0, "f")], popped
    print("힙 remove 확인: 중간 항목 제거 후에도 순서 유지\n")


def test_heap_cleaned_immediately() -> None:
    """DEL·덮어쓰기·재설정·메모리 제거 때 TTL 힙 항목이 즉시 사라진다."""
    clock = FakeClock()
    store = MiniRedisStore(clock=clock)

    # DEL.
    run_line(store, "SET a 1")
    run_line(store, "EXPIRE a 100")
    assert store._ttl_heap.size() == 1
    run_line(store, "DEL a")
    assert store._ttl_heap.size() == 0

    # SET 덮어쓰기(TTL 초기화).
    run_line(store, "SET b 1")
    run_line(store, "EXPIRE b 100")
    run_line(store, "SET b 2")
    assert store._ttl_heap.size() == 0

    # EXPIRE 재설정: 항목은 항상 하나만 유지.
    run_line(store, "SET c 1")
    run_line(store, "EXPIRE c 100")
    clock.advance(1)
    run_line(store, "EXPIRE c 200")
    assert store._ttl_heap.size() == 1
    assert run_line(store, "TTL c") == "(integer) 200"

    # 메모리 초과로 LRU 제거되는 키.
    run_line(store, "DEL c")
    run_line(store, "CONFIG SET maxmemory 5")
    run_line(store, "SET x 1")
    run_line(store, "EXPIRE x 100")
    run_line(store, "SET y 1")
    run_line(store, "SET z 1")  # 6바이트 초과 -> x(가장 오래됨) 제거.
    assert run_line(store, "EXISTS x") == "(integer) 0"
    assert store._ttl_heap.size() == 0

    # 만료 후에도 힙이 비워진다.
    run_line(store, "CONFIG SET maxmemory 0")
    run_line(store, "EXPIRE y 3")
    clock.advance(3)
    assert run_line(store, "GET y") == "(nil)"
    assert store._ttl_heap.size() == 0
    print("TTL 힙 즉시 정리 확인: DEL/덮어쓰기/재설정/LRU 제거/만료\n")


if __name__ == "__main__":
    print("=== PRD 실행 예시 ===")
    test_prd_execution_example()
    print("=== PRD 에러 출력 예시 ===")
    test_prd_error_examples()
    print("=== 기본 명령 ===")
    test_basic_commands()
    print("=== OOM ===")
    test_oom_single_entry()
    print("=== LRU 순서 ===")
    test_lru_order_on_get()
    print("=== 실제 TTL 카운트다운 ===")
    test_real_ttl_countdown()
    print("=== 힙 remove / 즉시 정리 ===")
    test_heap_remove()
    test_heap_cleaned_immediately()
    print("ALL TESTS PASSED")
