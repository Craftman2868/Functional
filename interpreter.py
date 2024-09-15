from io import StringIO


"""
TODO: priority

"""


class Value:
    def get_variables(self):
        return set()

    def get_errors(self, env: dict):
        return []

    @property
    def expr(self):
        raise NotImplementedError("Value.expr should be overriden")

    @property
    def pexpr(self):
        return f"({self.expr})"

    def get_value(self, env: dict):
        raise NotImplementedError("Value.get_value() should be overriden")


class Number(Value):
    def __init__(self, n: float | str):
        self.n = float(n)

    @property
    def expr(self):
        return str(self.n)

    pexpr = expr

    def get_value(self, env: dict):
        return self.n


class VariableError(Exception): pass

class Variable(Value):
    def __init__(self, name: str):
        self.name = name

    @property
    def expr(self):
        return self.name

    pexpr = expr

    def get_variables(self):
        return {self.name}

    def get_errors(self, env: dict):
        if self.name not in env:
            return ["undefined variable: " + self.name]

        return []

    def get_value(self, env: dict):
        if self.name not in env:
            raise VariableError(self.name)

        return env[self.name]


class Operation(Value):
    def __init__(self, *args: Value):
        self.args = args

    @property
    def expr(self):
        raise NotImplementedError("Operation.expr should be overriden")

    def get_variables(self):
        res = set()

        for arg in self.args:
            res.update(arg.get_variables())

        return res

    def get_errors(self, env: dict):
        return sum((arg.get_errors(env) for arg in self.args), [])

    def get_value(self, env: dict):
        raise NotImplementedError("Operation.get_value() should be overriden")


class Addition(Operation):
    def __init__(self, a1: Value, a2: Value):
        super().__init__(a1, a2)

    @property
    def expr(self):
        return " + ".join(arg.expr for arg in self.args)

    def get_value(self, env: dict):
        return sum(t.get_value(env) for t in self.args)


class Substraction(Operation):
    def __init__(self, a1: Value, a2: Value):
        super().__init__(a1, a2)

    @property
    def expr(self):
        return " - ".join(arg.expr for arg in self.args)

    def get_value(self, env: dict):
        return self.args[0].get_value(env) - self.args[1].get_value(env)


class Multiplication(Operation):
    def __init__(self, a1: Value, a2: Value):
        super().__init__(a1, a2)

    @property
    def expr(self):
        return " * ".join(arg.pexpr for arg in self.args)

    def get_value(self, env: dict):
        return self.args[0].get_value(env) * self.args[1].get_value(env)


class Division(Operation):
    def __init__(self, a1: Value, a2: Value):
        super().__init__(a1, a2)

    @property
    def expr(self):
        return " / ".join(arg.pexpr for arg in self.args)

    def get_errors(self, env: dict):
        errors = super().get_errors(env)

        if errors:
            return errors

        if self.args[1].get_value(env) == 0:
            return ["cannot devide by zero"]

        return []

    def get_value(self, env: dict):
        return self.args[0].get_value(env) / self.args[1].get_value(env)


class Modulo(Division):
    @property
    def expr(self):
        return " % ".join(arg.pexpr for arg in self.args)

    def get_value(self, env: dict):
        return self.args[0].get_value(env) % self.args[1].get_value(env)


class Power(Operation):
    def __init__(self, a1: Value, a2: Value):
        super().__init__(a1, a2)

    @property
    def expr(self):
        return " ^ ".join(arg.pexpr for arg in self.args)

    def get_errors(self, env: dict):
        errors = super().get_errors(env)

        if errors:
            return errors

        if self.args[0].get_value(env) < 0 and not self.args[1].get_value(env).is_integer():
            return ["complex numbers not supported"]

        return []

    def get_value(self, env: dict):
        return self.args[0].get_value(env) ** self.args[1].get_value(env)


class TokenizationError(Exception): pass

