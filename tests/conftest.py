"""Shared fixtures for Collabuild MAS tests."""

import pytest
from collabuild.providers import DevProvider, create_provider


@pytest.fixture
def dev_provider():
    """A DevProvider instance for offline testing."""
    return DevProvider()


@pytest.fixture
def dev_config():
    """Config dict that activates the DevProvider."""
    return {"provider": "dev"}


@pytest.fixture
def dev_pipeline():
    """A CollabuildPipeline wired to the DevProvider."""
    from collabuild.pipeline import CollabuildPipeline
    provider = DevProvider()
    return CollabuildPipeline(provider=provider, model="dev-model")
