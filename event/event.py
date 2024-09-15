from typing import Any
from collections.abc import Sequence


class BaseEvent:
    name = None
    event_types = {}

    def __init__(self, type: str, args: Sequence[Any]):
        if self.__class__ == BaseEvent:
            raise NotImplementedError("BaseEvent is an abstract class")
        self.type = type
        self.args = list(args)

    def __init_subclass__(cls):
        if cls.name is not None:
            BaseEvent.event_types[cls.name] = cls

    @staticmethod
    def load(event, args):
        event_cls = BaseEvent.event_types.get(event)

        if event_cls:
            return event_cls(*args)
        else:
            return OtherEvent(event, args)

    def match(self, value: Any):
        if isinstance(value, BaseEvent):
            return self.type == value.type and self.args == value.args
        if isinstance(value, str):
            return self.type.lower() == value.lower()
        if isinstance(value, Sequence):
            return self.type == value[0] and self.args == value[1:]
        return False

    def repr_args(self):
        return ", ".join([repr(a) for a in self.args])

    def __repr__(self):
        if self.__class__.name:
            return f"{self.__class__.__name__}({self.repr_args()})"

        return f"Event<{self.type}>({self.repr_args()})"


class KeyEvent(BaseEvent):
    name = "key"

    key: str
    alt: bool

    def __init__(self, key: str, alt: bool = False):
        super().__init__(self.name, (key, alt,))
        self.key = key
        self.alt = alt

    def match(self, value: Any):
        if super().match(value):
            return True

        if isinstance(value, Sequence) and len(value) == 1:
            return value[0] == self.key

        if isinstance(value, str):
            return value == self.key

        return False


class MouseEvent(BaseEvent):
    name = "mouse"

    MODIFIERS = {
        "shift": 4,
        "alt": 8,
        "meta": 8,
        "ctrl": 16,
        "hold": 32,
    }

    button: int
    x: int
    y: int

    shift: bool
    alt: bool
    meta: bool
    ctrl: bool
    hold: bool

    def __init__(self, button: int, x: int, y: int, modifiers: int):
        super().__init__("mouse", (button, x, y, modifiers))
        self.button = button
        self.x = x
        self.y = y

        for name, value in self.MODIFIERS.items():
            setattr(self, name, bool(modifiers & value))

    def match(self, value: Any):
        if super().match(value):
            return True

        if isinstance(value, Sequence) and len(value) == 2:
            return value[0] == self.x and value[1] == self.y

        return False


class PasteEvent(BaseEvent):
    name = "paste"

    def __init__(self, text: str):
        super().__init__(self.name, (text,))
        self.text: str = text


class ResizeEvent(BaseEvent):
    name = "resize"

    w: int
    h: int

    def __init__(self, w: int, h: int):
        super().__init__(self.name, (w, h))
        self.w = w
        self.h = h


class AnyEvent(BaseEvent):
    name = "any"

    event: BaseEvent

    def __init__(self, event: BaseEvent):
        super().__init__(self.name, (event,))
        self.event = event


class ErrorEvent(BaseEvent):
    name = "error"

    exc: BaseException

    def __init__(self, exc: BaseException):
        super().__init__(self.name, (exc,))
        self.exc = exc


class OtherEvent(BaseEvent):
    pass


Event = OtherEvent