def get_token(file: StringIO):
    t = None
    pos = file.tell()+1
    token = ""

    while (c := file.read(1)):
        if c.isspace():
            if t:
                file.seek(file.tell()-1)
                break
            t = "space"
            break

        if c.isalpha():
            if not t:
                t = "name"
            elif t != "name":
                file.seek(file.tell()-1)
                break
        elif t == "name":
            file.seek(file.tell()-1)
            break

        if c in "0123456789":
            if not t:
                t = "number"
            elif t != "number":
                file.seek(file.tell()-1)
                break
        elif c == ".":
            if t != "number":
                raise TokenizationError(f"'.' not expected (pos: {file.tell()})")
            if "." in token:
                raise TokenizationError(f"several '.' in one number (pos: {file.tell()})")
        elif t == "number":
            file.seek(file.tell()-1)
            break

        if c in "()+-*/%^":
            if t:
                file.seek(file.tell()-1)
                break
            return "special", c, pos

        if not t:
            raise TokenizationError(f"unexpected token: '{c}' (pos: {file.tell()})")

        token += c

    if not t:
        return None

    if t == "number" and token.endswith("."):
        raise TokenizationError(f"digit(s) expected after '.' (pos: {file.tell()})")

    return t, token, pos

def tokenize(file: StringIO):
    while (t := get_token(file)) is not None:
        if t[0] != "space":
            yield t


class CompilationError(Exception): pass

def compile_tokens(tokens, parenthesis: bool = False):
    val = None
    op = None

    def value(n: Value):
        nonlocal val, op

        if val is None:
            val = n
        else:
            if op is None:
                op = Multiplication
            val = op(val, n)
            op = None

    while True:
        try:
            t, token, pos = next(tokens)
        except StopIteration:
            break

        match t:
            case "number":
                n = Number(token)

                if op is None and isinstance(val, Number):
                    raise CompilationError(f"'{token}' unexpected (pos: {pos})")

                value(n)
                continue
            case "name":
                v = Variable(token)

                value(v)
                continue
            case "special":
                pass  # See below
            case _:
                raise AssertionError  # Impossible

        assert t == "special"

        match token:
            case "(":
                v = compile_tokens(tokens, True)

                if v == Ellipsis:
                    raise CompilationError(f"unmatched '(' (pos: {pos})")

                value(v)
            case ")":
                if not parenthesis:
                    raise CompilationError(f"unmatched ')' (pos: {pos})")
                elif val is None:
                    raise CompilationError(f"empty parenthesis (pos: {pos})") from None

                parenthesis = False

                break
            case "+":
                if op is not None:
                    raise CompilationError(f"'+' unexpected (pos: {pos})")

                if val is None:
                    val = Number(0)

                op = Addition
            case "-":
                if op is not None:
                    raise CompilationError(f"'-' unexpected (pos: {pos})")

                if val is None:
                    val = Number(0)

                op = Substraction
            case "*":
                if op is not None:
                    raise CompilationError(f"'*' unexpected (pos: {pos})")

                if val is None:
                    raise CompilationError(f"value expected before '*' (pos: {pos})")

                op = Multiplication
            case "/":
                if op is not None:
                    raise CompilationError(f"'/' unexpected (pos: {pos})")

                if val is None:
                    raise CompilationError(f"value expected before '/' (pos: {pos})")

                op = Division
            case "%":
                if op is not None:
                    raise CompilationError(f"'%' unexpected (pos: {pos})")

                if val is None:
                    raise CompilationError(f"value expected before '%' (pos: {pos})")

                op = Modulo
            case "^":
                if op is not None:
                    raise CompilationError(f"'^' unexpected (pos: {pos})")

                if val is None:
                    raise CompilationError(f"value expected before '^' (pos: {pos})")

                op = Power

    if op is not None:
        raise CompilationError(f"value expected after an operator (pos: {pos})")

    if parenthesis:
        return Ellipsis

    return val


class Function:
    def __init__(self, name: str, val: Value):
        self.name = name
        self.val = val

    @property
    def expr(self):
        return self.val.expr

    def get_variables(self):
        return sorted(self.val.get_variables())

    def get_errors(self, env: dict):
        try:
            return self.val.get_errors(env)
        except OverflowError:
            return ["overflow"]

    def execute(self, env: dict):
        if (errors := self.get_errors(env)):
            return False, errors

        try:
            return True, self.val.get_value(env)
        except OverflowError:
            return False, ["overflow"]

    @classmethod
    def compile(cls, name: str, text: str):
        file = StringIO(text)

        tokens = tokenize(file)

        val = compile_tokens(tokens)

        if val is None:
            return None

        return cls(name, val)

    def __repr__(self):
        return f"{self.name}({', '.join(self.get_variables())}) = {self.expr}"
