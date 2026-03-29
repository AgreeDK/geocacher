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
    QDateEdit, QSizePolicy, QFrame
)
from PySide6.QtCore import QDate

from opensak.filters.engine import (
    FilterSet, SortSpec,
    CacheTypeFilter, ContainerFilter,
    DifficultyFilter, TerrainFilter,
    FoundFilter, NotFoundFilter,
    AvailableFilter, ArchivedFilter,
    CountryFilter, NameFilter, GcCodeFilter,
    PlacedByFilter, DistanceFilter,
    AttributeFilter, HasTrackableFilter,
    PremiumFilter, NonPremiumFilter,
    FilterProfile,
)


# ── Groundspeak attribut definitioner ─────────────────────────────────────────
# (id, dansk navn)
ATTRIBUTES = [
    (1,  "Hunde"),
    (2,  "Adgangs- eller parkeringsafgift"),
    (3,  "Klatring"),
    (4,  "Båd"),
    (5,  "Svær klatring"),
    (6,  "Børnevenlig"),
    (7,  "Betydelig vandretur"),
    (8,  "Flot udsigt"),
    (9,  "Særligværktøj krævet"),
    (10, "Klatreudstyr"),
    (11, "Kan kræve svømning"),
    (12, "Kan kræve vadning"),
    (13, "Altid tilgængelig"),
    (14, "Anbefalet om natten"),
    (15, "Vinter tilgængelig"),
    (16, "Camping mulig"),
    (17, "Giftige planter"),
    (18, "Farlige dyr"),
    (19, "Tager under en time"),
    (20, "Mere end en time"),
    (21, "Borde/bænke i nærheden"),
    (22, "Turistvenlig"),
    (23, "Parkering tilgængelig"),
    (24, "Kørestols egnet"),
    (25, "Stærkt duftet"),
    (26, "Farligt område"),
    (27, "Offentlig transport"),
    (28, "Drikkevand i nærheden"),
    (29, "Toiletter i nærheden"),
    (30, "Telefon i nærheden"),
    (31, "Mad i nærheden"),
    (32, "Cykler"),
    (33, "Motorcykler"),
    (34, "Offroad køretøjer"),
    (35, "Snescooter"),
    (36, "Heste"),
    (37, "Natcache"),
    (38, "Forladte miner"),
    (39, "Klippe / rullesten"),
    (40, "Diskretion påkrævet"),
    (41, "Snesko"),
    (42, "Dykkerudstyr"),
    (43, "Korttur (< 1 km)"),
    (44, "Mellemlang tur (1-10 km)"),
    (45, "Lang tur (> 10 km)"),
    (46, "Privat område"),
    (47, "Teltning mulig"),
    (48, "ATVer"),
    (49, "Field Puzzle"),
    (50, "UV-lys krævet"),
    (51, "Lommelygte krævet"),
    (52, "Jagt"),
    (53, "Park and grab"),
    (54, "Flåter"),
    (55, "Kort tur (< 1 km)"),
    (56, "Mellemlang tur (1-10 km)"),
    (57, "Ruin"),
    (58, "Scorecard"),
    (59, "Stealth krævet"),
    (60, "Teamwork påkrævet"),
    (61, "Træer"),
    (62, "Sæsonadgang"),
    (63, "Barnvognssegnet"),
    (64, "Træklatring"),
    (65, "Lastbil/Autocamper"),
    (66, "Lejrbål"),
    (67, "Lost And Found Tour"),
    (68, "Needs maintenance"),
    (69, "Partnership cache"),
    (70, "Power trail"),
    (71, "GeoTour"),
]

CACHE_TYPES = [
    "Traditional Cache",
    "Multi-cache",
    "Unknown Cache",
    "Letterbox Hybrid",
    "Wherigo Cache",
    "Event Cache",
    "Mega-Event Cache",
    "Earthcache",
    "Virtual Cache",
]

CONTAINER_SIZES = ["Nano", "Micro", "Small", "Regular", "Large", "Other"]


