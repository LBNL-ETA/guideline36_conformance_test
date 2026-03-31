
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
    S.mk('present', True),
    S.mk('absent',  False) ]
presence = S.make_group(_)

_ = [
    S.mk('closed',  True),
    S.mk('open',    False),]
gate = S.make_group(_)

_ = [
    S.mk('on',      True),
    S.mk('off',     False),]
switch = S.make_group(_)

_ = [
    S.mk(  'occupied',  True),
    S.mk('unoccupied',  False),]
occupancy = S.make_group(_)

_ = [
    S.mk('warmup',       1),
    S.mk('cooldown',    -1),]
tempphase = S.make_group(_)

_ = [
    S.mk('setback', -1),
    S.mk('setup',    1),]
set_ = S.make_group(_)

_ = [
    S.mk('freeze-protection', 1)]
protection = S.make_group(_)


S.s = states = {}
for ss in (presence, gate, switch, occupancy, tempphase, set_, protection ):
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



