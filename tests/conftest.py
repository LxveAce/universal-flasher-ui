"""Shared pytest fixtures.

Qt widgets/threads are exercised headlessly via the offscreen platform plugin,
so the suite runs on CI and machines without a display. The pure-logic tests
(protocols, profile loader, cross-comm broker, settings) need none of this.
"""

import os

# Must be set before PyQt5 imports a platform plugin.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication for widget/thread tests."""
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
