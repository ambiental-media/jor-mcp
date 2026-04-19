from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True, scope="session")
def mock_firebase_init() -> MagicMock:
    """Prevent actual Firebase Admin SDK initialization during all tests.

    Patches get_app() to return a mock (simulating an already-initialized app)
    so AuthMiddleware.__init__ never calls initialize_app() against real GCP
    credentials.
    """
    mock_app = MagicMock(name="firebase_default_app")
    with patch("firebase_admin.get_app", return_value=mock_app), patch(
        "firebase_admin.initialize_app", return_value=mock_app
    ):
        yield mock_app
