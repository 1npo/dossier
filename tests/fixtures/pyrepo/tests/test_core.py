from unittest import mock

import pytest

from shopcart import core


@pytest.fixture  # @bs-fixture
def items():
    return []


def test_total(items):  # @test-1
    assert core.total(items) == 0


@pytest.mark.skip(reason="later")
def test_skipped():  # @test-skip
    pass


def test_mocked():
    with mock.patch("shopcart.core.log"):  # @test-mock
        core.total([])
