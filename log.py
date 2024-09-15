from traceback import format_exception, format_stack, extract_stack

from threading import Thread, current_thread, main_thread

from typing import Any, Callable, NoReturn, Hashable

from time import monotonic

__all__ = ["LOGGING", "LOGGER", "start_log", "stop_log", "log",
           "log_count", "log_exception", "log_stack", "log_func",
           "clear_log"]

LOGGING = True
FILENAME = "output.log"
DEFAULT_TIME_PRECISION = 4


class Logger:
    def __init__(self, filename: str):
        self.file = open(FILENAME, "w", encoding="utf-8")
        self.func_count = {}
        self.counters = {}
        self.thread = Thread(name="Log thread", target=self.loop)
        self.running = False
        self.message_queue = []

    def loop(self):
        while self.running:
            if not main_thread().is_alive():
                self.stop()

            if not self.message_queue:
                continue

            i = 0
            while self.message_queue:
                if i > 32:
                    break

                msg = self.message_queue.pop(0)

                if msg is None:
                    self.file.truncate(0)
                else:
                    print(*msg, file=self.file)

                i += 1

            self.file.flush()

    def start(self):
        if self.running:
            raise RuntimeError("Logging loop already started")

        self.running = True
        self.thread.start()

    def stop(self):
        if not self.running:
            raise RuntimeError("Logging loop not started")

        self.running = False

        if current_thread() != self.thread:
            self.thread.join()

        # Create a new thead to make the Logger startable again
        self.thread = Thread(name="Log thread", target=self.loop)

    def log(self, *args: Any) -> str:
        if not self.running:
            self.start()

        self.message_queue.append(args)
        
        return " ".join([str(arg) for arg in args])

    def log_count(self, *args: Any, _n: int = 1, id: Hashable | None = None) -> None:
        if id is None:
            frame = extract_stack()[-(1 + _n)]
            id = (frame.filename, frame.lineno, frame.name, frame.line)

        if id not in self.counters:
            self.counters[id] = 0

        self.counters[id] += 1

        c = self.counters[id]

        self.log(f"({c})", *args)
        
        return " ".join([str(arg) for arg in args])

    def log_exception(self, *exceptions: Exception):
        for e in exceptions:
            self.log("\n".join([l.removesuffix("\n")
                     for l in format_exception(e)]))

    def log_stack(self):
        self.log("\n".join([l.removesuffix("\n")
                 for l in format_stack(limit=2-len(extract_stack()))]))

    def log_func(self, func: Callable | None = None, *, log_args: bool = True,
                 log_self: bool = True, log_result: bool = ..., inline: bool = False,
                 count: bool = False, fullname: bool = False, time: bool | int = False):
        if time is True:
            time_precision = DEFAULT_TIME_PRECISION
        elif time is not False:
            assert isinstance(time, int)

            time_precision = time
            time = True

        def decorator(func: Callable):
            nonlocal log_result, log_self

            if count:
                self.func_count[func] = 0

            if log_result is Ellipsis:
                if "return" in func.__annotations__:
                    log_result = func.__annotations__[
                        "return"] not in [None, NoReturn]
                else:
                    log_result = True

            if fullname:
                n = func.__module__ + "." + func.__qualname__
            else:
                n = func.__name__

            def wrapper(*args, **kwargs):
                nonlocal log_self
                if not log_self and len(args) == 0:
                    log_self = True

                p = ""
                s = ""
                if count:
                    self.func_count[func] += 1
                    c = self.func_count[func]
                    p += f"({c}) "

                if log_args:
                    args_ = [repr(a) for a in args] + [n + "=" + repr(v) for n, v in kwargs.items()]

                    if not log_self:
                        args_[0] = "self"

                    a = ", ".join(args_)
                else:
                    a = ""

                if not log_args or (not inline and log_args) or (inline and not log_result and not time):
                    self.log(p + n + "(" + a + ")")

                if time:
                    start_time = monotonic()

                res = func(*args, **kwargs)

                if time:
                    interval = monotonic() - start_time

                    s = f" in {interval:.{time_precision}f}s"

                if not inline:
                    a = ""

                if log_result:
                    self.log(p + n + "(" + a + ")", "->", repr(res) + s)
                elif time:
                    self.log(p + n + "(" + a + ")" + s)

                return res

            return wrapper

        if func is not None:
            return decorator(func)

        return decorator

    def clear(self):
        self.message_queue.append(None)

    def __del__(self):
        self.file.close()


if LOGGING:
    LOGGER = Logger(FILENAME)
else:
    LOGGER = None


def start_log():
    if LOGGER:
        return LOGGER.start()


def stop_log():
    if LOGGER:
        return LOGGER.stop()


def log(*args: Any) -> str:
    if LOGGER:
        return LOGGER.log(*args)

    return " ".join([str(arg) for arg in args])


def log_count(*args: Any, id: Hashable | None = None) -> None:
    if LOGGER:
        return LOGGER.log_count(*args, _n=2, id=id)

    return " ".join([str(arg) for arg in args])


def log_exception(*exceptions: Exception):
    if LOGGER:
        return LOGGER.log_exception(*exceptions)


def log_stack():
    if LOGGER:
        return LOGGER.log_stack()


def log_func(func: Callable | None = None, **opts):
    if LOGGER:
        return LOGGER.log_func(func, **opts)

    if func is not None:
        return func

    return lambda f: f


def clear_log():
    if LOGGER:
        return LOGGER.clear()
