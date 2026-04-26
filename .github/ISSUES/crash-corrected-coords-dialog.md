---
type: bug
title: Crash when clicking "Add corrected coordinates..."
labels: ["bug"]
---

## Description

Clicking **Add corrected coordinates...** in the cache detail view crashes immediately with a `TypeError`. `cache_detail.py` calls `CorrectedCoordsDialog` with `orig_lat`, `orig_lon`, `corrected_lat`, and `corrected_lon`, but the dialog's `__init__` only accepted `current_lat` and `current_lon`.

```
TypeError: CorrectedCoordsDialog.__init__() got an unexpected keyword argument 'orig_lat'
```

## Steps to Reproduce

1. Open the app
2. Select any cache in the list
3. Click **Add corrected coordinates...**
4. Observe the crash in the terminal

## Expected Behavior

The corrected coordinates dialog should open and allow the user to enter or edit corrected coordinates.

## Environment

- OS: macOS 24.1.0 (Darwin)
- Branch: implement-65

## Fix

Updated `CorrectedCoordsDialog.__init__()` in `src/opensak/gui/dialogs/corrected_coords_dialog.py` to accept `orig_lat`, `orig_lon`, `corrected_lat`, `corrected_lon`. The dialog pre-fills the input with `corrected_lat`/`corrected_lon` (the existing corrected coordinates) and `orig_lat`/`orig_lon` are available for future use (e.g. displaying original coordinates as reference).
