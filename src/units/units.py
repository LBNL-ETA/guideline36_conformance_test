# from . import ureg. this should work if the code is packaged.
from src.units import unit_registry
reg = unit_registry
Q = reg.Quantity


def unit(q: str | Q, explicit=True): # explict. don't want pint to interpret. probably better performance
    if isinstance(q, str):
        assert(not q[0].isnumeric())
        if explicit:
            to_pint: dict[str, Q]  = { 
                # temps
                'F': reg('fahrenheit'), # just 'F' incorrectly interpreted
                'C': reg('celsius'),
                'K': reg('kelvin'),
                # flows
                'cfm': reg('cubic_foot / minute'), # 'cfm' incorrectly interpreted with default reg
                'm3/s': reg('meter ** 3 / second')
            }
            for d in ('F', 'C', ): # but not 'K'
                assert(d in to_pint)
                to_pint[f'delta_{d}'] = reg(f'delta_{to_pint[d].units}')
            return reg.Quantity(to_pint[q])
        else: # allow interpretation
            return reg.Quantity(q)
    else:
        assert(isinstance(q, Q))
        assert(q.magnitude == 1)
        return q
u = unit


def convert(frm: Q, to: Q):
    return frm.to(to)


# print(
# convert( Q(1, u('cfm')), u('m3/s') )
# #1 * Q('F')
# )
