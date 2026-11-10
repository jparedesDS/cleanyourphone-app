"""Feature pages registered into the main window stack."""

from .base import Page
from .blocked import SAFETY_DOCS_URL, BlockedPage
from .check import CheckPage
from .connect import ConnectPage
from .setup import ANDROID_SDK_TERMS_URL, SetupPage
from .welcome import WelcomePage

__all__ = [
    "ANDROID_SDK_TERMS_URL",
    "SAFETY_DOCS_URL",
    "BlockedPage",
    "CheckPage",
    "ConnectPage",
    "Page",
    "SetupPage",
    "WelcomePage",
]
