import pytest

from g36conftest.Test import Test
gtest = Test()

@pytest.mark.parametrize("test_type", [
'foo_units',
])
def test(test_type):
    name = test_type
    gtest.start_test(to_csv=True, name=name)
    assert(True)

