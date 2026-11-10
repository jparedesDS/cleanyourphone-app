# Third-party notices

CleanYourPhone 0.1.0 is built from several open-source components. This file is
installed next to the application by `CleanYourPhone-Setup-0.1.0.exe` and is
also present in the source repository.

## CleanYourPhone app

The desktop application source in this repository is licensed under the MIT
License. See [LICENSE](LICENSE). Copyright (c) 2026 jparedesDS.

## CleanYourPhone CLI (sidecar)

The app ships a frozen build of the CleanYourPhone CLI at tag `v0.3.1` from
<https://github.com/jparedesDS/cleanyourphone>. The CLI is licensed under the
MIT License, copyright (c) 2026 jparedesDS.

The sidecar includes its pinned profile catalog. Profiles are data, not code,
and are distributed with the CLI under the same MIT License. The sidecar is
started as a separate process from `resources/cli/cleanyourphone.exe`.

## PySide6, Qt for Python and Qt

The user interface uses PySide6 (Qt for Python), which is provided under the
GNU Lesser General Public License version 3 (LGPLv3), the GNU General Public
License version 3 (GPLv3), or a commercial Qt license. This application uses
PySide6 under the LGPLv3.

Qt 6 and the Qt libraries bundled with PySide6 are also available under the
LGPLv3 (or GPLv3/commercial terms). The Qt libraries are shipped unmodified as
separate dynamic libraries next to `CleanYourPhone.exe`, so they can be
replaced with compatible builds as allowed by the LGPL.

- Project: <https://www.qt.io/qt-for-python>
- PySide6 source: <https://code.qt.io/cgit/pyside/pyside-setup.git/>
- Qt source: <https://code.qt.io/cgit/qt/>
- LGPLv3 text: <https://www.gnu.org/licenses/lgpl-3.0.html>
- GPLv3 text: <https://www.gnu.org/licenses/gpl-3.0.html>

PySide6 and Qt include third-party components with their own permissive
licenses (for example PCRE2, zlib, FreeType, HarfBuzz and libpng). Their notices
and license texts are included in the PySide6/Qt distributions and source
archives linked above.

## Python

The frozen application embeds the CPython runtime. Python is distributed under
the Python Software Foundation License Version 2. See
<https://docs.python.org/3/license.html>.

## PyInstaller

The application and sidecar are frozen with PyInstaller. PyInstaller is
distributed under the GNU General Public License version 2 with a special
exception that permits distribution of frozen applications under their own
terms. See <https://pyinstaller.org/en/stable/license.html>.

## Inno Setup

The Windows installer is produced with Inno Setup 6. Inno Setup is free software
and permits royalty-free distribution of installers it creates. See
<https://jrsoftware.org/isinfo.php>.

## Android SDK Platform Tools / ADB

ADB (Android Debug Bridge) is **not bundled** with CleanYourPhone and is **not
redistributed** by this application or its installer. The app locates an
existing ADB installation or downloads Android SDK Platform Tools directly from
Google on first run, at the user's request. ADB remains subject to Google's
Android SDK license terms:

- <https://developer.android.com/studio/terms>
- <https://developer.android.com/tools/releases/platform-tools>

## MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
