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


@pytest.fixture(params=['foo_units', 'foo' ])
def gtest(request):
    """Generates a unique temporary file for each parameter set."""
    test_type = request.param    
    global_config_tmpl = test_dir / 'config' / 'global_config_template.yaml'
    dir = global_config_tmpl.parent
    pth = dir / f'{test_type}_global_config.yaml'
    from yaml import safe_load as load
    ct = load(open(global_config_tmpl))
    ct['test_type'] = test_type
    from yaml import dump
    dump(ct, open(pth, 'w'), indent=4)

    result = Path('conformance_tests') / test_type / 'results' / f'run_{test_type}' / \
            f'{test_type}_values.csv'
    if result.exists(): result.unlink() # does not repro if i don't delete
    gt = GTest(global_config_path=pth)
    gt._test_result_path = result # att to obj
    yield gt
    # cleanup
    if pth.exists():
        pth.unlink()


from g36conftest.Test import Test as GTest # to not confuse pytest
import pandas as pd
def test_result(gtest, dataframe_regression):
    gtest.start_test(to_csv=True, name=gtest.test_type)
    assert(gtest._test_result_path.exists())
    # conf = Path('conformance_tests') / test_type / 'config' / 'config.yaml'
    # assert(conf.exists())
    # from yaml import safe_load
    # conf = safe_load(open(conf))
    result = pd.read_csv(gtest._test_result_path).set_index('time')
    dataframe_regression.check(result) # might use text regression


#def test(test_type, )
# TODO make tests out of the spreadsheet tests hah
