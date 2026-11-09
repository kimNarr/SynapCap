from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from types import TracebackType

from config import CONFIG_FILE_PATH
from diagnostics import sanitize_diagnostic_text
from version import APP_NAME, APP_VERSION

MAX_LOG_BYTES = 256 * 1024


def runtime_log_directory() -> Path:
    return Path(CONFIG_FILE_PATH).resolve().parent / "logs"


def _rotate_if_needed(path: Path) -> None:
    try:
        if path.stat().st_size < MAX_LOG_BYTES:
            return
        previous = path.with_name(f"{path.stem}.previous{path.suffix}")
        path.replace(previous)
    except FileNotFoundError:
        return


def _append_log(path: Path, text: str) -> Path | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(path)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(sanitize_diagnostic_text(text).rstrip() + "\n")
        return path
    except OSError:
        return None


def record_runtime_event(
    event: str,
    details: str = "",
    *,
    log_dir: Path | None = None,
) -> Path | None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    suffix = f" · {details}" if details else ""
    return _append_log(
        (log_dir or runtime_log_directory()) / "runtime-events.log",
        f"{timestamp} · {event}{suffix}",
    )


def write_exception_report(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
    *,
    thread_name: str = "main",
    log_dir: Path | None = None,
) -> Path | None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    report = f"\n=== {timestamp} ===\n{APP_NAME} v{APP_VERSION} · thread={thread_name}\n{formatted}"
    return _append_log(
        (log_dir or runtime_log_directory()) / "crash.log",
        report,
    )


def install_exception_logging(*, log_dir: Path | None = None) -> Path:
    target_dir = log_dir or runtime_log_directory()
    previous_hook = sys.excepthook

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            previous_hook(exc_type, exc_value, exc_traceback)
            return
        write_exception_report(
            exc_type,
            exc_value,
            exc_traceback,
            log_dir=target_dir,
        )
        previous_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    previous_thread_hook = threading.excepthook

    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        write_exception_report(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            thread_name=args.thread.name if args.thread is not None else "unknown",
            log_dir=target_dir,
        )
        previous_thread_hook(args)

    threading.excepthook = handle_thread_exception
    return target_dir
