from io import StringIO

import math
from typing import Self


@(lambda cls: cls())
class IgnoreMe:
    def __repr__(self):
        return "IgnoreMe"


class Value:
    def ignore(self, env: dict):
        return False

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
        self.accept_function = False

    def ignore(self, env: dict):
        return env.get(self.name) is IgnoreMe

    @property
    def expr(self):
        return self.name

    pexpr = expr

    def get_variables(self):
        return {self.name}

    def get_errors(self, env: dict):
        if self.name not in env:
            return ["undefined variable: " + self.name]

        val = env[self.name]

        if val is IgnoreMe:
            return []

        if not self.accept_function and isinstance(val, NativeFunction):
            return ["variable expected (got a function): " + self.name]

        return []

    def get_value(self, env: dict):
        if self.name not in env:
            raise VariableError(self.name)

        return env[self.name]

    def is_func(self, env: dict):
        return isinstance(env.get(self.name), NativeFunction)


class Parenthesis(Value):
    def __init__(self, value: Value):
        self.value = value

    def ignore(self, env: dict):
        return self.value.ignore(env)

    def get_variables(self):
        return self.value.get_variables()

    def get_errors(self, env: dict):
        return self.value.get_errors(env)

    @property
    def expr(self):
        return self.value.expr

    def get_value(self, env: dict):
        return self.value.get_value(env)


class OperationType(type):
    def __lt__(cls, other: Self):
        if cls.priority is None:
            raise NotImplementedError("Operation priority not defined")

        return cls.priority < other.priority
    def __gt__(cls, other: Self):
        if cls.priority is None:
            raise NotImplementedError("Operation priority not defined")

        return cls.priority > other.priority

    def __eq__(cls, other: Self):
        if cls.priority is None:
            raise NotImplementedError("Operation priority not defined")

        return cls.priority == other.priority


class Operation(Value, metaclass=OperationType):
    priority = None

    def __init__(self, *args: Value):
        self.args = args

    def ignore(self, env: dict):
        return any(arg.ignore(env) for arg in self.args)

    @property
    def expr(self):
        raise NotImplementedError("Operation.expr should be overriden")

    def get_args(self, env: dict):
        return tuple(arg.get_value(env) for arg in self.args)

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
    priority = 1

    def __init__(self, a1: Value, a2: Value):
        super().__init__(a1, a2)

    @property
    def expr(self):
        return " + ".join(arg.expr for arg in self.args)

    def get_value(self, env: dict):
        if self.ignore(env):
            return IgnoreMe

        return sum(self.get_args(env))


class Substraction(Operation):
    priority = 1

    def __init__(self, a1: Value, a2: Value):
        super().__init__(a1, a2)

    @property
    def expr(self):
        return " - ".join(arg.expr for arg in self.args)

    def get_value(self, env: dict):
        if self.ignore(env):
            return IgnoreMe

        a0, a1 = self.get_args(env)

        return a0 - a1


class Multiplication(Operation):
    priority = 2

    def __init__(self, a1: Value, a2: Value):
        super().__init__(a1, a2)

    @property
    def expr(self):
        return " * ".join(arg.pexpr for arg in self.args)

    def get_value(self, env: dict):
        if self.ignore(env):
            return IgnoreMe

        a0, a1 = self.get_args(env)

        return a0 * a1


class ImplicitMultiplication(Multiplication):
    priority = 3

    def __init__(self, a1: Value, a2: Value):
        if isinstance(a1, Variable):
            a1.accept_function = True

        super().__init__(a1, a2)

    @property
    def expr(self):
        if not isinstance(self.args[0], Variable):
            return super().expr

        return f"{self.args[0].expr}({self.args[1].expr})"

    def get_value(self, env: dict):
        if self.ignore(env):
            return IgnoreMe

        if isinstance(self.args[0], Variable) and self.args[0].is_func(env):
            return self.args[0].get_value(env).execute(self.args[1].get_value(env))

        return super().get_value(env)


class Division(Operation):
    priority = 2

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
        if self.ignore(env):
            return IgnoreMe

        a0, a1 = self.get_args(env)

        return a0 / a1


