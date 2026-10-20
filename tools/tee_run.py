"""Run a service and copy its output to the console and a dated log file."""

import codecs
import ctypes
from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 4 or sys.argv[2] != "--" or not re.fullmatch(r"[A-Za-z0-9_-]+", sys.argv[1]):
        print("Usage: python tee_run.py <name> -- <command...>", file=sys.stderr)
        return 2

    name = sys.argv[1]
    command = sys.argv[3:]
    if os.name == "nt":
        try:
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass  # 로그 파일과 자식 프로세스는 콘솔 설정에 실패해도 계속 실행한다.
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_file = None
    try:
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / f"{name}_{datetime.now():%Y%m%d}.log"
        log_file = log_path.open("a", encoding="utf-8", newline="")
    except OSError as exc:
        print(f"[LOG] Could not open log file: {exc}", file=sys.stderr)

    def write_log(value: str) -> None:
        nonlocal log_file
        if log_file is None:
            return
        try:
            log_file.write(value)
            log_file.flush()
        except OSError as exc:
            print(f"[LOG] Could not write log file: {exc}", file=sys.stderr)
            try:
                log_file.close()
            except OSError:
                pass
            log_file = None

    def close_log() -> None:
        nonlocal log_file
        if log_file is not None:
            try:
                log_file.close()
            except OSError:
                pass
            log_file = None

    write_log(f"===== START {datetime.now().isoformat(timespec='seconds')} cmd={' '.join(command)} =====\n")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    except OSError as exc:
        print(f"[LOG] Could not start command: {exc}", file=sys.stderr)
        write_log("===== EXIT code=1 =====\n")
        close_log()
        return 1

    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    pending = ""

    def forward_output() -> None:
        nonlocal pending
        while True:
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            pending += decoder.decode(chunk)
            while "\n" in pending:
                line, pending = pending.split("\n", 1)
                write_log(f"[{datetime.now():%H:%M:%S}] {line}\n")

    exit_code = 1
    try:
        forward_output()
        exit_code = process.wait()
    except KeyboardInterrupt:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        forward_output()
        exit_code = 130
    finally:
        process.stdout.close()
        pending += decoder.decode(b"", final=True)
        if pending:
            write_log(f"[{datetime.now():%H:%M:%S}] {pending}\n")
        write_log(f"===== EXIT code={exit_code} =====\n")
        close_log()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
