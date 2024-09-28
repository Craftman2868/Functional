from event.event import BaseEvent, KeyEvent
from event.eventable import Eventable

from sys import stdout, platform
from threading import Thread, current_thread
from os import get_terminal_size
from time import monotonic
from string import printable

from typing import Any, Callable

from log import *

if platform == "win32":
    from msvcrt import kbhit, getch
    from colorama import init

    init()
    _UNIX = False
else:
    import tty
    import termios
    from sys import stdin
    import signal
    from select import select

    _UNIX = True

    def kbhit():
        return bool(select([stdin], [], [], 0)[0])

NO_UNDERLINE = False
NO_ITALIC = False

ESC = '\x1b'
CSI = ESC + '['
OSC = ESC + ']'
ENTER = '\n\r'
KEYS = [
    "home",
    "insert",
    "delete",
    "end",
    "pageup",
    "pagedown",
    "home",
    "end",
    None,
    None,
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    None,
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    None,
    "f11",
    "f12",
    "f13",
    "f14",
    None,
    "f15",
    "f16",
    None,
    "f17",
    "f18",
    "f19",
    "f20",
    None,
]
SS3_KEYS = {
    "P": "f1",
    "Q": "f2",
    "R": "f3",
    "S": "f4",
}
# Warning: may cause bugs if too low
ALT_TIMEOUT = 0.4  # s


@(lambda cls: cls())
class CTRL:
    """
    Convert a character to this character with the control modifier

    Example:
        CTRL("a")   ## represents `CTRL + A`
        CTRL.b      ## represents `CTRL + B`
        CTRL.C      ## represents `CTRL + C`
    """

    def __getattr__(self, char: str):
        return self(char)

    def __call__(self, char: str):
        if char.lower() == "space":
            char = " "
        return chr(ord(char) & 31)


old_settings = None


def get_key_init():
    global old_settings
    if _UNIX:
        old_settings = termios.tcgetattr(stdin.fileno())
        tty.setraw(stdin.fileno())


def get_key_quit():
    global old_settings

    if not old_settings:
        return

    if _UNIX:
        termios.tcsetattr(stdin.fileno(), termios.TCSAFLUSH, old_settings)
        old_settings = None


def get_key():
    if _UNIX:
        if not old_settings:
            raise RuntimeError(
                "get_key not initialized (call get_key_init before)")
        key = chr(ord(stdin.buffer.raw.read(1)))
    else:
        try:
            key = getch().decode()
        except UnicodeDecodeError:
            key = get_key()

    return key


def get_key_nb():
    if not kbhit():
        return None

    return get_key()


def generate_fg_color_string(r: int, g: int, b: int):
    return f"{CSI}38;2;{r};{g};{b}m"


def generate_bg_color_string(r: int, g: int, b: int):
    return f"{CSI}48;2;{r};{g};{b}m"


generate_color_string = generate_fg_color_string
bg = generate_bg_color_string
fg = generate_fg_color_string


def write(s, flush: bool = False):
    stdout.write(s)
    if flush:
        stdout.flush()


