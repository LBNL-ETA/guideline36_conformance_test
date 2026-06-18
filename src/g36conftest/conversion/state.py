from typing import Self


class State(str):
    def __new__(cls, name: str, value: int | bool = -1) -> Self:
        _ = super().__new__(cls, name, )
        if type(value) is int:
            _.int = value
            _.bool = bool(value)
        else:
            assert(type(value) is bool)
            _.bool = value
            _.int = int(value)
        return _


    bool: bool
    def __bool__(self) -> bool: return self.bool
    int: int
    def __int__(self) -> int:  return self.int
    
    def __eq__(self, other: Self) -> bool:
        s = self.normalize() == other.normalize()
        i = int(self) == int(other)
        return s and i
    normalize = str.upper

    def __str__(self): return self.normalize()
    def __repr__(self):return f"{self.__class__.__name__}({self}, {int(self)})"

    def __hash__(self) -> int:
        return hash((str(self), int(self)))


# might just use 'bidict' lib for the group
# but this code has more attached functionality / encapsulation
class Group(frozenset):
    def __new__(cls, states: list[State] = []) -> Self:
        _ = {str(s):s for s in states}
        # assert uniqueness
        # assert or Exception?
        assert(len(_) == len(frozenset(str(s) for s in _.values())) )
        assert(len(_) == len(frozenset(int(s) for s in _.values())) )
        _ = super().__new__(cls, states)
        return _

    from functools import cache
    @cache
    def __getitem__(self, key: str | int | bool) -> State:
        if isinstance(key, str):
            for s in self:
                if str(s) == str(State(key)):
                    return s
        else:
            assert(type(key) in {int, bool} )
            for s in self:
                if int(s) == key:
                    return s
        raise KeyError('State not found')

    s: Groups


class Groups(dict[str, Group]):
    def __new__(cls, groups: dict[str, Group] = {} ) -> Self:
        # assert uniqueness of keys
        from itertools import chain
        _ = chain.from_iterable(groups.values())
        _ = frozenset(str(s) for s in _)
        assert(
            sum(len(g) for g in groups.values())
            ==
            len(frozenset(str(s) for s in _)))
        _ = super().__new__(cls, groups)
        return _



S = State
G = Group
groups = G.s = Groups({

'boolean': G([
    S('True',   True),
    S('False',  False) ]),

'occupancy': G([
    S('present', True),
    S('absent',  False) ]),

'status': G([
    S('enabled',    True),
    S('disabled',   False) ]),

'commanded_state': G([
    S('start', True),
    S('stop',  False) ]),

'run_state': G([
    S('on',      True),
    S('off',     False),]),

'switch': G([
    S('closed',  True),
    S('open',    False),]),

'mode': G([
    S('occupied',    1),
    S('cooldown',    2),
    S('setup',       3),
    S('warmup',      4),
    S('setback',     5),
    S('unoccupied',  6),
    S('none',        7),]),
})



from typing import Literal, Callable
from functools import cache
@cache # make it a lookup 
def convert(
        frm: State | str | int | bool,
        to: Literal['int'] | Literal['bool'] | Literal['str'] = 'int',
        *,
        group: str | None = None,
        groups: Groups | Callable[[], Groups] = groups) \
            -> int | bool | str:
    assert(to in {'int', 'bool', 'str'})
    fmap = {'int': int, 'bool': bool, 'str': str}
    if isinstance(groups, Callable): groups = groups()

    if isinstance(frm, State):
        return fmap[to](frm)
    elif isinstance(frm, str):
        if group:
            s = groups[group][frm]
            return fmap[to](s)
        else:
            for n, g in groups.items():
                for s in g:
                    if State(frm).normalize() == (s).normalize():
                        return fmap[to](s)
    else:
        assert(type(frm) in (int, bool))
        if not group:
            raise ValueError('need group to convert from a number or bool')
        g = groups[group]
        s = g[frm]
        return fmap[to](s)
    raise ValueError('unhandled conversion')