class Modulo(Division):
    priority = 2

    @property
    def expr(self):
        return " % ".join(arg.pexpr for arg in self.args)

    def get_value(self, env: dict):
        if self.ignore(env):
            return IgnoreMe

        a0, a1 = self.get_args(env)

        return a0 % a1


class Power(Operation):
    priority = 4

    def __init__(self, a1: Value, a2: Value):
        super().__init__(a1, a2)

    @property
    def expr(self):
        return " ^ ".join(arg.pexpr for arg in self.args)

    def get_errors(self, env: dict):
        errors = super().get_errors(env)

        if errors:
            return errors

        a0 = self.args[0].get_value(env)
        a1 = self.args[1].get_value(env)

        if a0 is IgnoreMe or a1 is IgnoreMe:
            return []

        if a0 < 0 and not a1.is_integer():
            return ["complex numbers not supported"]

        if a0 == 0 and a1 < 0:
            return ["zero cannot be raised to a negative power"]

        return []

    def get_value(self, env: dict):
        if self.ignore(env):
            return IgnoreMe

        a0, a1 = self.get_args(env)

        return a0 ** a1


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


def fusion(v1: Value, op: OperationType, v2: Value):
    if not isinstance(v1, Operation):
        return op(v1, v2)

    if type(v1) > op:
        return op(v1, v2)

    return type(v1)(*v1.args[:-1], fusion(v1.args[-1], op, v2))


def compile_tokens(tokens, parenthesis: bool = False):
    val = None
    op = None

    def value(n: Value):
        nonlocal val, op

        if val is None:
            val = n
        else:
            if op is None:
                op = ImplicitMultiplication
            val = fusion(val, op, n)
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

                value(Parenthesis(v))
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


class BaseFunction:
    def __init__(self, name: str):
        self.name = name

    def get_variables(self):
        return []

    def get_errors(self, *args, **kwargs):
        raise NotImplementedError("BaseFunction.get_errors should be overriden")

    def execute(self, *args, **kwargs):
        raise NotImplementedError("BaseFunction.execute should be overriden")

    def __repr__(self):
        return f"{self.name}({', '.join(self.get_variables())})"

class Function(BaseFunction):
    def __init__(self, name: str, val: Value):
        self.name = name
        self.val = val

    @property
    def expr(self):
        return self.val.expr

    def get_variables(self):
        return sorted(self.val.get_variables())

    def get_errors(self, *args, **kwargs):
        assert not args

        try:
            return self.val.get_errors(kwargs)
        except OverflowError:
            return ["overflow"]
        except Exception as e:
            return [repr(e)]

    def execute(self, *args, **kwargs):
        assert not args

        if (errors := self.get_errors(**kwargs)):
            return False, errors

        try:
            return True, self.val.get_value(kwargs)
        except OverflowError:
            return False, ["overflow"]
        except Exception as e:
            return False, [repr(e)]

    @classmethod
    def compile(cls, name: str, text: str):
        file = StringIO(text)

        tokens = tokenize(file)

        val = compile_tokens(tokens)

        if val is None:
            return None

        return cls(name, val)

    def __repr__(self):
        return f"{super().__repr__()} = {self.expr}"


class NativeFunction(BaseFunction):
    def __init__(self, name: str):
        super().__init__(self)
        self.func = None

    def get_variables(self):
        return []

    def get_errors(self):
        return []

    def execute(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def __call__(self, func):
        self.func = func


class MathNativeFunction(NativeFunction):
    def __init__(self, f):
        super().__init__(f.__name__)
        self.func = f

    def get_variables(self):
        return ["x"]

    def execute(self, *args, **kwargs):
        assert not kwargs

        return super().execute(*args, **kwargs)

    __call__ = object.__call__


MATH_FUNCTIONS = {}
MATH_VARIABLES = {}

funcs = vars(math)
funcs["abs"] = abs

for n, v in funcs.items():
    if n.startswith("_"):
        continue

    if callable(v):
        f = MathNativeFunction(v)
        MATH_FUNCTIONS[n] = f
    else:
        MATH_VARIABLES[n] = v

MATH_ENV = MATH_FUNCTIONS | MATH_VARIABLES
