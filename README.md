# CleanYourPhone app

**Status: early MVP. There is no installer or public build yet.**

This repository will hold the optional local app for people who prefer buttons over prompts:
pick a profile, review every package, apply in small batches, and restore from the undo journal.
No root, no cloud, no telemetry.

The product available today is the agent skill:
[github.com/jparedesDS/cleanyourphone](https://github.com/jparedesDS/cleanyourphone).
The CLI lives in that repository too.

## Not available yet

- No installer.
- No public build.
- No release.

When the first build exists, it will be published in this repository's Releases.

## Development

The app is Windows 10/11 x64 only and requires Python 3.12 or newer.

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m cleanyourphone_app --version
```

The app source is MIT. See [LICENSE](LICENSE).
