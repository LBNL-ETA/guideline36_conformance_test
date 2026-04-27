
class State(str):
    
    def __bool__(self): return self.bool
    def __int__(self):  return self.int
    def __eq__(self, other: 'Self'):
        return self.lower() == other.lower()

    def normalize(self): return self.upper()

    def __str__(self): return self.normalize()
    def __repr__(self):return f"{self.__class__.__name__}({self})"

    @classmethod
    def make(cls, name: str, value: int | bool):
        _ = cls(name)
        if isinstance(value, int):
            _.int = value
            _.bool = bool(value)
        else:
            assert(isinstance(value, bool))
            _.bool = value
            _.int = int(value)
        return _
    mk = make

    @classmethod
    def make_group(cls, states) -> dict:
        _ = {str(n):n for n in states}
        # assert uniqueness
        assert(len(_) == len(frozenset(str(s) for s in _.values())) )
        return _
    

S = State

_ =  [
    S.mk('True', True),
    S.mk('False',  False) ]
boolean = S.make_group(_)

_ =  [
    S.mk('present', True),
    S.mk('absent',  False) ]
occupancy = S.make_group(_)

_ =  [
    S.mk('enabled', True),
    S.mk('disabled',  False) ]
status = S.make_group(_)

_ =  [
    S.mk('start', True),
    S.mk('stop',  False) ]
commanded_state = S.make_group(_)

_ = [
    S.mk('on',      True),
    S.mk('off',     False),]
run_state = S.make_group(_)

_ = [
    S.mk('closed',  True),
    S.mk('open',    False),]
switch = S.make_group(_)

_ = [
    S.mk('occupied',    1),
    S.mk('cooldown',    2),
    S.mk('setup',       3),
    S.mk('warmup',      4),
    S.mk('setback',     5),
    S.mk('unoccupied',  6),
    S.mk('none',        7),]
mode = S.make_group(_)


S.s = states = {}
for ss in (boolean, occupancy, status, commanded_state, run_state, switch, mode ):
    states.update(ss)
del ss
del _


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



