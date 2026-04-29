"""
src/opensak/gui/dialogs/filter_dialog.py — Komplet filter dialog.

Tre faner:
1. Generelt  — navn, type, D/T, afstand, fundet, tilgængelighed osv.
2. Datoer    — udlagt dato, seneste log dato
3. Attributter — alle Groundspeak attributter

Understøtter gem/indlæs filterprofiler.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QComboBox, QDoubleSpinBox, QTabWidget, QWidget,
    QGroupBox, QScrollArea, QGridLayout,
    QDialogButtonBox, QMessageBox, QInputDialog,
    QDateEdit, QSizePolicy, QFrame, QPlainTextEdit
)
from PySide6.QtCore import QDate

from opensak.lang import tr
from opensak.utils import flags
from opensak.filters.engine import (
    FilterSet, SortSpec,
    CacheTypeFilter, ContainerFilter,
    DifficultyFilter, TerrainFilter,
    FoundFilter, NotFoundFilter,
    AvailableFilter, ArchivedFilter, AvailabilityFilter,
    CountryFilter, NameFilter, GcCodeFilter,
    PlacedByFilter, DistanceFilter,
    AttributeFilter, HasTrackableFilter,
    PremiumFilter, NonPremiumFilter,
    FilterProfile,
)


# ── Groundspeak attribut definitioner ─────────────────────────────────────────
# Komplet officiel liste fra geocaching.com/about/icons.aspx
# Kilde for ID-numre: Groundspeak Live API / Project-GC database dump
# Format: (groundspeak_id, translation_key)
#
# TILLADELSER (Allowed/Not Allowed)
#   1  Dogs
#   32 Bicycles
#   33 Motorcycles
#   34 Off-road vehicles
#   35 Snowmobiles
#   36 Horses
#   16 Campfires
#   65 Trucks/RVs
#
# BETINGELSER (Yes/No)
#   6  Recommended for kids
#   7  Takes less than an hour
#   8  Scenic view
#   9  Significant hike
#   10 Difficult climbing
#   11 May require wading
#   12 May require swimming
#   13 Available at all times
#   14 Recommended at night
#   15 Available during winter
#   40 Stealth required
#   68 Needs maintenance
#   18 Dangerous animals / Livestock
#   49 Field puzzle
#   37 Night cache
#   53 Park and grab
#   57 Abandoned structure
#   43 Short hike (<1 km)
#   44 Medium hike (1-10 km)
#   45 Long hike (>10 km)
#   62 Seasonal access
#   22 Recommended for tourists
#   46 Yard (private residence)
#   60 Teamwork required
#   71 Challenge cache
#   72 Power trail
#   73 Bonus cache
#
# SPECIELLE (Yes/No)
#   67 Lost and Found tour
#   69 Partnership cache
#   70 GeoTour
#   74 Solution checker
#
# UDSTYR (Required/Not Required)
#   2  Access or parking fee
#   3  Climbing gear
#   4  Boat
#   5  Scuba gear
#   51 Flashlight required
#   50 UV light required
#   41 May require snowshoes
#   58 May require cross country skis
#   9  Special tool required  ← NOTE: 9 is "Significant hike" above
#      Actually ID 9 = Significant hike, special tool = different ID
#      From DB: id=9 is "Significant Hike", no separate "special tool" shown
#      Geocaching.com page says "Special tool required" — this maps to id=25
#      But DB shows id=25 = "Stroller accessible"? Let me use what geocaching.com image filenames show
#   25 Stroller accessible (from API result: id=41=stroller, but DB says 25)
#      → Use image filename as ground truth: stroller=41, special_tool=25 per some sources
#   64 Tree climbing required
#
# FARER (Present/Not Present)
#   17 Poisonous plants
#   18 Dangerous animals  (same id used for livestock above — they are the same attribute)
#   19 Ticks
#   20 Abandoned mines
#   21 Cliff / falling rocks
#   52 Hunting area
#   26 Dangerous area
#   28 Thorns  ← from geocaching.com list; 28 also = Public restrooms in some mappings
#              → Use geocaching.com image URL to verify: thorns = id 62 in some, 28 in others
#
# FACILITETER (Yes/No)
#   24 Wheelchair accessible
#   23 Parking nearby
#   27 Public transportation nearby
#   28 Drinking water nearby  ← conflict with Thorns above
#   29 Public restrooms nearby
#   30 Telephone nearby
#   21 Picnic tables nearby  ← conflict with Cliff above
#   47 Camping nearby
#   41 Stroller accessible
#   66 Fuel nearby
#   31 Food nearby
#
# NOTE: There are ID conflicts in various sources. The Project-GC DB dump (search result)
# is the most authoritative. We use those IDs. The DB showed:
#   17=Poisonous plants, 18=Dangerous Animals, 19=Ticks, 20=Abandoned mines, 21=Cliff/rocks
#   22=Scenic view(?), but geocaching.com page groups differently.
#   We keep IDs that are confirmed from the API JSON example (id=24=wheelchair, id=13=available,
#   id=7=onehour, id=6=kids, id=41=stroller, id=28=restrooms, id=26=public transport)
#   and the DB (1=dogs, 2=fee, 3=rappelling/climbing, 4=boat, 5=scuba, 6=kids, 7=onehour,
#   8=scenic, 9=hiking, 10=climbing, 11=wading, 12=swimming, 13=available, 14=night,
#   15=winter, 17=poisonoak, 18=dangerousanimals, 19=ticks, 20=mine, 21=cliff)

from opensak.utils.constants import ATTRIBUTES, CACHE_TYPES, CONTAINER_SIZES


# ── D/T spin box: snaps to valid 0.5-increment values (1.0–5.0) ──────────────

class DTSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox restricted to the nine standard D/T values (1.0–5.0 in 0.5 steps).
    The text field is read-only — value can only be changed via the arrow buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(1.0, 5.0)
        self.setSingleStep(0.5)
        self.setDecimals(1)
        self.setValue(1.0)
        self.lineEdit().setReadOnly(True)


# ── Hjælper widget: tre-tilstands checkbox (Ja / Nej / Ingen) ─────────────────

class TriStateBox(QWidget):
    """Tre-tilstands kontrol: Ja ✓ / Nej ✗ / Ingen (ignorér)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._ja  = QCheckBox(tr("yes"))
        self._nej = QCheckBox(tr("no"))
        layout.addWidget(self._ja)
        layout.addWidget(self._nej)

    @property
    def state(self) -> Optional[bool]:
        """None=ignorér, True=ja, False=nej"""
        if self._ja.isChecked() and not self._nej.isChecked():
            return True
        if self._nej.isChecked() and not self._ja.isChecked():
            return False
        return None

    def reset(self) -> None:
        self._ja.setChecked(False)
        self._nej.setChecked(False)


