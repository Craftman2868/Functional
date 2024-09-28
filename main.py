from event.eventable import Eventable
from event.event import ResizeEvent, KeyEvent, ErrorEvent, PasteEvent, MouseEvent

from terminal import Terminal, CTRL

from interpreter import Function, TokenizationError, CompilationError, MATH_ENV, IgnoreMe
from canvas import Canvas

from string import printable

from log import *

from sys import argv

from math import isfinite


NO_TILDE = False


CHARS = '_,..-~*"^`'
if NO_TILDE:
    CHARS = CHARS.replace("~", "-")
DEFAULT_ZOOM = 4, 2


def get_char(n: float):
    return CHARS[round(n * (len(CHARS) - 1))]


class App(Eventable):
    def __init__(self, w: int, h: int, f: str = None):
        super().__init__()

        self.terminal = Terminal(self.event_queue)

        self.screen = Canvas(*(n-1 for n in self.terminal.size))

        self.initialized = False
        self.updated = False
        self.running = False

        self.env = MATH_ENV

        self.f_str = f or ""
        self.cursor = len(self.f_str)
        self.f = None
        self.fw = self.screen.w // 3
        self.error = None

        self.graph_updated = False

        self.show_axis = True
        self.show_orig = True

        self.origin = (self.screen.w//2, self.screen.h//2)
        self.dx, self.dy = DEFAULT_ZOOM

        self.mouse = None
        self.pointer = (0, 0)

        if self.f_str:
            self.update_f()

    @property
    def show_bg(self):
        return self.show_axis or self.show_orig

    @show_bg.setter
    def show_bg(self, value: bool):
        self.show_axis = value
        self.show_orig = value

    def screenToX(self, x: int | float):
        if self.dx == 0:
            return 0

        return (x - self.origin[0]) / self.dx

    def screenToY(self, y: int | float):
        if self.dy == 0:
            return 0

        return (self.origin[1] - y) / self.dy

    def xToScreen(self, x: float):
        return (x * self.dx) + self.origin[0]

    def yToScreen(self, y: float):
        return self.origin[1] - (y * self.dy)

    def isVisible(self, x: float, y: float):
        return 0 <= self.xToScreen(x) < self.screen.w and 0 <= self.yToScreen(y) < self.screen.h

    def focus(self, x: float, y: float):
        self.origin = (
            round(-(x * self.dx - self.screen.w / 2)),
            round(y * self.dy + self.screen.h / 2)
        )
        log("Orig", self.origin)

    def stop(self):
        self.running = False

    def init(self):
        if self.initialized:
            return

        self.terminal.start_get_chars()
        self.terminal.init_sig()

        self.terminal.enable_alternative_screen()
        self.terminal.enable_mouse_tracking()
        self.terminal.enable_bracketed_paste()
        self.terminal.reset()
        self.terminal.clear_screen()
        self.terminal.hide_cursor()
        self.terminal.home()

        self.initialized = True

    def quit(self):
        if not self.initialized:
            return

        self.initialized = False

        self.terminal.uninit_sig()
        self.terminal.stop()

    def update(self):
        self.handle_events()

    def update_f(self):
        old_f = self.f is not None

        try:
            self.f = Function.compile("f", self.f_str)
        except (TokenizationError, CompilationError) as e:
            self.f = None
            self.error = e.args[0]
        else:
            self.error = None

        if self.f is not None:
            self.env["x"] = IgnoreMe

            errors = self.f.get_errors(**self.env)

            if errors:
                self.error = errors[0]
                self.f = None

        if old_f or self.f is not None:
            self.graph_updated = True
        self.updated = True

        log(self.f or self.error)

    def x_axis(self):
        if self.dx == 0:
            return

        if self.dx == 1:
            return Canvas(self.screen.w, 1, "+")

        cv = Canvas(self.screen.w, 1, "-")

        for sx in range(self.screen.w):
            x = self.screenToX(sx)

            if x.is_integer():
                cv.set_at(sx, 0, "+")

        return cv

    def y_axis(self):
        if self.dy == 0:
            return

        if self.dy == 1:
            return Canvas(1, self.screen.h, "+")

        cv = Canvas(1, self.screen.h, "|")

        for sy in range(self.screen.h):
            y = self.screenToY(sy)

            if y.is_integer():
                cv.set_at(0, sy, "+")

        return cv

    def draw_bg(self):
        if not self.show_bg:
            return

        if self.show_axis:
            # X axis
            if 0 <= self.origin[1] < self.screen.h and (xa := self.x_axis()):
                self.screen.blit(xa, 0, self.origin[1])

            # Y axis
            if 0 <= self.origin[0] < self.screen.w and (ya := self.y_axis()):
                self.screen.blit(ya, self.origin[0], 0)

        if self.show_orig and 0 <= self.origin[0] < self.screen.w and 0 <= self.origin[1] < self.screen.h:
            # Origin
            self.screen.set_at(*self.origin, "0")

    def write_f(self):
        self.screen.write_at(0, self.screen.h-2, f"> {self.f_str}"[-self.fw:])
        if self.error:
            self.screen.write_at(0, self.screen.h-1, ("Error: " + self.error)[-self.fw:])
        elif self.f:
            self.screen.write_at(0, self.screen.h-1, f"f(x)={self.f.expr}"[-self.fw:])

    def calc_f(self, x: int):
        if not self.f:
            return None

        self.env["x"] = x

        success, res = self.f.execute(**self.env)

        if not success:
            log(f"Errors for f({x}):", *res)
            return None

        try:
            if not isfinite(res):
                log(f"Warning for f({x}): found", res)
                return None
        except OverflowError:
            log(f"Warning for f({x}): overflow")
            return None

        return res

    def draw_f(self):
        if not self.f:
            return

        for sx in range(self.screen.w):
            x = self.screenToX(sx)

            y = self.calc_f(x)

            # log(f"f({x})={y}")

            if y is None:
                continue

            sy = self.yToScreen(y)

            if not isfinite(sy):
                continue

            sy_int = round(sy)
            sy_float = sy - sy_int

            if 0 <= sy_int < self.screen.h:
                if self.dx > 10 and x.is_integer():
                    char = "x"
                else:
                    char = get_char(0.5 - sy_float)
                self.screen.set_at(sx, sy_int, char)

    def draw_pointer(self):
        if not self.isVisible(*self.pointer):
            self.pointer = self.screenToX(self.screen.w/2), self.screenToY(self.screen.h/2)

        self.screen.set_at(round(self.xToScreen(self.pointer[0])), round(self.yToScreen(self.pointer[1])), "o")

        fx = self.calc_f(self.pointer[0])

        if fx is None:
            fx = ""
        else:
            fx = f", f(x)={fx}"

        text = f"x={self.pointer[0]}, y={self.pointer[1]}" + fx

        self.screen.write_at(self.screen.w-1-len(text), self.screen.h-1, text)

    def draw_xscale(self):
        i = -10
        while (w := round(10**(-i) * self.dx)) > 20:
            i += 1

        text = f"{10**(-i)} " + "-" * w + " x "

        self.screen.write_at(self.screen.w-2-len(text), self.screen.h-2, text)

    def draw_yscale(self):
        i = -10
        while (h := round(10**(-i) * self.dy)) > 10:
            i += 1

        s = Canvas(1, h, "|")

        self.screen.blit(s, self.screen.w-2, self.screen.h-2-h)

        text = f"{10**(-i)}"
        self.screen.write_at(self.screen.w-1-len(text), self.screen.h-3-h, text)

        self.screen.set_at(self.screen.w-2, self.screen.h-2, "y")

    def draw_scale(self):
        self.draw_xscale()
        self.draw_yscale()

    @log_func(time=10, log_self=False, log_result=False, inline=True)
    def render(self):
        log_count("===============[ Render ]===============", id="render")

        if self.graph_updated:
            log("Draw graph")
            self.screen.fill(" ")
            self.draw_bg()
            self.draw_f()
            self.draw_pointer()
            self.draw_scale()

        self.screen.rect(0, self.screen.h-2, self.fw + 1, 2)
        self.write_f()

        self.terminal.hide_cursor()
        self.terminal.home()
        self.screen.draw(self.terminal)

        self.terminal.set_cursor(min(2 + self.cursor, self.fw), self.screen.h-2)
        self.terminal.show_cursor()

        self.terminal.flush()

    def run(self):
        try:
            self.init()
        except Exception as e:
            log_exception(e)
            return

        self.running = True
        self.updated = True
        self.graph_updated = True
        self.call_event("run")

        self.update()

        while self.running:
            try:
                while self.running and not self.updated:
                    self.update()
            except Exception as e:
                log_exception(e)
                # self.call_event("error", e)
                # self.update_events()
                break

            if not self.running:
                break

            try:
                self.render()
            except Exception as e:
                log_exception(e)
                # self.call_event("error", e)
                # self.update_events()
                break

            self.updated = False
            self.graph_updated = False

        self.quit()

    def insert(self, text: str):
        if not text:
            return

        self.f_str = self.f_str[:self.cursor] + text + self.f_str[self.cursor:]
        self.cursor += len(text)
        self.update_f()

    def erase(self, n: int = 1):
        if not self.cursor or not n:
            return ""

        c = self.f_str[self.cursor-1]

        self.f_str = self.f_str[:self.cursor-1] + self.f_str[self.cursor:]
        self.cursor -= 1

        if n == 1:
            self.update_f()

        return self.erase(n - 1) + c

    def zoom_x(self, n: float = 1):
        self.dx *= 2**n

    def zoom_y(self, n: float = 1):
        self.dy *= 2**n

    def zoom(self, n: float = 1):
        self.zoom_x(n)
        self.zoom_y(n)

    def unzoom_x(self, n: float = 1):
        self.zoom_x(-n)

    def unzoom_y(self, n: float = 1):
        self.zoom_y(-n)

    def unzoom(self, n: float = 1):
        return self.zoom(-n)

    # ========[ Event listeners ]========

    def on_key(self, ev: KeyEvent):
        match ev.key:
            case CTRL.c | CTRL.d | CTRL.q:
                self.stop()
            case CTRL.g:
                self.graph_updated = True  # refresh graph
            case CTRL.r:
                pass  # refresh
            case CTRL.space:
                self.origin = (self.screen.w//2, self.screen.h//2)
                self.pointer = (0, 0)
                self.dx, self.dy = DEFAULT_ZOOM
                self.graph_updated = True
            case CTRL.f:
                x = self.pointer[0]
                fx = self.calc_f(x)

                if fx is None:
                    return

                self.pointer = x, fx
                if not self.isVisible(*self.pointer):
                    self.focus(*self.pointer)

                self.graph_updated = True
            case CTRL.z:
                if not ev.alt:
                    self.origin = self.origin[0] - (round(self.xToScreen(self.pointer[0])) - self.origin[0]), self.origin[1] - (round(self.yToScreen(self.pointer[1])) - self.origin[1])
                self.zoom()
                self.graph_updated = True
            case CTRL.u:
                if not ev.alt:
                    self.origin = self.origin[0] + (round(self.xToScreen(self.pointer[0])) - self.origin[0]) // 2, self.origin[1] + (round(self.yToScreen(self.pointer[1])) - self.origin[1]) // 2
                self.unzoom()
                self.graph_updated = True
            case "b" if ev.alt:
                self.show_bg = not self.show_bg
                self.graph_updated = True
            case "a" if ev.alt:
                self.show_axis = not self.show_axis
                self.graph_updated = True
            case "o" if ev.alt:
                self.show_orig = not self.show_orig
                self.graph_updated = True
            case "x" if ev.alt:
                self.zoom_x()
                self.graph_updated = True
            case "X" if ev.alt:
                self.unzoom_x()
                self.graph_updated = True
            case "y" if ev.alt:
                self.zoom_y()
                self.graph_updated = True
            case "Y" if ev.alt:
                self.unzoom_y()
                self.graph_updated = True
            case "left":
                if self.cursor == 0:
                    return
                self.cursor -= 1
            case "right":
                if self.cursor == len(self.f_str):
                    return
                self.cursor += 1
            case "home":
                if self.cursor == 0:
                    return
                self.cursor = 0
            case "end":
                if self.cursor == len(self.f_str):
                    return
                self.cursor = len(self.f_str)
            case "\t" | "\n" | "\r" | "\x0b" | "\x0c":
                return
            case c if c in printable and not ev.alt:
                self.insert(c)
                return
            case "\x7f":
                self.erase(1)
                return
            case "delete":
                if self.cursor == len(self.f_str):
                    return
                self.cursor += 1
                self.erase(1)
                return
            case _:
                return

        self.updated = True

    def on_paste(self, ev: PasteEvent):
        self.insert(ev.text)

    def on_mouse(self, ev: MouseEvent):
        match ev.button:
            case Terminal.BUTTON_LEFT:
                if ev.hold and self.mouse:
                    self.origin = self.origin[0] - self.mouse[0] + ev.x, self.origin[1] - self.mouse[1] + ev.y
                self.pointer = self.screenToX(ev.x), self.screenToY(ev.y)
                self.updated = True
                self.graph_updated = True
                self.mouse = (ev.x, ev.y)
            case Terminal.BUTTON_RIGHT:
                self.pointer = self.screenToX(ev.x), self.screenToY(ev.y)
                self.updated = True
                self.graph_updated = True
            case Terminal.BUTTON_RELEASE:
                self.mouse = None
            case Terminal.SCROLL_UP:
                if not ev.alt:
                    self.origin = self.origin[0] - (ev.x - self.origin[0]), self.origin[1] - (ev.y - self.origin[1])
                self.zoom()
                self.updated = True
                self.graph_updated = True
            case Terminal.SCROLL_DOWN:
                if not ev.alt:
                    self.origin = self.origin[0] + (ev.x - self.origin[0]) // 2, self.origin[1] + (ev.y - self.origin[1]) // 2
                self.unzoom()
                self.updated = True
                self.graph_updated = True

    def on_resize(self, ev: ResizeEvent):
        self.screen = Canvas(ev.w - 1, ev.h - 1)
        self.updated = True
        self.graph_updated = True
        self.terminal.clear()

    def on_error(self, ev: ErrorEvent):
        log_exception(ev.exc)


def main(f: str = None):
    app = App(80, 30, f)

    app.run()

if __name__ == "__main__":
    try:
        start_log()
        main(" ".join(argv[1:]))
    finally:
        stop_log()
