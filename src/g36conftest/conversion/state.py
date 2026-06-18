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
    def __repr__(self):return f"{self.__class__.__name__}({self})"


    @classmethod
    def make_group(cls, states: list[Self]):
        _ = {str(s):s for s in states}
        # assert uniqueness
        assert(len(_) == len(frozenset(str(s) for s in states)) )
        assert(len(_) == len(frozenset(int(s) for s in states)) )
        return _



S = State
_ =  [
    S('True',   True),
    S('False',  False) ]
boolean = S.make_group(_)

_ =  [
    S('present', True),
    S('absent',  False) ]
occupancy = S.make_group(_)

_ =  [
    S('enabled', True),
    S('disabled',  False) ]
status = S.make_group(_)

_ =  [
    S('start', True),
    S('stop',  False) ]
commanded_state = S.make_group(_)

_ = [
    S('on',      True),
    S('off',     False),]
run_state = S.make_group(_)

_ = [
    S('closed',  True),
    S('open',    False),]
switch = S.make_group(_)

_ = [
    S('occupied',    1),
    S('cooldown',    2),
    S('setup',       3),
    S('warmup',      4),
    S('setback',     5),
    S('unoccupied',  6),
    S('none',        7),]
mode = S.make_group(_)


S.s = states = {}
for ss in (boolean, occupancy, status, commanded_state, run_state, switch, mode ):
    states.update(ss)
del ss
del _


# from int or bool, requires knowing the group

from typing import Literal
from functools import cache
@cache # make it a lookup 
def convert(state: State | str, dtype: Literal['int'] | Literal['bool'] = 'int') -> int | bool:
    if isinstance(state, str):
        state = states[str(State(state))]
    else:
        assert(isinstance(state, State))
    
    if dtype == 'int':
        value = int(state)
    else:
        assert(dtype == 'bool')
        value = bool(state)
    return value


