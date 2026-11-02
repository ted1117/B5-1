"""Mini Redis CLI REPL.

한 줄 입력을 파싱해 MiniRedisStore에 명령을 위임하고, Redis 스타일로 출력한다.
명령어 이름은 대소문자를 무시하고, 키/값은 대소문자를 구분한다.
"""

from __future__ import annotations

import sys

from store import MiniRedisStore, OutOfMemoryError

PROMPT = "mini-redis> "

# 에러 메시지 상수(PRD 출력 포맷 그대로).
_ERR_INTEGER = "(error) ERR value is not an integer or out of range"
_ERR_OOM = "(error) OOM command not allowed when used_memory > 'maxmemory'"


class CommandError(Exception):
    """CLI 계층에서 발생하는 사용자 입력 오류. message가 그대로 출력된다."""


def tokenize(line: str) -> list[str]:
    """공백으로 토큰을 나누되 큰따옴표로 감싼 값은 하나의 토큰으로 묶는다.

    예: SET name "Alice Lee" -> ["SET", "name", "Alice Lee"]
    """
    tokens: list[str] = []
    current: list[str] = []
    in_quote = False
    has_token = False  # 빈 따옴표("")도 토큰으로 인식하기 위한 플래그.

    for char in line:
        if in_quote:
            if char == '"':
                in_quote = False
            else:
                current.append(char)
        elif char == '"':
            in_quote = True
            has_token = True
        elif char.isspace():
            if has_token:
                tokens.append("".join(current))
                current = []
                has_token = False
        else:
            current.append(char)
            has_token = True

    if has_token:
        tokens.append("".join(current))
    return tokens


def _parse_int(text: str) -> int:
    """정수로 파싱한다. 실패하면 PRD 정수 에러를 발생시킨다."""
    try:
        return int(text)
    except ValueError:
        raise CommandError(_ERR_INTEGER)


def _wrong_args(command: str) -> CommandError:
    """인자 개수 오류를 입력한 명령 이름 그대로 생성한다."""
    return CommandError(
        f"(error) ERR wrong number of arguments for '{command}' command"
    )


def _format_keys(keys: list[str]) -> str:
    """KEYS 결과를 번호 매긴 목록으로, 비어 있으면 (empty array)로 포맷한다."""
    if not keys:
        return "(empty array)"
    lines = [f'{index}. "{key}"' for index, key in enumerate(keys, start=1)]
    return "\n".join(lines)


def dispatch(store: MiniRedisStore, command: str, args: list[str]) -> str:
    """명령 하나를 실행하고 출력 문자열을 반환한다. 오류는 CommandError로 던진다."""
    name = command.upper()

    if name == "SET":
        if len(args) != 2:
            raise _wrong_args(command)
        try:
            store.set(args[0], args[1])
        except OutOfMemoryError:
            raise CommandError(_ERR_OOM)
        return "OK"

    if name == "GET":
        if len(args) != 1:
            raise _wrong_args(command)
        value = store.get(args[0])
        return "(nil)" if value is None else f'"{value}"'

    if name == "DEL":
        if len(args) != 1:
            raise _wrong_args(command)
        return f"(integer) {store.delete(args[0])}"

    if name == "EXISTS":
        if len(args) != 1:
            raise _wrong_args(command)
        return f"(integer) {store.exists(args[0])}"

    if name == "DBSIZE":
        if args:
            raise _wrong_args(command)
        return f"(integer) {store.dbsize()}"

    if name == "KEYS":
        if args:
            raise _wrong_args(command)
        return _format_keys(store.keys())

    if name == "EXPIRE":
        if len(args) != 2:
            raise _wrong_args(command)
        seconds = _parse_int(args[1])
        return f"(integer) {store.expire(args[0], seconds)}"

    if name == "TTL":
        if len(args) != 1:
            raise _wrong_args(command)
        return f"(integer) {store.ttl(args[0])}"

    if name == "CONFIG":
        # 지원 형태: CONFIG SET maxmemory <bytes>
        if len(args) != 3 or args[0].upper() != "SET" or args[1].lower() != "maxmemory":
            raise _wrong_args(command)
        maxmemory = _parse_int(args[2])
        if maxmemory < 0:
            raise CommandError(_ERR_INTEGER)
        store.set_maxmemory(maxmemory)
        return "OK"

    if name == "INFO":
        # 지원 형태: INFO memory
        if len(args) != 1 or args[0].lower() != "memory":
            raise _wrong_args(command)
        used, maxmemory, evicted = store.info_memory()
        return f"used_memory:{used}\nmaxmemory:{maxmemory}\nevicted_keys:{evicted}"

    raise CommandError(f"(error) ERR unknown command '{command}'")


def run_line(store: MiniRedisStore, line: str) -> str | None:
    """입력 한 줄을 처리한다. 출력이 없으면(빈 줄) None을 반환한다."""
    tokens = tokenize(line)
    if not tokens:
        return None
    command, args = tokens[0], tokens[1:]
    try:
        return dispatch(store, command, args)
    except CommandError as error:
        return str(error)


def main() -> None:
    """REPL 루프. exit/quit 또는 EOF로 종료한다."""
    store = MiniRedisStore()
    while True:
        try:
            line = input(PROMPT)
        except EOFError:
            print()
            break

        if line.strip().lower() in ("exit", "quit"):
            break

        output = run_line(store, line)
        if output is not None:
            print(output)


if __name__ == "__main__":
    main()
