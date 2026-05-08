import pytest
from g36conftest.Test import Test as GTest # to not confuse pytest
gtest = GTest()

from pathlib import Path

@pytest.mark.parametrize("test_type", [
'foo_units',
])
def test(name):
    gtest.start_test(to_csv=True, name=name)        
    assert(True)

