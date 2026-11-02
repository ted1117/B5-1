# Mini Redis

CLI 기반 In-Memory Key-Value 저장소. Python으로 구현한 Redis 서브셋.

## 실행

```bash
python3 cli.py
```

종료: `exit` 또는 `quit`

## 명령어

### String

| 명령어 | 설명 |
|---|---|
| `SET key value` | 값 저장, LRU 갱신 |
| `GET key` | 값 조회, LRU 갱신 |
| `DEL key` | 키 삭제 |
| `EXISTS key` | 키 존재 여부 |
| `DBSIZE` | 전체 키 개수 |
| `KEYS` | 전체 키 목록 |

### 메모리

| 명령어 | 설명 |
|---|---|
| `CONFIG SET maxmemory <bytes>` | 최대 메모리 설정 (0 = 무제한) |
| `INFO memory` | 메모리 사용량 조회 |

### TTL

| 명령어 | 설명 |
|---|---|
| `EXPIRE key <seconds>` | 만료 시간 설정 |
| `TTL key` | 남은 만료 시간 조회 |

## 출력 형식

```
OK
"value"
(nil)
(integer) N
(error) ERR ...
```

## 자료구조

| 파일 | 역할 |
|---|---|
| `doubly_linked_list.py` | LRU 순서 관리 |
| `hash_map.py` | 키-값 저장소 (체이닝 방식 충돌 해결, load factor 0.75 리사이즈) |
| `min_heap.py` | TTL 만료 시간 관리 |

## 메모리 관리

- `used_memory = Σ(UTF-8 바이트(key) + UTF-8 바이트(value))`
- 단일 엔트리가 `maxmemory` 초과 시 OOM 에러 반환
- `SET` 후 초과 시 가장 오래 사용하지 않은 키부터 자동 제거

## 테스트

```bash
python3 test_mini_redis.py
```
