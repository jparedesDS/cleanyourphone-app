"""Feature pages registered into the main window stack."""

from .base import Page
from .connect import ConnectPage
from .setup import ANDROID_SDK_TERMS_URL, SetupPage
from .welcome import WelcomePage

__all__ = [
    "ANDROID_SDK_TERMS_URL",
    "ConnectPage",
    "Page",
    "SetupPage",
    "WelcomePage",
]
