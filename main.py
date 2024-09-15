from event.eventable import Eventable
from event.event import ResizeEvent, KeyEvent, ErrorEvent, PasteEvent, MouseEvent

from terminal import Terminal, CTRL

from interpreter import Function, TokenizationError, CompilationError
from canvas import Canvas

from string import printable

from log import *


CHARS = '_,..-~*"^`'


def get_char(n: float):
    return CHARS[round(n * (len(CHARS) - 1))]


class App(Eventable):
    def __init__(self, w: int, h: int):
        super().__init__()

        self.terminal = Terminal(self.event_queue)

        self.screen = Canvas(*(n-1 for n in self.terminal.size))

        self.initialized = False
        self.updated = False
        self.running = False

        self.f_str = ""
        self.f = None
        self.fw = 50
        self.error = None

        self.bg_updated = False

        self.show_axis = True
        self.show_orig = True

        self.origin = (self.screen.w//2, self.screen.h//2)
        self.dx = 2
        self.dy = 1

        self.mouse = None

    @property
    def show_bg(self):
        return self.show_axis or self.show_orig

    @show_bg.setter
    def show_bg(self, value: bool):
        self.show_axis = value
        self.show_orig = value

    def screenToX(self, x: int):
        if self.dx == 0:
            return 0

        return (x - self.origin[0]) / self.dx

    def screenToY(self, y: int):
        if self.dy == 0:
            return 0

        return (self.origin[1] - y) / self.dy

    def xToScreen(self, x: int):
        return (x * self.dx) + self.origin[0]

    def yToScreen(self, y: int):
        return self.origin[1] - (y * self.dy)

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
        try:
            self.f = Function.compile("f", self.f_str)
        except (TokenizationError, CompilationError) as e:
            self.f = None
            self.error = e.args[0]
        else:
            if self.f and (vars := self.f.get_variables()) and vars != ["x"]:
                self.f = None
                self.error = "undefined variable(s): " + ", ".join(sorted(set(vars) - {"x"}))
            else:
                self.error = None

    def x_axis(self):
        if self.dx == 0:
            return

        if self.dx == 1:
            return Canvas(self.screen.w-1, 1, "+")

        cv = Canvas(self.screen.w-1, 1, "-")

        for sx in range(self.screen.w-1):
            x = self.screenToX(sx)

            if x.is_integer():
                cv.set_at(sx, 0, "+")

        return cv

    def y_axis(self):
        if self.dy == 0:
            return

        if self.dy == 1:
            return Canvas(1, self.screen.h-1, "+")

        cv = Canvas(1, self.screen.h-1, "|")

        for sy in range(self.screen.h-1):
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
        self.screen.write_at(0, self.screen.h-2, f"f(x)={self.f_str}"[-self.fw:])
        if self.error:
            self.screen.write_at(0, self.screen.h-1, ("Error: " + self.error)[-self.fw:])
        elif self.f:
            self.screen.write_at(0, self.screen.h-1, repr(self.f)[-self.fw:])

    def calc_f(self, x: int):
        if not self.f:
            return None

        success, res = self.f.execute({"x": x})

        if not success:
            log(f"Errors for f({x}):", *res)
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
            sy_int = round(sy)
            sy_float = sy - sy_int

            if 0 <= sy_int < self.screen.h:
                self.screen.set_at(sx, sy_int, get_char(0.5 - sy_float))

    def render(self):
        log_count("===============[ Render ]===============", id="render")

        # if self.bg_updated:
        if True:
            self.screen.fill(" ")
            self.draw_bg()
            self.draw_f()
        else:
            self.screen.rect(0, self.screen.h-2, self.fw, 2)
        self.write_f()

        self.terminal.hide_cursor()
        self.terminal.home()
        self.screen.draw(self.terminal)

        self.terminal.set_cursor(5 + len(self.f_str), self.screen.h-2)
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
        self.bg_updated = True
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
            self.bg_updated = False

        self.quit()

    # ========[ Event listeners ]========

    def on_key(self, ev: KeyEvent):
        match ev.key:
            case CTRL.c | CTRL.d | CTRL.q:
                self.stop()
            case CTRL.r:
                pass  # refresh
            case CTRL.space:
                self.origin = (self.screen.w//2, self.screen.h//2)
                self.dx = 2
                self.dy = 1
            case "b" if ev.alt:
                self.show_bg = not self.show_bg
            case "a" if ev.alt:
                self.show_axis = not self.show_axis
            case "o" if ev.alt:
                self.show_orig = not self.show_orig
            case "x" if ev.alt:
                self.dx += 1
            case "X" if ev.alt:
                self.dx -= 1
            case "y" if ev.alt:
                self.dy += 1
            case "Y" if ev.alt:
                self.dy -= 1
            case c if c in printable and not ev.alt:
                self.f_str += c
                self.update_f()
            case "\x7f":
                if not self.f_str:
                    return
                self.f_str = self.f_str[:-1]
                self.update_f()
            case _:
                return

        self.updated = True

    def on_paste(self, ev: PasteEvent):
        self.f_str += ev.text
        self.update_f()

    def on_mouse(self, ev: MouseEvent):
        match ev.button:
            case Terminal.BUTTON_LEFT:
                if ev.hold and self.mouse:
                    self.origin = self.origin[0] - self.mouse[0] + ev.x, self.origin[1] - self.mouse[1] + ev.y
                    self.updated = True
                self.mouse = (ev.x, ev.y)
            case Terminal.BUTTON_RELEASE:
                self.mouse = None
            case Terminal.SCROLL_UP:
                if not ev.alt:
                    self.origin = self.origin[0] - (ev.x - self.origin[0]) // 2, self.origin[1] - (ev.y - self.origin[1]) // 2
                self.dx *= 2
                self.dy *= 2
                self.updated = True
            case Terminal.SCROLL_DOWN:
                if not ev.alt:
                    self.origin = self.origin[0] + (ev.x - self.origin[0]) // 2, self.origin[1] + (ev.y - self.origin[1]) // 2
                self.dx /= 2
                self.dy /= 2
                self.updated = True

    def on_resize(self, ev: ResizeEvent):
        self.screen = Canvas(ev.w - 1, ev.h - 1)
        self.updated = True
        self.terminal.clear()

    def on_error(self, ev: ErrorEvent):
        log_exception(ev.exc)


def main():
    app = App(80, 30)

    app.run()

if __name__ == "__main__":
    try:
        start_log()
        main()
    finally:
        stop_log()
