from event.event import BaseEvent
from event.eventQueue import EventQueue

from log import *

from typing import Any, Callable

CATCH_EXCEPTIONS = True
ANY_EVENTS = False


class Eventable:
    def __init__(self, event_queue: list[BaseEvent] | None = None):
        self.event_queue = event_queue
        if self.event_queue is None:
            self.event_queue = []
        self.listeners: dict[Any, tuple[Callable[..., Any], bool]] = {}
        self.set_default_listeners()

    def handle_events(self, limit: int = 16) -> int:
        i = 0

        while i < limit and self.event_queue:
            event = self.event_queue.pop(0)

            self.handle_event(event)

            i += 1

        return i

    def exec_callback(self, callback: Callable[..., Any], event: BaseEvent) -> bool:
        try:
            callback(event)
        except Exception as e:
            if CATCH_EXCEPTIONS:
                if event.type != "error":
                    self.call_event("error", e)
            else:
                raise

            return False

        return True

    def handle_event(self, event: BaseEvent):
        for e, listners in self.listeners.copy().items():
            if event.match(e):
                for callback, auto_remove in listners:
                    self.exec_callback(callback, event)
                    if auto_remove:
                        self.listeners[e].remove((callback, auto_remove))

        if hasattr(self, "on_"+event.type):
            self.exec_callback(getattr(self, "on_"+event.type), event)

    def call_event(self, event: str | BaseEvent, *args) -> BaseEvent:
        if not isinstance(event, BaseEvent):
            event = BaseEvent.load(event, args)
        elif args:
            raise ValueError(
                "No argument can be specified if event is already an Event.")

        self.event_queue.append(event)

        if ANY_EVENTS and event.type != "any":
            self.call_event("any", event)

        if event.type != "any" or not ANY_EVENTS:
            log(self.__class__.__name__ + ": ", event)

        return event

    def add_listener(self, event: Any, callback: Callable[..., Any], auto_remove: bool = False) -> None:
        if event not in self.listeners:
            self.listeners[event] = []

        self.listeners[event].append((callback, auto_remove))

    def reset_listeners(self) -> None:
        self.listeners = {}
        self.set_default_listeners()

    def set_default_listeners(self) -> None:
        pass

    def on(self, event: str | Callable[..., Any] = ..., auto_remove: bool = False) -> Callable[..., Any]:
        """Add a listener on the specified event (detect the event in the function name if none is given).

        Example:
            @app.on
            def on_run(event: Event):  # Will be run when the app will start (just before the main loop)
                app.open_file("my_file.bf")

            @app.on("resize")
            def size_changed(event: ResizeEvent):
                app.set_message(f"New size: {event.w}x{event.h}")
        """
        def decorator(callback):
            nonlocal event
            if event is Ellipsis:
                if not callback.__name__.startswith("on_"):
                    raise Exception(
                        "Event listeners must start with 'on_' if no event is specified")
                event = callback.__name__[3:]
            self.add_listener(event, callback, auto_remove)
            return callback

        if callable(event):
            f = event
            event = Ellipsis
            return decorator(f)

        return decorator