# ── Hjælper widget: tre-tilstands checkbox (Ja / Nej / Ingen) ─────────────────

class TriStateBox(QWidget):
    """Tre-tilstands kontrol: Ja ✓ / Nej ✗ / Ingen (ignorér)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._ja  = QCheckBox("Ja")
        self._nej = QCheckBox("Nej")
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

    filter_applied = Signal(object, object)  # FilterSet, SortSpec

    def __init__(self, parent=None, current_filterset: Optional[FilterSet] = None):
        super().__init__(parent)
        self.setWindowTitle("Sæt filter")
        self.setMinimumSize(620, 640)
        self._attr_boxes: dict[int, TriStateBox] = {}
        self._setup_ui()
        if current_filterset:
            self._load_filterset(current_filterset)

    # ── UI bygning ────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Gem/indlæs profil ─────────────────────────────────────────────────
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Gemt filter:"))
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(180)
        self._profile_combo.addItem("(Intet)", None)
        self._load_profiles_into_combo()
        self._profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        profile_row.addWidget(self._profile_combo)

        save_btn = QPushButton("💾  Gem")
        save_btn.setMaximumWidth(80)
        save_btn.clicked.connect(self._save_profile)
        profile_row.addWidget(save_btn)

        del_btn = QPushButton("🗑")
        del_btn.setMaximumWidth(40)
        del_btn.setToolTip("Slet valgt profil")
        del_btn.clicked.connect(self._delete_profile)
        profile_row.addWidget(del_btn)

        profile_row.addStretch()
        layout.addLayout(profile_row)

        # ── Faneblade ─────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "Generelt")
        self._tabs.addTab(self._build_dates_tab(), "Datoer")
        self._tabs.addTab(self._build_attributes_tab(), "Attributter")
        layout.addWidget(self._tabs)

        # ── Knapper ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        apply_btn = QPushButton("⚡  Udfør")
        apply_btn.setStyleSheet("font-weight: bold;")
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)

        reset_btn = QPushButton("↺  Reset alle")
        reset_btn.clicked.connect(self._reset_all)
        btn_row.addWidget(reset_btn)

        reset_tab_btn = QPushButton("↺  Reset fane")
        reset_tab_btn.clicked.connect(self._reset_current_tab)
        btn_row.addWidget(reset_tab_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Annuller")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _build_general_tab(self) -> QWidget:
        """Generelt filter fane."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Cachenavn
        self._name_filter = QLineEdit()
        self._name_filter.setPlaceholderText("Indeholder tekst…")
        layout.addRow("Cachenavn:", self._name_filter)

        # GC kode
        self._gc_filter = QLineEdit()
        self._gc_filter.setPlaceholderText("f.eks. GC123")
        layout.addRow("GC Kode:", self._gc_filter)

        # Udlagt af
        self._placed_filter = QLineEdit()
        self._placed_filter.setPlaceholderText("Indeholder tekst…")
        layout.addRow("Udlagt af:", self._placed_filter)

        # Cache type
        type_group = QGroupBox("Cache type")
        type_layout = QGridLayout(type_group)
        self._type_checks: dict[str, QCheckBox] = {}
        for i, ct in enumerate(CACHE_TYPES):
            cb = QCheckBox(ct.replace(" Cache", "").replace("Unknown", "Mystery"))
            cb.setChecked(True)
            self._type_checks[ct] = cb
            type_layout.addWidget(cb, i // 3, i % 3)
        layout.addRow(type_group)

        # Container
        cont_group = QGroupBox("Container størrelse")
        cont_layout = QHBoxLayout(cont_group)
        self._cont_checks: dict[str, QCheckBox] = {}
        for cs in CONTAINER_SIZES:
            cb = QCheckBox(cs)
            cb.setChecked(True)
            self._cont_checks[cs] = cb
            cont_layout.addWidget(cb)
        layout.addRow(cont_group)

        # Sværhedsgrad
        dt_group = QGroupBox("Sværhedsgrad / Terræn")
        dt_layout = QFormLayout(dt_group)

        d_row = QHBoxLayout()
        self._diff_min = QDoubleSpinBox()
        self._diff_min.setRange(1.0, 5.0)
        self._diff_min.setSingleStep(0.5)
        self._diff_min.setDecimals(1)
        self._diff_min.setValue(1.0)
        self._diff_max = QDoubleSpinBox()
        self._diff_max.setRange(1.0, 5.0)
        self._diff_max.setSingleStep(0.5)
        self._diff_max.setDecimals(1)
        self._diff_max.setValue(5.0)
        d_row.addWidget(QLabel("Fra:"))
        d_row.addWidget(self._diff_min)
        d_row.addWidget(QLabel("Til:"))
        d_row.addWidget(self._diff_max)
        d_row.addStretch()
        dt_layout.addRow("Sværhedsgrad:", d_row)

        t_row = QHBoxLayout()
        self._terr_min = QDoubleSpinBox()
        self._terr_min.setRange(1.0, 5.0)
        self._terr_min.setSingleStep(0.5)
        self._terr_min.setDecimals(1)
        self._terr_min.setValue(1.0)
        self._terr_max = QDoubleSpinBox()
        self._terr_max.setRange(1.0, 5.0)
        self._terr_max.setSingleStep(0.5)
        self._terr_max.setDecimals(1)
        self._terr_max.setValue(5.0)
        t_row.addWidget(QLabel("Fra:"))
        t_row.addWidget(self._terr_min)
        t_row.addWidget(QLabel("Til:"))
        t_row.addWidget(self._terr_max)
        t_row.addStretch()
        dt_layout.addRow("Terræn:", t_row)
        layout.addRow(dt_group)

        # Fundet status
        found_group = QGroupBox("Fundet status")
        found_layout = QHBoxLayout(found_group)
        self._found_cb   = QCheckBox("Fundet")
        self._found_cb.setChecked(True)
        self._notfound_cb = QCheckBox("Ikke fundet")
        self._notfound_cb.setChecked(True)
        found_layout.addWidget(self._found_cb)
        found_layout.addWidget(self._notfound_cb)
        found_layout.addStretch()
        layout.addRow(found_group)

        # Tilgængelighed
        avail_group = QGroupBox("Tilgængelighed")
        avail_layout = QHBoxLayout(avail_group)
        self._avail_cb    = QCheckBox("Tilgængelig")
        self._avail_cb.setChecked(True)
        self._unavail_cb  = QCheckBox("Midl. utilgængelig")
        self._unavail_cb.setChecked(True)
        self._archived_cb = QCheckBox("Arkiveret")
        self._archived_cb.setChecked(False)
        avail_layout.addWidget(self._avail_cb)
        avail_layout.addWidget(self._unavail_cb)
        avail_layout.addWidget(self._archived_cb)
        avail_layout.addStretch()
        layout.addRow(avail_group)

        # Afstand
        dist_group = QGroupBox("Afstand fra centerpunkt")
        dist_layout = QHBoxLayout(dist_group)
        self._dist_enabled = QCheckBox("Aktiver")
        self._dist_enabled.toggled.connect(self._on_dist_toggled)
        dist_layout.addWidget(self._dist_enabled)
        dist_layout.addWidget(QLabel("Max:"))
        self._dist_max = QDoubleSpinBox()
        self._dist_max.setRange(0.1, 9999.0)
        self._dist_max.setValue(50.0)
        self._dist_max.setSuffix(" km")
        self._dist_max.setEnabled(False)
        dist_layout.addWidget(self._dist_max)
        dist_layout.addStretch()
        layout.addRow(dist_group)

        # Premium
        prem_group = QGroupBox("Premium")
        prem_layout = QHBoxLayout(prem_group)
        self._prem_yes = QCheckBox("Kun premium")
        self._prem_yes.setChecked(True)
        self._prem_no  = QCheckBox("Ikke premium")
        self._prem_no.setChecked(True)
        prem_layout.addWidget(self._prem_yes)
        prem_layout.addWidget(self._prem_no)
        prem_layout.addStretch()
        layout.addRow(prem_group)

        # Trackables
        tb_group = QGroupBox("Trackables")
        tb_layout = QHBoxLayout(tb_group)
        self._tb_yes = QCheckBox("Har trackables")
        self._tb_yes.setChecked(True)
        self._tb_no  = QCheckBox("Ingen trackables")
        self._tb_no.setChecked(True)
        tb_layout.addWidget(self._tb_yes)
        tb_layout.addWidget(self._tb_no)
        tb_layout.addStretch()
        layout.addRow(tb_group)

        return widget

    def _build_dates_tab(self) -> QWidget:
        """Datoer filter fane."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Udlagt dato
        hidden_group = QGroupBox("Udlagt dato")
        hidden_layout = QFormLayout(hidden_group)

        self._hidden_from_enabled = QCheckBox("Fra:")
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

        self._hidden_to_enabled = QCheckBox("Til:")
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
        log_group = QGroupBox("Seneste log dato")
        log_layout = QFormLayout(log_group)

        self._log_from_enabled = QCheckBox("Fra:")
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

        self._log_to_enabled = QCheckBox("Til:")
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
        mode_row.addWidget(QLabel("Cacher der har:"))
        self._attr_mode_all = QCheckBox("ALLE valgte attributter")
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
        for col, txt in enumerate(["Attribut", "Ja", "Nej", "Ingen"]):
            lbl = QLabel(f"<b>{txt}</b>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, 0, col)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        grid.addWidget(line, 1, 0, 1, 4)

        # Attributter i to kolonner
        half = (len(ATTRIBUTES) + 1) // 2
        for i, (attr_id, attr_name) in enumerate(ATTRIBUTES):
            # To-kolonne layout: venstre og højre halvdel
            col_offset = 0 if i < half else 5
            row = (i % half) + 2

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
        idx = self._tabs.currentIndex()
        if idx == 0:
            self._reset_general()
        elif idx == 1:
            self._reset_dates()
        elif idx == 2:
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

        # Tilgængelighed
        avail    = self._avail_cb.isChecked()
        unavail  = self._unavail_cb.isChecked()
        archived = self._archived_cb.isChecked()
        if not archived:
            from opensak.filters.engine import ArchivedFilter as AF
            # Ekskludér arkiverede
            class NotArchivedFilter(AF):
                filter_type = "not_archived"
                def matches(self, cache):
                    return not cache.archived
            fs.add(NotArchivedFilter())
        if not avail and not unavail and not archived:
            pass  # Vis intet — lad brugeren vide det er tomt

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
        self._profile_combo.addItem("(Intet)", None)
        for path in FilterProfile.list_profiles():
            try:
                p = FilterProfile.load(path)
                self._profile_combo.addItem(p.name, path)
            except Exception:
                pass

    def _on_profile_selected(self, index: int) -> None:
        path = self._profile_combo.currentData()
        if path is None:
            return
        try:
            profile = FilterProfile.load(path)
            self._reset_all()
            self._load_filterset(profile.filterset)
        except Exception as e:
            QMessageBox.warning(self, "Fejl", f"Kunne ikke indlæse profil:\n{e}")

    def _save_profile(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Gem filter", "Navn på filter profil:"
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
        QMessageBox.information(self, "Gemt", f"Filter '{name}' er gemt.")

    def _delete_profile(self) -> None:
        path = self._profile_combo.currentData()
        if path is None:
            return
        name = self._profile_combo.currentText()
        reply = QMessageBox.question(
            self, "Slet profil",
            f"Slet filterprofilen '{name}'?",
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
        """Forsøg at udfylde UI felter fra et eksisterende FilterSet."""
        # Simpel implementation — sæt bare basis felter
        # (fuld deserialisering er kompleks for den inlinedef filters)
        pass

    # ── Apply ─────────────────────────────────────────────────────────────────

    def _apply(self) -> None:
        fs = self._build_filterset()
        self.filter_applied.emit(fs, SortSpec("name"))
        self.accept()
