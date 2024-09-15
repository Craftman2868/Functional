from threading import Thread, current_thread

from typing import Callable, TypeVar, Generic

from event.event import BaseEvent


class EventQueue:
    def __init__(self, *callbacks: Callable[[BaseEvent], None]):
        self.queue: list[BaseEvent] = []
        self.thread = Thread(target=self.loop)
        self.running = False
        self.handlers: list[Callable[[BaseEvent], None]] = list(callbacks)

    def queue_event(self, event: BaseEvent):
        self.queue.append(event)

    def handle_event(self, event: BaseEvent):
        for handler in self.handlers:
            handler(event)

    def loop(self):
        while self.running:
            if not self.queue:
                continue

            ev = self.queue.pop(0)

            self.handle_event(ev)

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread.start()

    def stop(self, wait: bool = False):
        if current_thread() is self.thread or not self.thread.is_alive():  # ignore wait (it would block the thread)
            self.running = False
            return

        if not self.running:
            if self.thread.is_alive():
                self.thread.join()
            return

        if wait:
            while self.queue:
                pass

        self.running = False

        self.thread.join()

    def add_handler(self, callback: Callable[[BaseEvent], None]):
        self.handlers.append(callback)

        return callback

    def remove_handler(self, callback: Callable[[BaseEvent], None]):
        self.handlers.remove(callback)

    handler = add_handler