# ── Filter dialog ─────────────────────────────────────────────────────────────

class FilterDialog(QDialog):
    """Komplet filter dialog med tre faner."""

    filter_applied = Signal(object, object, str)  # FilterSet, SortSpec, profile_name

    def __init__(self, parent=None, current_filterset: Optional[FilterSet] = None,
                 last_profile_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr("filter_dialog_title"))
        self._attr_boxes: dict[int, tuple] = {}
        # Startsstørrelse: 70% af skærm, aldrig større end 1000x850
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            w = min(1000, int(rect.width()  * 0.70))
            h = min(850,  int(rect.height() * 0.70))
            self.resize(w, h)
            # Centrér på skærmen
            self.move(
                rect.x() + (rect.width()  - w) // 2,
                rect.y() + (rect.height() - h) // 2,
            )
        self._setup_ui()
        if last_profile_name:
            for i in range(self._profile_combo.count()):
                if self._profile_combo.itemText(i) == last_profile_name:
                    self._profile_combo.setCurrentIndex(i)
                    break
        elif current_filterset:
            self._load_filterset(current_filterset)

    # ── UI bygning ────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Gem/indlæs profil ─────────────────────────────────────────────────
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel(tr("filter_saved_label")))
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(180)
        # Undgå at udløse _on_profile_selected mens vi fylder combo
        self._profile_combo.blockSignals(True)
        self._load_profiles_into_combo()
        self._profile_combo.blockSignals(False)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        profile_row.addWidget(self._profile_combo)

        save_btn = QPushButton(tr("filter_save_btn"))
        save_btn.setMaximumWidth(80)
        save_btn.clicked.connect(self._save_profile)
        profile_row.addWidget(save_btn)

        self._del_btn = QPushButton("🗑")
        self._del_btn.setMaximumWidth(40)
        self._del_btn.setToolTip(tr("filter_delete_profile_tooltip"))
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._delete_profile)
        profile_row.addWidget(self._del_btn)

        profile_row.addStretch()
        layout.addLayout(profile_row)

        # ── Faneblade ─────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._where_tab = None
        self._general_tab = self._build_general_tab()
        self._dates_tab = self._build_dates_tab()
        self._attributes_tab = self._build_attributes_tab()
        self._tabs.addTab(self._general_tab, tr("filter_tab_general"))
        self._tabs.addTab(self._dates_tab, tr("filter_tab_dates"))
        self._tabs.addTab(self._attributes_tab, tr("filter_tab_attributes"))
        if flags.where_filter:
            self._where_tab = self._build_where_tab()
            self._tabs.addTab(self._where_tab, tr("filter_tab_where"))
        layout.addWidget(self._tabs)

        # ── Knapper ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        apply_btn = QPushButton(tr("filter_apply_btn"))
        apply_btn.setStyleSheet("font-weight: bold;")
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)

        reset_btn = QPushButton(tr("filter_reset_all_btn"))
        reset_btn.clicked.connect(self._reset_all)
        btn_row.addWidget(reset_btn)

        reset_tab_btn = QPushButton(tr("filter_reset_tab_btn"))
        reset_tab_btn.clicked.connect(self._reset_current_tab)
        btn_row.addWidget(reset_tab_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton(tr("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _build_general_tab(self) -> QWidget:
        """Generelt filter fane — indpakket i QScrollArea så indhold ikke klemmes."""
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        layout = QFormLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Cachenavn
        self._name_filter = QLineEdit()
        self._name_filter.setPlaceholderText(tr("filter_contains_placeholder"))
        layout.addRow(tr("filter_name_label"), self._name_filter)

        # GC kode
        self._gc_filter = QLineEdit()
        self._gc_filter.setPlaceholderText(tr("filter_gc_placeholder"))
        layout.addRow(tr("filter_gc_label"), self._gc_filter)

        # Udlagt af
        self._placed_filter = QLineEdit()
        self._placed_filter.setPlaceholderText(tr("filter_contains_placeholder"))
        layout.addRow(tr("filter_placed_by_label"), self._placed_filter)

        # Cache type
        type_group = QGroupBox(tr("filter_cache_type_group"))
        type_layout = QGridLayout(type_group)
        self._type_checks: dict[str, QCheckBox] = {}
        for i, ct in enumerate(CACHE_TYPES):
            cb = QCheckBox(ct.replace(" Cache", "").replace("Unknown", "Mystery"))
            cb.setChecked(True)
            self._type_checks[ct] = cb
            type_layout.addWidget(cb, i // 3, i % 3)
        layout.addRow(type_group)

        # Container
        cont_group = QGroupBox(tr("filter_container_group"))
        cont_layout = QHBoxLayout(cont_group)
        self._cont_checks: dict[str, QCheckBox] = {}
        for cs in CONTAINER_SIZES:
            cb = QCheckBox(cs)
            cb.setChecked(True)
            self._cont_checks[cs] = cb
            cont_layout.addWidget(cb)
        layout.addRow(cont_group)

        # Sværhedsgrad
        dt_group = QGroupBox(tr("filter_dt_group"))
        dt_layout = QFormLayout(dt_group)

        d_row = QHBoxLayout()
        self._diff_min = DTSpinBox()
        self._diff_max = DTSpinBox()
        self._diff_max.setValue(5.0)
        d_row.addWidget(QLabel(tr("filter_from")))
        d_row.addWidget(self._diff_min)
        d_row.addWidget(QLabel(tr("filter_to")))
        d_row.addWidget(self._diff_max)
        d_row.addStretch()
        dt_layout.addRow(tr("filter_difficulty_label"), d_row)

        t_row = QHBoxLayout()
        self._terr_min = DTSpinBox()
        self._terr_max = DTSpinBox()
        self._terr_max.setValue(5.0)
        t_row.addWidget(QLabel(tr("filter_from")))
        t_row.addWidget(self._terr_min)
        t_row.addWidget(QLabel(tr("filter_to")))
        t_row.addWidget(self._terr_max)
        t_row.addStretch()
        dt_layout.addRow(tr("filter_terrain_label"), t_row)
        layout.addRow(dt_group)

        # Fundet status
        found_group = QGroupBox(tr("filter_found_group"))
        found_layout = QHBoxLayout(found_group)
        self._found_cb   = QCheckBox(tr("quick_found"))
        self._found_cb.setChecked(True)
        self._notfound_cb = QCheckBox(tr("quick_not_found"))
        self._notfound_cb.setChecked(True)
        found_layout.addWidget(self._found_cb)
        found_layout.addWidget(self._notfound_cb)
        found_layout.addStretch()
        layout.addRow(found_group)

        # Tilgængelighed
        avail_group = QGroupBox(tr("filter_avail_group"))
        avail_layout = QHBoxLayout(avail_group)
        self._avail_cb    = QCheckBox(tr("filter_available"))
        self._avail_cb.setChecked(True)
        self._unavail_cb  = QCheckBox(tr("filter_unavailable"))
        self._unavail_cb.setChecked(True)
        self._archived_cb = QCheckBox(tr("quick_archived"))
        self._archived_cb.setChecked(False)
        avail_layout.addWidget(self._avail_cb)
        avail_layout.addWidget(self._unavail_cb)
        avail_layout.addWidget(self._archived_cb)
        avail_layout.addStretch()
        layout.addRow(avail_group)

        # Afstand
        dist_group = QGroupBox(tr("filter_distance_group"))
        dist_layout = QHBoxLayout(dist_group)
        self._dist_enabled = QCheckBox(tr("filter_enable"))
        self._dist_enabled.toggled.connect(self._on_dist_toggled)
        dist_layout.addWidget(self._dist_enabled)
        dist_layout.addWidget(QLabel(tr("filter_max")))
        self._dist_max = QDoubleSpinBox()
        self._dist_max.setRange(0.1, 9999.0)
        self._dist_max.setValue(50.0)
        self._dist_max.setSuffix(" km")
        self._dist_max.setEnabled(False)
        dist_layout.addWidget(self._dist_max)
        dist_layout.addStretch()
        layout.addRow(dist_group)

        # Premium
        prem_group = QGroupBox(tr("filter_premium_group"))
        prem_layout = QHBoxLayout(prem_group)
        self._prem_yes = QCheckBox(tr("filter_premium_only"))
        self._prem_yes.setChecked(True)
        self._prem_no  = QCheckBox(tr("filter_not_premium"))
        self._prem_no.setChecked(True)
        prem_layout.addWidget(self._prem_yes)
        prem_layout.addWidget(self._prem_no)
        prem_layout.addStretch()
        layout.addRow(prem_group)

        # Trackables
        tb_group = QGroupBox(tr("filter_trackables_group"))
        tb_layout = QHBoxLayout(tb_group)
        self._tb_yes = QCheckBox(tr("filter_has_trackables"))
        self._tb_yes.setChecked(True)
        self._tb_no  = QCheckBox(tr("filter_no_trackables"))
        self._tb_no.setChecked(True)
        tb_layout.addWidget(self._tb_yes)
        tb_layout.addWidget(self._tb_no)
        tb_layout.addStretch()
        layout.addRow(tb_group)

        scroll.setWidget(inner)
        outer_layout.addWidget(scroll)
        return outer

    def _build_dates_tab(self) -> QWidget:
        """Datoer filter fane."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Udlagt dato
        hidden_group = QGroupBox(tr("filter_hidden_date_group"))
        hidden_layout = QFormLayout(hidden_group)

        self._hidden_from_enabled = QCheckBox(tr("filter_from"))
        self._hidden_from = QDateEdit()
        self._hidden_from.setCalendarPopup(True)
        self._hidden_from.setDate(QDate(2000, 1, 1))
        self._hidden_from.setEnabled(False)
        self._hidden_from_enabled.toggled.connect(self._hidden_from.setEnabled)
        hidden_row1 = QHBoxLayout()
        hidden_row1.addWidget(self._hidden_from_enabled)
        hidden_row1.addWidget(self._hidden_from)
        hidden_row1.addStretch()
        hidden_layout.addRow(hidden_row1)

        self._hidden_to_enabled = QCheckBox(tr("filter_to"))
        self._hidden_to = QDateEdit()
        self._hidden_to.setCalendarPopup(True)
        self._hidden_to.setDate(QDate.currentDate())
        self._hidden_to.setEnabled(False)
        self._hidden_to_enabled.toggled.connect(self._hidden_to.setEnabled)
        hidden_row2 = QHBoxLayout()
        hidden_row2.addWidget(self._hidden_to_enabled)
        hidden_row2.addWidget(self._hidden_to)
        hidden_row2.addStretch()
        hidden_layout.addRow(hidden_row2)

        layout.addRow(hidden_group)

        # Seneste log dato
        log_group = QGroupBox(tr("filter_log_date_group"))
        log_layout = QFormLayout(log_group)

        self._log_from_enabled = QCheckBox(tr("filter_from"))
        self._log_from = QDateEdit()
        self._log_from.setCalendarPopup(True)
        self._log_from.setDate(QDate(2000, 1, 1))
        self._log_from.setEnabled(False)
        self._log_from_enabled.toggled.connect(self._log_from.setEnabled)
        log_row1 = QHBoxLayout()
        log_row1.addWidget(self._log_from_enabled)
        log_row1.addWidget(self._log_from)
        log_row1.addStretch()
        log_layout.addRow(log_row1)

        self._log_to_enabled = QCheckBox(tr("filter_to"))
        self._log_to = QDateEdit()
        self._log_to.setCalendarPopup(True)
        self._log_to.setDate(QDate.currentDate())
        self._log_to.setEnabled(False)
        self._log_to_enabled.toggled.connect(self._log_to.setEnabled)
        log_row2 = QHBoxLayout()
        log_row2.addWidget(self._log_to_enabled)
        log_row2.addWidget(self._log_to)
        log_row2.addStretch()
        log_layout.addRow(log_row2)

        layout.addRow(log_group)

        return widget

    def _build_attributes_tab(self) -> QWidget:
        """Attributter filter fane med scrollbar."""
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Mode
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(tr("filter_caches_with")))
        self._attr_mode_all = QCheckBox(tr("filter_all_selected"))
        self._attr_mode_all.setChecked(True)
        mode_row.addWidget(self._attr_mode_all)
        mode_row.addStretch()
        outer_layout.addLayout(mode_row)

        # Scrollbar area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        grid = QGridLayout(content)
        grid.setSpacing(2)
        grid.setContentsMargins(6, 6, 6, 6)

        # Header
        for col, txt in enumerate([tr("filter_attr_col_name"), tr("yes"), tr("no"), tr("filter_none_short")]):
            lbl = QLabel(f"<b>{txt}</b>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, 0, col)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        grid.addWidget(line, 1, 0, 1, 4)

        # Attributter i to kolonner
        half = (len(ATTRIBUTES) + 1) // 2
        for i, (attr_id, attr_key) in enumerate(ATTRIBUTES):
            # To-kolonne layout: venstre og højre halvdel
            col_offset = 0 if i < half else 5
            row = (i % half) + 2

            # Hent oversat navn; fald tilbage til nøglen hvis mangler
            attr_name = tr(attr_key)
            name_lbl = QLabel(attr_name)
            name_lbl.setToolTip(f"Attribut ID: {attr_id}")
            grid.addWidget(name_lbl, row, col_offset)

            ja_cb  = QCheckBox()
            nej_cb = QCheckBox()
            ingen_cb = QCheckBox()
            ingen_cb.setChecked(True)

            # Kun ét valg ad gangen
            def make_exclusive(j, n, ig):
                def on_ja(v):
                    if v:
                        n.setChecked(False)
                        ig.setChecked(False)
                def on_nej(v):
                    if v:
                        j.setChecked(False)
                        ig.setChecked(False)
                def on_ingen(v):
                    if v:
                        j.setChecked(False)
                        n.setChecked(False)
                j.toggled.connect(on_ja)
                n.toggled.connect(on_nej)
                ig.toggled.connect(on_ingen)

            make_exclusive(ja_cb, nej_cb, ingen_cb)

            grid.addWidget(ja_cb,    row, col_offset + 1, Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(nej_cb,   row, col_offset + 2, Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(ingen_cb, row, col_offset + 3, Qt.AlignmentFlag.AlignCenter)

            self._attr_boxes[attr_id] = (ja_cb, nej_cb, ingen_cb)

        # Separator mellem de to kolonner
        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        grid.addWidget(vsep, 0, 4, half + 2, 1)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)
        return outer

    def _build_where_tab(self) -> QWidget:
        """Where filter fane — SQL WHERE clause editor."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        self._where_sql_general = QPlainTextEdit()
        self._where_sql_general.setPlaceholderText(tr("filter_where_sql_placeholder"))
        layout.addWidget(self._where_sql_general)

        return widget

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_dist_toggled(self, checked: bool) -> None:
        self._dist_max.setEnabled(checked)

    def _reset_general(self) -> None:
        self._name_filter.clear()
        self._gc_filter.clear()
        self._placed_filter.clear()
        for cb in self._type_checks.values():
            cb.setChecked(True)
        for cb in self._cont_checks.values():
            cb.setChecked(True)
        self._diff_min.setValue(1.0)
        self._diff_max.setValue(5.0)
        self._terr_min.setValue(1.0)
        self._terr_max.setValue(5.0)
        self._found_cb.setChecked(True)
        self._notfound_cb.setChecked(True)
        self._avail_cb.setChecked(True)
        self._unavail_cb.setChecked(True)
        self._archived_cb.setChecked(False)
        self._dist_enabled.setChecked(False)
        self._dist_max.setValue(50.0)
        self._prem_yes.setChecked(True)
        self._prem_no.setChecked(True)
        self._tb_yes.setChecked(True)
        self._tb_no.setChecked(True)

    def _reset_dates(self) -> None:
        self._hidden_from_enabled.setChecked(False)
        self._hidden_to_enabled.setChecked(False)
        self._log_from_enabled.setChecked(False)
        self._log_to_enabled.setChecked(False)

    def _reset_attributes(self) -> None:
        for ja_cb, nej_cb, ingen_cb in self._attr_boxes.values():
            ja_cb.setChecked(False)
            nej_cb.setChecked(False)
            ingen_cb.setChecked(True)

    def _reset_all(self) -> None:
        self._reset_general()
        self._reset_dates()
        self._reset_attributes()

    def _reset_current_tab(self) -> None:
        tab = self._tabs.currentWidget()
        if tab is self._where_tab:
            self._where_sql_general.clear()
        elif tab is self._general_tab:
            self._reset_general()
        elif tab is self._dates_tab:
            self._reset_dates()
        elif tab is self._attributes_tab:
            self._reset_attributes()

    # ── Byg FilterSet fra UI ──────────────────────────────────────────────────

    def _build_filterset(self) -> FilterSet:
        fs = FilterSet(mode="AND")

        # Navn
        if self._name_filter.text().strip():
            fs.add(NameFilter(self._name_filter.text().strip()))

        # GC kode
        if self._gc_filter.text().strip():
            fs.add(GcCodeFilter(self._gc_filter.text().strip()))

        # Udlagt af
        if self._placed_filter.text().strip():
            fs.add(PlacedByFilter(self._placed_filter.text().strip()))

        # Cache type — byg OR gruppe af valgte typer
        selected_types = [t for t, cb in self._type_checks.items() if cb.isChecked()]
        if selected_types and len(selected_types) < len(CACHE_TYPES):
            fs.add(CacheTypeFilter(selected_types))

        # Container
        selected_cont = [c for c, cb in self._cont_checks.items() if cb.isChecked()]
        if selected_cont and len(selected_cont) < len(CONTAINER_SIZES):
            fs.add(ContainerFilter(selected_cont))

        # D/T
        if self._diff_min.value() > 1.0 or self._diff_max.value() < 5.0:
            fs.add(DifficultyFilter(self._diff_min.value(), self._diff_max.value()))
        if self._terr_min.value() > 1.0 or self._terr_max.value() < 5.0:
            fs.add(TerrainFilter(self._terr_min.value(), self._terr_max.value()))

        # Fundet — byg OR gruppe
        show_found    = self._found_cb.isChecked()
        show_notfound = self._notfound_cb.isChecked()
        if show_found and not show_notfound:
            fs.add(FoundFilter())
        elif show_notfound and not show_found:
            fs.add(NotFoundFilter())
        # Begge valgt = vis alt = ingen filter

        # Tilgængelighed — byg OR-gruppe af de valgte statusser.
        # Brugeren kan vælge enhver kombination af: tilgængelig / utilgængelig / arkiveret.
        # Hvis alle tre er valgt: ingen filter (vis alt).
        avail    = self._avail_cb.isChecked()
        unavail  = self._unavail_cb.isChecked()
        archived = self._archived_cb.isChecked()

        if not (avail and unavail and archived):
            # Mindst én er fravalgt — tilføj filter
            fs.add(AvailabilityFilter(
                show_avail=avail,
                show_unavail=unavail,
                show_archived=archived,
            ))

        # Afstand
        if self._dist_enabled.isChecked():
            from opensak.gui.settings import get_settings
            s = get_settings()
            fs.add(DistanceFilter(s.home_lat, s.home_lon, self._dist_max.value()))

        # Premium
        prem_yes = self._prem_yes.isChecked()
        prem_no  = self._prem_no.isChecked()
        if prem_yes and not prem_no:
            fs.add(PremiumFilter())
        elif prem_no and not prem_yes:
            fs.add(NonPremiumFilter())

        # Trackables
        tb_yes = self._tb_yes.isChecked()
        tb_no  = self._tb_no.isChecked()
        if tb_yes and not tb_no:
            fs.add(HasTrackableFilter())

        # Datoer
        if self._hidden_from_enabled.isChecked() or self._hidden_to_enabled.isChecked():
            from opensak.filters.engine import BaseFilter
            from_date = (
                datetime(
                    self._hidden_from.date().year(),
                    self._hidden_from.date().month(),
                    self._hidden_from.date().day()
                ) if self._hidden_from_enabled.isChecked() else None
            )
            to_date = (
                datetime(
                    self._hidden_to.date().year(),
                    self._hidden_to.date().month(),
                    self._hidden_to.date().day(),
                    23, 59, 59
                ) if self._hidden_to_enabled.isChecked() else None
            )

            class HiddenDateFilter(BaseFilter):
                filter_type = "hidden_date_range"
                def __init__(self, fd, td):
                    self.from_date = fd
                    self.to_date   = td
                def matches(self, cache):
                    if cache.hidden_date is None:
                        return False
                    hd = cache.hidden_date.replace(tzinfo=None)
                    if self.from_date and hd < self.from_date:
                        return False
                    if self.to_date and hd > self.to_date:
                        return False
                    return True
                def to_dict(self):
                    return {"filter_type": self.filter_type}

            fs.add(HiddenDateFilter(from_date, to_date))

        # Attributter
        attr_mode_and = self._attr_mode_all.isChecked()
        attr_filters  = []
        for attr_id, (ja_cb, nej_cb, _ingen_cb) in self._attr_boxes.items():
            if ja_cb.isChecked():
                attr_filters.append(AttributeFilter(attr_id, True))
            elif nej_cb.isChecked():
                attr_filters.append(AttributeFilter(attr_id, False))

        if attr_filters:
            if attr_mode_and:
                for af in attr_filters:
                    fs.add(af)
            else:
                attr_or = FilterSet(mode="OR")
                for af in attr_filters:
                    attr_or.add(af)
                fs.add(attr_or)

        return fs

    # ── Gem/indlæs profiler ───────────────────────────────────────────────────

    def _load_profiles_into_combo(self) -> None:
        self._profile_combo.clear()
        self._profile_combo.addItem(tr("filter_none"), None)
        for path in FilterProfile.list_profiles():
            try:
                p = FilterProfile.load(path)
                self._profile_combo.addItem(p.name, path)
            except Exception:
                pass

    def _on_profile_selected(self, index: int) -> None:
        path = self._profile_combo.currentData()
        self._del_btn.setEnabled(path is not None)
        if path is None:
            return
        try:
            profile = FilterProfile.load(path)
            # _load_filterset kalder selv _reset_all først
            self._load_filterset(profile.filterset)
        except Exception as e:
            QMessageBox.warning(self, tr("error"), tr("filter_load_error", error=e))

    def _save_profile(self) -> None:
        name, ok = QInputDialog.getText(
            self, tr("filter_save_title"), tr("filter_profile_name_label")
        )
        if not ok or not name.strip():
            return
        fs = self._build_filterset()
        profile = FilterProfile(name.strip(), fs)
        profile.save()
        self._load_profiles_into_combo()
        # Vælg den nye profil i combo
        for i in range(self._profile_combo.count()):
            if self._profile_combo.itemText(i) == name.strip():
                self._profile_combo.setCurrentIndex(i)
                break
        QMessageBox.information(self, tr("filter_saved_title"), tr("filter_saved_msg", name=name))

    def _delete_profile(self) -> None:
        path = self._profile_combo.currentData()
        if path is None:
            return
        name = self._profile_combo.currentText()
        reply = QMessageBox.question(
            self, tr("filter_delete_title"),
            tr("filter_delete_msg", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            import os
            try:
                os.remove(path)
            except Exception:
                pass
            self._load_profiles_into_combo()

    def _load_filterset(self, fs: FilterSet) -> None:
        """Udfyld UI felter fra et eksisterende FilterSet.

        Itererer gennem filtrene og sætter de matchende widgets.
        Ukendte/inline-definerede filtre ignoreres stille.
        """
        # Først: ryd UI så vi starter fra en kendt tilstand
        self._reset_all()

        # Saml filtre — hvis der er en nested OR-gruppe (fx attributter i OR-mode),
        # flad den ud, men husk at attributmode skal sættes.
        attr_mode_or_detected = False
        flat_filters: list = []
        for f in fs._filters:
            if isinstance(f, FilterSet):
                if f.mode == "OR":
                    # Antag at OR-grupper kommer fra attributter
                    attr_mode_or_detected = True
                flat_filters.extend(f._filters)
            else:
                flat_filters.append(f)

        if attr_mode_or_detected:
            self._attr_mode_any.setChecked(True)
        else:
            self._attr_mode_all.setChecked(True)

        for f in flat_filters:
            ftype = getattr(f, "filter_type", None)

            if ftype == "name":
                self._name_filter.setText(getattr(f, "text", ""))
            elif ftype == "gc_code":
                self._gc_filter.setText(getattr(f, "text", ""))
            elif ftype == "placed_by":
                self._placed_filter.setText(getattr(f, "text", ""))
            elif ftype == "cache_type":
                types = getattr(f, "types", [])
                for ct, cb in self._type_checks.items():
                    cb.setChecked(ct in types)
            elif ftype == "container":
                sizes = getattr(f, "sizes", [])
                for cs, cb in self._cont_checks.items():
                    cb.setChecked(cs in sizes)
            elif ftype == "difficulty":
                self._diff_min.setValue(getattr(f, "min_difficulty", 1.0))
                self._diff_max.setValue(getattr(f, "max_difficulty", 5.0))
            elif ftype == "terrain":
                self._terr_min.setValue(getattr(f, "min_terrain", 1.0))
                self._terr_max.setValue(getattr(f, "max_terrain", 5.0))
            elif ftype == "found":
                self._found_cb.setChecked(True)
                self._notfound_cb.setChecked(False)
            elif ftype == "not_found":
                self._found_cb.setChecked(False)
                self._notfound_cb.setChecked(True)
            elif ftype == "availability":
                self._avail_cb.setChecked(getattr(f, "show_avail", True))
                self._unavail_cb.setChecked(getattr(f, "show_unavail", False))
                self._archived_cb.setChecked(getattr(f, "show_archived", False))
            elif ftype == "available":
                # Legacy / simpelt AvailableFilter
                self._avail_cb.setChecked(True)
                self._unavail_cb.setChecked(False)
                self._archived_cb.setChecked(False)
            elif ftype == "archived":
                self._avail_cb.setChecked(False)
                self._unavail_cb.setChecked(False)
                self._archived_cb.setChecked(True)
            elif ftype == "distance":
                self._dist_enabled.setChecked(True)
                self._dist_max.setValue(getattr(f, "max_km", 10.0))
            elif ftype == "premium":
                self._prem_yes.setChecked(True)
                self._prem_no.setChecked(False)
            elif ftype == "non_premium":
                self._prem_yes.setChecked(False)
                self._prem_no.setChecked(True)
            elif ftype == "has_trackable":
                self._tb_yes.setChecked(True)
                self._tb_no.setChecked(False)
            elif ftype == "attribute":
                attr_id = getattr(f, "attribute_id", None)
                is_on   = getattr(f, "is_on", True)
                if attr_id in self._attr_boxes:
                    ja_cb, nej_cb, _ingen = self._attr_boxes[attr_id]
                    if is_on:
                        ja_cb.setChecked(True)
                    else:
                        nej_cb.setChecked(True)
            # Andre/inline filtre ignoreres stille (fx gammel hidden_date)

    # ── Apply ─────────────────────────────────────────────────────────────────

    def _apply(self) -> None:
        fs = self._build_filterset()
        profile_name = (
            self._profile_combo.currentText()
            if self._profile_combo.currentData() is not None
            else ""
        )
        self.filter_applied.emit(fs, SortSpec("name"), profile_name)
        self.accept()
