# Packaging Plan — Linux AppImage

## Goal
Package Money Tracker as a single `.AppImage` file for Linux so a new user can download it and double-click to run — no Python, no package manager, no install required.

## Key decisions
- **Linux only** (for now)
- **Tool**: `python-appimage`
- **Database stays external**: lives at `~/.local/share/money-tracker/money_tracker.db`, created automatically on first run — not bundled inside the image (AppImage filesystem is read-only)

## What ends up on the user's machine
| File | Location |
|------|----------|
| `MoneyTracker.AppImage` | Wherever they download it |
| `money_tracker.db` | `~/.local/share/money-tracker/` (auto-created on first run) |

To uninstall: delete the AppImage + optionally `~/.local/share/money-tracker/`.

## New user steps
1. Download `MoneyTracker.AppImage`
2. `chmod +x MoneyTracker.AppImage` (or right-click → Allow Executing in file manager)
3. Double-click to run
4. DB is created automatically on first launch

## Build steps (to implement)
1. Install `python-appimage` on the build machine
2. Create an `appimage-builder` recipe or use `python-appimage` CLI to wrap `app.py` and its dependencies
3. Ensure `customtkinter` assets (themes, fonts) are included — may need explicit `--include-data-dir` flags
4. Test on a clean Linux VM with no Python installed
5. Verify `~/.local/share/money-tracker/` path works correctly from inside the AppImage environment

## Notes
- Build machine needs the same architecture as target (x86-64 → x86-64)
- `python-appimage` downloads a base Python AppImage and layers the app on top — no system Python needed on the build machine either (just pip)
- If Tcl/Tk issues arise, `python-appimage` bundles its own Tcl/Tk so this should be handled automatically
- Future: Mac distribution would use `briefcase` (`.app` / `.dmg`); Windows would use PyInstaller or briefcase
