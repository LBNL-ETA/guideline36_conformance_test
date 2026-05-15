import pytest
import pytest
from pathlib import Path
test_dir = Path(__file__).parent

@pytest.fixture(scope='session')
def cache_dir() ->Path:
    return test_dir / '.pytest_cache'
@pytest.fixture(scope="session")
def lazy_datadir() -> Path:
    return test_dir / "regression-data"
@pytest.fixture(scope="session")
def original_datadir() -> Path:
    return test_dir / "regression-data"



from g36conftest.Test import Test as GTest # to not confuse pytest
gtest = GTest()

import pandas as pd

@pytest.mark.parametrize("test_type", [
'foo_units',
])
def test(test_type, dataframe_regression):
    name = test_type
    gtest.start_test(to_csv=True, name=name)

    # conf = Path('conformance_tests') / test_type / 'config' / 'config.yaml'
    # assert(conf.exists())
    # from yaml import safe_load
    # conf = safe_load(open(conf))
    result = Path('conformance_tests') / name / 'results' / f'run_{name}' / \
        f'{name}_values.csv'
    assert(result.exists())
    result = pd.read_csv(result)
    dataframe_regression.check(result) # might use text regression

