"""Shared fixtures for versioned training inputs."""

import pytest

from tests.fixtures.training import create_training_repository


@pytest.fixture
def training_dataset(tmp_path):
    return create_training_repository(tmp_path)
