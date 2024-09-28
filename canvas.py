from typing import Self
from terminal import Terminal


DEFAULT_CHAR = " "
DEFAULT_STYLE = Terminal.RESET


assert isinstance(DEFAULT_CHAR, str) and len(DEFAULT_CHAR) == 1


class Canvas:
    def __init__(self, w: int, h: int, char: str = DEFAULT_CHAR):
        assert len(char) == 1

        self.w = w
        self.h = h
        self.data = [char * self.w] * self.h

    def draw(self, term: Terminal):
        for line in self.data:
            l = line.rstrip()

            term.write(l)

            if len(l) != len(line):
                term.clear_to_end_of_line()

            term.write_line()

    def get_at(self, x: int, y: int):
        # assert 0 <= x < self.w  ## Will be checked in get_line_part()
        # assert 0 <= y < self.h

        return self.get_line_part(y, x, 1)

    def set_at(self, x: int, y: int, char: str):
        # assert 0 <= x < self.w  ## Will be checked in set_line_part()
        # assert 0 <= y < self.h
        assert len(char) == 1

        self.set_line_part(y, x, char)

    def split_text(self, x: int, y: int, text: str):
        assert 0 <= x < self.w
        assert 0 <= y < self.h

        for line in text.split("\n"):
            while True:
                pw = min(self.w - x, len(line))
                yield x, y, line[:pw]
                line = line[pw:]
                y += 1
                if y >= self.h:
                    return
                x = 0

                if not line:
                    break

    def write_at(self, x: int, y: int, text: str):
        for x, y, part in self.split_text(x, y, text):
            self.set_line_part(y, x, part)

    def get_line(self, y: int):
        assert 0 <= y < self.h

        return self.data[y]

    def set_line(self, y: int, line: str):
        assert 0 <= y < self.h
        assert len(line) == self.w

        self.data[y] = line

    def get_line_part(self, y: int, x: int, w: int):
        if not w:
            return ""

        assert 0 <= x < self.w
        assert 0 <= y < self.h
        assert 0 <= w <= self.w - x

        return self.get_line(y)[x:x+w]

    def set_line_part(self, y: int, x: int, part: str):
        if not part:
            return

        assert 0 <= x < self.w
        assert 0 <= y < self.h

        w = len(part)
        
        assert 0 <= w <= self.w - x

        l = self.get_line(y)

        self.set_line(y, l[:x] + part + l[x+w:])

    def fill(self, char: str):
        assert len(char) == 1

        l = char * self.w

        for y in range(self.h):
            self.set_line(y, l)
    
    def clear(self):
        self.fill(DEFAULT_CHAR)

    def copy(self):
        new = self.__class__(self.w, self.h)

        new.data = self.data.copy()

        return new

    def copy_line_part(self, dest: Self, y: int, dest_y: int, x: int):
        assert 0 <= x < self.w
        assert 0 <= y < self.h
        assert 0 <= dest_y <= dest.w

        dest.set_line(dest_y, self.get_line_part(y, x, dest.w))

    def blit_line_part(self, src: Self, y: int, src_y: int, x: int):
        assert 0 <= x < self.w
        assert 0 <= y < self.h
        assert 0 <= src_y <= src.h

        self.set_line_part(y, x, src.get_line(src_y))

    def copy_line(self, dest: Self, y: int, dest_y: int):
        assert 0 <= y < self.h
        assert 0 <= dest_y <= dest.w
        assert dest.w == self.w

        dest.set_line(dest_y, self.get_line(y))

    def blit_line(self, src: Self, y: int, src_y: int):
        return src.copy_line(self, src_y, y)

    def sub(self, x: int, y: int, w: int, h: int):
        assert 0 <= x < self.w
        assert 0 <= y < self.h
        assert 0 <= w <= self.w - x
        assert 0 <= h <= self.h - y

        if x == 0 and y == 0 and w == self.w and h == self.h:
            return self.copy()

        new = self.__class__(w, h)

        for new_y, cur_y in enumerate(range(y, y + h)):
            self.copy_line_part(new, cur_y, new_y, x)

        return new

    def blit(self, src: Self, x: int, y: int):
        assert 0 <= x < self.w
        assert 0 <= y < self.h
        assert 0 <= src.w <= self.w - x
        assert 0 <= src.h <= self.h - y

        for src_y, cur_y in enumerate(range(y, y + src.h)):
            self.blit_line_part(src, cur_y, src_y, x)

    def rect(self, x: int, y: int, w: int, h: int, *args):
        self.blit(
            self.__class__(w, h, *args),
            x, y
        )

    def __repr__(self):
        return f"<{self.__class__.__name__} w={self.w} h={self.h}>"


class StylizedCanvas(Canvas):
    def __init__(self, w: int, h: int, char: str = DEFAULT_CHAR, style: int = DEFAULT_STYLE):
        super().__init__(w, h)

        self.styles = [[style] * self.w for _ in range(self.h)]

    def draw(self, term: Terminal):
        for line, style in zip(self.data, self.styles):
            for c, s in zip(line, style):
                term.render.set_style(s, False)
                term.render.write(c, False)
            term.write_line(flush=False)

        term.reset(True)

    def get_style_at(self, x: int, y: int):
        # assert 0 <= x < self.w  ## Will be checked in get_style_line_part()
        # assert 0 <= y < self.h

        return self.get_style_line_part(y, x, 1)[0]

    def set_style_at(self, x: int, y: int, style: int):
        # assert 0 <= x < self.w  ## Will be checked in set_style_line_part()
        # assert 0 <= y < self.h

        self.set_style_line_part(y, x, [style])

    def get_style_line(self, y: int):
        assert 0 <= y < self.h

        return self.styles[y]

    def set_style_line(self, y: int, style: list):
        assert 0 <= y < self.h
        assert len(style) == self.w

        self.styles[y] = style.copy()

    def get_style_line_part(self, y: int, x: int, w: int):
        if not w:
            return []

        assert 0 <= x < self.w
        assert 0 <= y < self.h
        assert 0 <= w <= self.w - x

        return self.get_style_line(y)[x:x+w]

    def set_style_line_part(self, y: int, x: int, part: list):
        if not part:
            return

        assert 0 <= x < self.w
        assert 0 <= y < self.h

        w = len(part)

        assert 0 <= w <= self.w - x

        l = self.get_style_line(y)

        self.set_style_line(y, l[:x] + part + l[x+w:])

    def copy(self):
        new = super().copy()

        new.styles = self.styles.copy()

    def copy_line(self, dest: Self, y: int, dest_y: int, x: int):
        super().copy_line(dest, y, dest_y, x)

        dest.set_style_line(dest_y, self.get_style_line(y))

    def copy_line_part(self, dest: Self, y: int, dest_y: int, x: int):
        super().copy_line_part(dest, y, dest_y, x)

        dest.set_style_line(dest_y, self.get_style_line_part(y, x, dest.w))

    def blit_line_part(self, src: Self, y: int, src_y: int, x: int):
        super().blit_line_part(src, y, src_y, x)

        self.set_style_line_part(y, x, src.get_style_line(src_y))

    def fill_style(self, style: int):
        for y in range(self.h):
            self.set_style_line(y, [style] * self.w)

    def clear_style(self):
        self.fill_style(DEFAULT_STYLE)

    def clear(self):
        super().clear()
        self.clear_style()
