import pytest
from g36conftest.Test import Test as GTest # to not confuse pytest
gtest = GTest()

from pathlib import Path

@pytest.mark.parametrize("test_type", [
'foo_units',
])
def test(test_type):
    name = test_type
    gtest.start_test(to_csv=True, name=name)

    # conf = Path('conformance_tests') / test_type / 'config' / 'config.yaml'
    # assert(conf.exists())
    # from yaml import safe_load
    # conf = safe_load(open(conf))
    result = Path('conformance_tests') / name / 'results' / f'run_{name}' / \
        f'{name}_values.csv'
    assert(result.exists())
