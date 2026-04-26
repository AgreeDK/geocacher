"""
tests/test_monkey.py — GUI monkey test.

Strategy
--------
1. Systematic pass  — shuffle every discoverable target (actions, buttons,
   combos, table rows, line edits) and fire each one exactly once.
2. Random pass      — RANDOM_ACTIONS additional random interactions to hit
   combinations and state-dependent code paths.

A background QTimer auto-dismisses every modal that pops up, always
choosing the safe/non-destructive button (No / Cancel / Escape).
Non-modal top-level windows (e.g. trip planner) are closed after each step.

The test fails if any unhandled exception is caught via sys.excepthook or
sys.unraisablehook (the latter catches exceptions raised inside Qt slots).

Run manually:
    pytest tests/test_monkey.py -v -s

Skipped automatically when pytest-qt is not installed (regular unit-test CI
job does not install GUI dependencies).
"""

from __future__ import annotations

import random
import sys

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QLineEdit,
    QMessageBox,
    QWidget,
)

# ── Config ────────────────────────────────────────────────────────────────────

RANDOM_ACTIONS = 60
SEED = 42
DISMISS_INTERVAL_MS = 150

_RANDOM_TEXT = ["", "GC12345", "abc", "!@#$%", "0", "N 55° 12.345 E 012° 34.567"]

# ── Helpers ───────────────────────────────────────────────────────────────────


def _dismiss_modal(app: QApplication) -> None:
    """Close the active modal dialog, preferring the safe/non-destructive button."""
    modal = app.activeModalWidget()
    if modal is None:
        return
    if isinstance(modal, QMessageBox):
        for role in (
            QMessageBox.ButtonRole.RejectRole,
            QMessageBox.ButtonRole.NoRole,
        ):
            for btn in modal.buttons():
                if modal.buttonRole(btn) == role:
                    btn.click()
                    return
        QTest.keyClick(modal, Qt.Key.Key_Escape)
    elif isinstance(modal, QDialog):
        QTest.keyClick(modal, Qt.Key.Key_Escape)


def _close_stray_windows(main_window: QWidget) -> None:
    """Close any top-level window that isn't the main window (e.g. trip planner)."""
    for w in QApplication.topLevelWidgets():
        if w is not main_window and w.isVisible() and isinstance(w, QWidget):
            w.close()


def _collect_targets(window: QWidget) -> list[tuple[str, object]]:
    """Return (kind, target) pairs for every interactive element in the window."""
    targets: list[tuple[str, object]] = []

    # QActions from menus and toolbar — skip Quit (Ctrl+Q) to keep the window alive.
    quit_seq = QKeySequence("Ctrl+Q")
    for action in window.findChildren(QAction):
        if action.isEnabled() and not action.isSeparator():
            if action.shortcut() != quit_seq:
                targets.append(("action", action))

    for widget in window.findChildren(QAbstractButton):
        if widget.isVisible() and widget.isEnabled():
            targets.append(("button", widget))

    for widget in window.findChildren(QComboBox):
        if widget.isVisible() and widget.isEnabled() and widget.count() > 0:
            targets.append(("combo", widget))

    for widget in window.findChildren(QAbstractItemView):
        if widget.isVisible() and widget.isEnabled():
            model = widget.model()
            if model and model.rowCount() > 0:
                targets.append(("table", widget))

    for widget in window.findChildren(QLineEdit):
        if widget.isVisible() and widget.isEnabled():
            targets.append(("lineedit", widget))

    return targets


def _label(kind: str, target: object) -> str:
    """Return a human-readable identifier for a target (used in the coverage report)."""
    if kind == "action":
        text = target.text().replace("&", "").strip()  # type: ignore[union-attr]
        shortcut = target.shortcut().toString()  # type: ignore[union-attr]
        return f"action  {text!r}" + (f" [{shortcut}]" if shortcut else "")
    text = getattr(target, "text", lambda: "")()
    name = target.objectName() if hasattr(target, "objectName") else ""  # type: ignore[union-attr]
    cls = type(target).__name__
    identifier = text or name or cls
    return f"{kind:<8} {identifier!r}"


def _fire(kind: str, target: object, rng: random.Random, qtbot) -> None:
    """Trigger one interaction."""
    if kind == "action":
        target.trigger()  # type: ignore[union-attr]
    elif kind == "button":
        qtbot.mouseClick(target, Qt.MouseButton.LeftButton)
    elif kind == "combo":
        target.setCurrentIndex(rng.randint(0, target.count() - 1))  # type: ignore[union-attr]
    elif kind == "table":
        model = target.model()  # type: ignore[union-attr]
        if model and model.rowCount() > 0:
            row = rng.randint(0, model.rowCount() - 1)
            target.setCurrentIndex(model.index(row, 0))  # type: ignore[union-attr]
    elif kind == "lineedit":
        target.setText(rng.choice(_RANDOM_TEXT))  # type: ignore[union-attr]


# ── Fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture
def monkey_window(qtbot, tmp_path, monkeypatch):
    """MainWindow backed by a fresh throwaway database."""
    import opensak.db.manager as mgr_module
    from opensak.db.database import init_db
    from opensak.db.manager import DatabaseInfo
    from opensak.lang import load_language

    load_language("en")

    db_path = tmp_path / "monkey.db"
    init_db(db_path=db_path)

    # Seed the DB with real GPX data so the table, detail panel, and cache-
    # dependent actions (edit/delete waypoint, GPS export, trip planner…) are
    # all exercised with actual rows rather than an empty database.
    from opensak.db.database import get_session
    from opensak.importer import import_gpx
    from tests.data import SAMPLE_GPX, SAMPLE_WPTS_GPX, make_variant_gpx

    gpx_file = tmp_path / "sample.gpx"
    gpx_file.write_text(SAMPLE_GPX, encoding="utf-8")
    wpts_file = tmp_path / "sample-wpts.gpx"
    wpts_file.write_text(SAMPLE_WPTS_GPX, encoding="utf-8")

    with get_session() as session:
        import_gpx(gpx_file, session, wpts_path=wpts_file)

    variant_file = tmp_path / "variant.gpx"
    variant_file.write_text(make_variant_gpx("GCAAA01", "GCAAA02"), encoding="utf-8")
    with get_session() as session:
        import_gpx(variant_file, session)

    # Lightweight stand-in that never touches the user's QSettings or real DBs.
    class _FakeManager:
        def __init__(self):
            self._info = DatabaseInfo("MonkeyTest", db_path)

        @property
        def active(self):
            return self._info

        @property
        def active_path(self):
            return self._info.path

        @property
        def databases(self):
            return [self._info]

        def ensure_active_initialised(self):
            pass

        def switch_to(self, db_info):
            pass

        def new_database(self, name, path=None):
            raise RuntimeError("new_database called during monkey test")

    monkeypatch.setattr(mgr_module, "_manager", _FakeManager())

    from opensak.gui.mainwindow import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    # Wait for the QTimer.singleShot(100) that loads the cache table.
    qtbot.wait(300)

    yield window

    mgr_module._manager = None


# ── Test ──────────────────────────────────────────────────────────────────────


def test_monkey(monkey_window, qtbot):
    """
    Systematic pass through all targets, then RANDOM_ACTIONS random extras.
    Fails on any unhandled exception (both excepthook and unraisablehook).
    """
    window = monkey_window
    app = QApplication.instance()
    rng = random.Random(SEED)
    errors: list[Exception] = []

    original_excepthook = sys.excepthook
    original_unraisablehook = sys.unraisablehook

    def _capture(exc_type, exc_value, tb):
        errors.append(exc_value)
        original_excepthook(exc_type, exc_value, tb)

    def _capture_unraisable(unraisable):
        errors.append(unraisable.exc_value)
        original_unraisablehook(unraisable)

    sys.excepthook = _capture
    sys.unraisablehook = _capture_unraisable

    dismisser = QTimer()
    dismisser.setInterval(DISMISS_INTERVAL_MS)
    dismisser.timeout.connect(lambda: _dismiss_modal(app))
    dismisser.start()

    fired: set[str] = set()

    def _step(kind, target):
        lbl = _label(kind, target)
        print(f"  → {lbl}")
        fired.add(lbl)
        _dismiss_modal(app)
        qtbot.wait(40)
        try:
            _fire(kind, target, rng, qtbot)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        _dismiss_modal(app)
        _close_stray_windows(window)
        qtbot.wait(30)

    try:
        # ── Warm-up: select the first cache so the detail panel populates and
        #    cache-dependent buttons (corrected coords, edit, delete…) become
        #    visible before the systematic scan runs.
        for view in window.findChildren(QAbstractItemView):
            model = view.model()
            if model and model.rowCount() > 0:
                view.setCurrentIndex(model.index(0, 0))
                qtbot.wait(150)
                break

        # ── 1. Systematic pass: every target once, in shuffled order ──────────
        print("\n── Systematic pass ──────────────────────────────────────────")
        all_targets = _collect_targets(window)
        rng.shuffle(all_targets)
        for kind, target in all_targets:
            if not window.isVisible():
                break
            _step(kind, target)

        # ── 2. Random pass: re-collect (state may have changed) and randomise ─
        print("\n── Random pass ──────────────────────────────────────────────")
        for _ in range(RANDOM_ACTIONS):
            if not window.isVisible():
                break
            targets = _collect_targets(window)
            if targets:
                kind, target = rng.choice(targets)
                _step(kind, target)

    finally:
        dismisser.stop()
        sys.excepthook = original_excepthook
        sys.unraisablehook = original_unraisablehook
        _dismiss_modal(app)
        _close_stray_windows(window)

    # ── Coverage report ───────────────────────────────────────────────────────
    final_targets = _collect_targets(window)
    never_fired = {_label(k, t) for k, t in final_targets} - fired
    print(f"\n── Coverage report ──────────────────────────────────────────")
    print(f"   Fired {len(fired)} unique targets across both passes.")
    if never_fired:
        print(f"   ⚠  {len(never_fired)} target(s) visible at end but never fired:")
        for lbl in sorted(never_fired):
            print(f"      • {lbl}")
    else:
        print("   ✓ All targets visible at end of test were fired at least once.")

    assert not errors, (
        f"Monkey test caught {len(errors)} exception(s):\n"
        + "\n".join(str(e) for e in errors)
    )