class Terminal(Eventable):
    RESET = 0

    # Styles
    BOLD =      1 << 0
    DIM =       1 << 1
    ITALIC =    1 << 2
    UNDERLINE = 1 << 3
    BLINK =     1 << 4
    INVERSE =   1 << 5
    # OVERLINED = 1 << 6

    # Foreground colors
    FG_BLACK =  1 << 8
    FG_RED =    1 << 9
    FG_GREEN =  1 << 10
    FG_YELLOW = 1 << 11
    FG_BLUE =   1 << 12
    FG_MAGENTA =1 << 13
    FG_CYAN =   1 << 14
    FG_WHITE =  1 << 15

    # Background colors
    BG_BLACK =  1 << 16
    BG_RED =    1 << 17
    BG_GREEN =  1 << 18
    BG_YELLOW = 1 << 19
    BG_BLUE =   1 << 20
    BG_MAGENTA =1 << 21
    BG_CYAN =   1 << 22
    BG_WHITE =  1 << 23

    STYLES = {
        # Styles
        BOLD:       "1",
        DIM:        "2",
        ITALIC:     "3",
        UNDERLINE:  "4",
        BLINK:      "5",
        INVERSE:    "7",
        # OVERLINED:  "53",

        # Foreground colors
        FG_BLACK:   "30",
        FG_RED:     "31",
        FG_GREEN:   "32",
        FG_YELLOW:  "33",
        FG_BLUE:    "34",
        FG_MAGENTA: "35",
        FG_CYAN:    "36",
        FG_WHITE:   "37",

        # Background colors
        BG_BLACK:   "40",
        BG_RED:     "41",
        BG_GREEN:   "42",
        BG_YELLOW:  "43",
        BG_BLUE:    "44",
        BG_MAGENTA: "45",
        BG_CYAN:    "46",
        BG_WHITE:   "47",
    }

    # Mouse
    BUTTON_LEFT = 0
    BUTTON_MIDDLE = 1
    BUTTON_RIGHT = 2
    BUTTON_RELEASE = 3
    SCROLL_UP = 64
    SCROLL_DOWN = 65

    def __init__(self, event_queue: list[BaseEvent] | None = None):
        super().__init__(event_queue)

        self.cursorPos = [0, 0]
        self.get_char_thread = Thread(target=self.loop_get_chars)
        self.thread_started = False
        self.running = False
        self.show_char = False
        self.pasting = False
        self.paste_text = None
        self.last_key = None
        self.props = {}
        self.current_style = None

    @property
    def size(self):
        return self.get_size()

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]

    @staticmethod
    def term_prop(name: str, value: Any = ...):
        def decorator(func: Callable):
            def wrapper(self, force: bool = False, *args, **kwargs):
                if self.set_prop(name, value) or force:
                    return func(self, *args, **kwargs)

            return wrapper

        if value is Ellipsis:
            if callable(name):
                func = name

                n = func.__name__

                if (name := n.removeprefix("enable_")) != n:
                    value = True
                elif (name := n.removeprefix("disable_")) != n:
                    value = False
                else:
                    raise ValueError("Cannot detect property name")

                return decorator(func)
            else:
                raise ValueError("Must specify a value to the property")

        return decorator

    def get_prop(self, name: str) -> Any:
        return self.props.get(name)

    def set_prop(self, name: str, value: Any) -> bool:
        if self.get_prop(name) == value:
            return False

        self.props[name] = value
        return True

    def enable_show_char(self):
        self.show_char = True

    def disable_show_char(self):
        self.show_char = False

    def stop_running(self):
        self.running = False

    @term_prop
    def enable_mouse_tracking(self, flush: bool = False):
        write(CSI + '?1002h', flush=flush)

    @term_prop
    def disable_mouse_tracking(self, flush: bool = False):
        write(CSI + '?1002l', flush=flush)

    @term_prop
    def enable_bracketed_paste(self, flush: bool = False):
        write(CSI + '?2004h', flush=flush)

    @term_prop
    def disable_bracketed_paste(self, flush: bool = False):
        write(CSI + '?2004l', flush=flush)

    def reset(self, flush: bool = False):
        if self.current_style == 0:
            return

        self.current_style = 0
        write(CSI + '0m', flush=flush)

    def add_style(self, style: int = 0, flush: bool = False):
        if self.current_style is None:
            self.reset()

        for s, code in self.STYLES.items():
            if style & s:
                if self.current_style & s:
                    continue
                self.current_style |= s
                if NO_UNDERLINE and s == self.UNDERLINE:
                    continue
                if NO_ITALIC and s == self.ITALIC:
                    continue
                write(CSI + code + "m")

        if flush:
            self.flush()

    def set_style(self, style: int = 0, flush: bool = False):
        if self.current_style is None:
            self.reset()
        elif self.current_style & ~style:
            self.reset()

        self.add_style(style, flush=flush)

    def remove_style(self, style: int = 0, flush: bool = False):
        if self.current_style is None:
            self.reset()

        self.set_style(self.current_style & ~style, flush=flush)

    def get_cursor_pos(self):
        write(CSI + '6n')

    def start_get_chars(self):
        self.get_char_thread.start()
        self.thread_started = True

    def stop_get_chars(self):
        self.stop_running()
        if not self.thread_started:
            return
        if self.get_char_thread is not current_thread():
            self.get_char_thread.join()
        self.thread_started = False

    def handle_sigwinch(self, *_):
        self.call_event("resize", *self.size)

    def parse_csi(self):
        # log("Parsing CSI...")
        args = get_key()

        if args == 'M':
            # log("Mouse tracking")
            if not self.get_prop("mouse_tracking"):
                log("Error: got a mouse tracking command but mouse tracking is not enabled")
                return
            args = [get_key() for _ in range(3)]
            # log("Mouse tracking args:", ", ".join(str(ord(a)) for a in args))
            self.call_event("mouse", *self.parse_mouse_event(args))
            return

        # log("CSI arg:", args)
        while not (args[-1].isalpha() or args[-1] == '~'):
            args += get_key()
            # log("CSI arg:", args[-1])

            if len(args) > 10:
                # log("CSI args too long: cancel")
                self.call_event("key", ESC)
                self.call_event("key", c)
                for c in args:
                    self.call_event("key", c)
                break
        else:
            # log("CSI command: ", repr(args))
            self.csi_command(args[:-1], args[-1])

    def parse_ss3(self):
        c = get_key()

        if c not in SS3_KEYS:
            log("Error: invalid SS3 key:", repr(c))
            return

        key = SS3_KEYS[c]

        self.call_event("key", key)

    def get_chars(self, last_is_escape: bool = False) -> bool:
        try:
            c = get_key_nb()
            t = monotonic()
        except UnicodeDecodeError:
            return False

        if not self.running:
            return None

        if self.last_key:
            ti = t - self.last_key
        else:
            ti = 0

        if last_is_escape and ti >= ALT_TIMEOUT:
            self.call_event("key", ESC)
            last_is_escape = False

        if c == None:
            return last_is_escape

        self.last_key = t

        if c == ESC:
            return True

        if c == "\r":
            c = "\n"

        match c:
            case '[' if last_is_escape:
                self.parse_csi()
            case 'O' if last_is_escape:
                self.parse_ss3()
            case char if last_is_escape:  # and ti < ALT_TIMEOUT  ## (see above)
                self.call_event("key", char, True)
            case _:
                if self.pasting:
                    last_is_escape = False  # Ignore escape chars
                    self.paste_text += c
                    # self.call_event("paste_char", c)
                    return False
                self.call_event("key", c)

        return False

    def loop_get_chars(self):
        self.running = True

        get_key_init()

        self.call_event("start")

        last_is_escape = False
        while self.running:
            try:
                last_is_escape = self.get_chars(last_is_escape)
            except Exception as e:
                self.call_event("error", e)

        get_key_quit()

    def parse_mouse_event(self, args):
        button = ord(args[0]) - 32
        x = ord(args[1]) - 32
        y = ord(args[2]) - 32
        return [button & 67, x-1, y-1, button & 60]

    def csi_command(self, args: str, command: str):
        # log("CSI", repr(args), repr(command))
        command = command.upper()
        match command:
            case 'A':
                self.call_event("key", "up")
            case 'B':
                self.call_event("key", "down")
            case 'C':
                self.call_event("key", "right")
            case 'D':
                self.call_event("key", "left")
            case 'F':
                self.call_event("key", "end")
            case 'H':
                self.call_event("key", "home")
            case '~':
                if not args.isdecimal():
                    log("Error: invalid CSI command arg for '~':", repr(args))
                    return
                n = int(args)
                if n < len(KEYS):
                    key = KEYS[int(args)-1]

                    if key is not None:
                        self.call_event("key", key)
                else:
                    if n == 200:
                        self.pasting = True
                        self.paste_text = ""
                        self.call_event("paste_begin")
                    elif n == 201:
                        self.pasting = False
                        self.call_event("paste", self.paste_text)
                        self.paste_text = None
            case 'R':
                self.cursorPos = [int(n) for n in args.split(';')]
                self.call_event("cursor_pos", self.cursorPos)
            case _:
                log("Warning: got an unknown CSI command:",
                    repr(args), repr(command))

    def on_key(self, event: KeyEvent):
        if self.show_char:
            if event.key in ENTER:
                write('\n')
            elif event.key in printable:
                write(event.key)
            elif event.key in "\x7f\x08":
                self.left()
                write(' ')
                self.left()

    def set_default_listeners(self):
        self.add_listener(CTRL.C, lambda _: (self.call_event("stop")))
        self.add_listener(CTRL.D, lambda _: (self.call_event("stop")))

    def scroll_up(self, lines=1, flush: bool = False):
        write(CSI + f'{lines}S', flush=flush)

    scroll = scroll_up

    def scroll_down(self, lines=1, flush: bool = False):
        write(CSI + f'{lines}T', flush=flush)

    def clear_screen(self, flush: bool = False):
        write(CSI + '2J', flush=flush)

    clear = clear_screen

    def clear_line(self, y: int = None, flush: bool = False):
        if y is not None:
            self.set_cursor_pos(0, y)
        write(CSI + '2K', flush=flush)

    def clear_to_end_of_line(self, flush: bool = False):
        write(CSI + '0K', flush=flush)

    def clear_to_end_of_screen(self, flush: bool = False):
        write(CSI + '0J', flush=flush)

    def set_cursor_pos(self, x: int, y: int, flush: bool = False):
        write(CSI + str(y+1) + ';' + str(x+1) + 'H', flush=flush)

    set_cursor = set_cursor_pos
    move_to = set_cursor_pos
    go_to = set_cursor_pos
    move = set_cursor_pos
    move_cursor = set_cursor_pos

    @term_prop("cursor_visible", True)
    def set_cursor_visible(self, flush: bool = False):
        write(CSI + '?25h', flush=flush)

    show_cursor = set_cursor_visible

    @term_prop("cursor_visible", False)
    def set_cursor_invisible(self, flush: bool = False):
        write(CSI + '?25l', flush=flush)

    hide_cursor = set_cursor_invisible

    @term_prop("cursor_blink", True)
    def set_cursor_blink(self, flush: bool = False):
        write(CSI + '?12h', flush=flush)

    @term_prop("cursor_blink", False)
    def set_cursor_no_blink(self, flush: bool = False):
        write(CSI + '?12l', flush=flush)

    def left(self, flush: bool = False):
        write(CSI + 'D', flush=flush)

    def right(self, flush: bool = False):
        write(CSI + 'C', flush=flush)

    def up(self, flush: bool = False):
        write(CSI + 'A', flush=flush)

    def down(self, flush: bool = False):
        write(CSI + 'B', flush=flush)

    def set_title(self, title, flush: bool = False):
        write(OSC + '2;' + title + '\x07', flush=flush)

    @term_prop
    def enable_alternative_screen(self, flush: bool = False):
        self.save_cursor_pos()
        write(CSI + '?1049h')
        self.reset()
        self.clear_screen(flush=flush)

    @term_prop
    def disable_alternative_screen(self, flush: bool = False):
        write(CSI + '?1049l')
        self.restore_cursor_pos(flush=flush)

    def save_cursor_pos(self, flush: bool = False):
        write(CSI + 's', flush=flush)

    def restore_cursor_pos(self, flush: bool = False):
        write(CSI + 'u', flush=flush)

    def home(self, flush: bool = False):
        write(CSI + 'H', flush=flush)

    def set_fg_color(self, r: int, g: int, b: int, force: bool = False, flush: bool = False):
        """
        WARNING: Avoid using this method (not compatible with Terminal.set_style...)
        """
        if self.set_prop("fg", (r, g, b)) or force:
            write(generate_fg_color_string(r, g, b), flush=flush)

    def set_bg_color(self, r: int, g: int, b: int, force: bool = False, flush: bool = False):
        """
        WARNING: Avoid using this method (not compatible with Terminal.set_style...)
        """
        if self.set_prop("bg", (r, g, b)) or force:
            write(generate_bg_color_string(r, g, b), flush=flush)

    fg = set_fg_color
    bg = set_bg_color

    def flush(self):
        stdout.flush()

    def write(self, text: str, flush: bool = False):
        if NO_UNDERLINE and self.current_style & self.UNDERLINE:
            text = text.replace(" ", "_")
        write(text, flush=flush)

    def write_line(self, line: str = "", flush: bool = False):
        self.write(line + "\r\n", flush=flush)

    def write_at(self, x: int, y: int, text: str, flush: bool = False):
        self.set_cursor_pos(x, y)
        self.write(text, flush=flush)

    def fill(self, x: int, y: int, w: int, h: int, char: str, flush: bool = False):
        for i in range(h):
            self.write_at(x, y + i, char * w)

        if flush:
            self.flush()

    def get_size(self):
        return tuple(get_terminal_size())

    def init_sig(self):
        if _UNIX:
            signal.signal(signal.SIGWINCH, self.handle_sigwinch)

    def uninit_sig(self):
        if _UNIX:
            signal.signal(signal.SIGWINCH, signal.SIG_DFL)

    def uninit(self):
        self.disable_alternative_screen()
        self.disable_mouse_tracking()
        self.disable_bracketed_paste()
        self.show_cursor()
        self.reset()

    def stop(self):
        self.uninit()
        self.stop_get_chars()
