# -*- coding: utf-8 -*-
"""DraveBackup - geplande lokale back-up/sync van mappen (Dravenlock).

Maakt back-ups van bronmappen naar een doelmap (sync/kopie) of naar een zip.
Volledig lokaal en offline. Per taak in te plannen; draait via het systeemvak
op de achtergrond door.
"""
import os
import sys
import json
import time
import shutil
import zipfile
import traceback

APP_NAAM = "DraveBackup"
APP_VERSIE = "0.1.1"
DONATIE_URL = "https://paypal.me/roger076"
CONTACT = "service@dravenlock.nl"

WINDOWS = (os.name == "nt")

if getattr(sys, "frozen", False):
    BASIS = os.path.dirname(sys.executable)
else:
    BASIS = os.path.dirname(os.path.abspath(__file__))
FOUT_BESTAND = os.path.join(BASIS, "app-fout.txt")
DATA_MAP = os.path.join(BASIS, "DraveBackup-data")
CONFIG_BESTAND = os.path.join(DATA_MAP, "instellingen.json")
LOG_MAP = os.path.join(DATA_MAP, "logs")

BG = "#0e0e11"; PANEL = "#16161b"; PANEL2 = "#1c1c22"; TEXT = "#d4d4d4"
MUTED = "#8a8a94"; ACCENT = "#6fa3d6"; LINE = "#23232b"; WARN = "#d68a6f"
GOED = "#7fb069"


def zorg_voor_mappen():
    for m in (DATA_MAP, LOG_MAP):
        try:
            os.makedirs(m, exist_ok=True)
        except OSError:
            pass


def _excepthook(soort, waarde, tb):
    try:
        with open(FOUT_BESTAND, "w", encoding="utf-8") as f:
            f.write("DraveBackup startfout\n\n")
            f.write("".join(traceback.format_exception(soort, waarde, tb)))
    except Exception:
        pass
    sys.__excepthook__(soort, waarde, tb)


sys.excepthook = _excepthook


# ---------------------------------------------------------------------------
# Instellingen
# ---------------------------------------------------------------------------
STANDAARD_CONFIG = {
    "taal": "auto",
    "taken": [],
    "naar_systeemvak": True,     # venster sluiten = naar systeemvak (blijft plannen)
    "start_met_windows": False,
    "tray_uitleg_getoond": False,
}


def laad_config():
    cfg = dict(STANDAARD_CONFIG)
    try:
        with open(CONFIG_BESTAND, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except Exception:
        pass
    return cfg


def bewaar_config(cfg):
    try:
        tmp = CONFIG_BESTAND + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_BESTAND)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Back-upmotor
# ---------------------------------------------------------------------------
def _veilige_naam(naam):
    uit = "".join(c if (c.isalnum() or c in " -_") else "_" for c in naam).strip()
    return uit or "backup"


def _alle_bestanden(m):
    for root, _dirs, files in os.walk(m):
        for f in files:
            vol = os.path.join(root, f)
            yield vol, os.path.relpath(vol, m)


def tel_bestanden(bronnen):
    n = 0
    for bron in bronnen:
        if os.path.isdir(bron):
            for _ in _alle_bestanden(bron):
                n += 1
    return n


def sync_map(bron, doel_basis, incrementeel, spiegelen, log, tik):
    """Kopieer bron-boom naar doel_basis/<bronnaam>/. Geeft (gekopieerd, gewist)."""
    doel = os.path.join(doel_basis, os.path.basename(bron.rstrip("/\\")) or "map")
    bron_rel = set()
    gekopieerd = 0
    for vol, rel in _alle_bestanden(bron):
        bron_rel.add(rel)
        dst = os.path.join(doel, rel)
        try:
            if incrementeel and os.path.exists(dst):
                s = os.stat(vol); d = os.stat(dst)
                if int(s.st_mtime) == int(d.st_mtime) and s.st_size == d.st_size:
                    tik()
                    continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(vol, dst)
            gekopieerd += 1
            log("kopie: " + rel)
        except Exception as e:
            log("FOUT bij " + rel + ": " + str(e))
        tik()
    gewist = 0
    if spiegelen and os.path.isdir(doel):
        for vol, rel in list(_alle_bestanden(doel)):
            if rel not in bron_rel:
                try:
                    os.remove(vol); gewist += 1
                    log("verwijderd (spiegel): " + rel)
                except Exception:
                    pass
    return gekopieerd, gewist


def maak_zip(bronnen, doel_basis, naam, tijdstempel, log, tik):
    os.makedirs(doel_basis, exist_ok=True)
    stamp = time.strftime("_%Y%m%d_%H%M%S") if tijdstempel else ""
    zippad = os.path.join(doel_basis, _veilige_naam(naam) + stamp + ".zip")
    items = []
    for bron in bronnen:
        if not os.path.isdir(bron):
            continue
        b = os.path.basename(bron.rstrip("/\\")) or "map"
        for vol, rel in _alle_bestanden(bron):
            items.append((vol, os.path.join(b, rel)))
    tmp = zippad + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for vol, arc in items:
            try:
                z.write(vol, arc)
            except Exception as e:
                log("FOUT bij " + arc + ": " + str(e))
            tik()
    os.replace(tmp, zippad)
    log("zip gemaakt: " + os.path.basename(zippad))
    return zippad


def voer_taak_uit(taak, log, tik):
    """Voert een enkele taak uit. log(tekst), tik() = 1 bestand verwerkt."""
    bronnen = [b for b in taak.get("bronnen", []) if os.path.isdir(b)]
    doel = taak.get("doel", "")
    if not bronnen:
        log("Geen geldige bronmappen.")
        return False, "geen bronnen"
    if not doel:
        log("Geen doel ingesteld.")
        return False, "geen doel"
    try:
        os.makedirs(doel, exist_ok=True)
        if taak.get("modus", "sync") == "zip":
            maak_zip(bronnen, doel, taak.get("naam", "backup"),
                     taak.get("tijdstempel", True), log, tik)
        else:
            tot_k = tot_w = 0
            for bron in bronnen:
                k, w = sync_map(bron, doel, taak.get("incrementeel", True),
                                taak.get("spiegelen", False), log, tik)
                tot_k += k; tot_w += w
            log("Klaar: %d gekopieerd, %d gewist." % (tot_k, tot_w))
        return True, "ok"
    except Exception as e:
        log("FOUT: " + str(e))
        return False, str(e)


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------
def taak_is_verschuldigd(taak, nu=None):
    """Bepaalt of een taak volgens zijn planning nu uitgevoerd moet worden."""
    pl = taak.get("planning", {})
    soort = pl.get("type", "uit")
    if soort == "uit":
        return False
    nu = nu or time.time()
    laatste = taak.get("laatste_run_ts", 0)
    if soort == "interval":
        uren = max(1, int(pl.get("uren", 6)))
        return (nu - laatste) >= uren * 3600
    if soort == "dagelijks":
        tijd = pl.get("tijd", "03:00")
        try:
            uur, minuut = [int(x) for x in tijd.split(":")[:2]]
        except Exception:
            uur, minuut = 3, 0
        lt = time.localtime(nu)
        # is het al voorbij het geplande tijdstip vandaag?
        gepland_vandaag = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday,
                                       uur, minuut, 0, 0, 0, -1))
        if nu < gepland_vandaag:
            return False
        # al een keer gedraaid na het geplande tijdstip van vandaag?
        return laatste < gepland_vandaag
    return False


def taal_detecteren():
    try:
        from PyQt6.QtCore import QLocale
        return "nl" if QLocale.system().name().lower().startswith("nl") else "en"
    except Exception:
        return "en"


# ---------------------------------------------------------------------------
# Taal
# ---------------------------------------------------------------------------
TEKST = {
    "nl": {
        "ondertitel": "Geplande lokale back-up van je mappen - naar een schijf of zip",
        "menu_bestand": "Bestand", "menu_help": "Help",
        "instellingen": "Instellingen", "afsluiten": "Afsluiten",
        "snelgids": "Snelgids", "over": "Over DraveBackup", "donatie": "Donatie",
        "sluiten": "Sluiten", "opslaan": "Opslaan", "annuleren": "Annuleren",
        "taken": "Back-uptaken",
        "nieuw": "Nieuw", "bewerken": "Bewerken", "verwijderen": "Verwijderen",
        "nu_uitvoeren": "Nu uitvoeren", "alle_uitvoeren": "Alle uitvoeren",
        "geen_taken": "Nog geen back-uptaken. Klik op 'Nieuw' om er een te maken.",
        "geen_selectie": "Selecteer eerst een taak.",
        "verwijder_vraag": "Taak '{naam}' verwijderen?",
        "log": "Logboek",
        "bezig": "Bezig met back-up...", "klaar": "Back-up klaar.",
        "klaar_fout": "Back-up afgerond met fouten (zie logboek).",
        # taak-velden
        "t_naam": "Naam", "t_bronnen": "Bronmappen (wat je wilt back-uppen)",
        "t_doel": "Doel (map op andere schijf, of waar de zip komt)",
        "map_toevoegen": "Map toevoegen", "map_verwijderen": "Verwijderen",
        "bladeren": "Bladeren...",
        "t_modus": "Soort", "modus_sync": "Sync/kopie (alleen nieuwe/gewijzigde)",
        "modus_zip": "Zip-bestand (ingepakt, met tijdstempel)",
        "opt_incrementeel": "Incrementeel (ongewijzigde bestanden overslaan)",
        "opt_spiegelen": "Spiegelen: extra bestanden op het doel verwijderen (LET OP)",
        "opt_tijdstempel": "Tijdstempel in de zip-naam",
        "t_planning": "Planning",
        "pl_uit": "Uit (alleen handmatig)", "pl_interval": "Elke X uur",
        "pl_dagelijks": "Dagelijks om",
        "pl_uren": "uur", "taak_nieuw": "Nieuwe taak", "taak_bewerk": "Taak bewerken",
        "naam_leeg": "Geef de taak een naam.", "bron_leeg": "Voeg minstens een bronmap toe.",
        "doel_leeg": "Kies een doelmap.",
        # detail
        "d_bronnen": "Bronnen", "d_doel": "Doel", "d_soort": "Soort",
        "d_planning": "Planning", "d_laatste": "Laatste keer",
        "nooit": "nog niet uitgevoerd",
        # instellingen
        "inst_taal": "Taal", "inst_taal_auto": "Automatisch (computertaal)",
        "inst_tray": "Sluiten verbergt naar het systeemvak (blijft plannen)",
        "inst_autostart": "Met Windows meestarten (achtergrond)",
        "herstart_taal": "Herstart de app om de taal volledig toe te passen.",
        # tray
        "tray_tonen": "Tonen", "tray_alle": "Alle taken nu uitvoeren",
        "tray_afsluiten": "Afsluiten",
        "tray_actief": "DraveBackup draait door in het systeemvak. Rechtsklik op het "
                       "icoon voor het menu (Afsluiten om echt te stoppen).",
        "tray_uitleg": "DraveBackup is naar het systeemvak verplaatst en blijft je "
                       "geplande back-ups uitvoeren. Klik met rechts op het icoon "
                       "rechtsonder om het te tonen of af te sluiten.",
        # over
        "over_tekst": "DraveBackup v{versie}\n\nGeplande lokale back-up van je mappen, "
                      "volledig offline.\n\nContact: {contact}\nDonatie: {donatie}",
    },
    "en": {
        "ondertitel": "Scheduled local backup of your folders - to a drive or zip",
        "menu_bestand": "File", "menu_help": "Help",
        "instellingen": "Settings", "afsluiten": "Quit",
        "snelgids": "Quick guide", "over": "About DraveBackup", "donatie": "Donate",
        "sluiten": "Close", "opslaan": "Save", "annuleren": "Cancel",
        "taken": "Backup tasks",
        "nieuw": "New", "bewerken": "Edit", "verwijderen": "Delete",
        "nu_uitvoeren": "Run now", "alle_uitvoeren": "Run all",
        "geen_taken": "No backup tasks yet. Click 'New' to create one.",
        "geen_selectie": "Select a task first.",
        "verwijder_vraag": "Delete task '{naam}'?",
        "log": "Log",
        "bezig": "Backing up...", "klaar": "Backup done.",
        "klaar_fout": "Backup finished with errors (see log).",
        "t_naam": "Name", "t_bronnen": "Source folders (what to back up)",
        "t_doel": "Destination (folder on another drive, or where the zip goes)",
        "map_toevoegen": "Add folder", "map_verwijderen": "Remove",
        "bladeren": "Browse...",
        "t_modus": "Type", "modus_sync": "Sync/copy (only new/changed)",
        "modus_zip": "Zip file (packed, with timestamp)",
        "opt_incrementeel": "Incremental (skip unchanged files)",
        "opt_spiegelen": "Mirror: delete extra files on the destination (CAUTION)",
        "opt_tijdstempel": "Timestamp in the zip name",
        "t_planning": "Schedule",
        "pl_uit": "Off (manual only)", "pl_interval": "Every X hours",
        "pl_dagelijks": "Daily at",
        "pl_uren": "hours", "taak_nieuw": "New task", "taak_bewerk": "Edit task",
        "naam_leeg": "Give the task a name.", "bron_leeg": "Add at least one source folder.",
        "doel_leeg": "Choose a destination folder.",
        "d_bronnen": "Sources", "d_doel": "Destination", "d_soort": "Type",
        "d_planning": "Schedule", "d_laatste": "Last run",
        "nooit": "not run yet",
        "inst_taal": "Language", "inst_taal_auto": "Automatic (system language)",
        "inst_tray": "Closing hides to the system tray (keeps scheduling)",
        "inst_autostart": "Start with Windows (background)",
        "herstart_taal": "Restart the app to fully apply the language.",
        "tray_tonen": "Show", "tray_alle": "Run all tasks now",
        "tray_afsluiten": "Quit",
        "tray_actief": "DraveBackup keeps running in the system tray. Right-click the "
                       "icon for the menu (Quit to stop completely).",
        "tray_uitleg": "DraveBackup moved to the system tray and keeps running your "
                       "scheduled backups. Right-click the icon at the bottom right "
                       "to show or quit it.",
        "over_tekst": "DraveBackup v{versie}\n\nScheduled local backup of your folders, "
                      "fully offline.\n\nContact: {contact}\nDonate: {donatie}",
    },
}

_TAAL = "nl"


def T(s):
    return TEKST.get(_TAAL, TEKST["nl"]).get(s, s)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox, QDialog, QLineEdit,
    QFormLayout, QRadioButton, QCheckBox, QComboBox, QSpinBox, QTimeEdit,
    QTextEdit, QProgressBar, QStatusBar, QSplitter, QFileDialog, QButtonGroup,
    QSystemTrayIcon, QMenu,
)
from PyQt6.QtGui import QAction, QIcon, QDesktopServices, QGuiApplication
from PyQt6.QtCore import Qt, QUrl, QTimer, QThread, pyqtSignal, QTime


def _bundel_bestand(naam):
    return os.path.join(getattr(sys, "_MEIPASS", BASIS), naam)


def app_icoon():
    for naam in ("app.ico", "logo.png"):
        pad = _bundel_bestand(naam)
        if os.path.isfile(pad):
            ic = QIcon(pad)
            if not ic.isNull():
                return ic
    return QIcon()


def STIJL():
    return """
    QWidget { background: %(bg)s; color: %(text)s; font-size: 15px; }
    QLabel#titel { font-size: 26px; font-weight: bold; }
    QLabel#sub { color: %(muted)s; }
    QLabel#uitleg { color: %(muted)s; }
    QLineEdit, QTextEdit, QSpinBox, QComboBox, QTimeEdit {
        background: %(panel2)s; color: %(text)s; border: 1px solid %(line)s;
        border-radius: 8px; padding: 8px; selection-background-color: %(accent)s;
        selection-color: #0b0b0e; }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus { border: 1px solid %(accent)s; }
    QListWidget { background: %(panel)s; border: 1px solid %(line)s;
        border-radius: 10px; padding: 4px; }
    QListWidget::item { padding: 10px; border-radius: 6px; }
    QListWidget::item:selected { background: %(accent)s; color: #0b0b0e; }
    QTextEdit { font-family: Consolas, monospace; }
    QPushButton { background: %(panel2)s; color: %(text)s; border: 1px solid %(line)s;
        border-radius: 9px; padding: 9px 14px; }
    QPushButton:hover { border: 1px solid %(accent)s; }
    QPushButton:disabled { color: %(muted)s; }
    QPushButton#primair { background: %(accent)s; color: #0b0b0e; border: none; font-weight: bold; }
    QPushButton#primair:hover { background: #84b4e0; }
    QPushButton#gevaar { border: 1px solid %(warn)s; color: %(warn)s; }
    QProgressBar { background: %(panel2)s; border: 1px solid %(line)s; border-radius: 8px;
        text-align: center; color: %(text)s; }
    QProgressBar::chunk { background: %(accent)s; border-radius: 7px; }
    QMenuBar { background: %(bg)s; color: %(text)s; }
    QMenuBar::item:selected { background: %(panel2)s; }
    QMenu { background: %(panel)s; color: %(text)s; border: 1px solid %(line)s; }
    QMenu::item:selected { background: %(accent)s; color: #0b0b0e; }
    QStatusBar { background: %(bg)s; color: %(muted)s; }
    QSplitter::handle { background: %(line)s; }
    QRadioButton, QCheckBox { spacing: 8px; }
    """ % {"bg": BG, "panel": PANEL, "panel2": PANEL2, "text": TEXT,
           "muted": MUTED, "accent": ACCENT, "line": LINE, "warn": WARN}


def centreer(dialoog, ouder=None):
    try:
        scherm = (ouder.screen() if ouder else None) or QGuiApplication.primaryScreen()
        geo = scherm.availableGeometry()
        dialoog.move(geo.center().x() - dialoog.width() // 2,
                     geo.center().y() - dialoog.height() // 2)
    except Exception:
        pass


class BackupThread(QThread):
    logregel = pyqtSignal(str)
    voortgang = pyqtSignal(int, int)     # gedaan, totaal
    klaar = pyqtSignal(bool)             # zonder fouten?

    def __init__(self, taken):
        super().__init__()
        self.taken = taken
        self._gedaan = 0
        self._totaal = 0

    def run(self):
        self._totaal = sum(tel_bestanden(t.get("bronnen", [])) for t in self.taken) or 1
        self._gedaan = 0
        fout = False

        def log(tekst):
            self.logregel.emit(tekst)

        def tik():
            self._gedaan += 1
            self.voortgang.emit(self._gedaan, self._totaal)

        for taak in self.taken:
            log("== %s ==" % taak.get("naam", ""))
            ok, _ = voer_taak_uit(taak, log, tik)
            taak["laatste_run_ts"] = time.time()
            taak["laatste_status"] = "ok" if ok else "fout"
            if not ok:
                fout = True
        self.voortgang.emit(self._totaal, self._totaal)
        self.klaar.emit(not fout)


class TaakDialoog(QDialog):
    def __init__(self, ouder, taak=None):
        super().__init__(ouder)
        self.taak = dict(taak) if taak else {}
        self.setWindowTitle(T("taak_bewerk") if taak else T("taak_nieuw"))
        self.setWindowIcon(app_icoon())
        self.resize(640, 620)
        self.setStyleSheet(STIJL())
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.naam = QLineEdit(self.taak.get("naam", ""))
        form.addRow(T("t_naam"), self.naam)
        lay.addLayout(form)

        lay.addWidget(QLabel(T("t_bronnen")))
        self.bronnen = QListWidget()
        for b in self.taak.get("bronnen", []):
            self.bronnen.addItem(b)
        self.bronnen.setMaximumHeight(120)
        lay.addWidget(self.bronnen)
        rij = QHBoxLayout()
        b1 = QPushButton(T("map_toevoegen")); b1.clicked.connect(self._voeg_bron)
        rij.addWidget(b1)
        b2 = QPushButton(T("map_verwijderen")); b2.clicked.connect(self._wis_bron)
        rij.addWidget(b2)
        rij.addStretch(1)
        lay.addLayout(rij)

        lay.addWidget(QLabel(T("t_doel")))
        drij = QHBoxLayout()
        self.doel = QLineEdit(self.taak.get("doel", ""))
        drij.addWidget(self.doel, 1)
        bb = QPushButton(T("bladeren")); bb.clicked.connect(self._kies_doel)
        drij.addWidget(bb)
        lay.addLayout(drij)

        lay.addWidget(QLabel(T("t_modus")))
        self.r_sync = QRadioButton(T("modus_sync"))
        self.r_zip = QRadioButton(T("modus_zip"))
        grp = QButtonGroup(self); grp.addButton(self.r_sync); grp.addButton(self.r_zip)
        (self.r_zip if self.taak.get("modus") == "zip" else self.r_sync).setChecked(True)
        lay.addWidget(self.r_sync); lay.addWidget(self.r_zip)
        self.c_incr = QCheckBox(T("opt_incrementeel"))
        self.c_incr.setChecked(self.taak.get("incrementeel", True))
        self.c_spieg = QCheckBox(T("opt_spiegelen"))
        self.c_spieg.setChecked(self.taak.get("spiegelen", False))
        self.c_stamp = QCheckBox(T("opt_tijdstempel"))
        self.c_stamp.setChecked(self.taak.get("tijdstempel", True))
        for c in (self.c_incr, self.c_spieg, self.c_stamp):
            lay.addWidget(c)

        # planning
        lay.addWidget(QLabel(T("t_planning")))
        prij = QHBoxLayout()
        self.pl = QComboBox()
        self.pl.addItem(T("pl_uit"), "uit")
        self.pl.addItem(T("pl_interval"), "interval")
        self.pl.addItem(T("pl_dagelijks"), "dagelijks")
        plan = self.taak.get("planning", {})
        i = max(0, self.pl.findData(plan.get("type", "uit")))
        self.pl.setCurrentIndex(i)
        self.pl.currentIndexChanged.connect(self._plan_ui)
        prij.addWidget(self.pl)
        self.pl_uren = QSpinBox(); self.pl_uren.setRange(1, 168)
        self.pl_uren.setValue(int(plan.get("uren", 6)))
        self.pl_uren_lbl = QLabel(T("pl_uren"))
        prij.addWidget(self.pl_uren); prij.addWidget(self.pl_uren_lbl)
        self.pl_tijd = QTimeEdit()
        try:
            uur, minuut = [int(x) for x in plan.get("tijd", "03:00").split(":")[:2]]
        except Exception:
            uur, minuut = 3, 0
        self.pl_tijd.setTime(QTime(uur, minuut))
        prij.addWidget(self.pl_tijd)
        prij.addStretch(1)
        lay.addLayout(prij)
        self._plan_ui()

        knr = QHBoxLayout(); knr.addStretch(1)
        ann = QPushButton(T("annuleren")); ann.clicked.connect(self.reject)
        knr.addWidget(ann)
        ok = QPushButton(T("opslaan")); ok.setObjectName("primair")
        ok.clicked.connect(self._ok)
        knr.addWidget(ok)
        lay.addLayout(knr)
        QTimer.singleShot(0, lambda: centreer(self, ouder))

    def _plan_ui(self):
        soort = self.pl.currentData()
        self.pl_uren.setVisible(soort == "interval")
        self.pl_uren_lbl.setVisible(soort == "interval")
        self.pl_tijd.setVisible(soort == "dagelijks")

    def _voeg_bron(self):
        m = QFileDialog.getExistingDirectory(self, T("map_toevoegen"), BASIS)
        if m:
            self.bronnen.addItem(m)

    def _wis_bron(self):
        for it in self.bronnen.selectedItems():
            self.bronnen.takeItem(self.bronnen.row(it))

    def _kies_doel(self):
        m = QFileDialog.getExistingDirectory(self, T("t_doel"), BASIS)
        if m:
            self.doel.setText(m)

    def _ok(self):
        if not self.naam.text().strip():
            QMessageBox.information(self, APP_NAAM, T("naam_leeg")); return
        bronnen = [self.bronnen.item(i).text() for i in range(self.bronnen.count())]
        if not bronnen:
            QMessageBox.information(self, APP_NAAM, T("bron_leeg")); return
        if not self.doel.text().strip():
            QMessageBox.information(self, APP_NAAM, T("doel_leeg")); return
        self.taak.update({
            "naam": self.naam.text().strip(),
            "bronnen": bronnen,
            "doel": self.doel.text().strip(),
            "modus": "zip" if self.r_zip.isChecked() else "sync",
            "incrementeel": self.c_incr.isChecked(),
            "spiegelen": self.c_spieg.isChecked(),
            "tijdstempel": self.c_stamp.isChecked(),
            "planning": {
                "type": self.pl.currentData(),
                "uren": self.pl_uren.value(),
                "tijd": self.pl_tijd.time().toString("HH:mm"),
            },
        })
        self.accept()


class InstellingenDialoog(QDialog):
    def __init__(self, ouder, cfg):
        super().__init__(ouder)
        self.cfg = cfg
        self.setWindowTitle(T("instellingen"))
        self.setWindowIcon(app_icoon())
        self.resize(480, 240)
        self.setStyleSheet(STIJL())
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.taal = QComboBox()
        self.taal.addItem(T("inst_taal_auto"), "auto")
        self.taal.addItem("Nederlands", "nl")
        self.taal.addItem("English", "en")
        self.taal.setCurrentIndex(max(0, self.taal.findData(cfg.get("taal", "auto"))))
        form.addRow(T("inst_taal"), self.taal)
        lay.addLayout(form)
        self.tray = QCheckBox(T("inst_tray"))
        self.tray.setChecked(cfg.get("naar_systeemvak", True))
        lay.addWidget(self.tray)
        self.autostart = QCheckBox(T("inst_autostart"))
        self.autostart.setChecked(cfg.get("start_met_windows", False))
        lay.addWidget(self.autostart)
        lay.addStretch(1)
        knr = QHBoxLayout(); knr.addStretch(1)
        ann = QPushButton(T("annuleren")); ann.clicked.connect(self.reject)
        knr.addWidget(ann)
        ok = QPushButton(T("opslaan")); ok.setObjectName("primair")
        ok.clicked.connect(self._ok)
        knr.addWidget(ok)
        lay.addLayout(knr)
        QTimer.singleShot(0, lambda: centreer(self, ouder))

    def _ok(self):
        self.cfg["taal"] = self.taal.currentData()
        self.cfg["naar_systeemvak"] = self.tray.isChecked()
        self.cfg["start_met_windows"] = self.autostart.isChecked()
        self.accept()


SNELGIDS_NL = """
<h2>DraveBackup - Snelgids</h2>
<p>DraveBackup maakt <b>back-ups</b> van mappen die jij kiest, naar een andere
schijf of naar een zip-bestand. Volledig lokaal; er gaat niets naar internet.</p>
<h3>1. Een taak maken</h3>
<p><b>Nieuw</b> -&gt; geef een naam, voeg een of meer <b>bronmappen</b> toe (wat je
wilt back-uppen) en kies een <b>doel</b> (bijvoorbeeld een externe schijf).</p>
<h3>2. Soort back-up</h3>
<ul>
<li><b>Sync/kopie</b>: kopieert de bestanden naar de doelmap. Met
<b>incrementeel</b> worden ongewijzigde bestanden overgeslagen (sneller).</li>
<li><b>Zip</b>: pakt alles in een zip met datum/tijd in de naam - handig als
losse, gedateerde back-up.</li>
</ul>
<p><b>Spiegelen</b> (alleen sync) verwijdert bestanden op het doel die niet meer in
de bron staan. Handig voor een exacte kopie, maar wees voorzichtig: het wist echt.</p>
<h3>3. Plannen</h3>
<p>Per taak: <b>uit</b> (alleen handmatig), <b>elke X uur</b>, of <b>dagelijks om</b>
een tijd. Zet bij Instellingen aan dat sluiten naar het <b>systeemvak</b> gaat (en
eventueel met Windows meestarten), dan draaien geplande back-ups op de achtergrond.</p>
<h3>4. Uitvoeren</h3>
<p><b>Nu uitvoeren</b> voor de gekozen taak of <b>Alle uitvoeren</b>. De voortgang en
meldingen zie je in het <b>logboek</b> onderaan.</p>
<p>Tip: test een nieuwe taak eerst met een kleine map. Donatie (vrijwillig):
<b>paypal.me/roger076</b> &middot; service@dravenlock.nl</p>
"""

SNELGIDS_EN = """
<h2>DraveBackup - Quick guide</h2>
<p>DraveBackup backs up folders you choose, to another drive or to a zip file.
Fully local; nothing goes to the internet.</p>
<h3>1. Create a task</h3>
<p><b>New</b> -&gt; give it a name, add one or more <b>source folders</b> (what to
back up) and choose a <b>destination</b> (e.g. an external drive).</p>
<h3>2. Backup type</h3>
<ul>
<li><b>Sync/copy</b>: copies the files to the destination. With <b>incremental</b>
unchanged files are skipped (faster).</li>
<li><b>Zip</b>: packs everything into a zip with date/time in the name.</li>
</ul>
<p><b>Mirror</b> (sync only) deletes files on the destination that are no longer in
the source. Great for an exact copy, but be careful: it really deletes.</p>
<h3>3. Schedule</h3>
<p>Per task: <b>off</b> (manual only), <b>every X hours</b>, or <b>daily at</b> a
time. In Settings, enable closing to the <b>system tray</b> (and optionally start
with Windows) so scheduled backups run in the background.</p>
<h3>4. Run</h3>
<p><b>Run now</b> for the selected task or <b>Run all</b>. Progress and messages
appear in the <b>log</b> at the bottom.</p>
<p>Tip: test a new task with a small folder first. Donate (voluntary):
<b>paypal.me/roger076</b> &middot; service@dravenlock.nl</p>
"""


class SnelgidsDialoog(QDialog):
    def __init__(self, ouder):
        super().__init__(ouder)
        self.setWindowTitle(T("snelgids"))
        self.setWindowIcon(app_icoon())
        self.resize(680, 600)
        self.setStyleSheet(STIJL())
        from PyQt6.QtWidgets import QTextBrowser
        lay = QVBoxLayout(self)
        b = QTextBrowser(); b.setOpenExternalLinks(True)
        b.setHtml(SNELGIDS_NL if _TAAL == "nl" else SNELGIDS_EN)
        lay.addWidget(b)
        k = QPushButton(T("sluiten")); k.clicked.connect(self.accept)
        lay.addWidget(k)
        QTimer.singleShot(0, lambda: centreer(self, ouder))


def zet_autostart_windows(aan):
    if not WINDOWS:
        return
    try:
        import winreg
        sleutel = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
        if aan:
            if getattr(sys, "frozen", False):
                opdracht = '"%s" --systeemvak' % sys.executable
            else:
                opdracht = '"%s" "%s" --systeemvak' % (sys.executable,
                                                       os.path.abspath(__file__))
            winreg.SetValueEx(sleutel, APP_NAAM, 0, winreg.REG_SZ, opdracht)
        else:
            try:
                winreg.DeleteValue(sleutel, APP_NAAM)
            except FileNotFoundError:
                pass
        winreg.CloseKey(sleutel)
    except Exception:
        pass


class Hoofdvenster(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self._thread = None
        self._tray = None
        self.setWindowTitle("%s  v%s" % (APP_NAAM, APP_VERSIE))
        self.setWindowIcon(app_icoon())
        self.resize(1000, 680)
        self.setStyleSheet(STIJL())
        self._menu()
        self._bouw()
        self._ververs()

        sb = QStatusBar(); self.setStatusBar(sb)
        self.btn_donatie = QPushButton(" \u2665 " + T("donatie"))
        self.btn_donatie.setObjectName("primair")
        self.btn_donatie.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(DONATIE_URL)))
        sb.addPermanentWidget(self.btn_donatie)

        self._maak_tray()
        # planner: elke 30s kijken of er een taak verschuldigd is
        self._planner = QTimer(self)
        self._planner.timeout.connect(self._controleer_planning)
        self._planner.start(30000)
        QTimer.singleShot(2000, self._controleer_planning)

    def _menu(self):
        balk = self.menuBar()
        m = balk.addMenu(T("menu_bestand"))
        a = QAction(T("instellingen"), self); a.triggered.connect(self._instellingen)
        m.addAction(a)
        m.addSeparator()
        a = QAction(T("afsluiten"), self); a.setShortcut("Ctrl+Q")
        a.triggered.connect(self._echt_afsluiten); m.addAction(a)
        h = balk.addMenu(T("menu_help"))
        a = QAction(T("snelgids"), self); a.setShortcut("F1")
        a.triggered.connect(lambda: SnelgidsDialoog(self).exec()); h.addAction(a)
        a = QAction(T("over"), self); a.triggered.connect(self._over); h.addAction(a)
        a = QAction(T("donatie"), self)
        a.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(DONATIE_URL)))
        h.addAction(a)

    def _bouw(self):
        centraal = QWidget(); self.setCentralWidget(centraal)
        lay = QVBoxLayout(centraal)
        kop = QLabel(APP_NAAM); kop.setObjectName("titel"); lay.addWidget(kop)
        sub = QLabel(T("ondertitel")); sub.setObjectName("sub"); lay.addWidget(sub)

        split = QSplitter(Qt.Orientation.Vertical)
        boven = QWidget(); bl = QHBoxLayout(boven); bl.setContentsMargins(0, 0, 0, 0)
        linker = QWidget(); ll = QVBoxLayout(linker); ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel(T("taken")))
        self.lijst = QListWidget()
        self.lijst.itemSelectionChanged.connect(self._toon_detail)
        self.lijst.itemDoubleClicked.connect(lambda *_: self._bewerk())
        ll.addWidget(self.lijst, 1)
        bl.addWidget(linker, 1)

        rechter = QWidget(); rl = QVBoxLayout(rechter); rl.setContentsMargins(0, 0, 0, 0)
        self.detail = QLabel(""); self.detail.setObjectName("uitleg")
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rl.addWidget(self.detail, 1)
        bl.addWidget(rechter, 1)

        knoppen = QVBoxLayout()
        for tekst, fn, obj in (
                (T("nieuw"), self._nieuw, "primair"),
                (T("bewerken"), self._bewerk, ""),
                (T("verwijderen"), self._verwijder, "gevaar"),
                (T("nu_uitvoeren"), self._nu, "primair"),
                (T("alle_uitvoeren"), self._alle, "")):
            b = QPushButton(tekst)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            knoppen.addWidget(b)
        knoppen.addStretch(1)
        bl.addLayout(knoppen)
        split.addWidget(boven)

        onder = QWidget(); ol = QVBoxLayout(onder); ol.setContentsMargins(0, 0, 0, 0)
        ol.addWidget(QLabel(T("log")))
        self.balk = QProgressBar(); self.balk.setVisible(False)
        ol.addWidget(self.balk)
        self.logvak = QTextEdit(); self.logvak.setReadOnly(True)
        ol.addWidget(self.logvak, 1)
        split.addWidget(onder)
        split.setSizes([420, 240])
        lay.addWidget(split, 1)

    # ---- lijst / detail ----
    def _ververs(self):
        self.lijst.clear()
        for t in self.cfg.get("taken", []):
            pl = t.get("planning", {}).get("type", "uit")
            merk = {"interval": " \u23f1", "dagelijks": " \u23f0"}.get(pl, "")
            qi = QListWidgetItem(t.get("naam", "") + merk)
            qi.setData(Qt.ItemDataRole.UserRole, t.get("id"))
            self.lijst.addItem(qi)
        if not self.cfg.get("taken"):
            self.detail.setText(T("geen_taken"))

    def _huidige(self):
        it = self.lijst.currentItem()
        if not it:
            return None
        wid = it.data(Qt.ItemDataRole.UserRole)
        for t in self.cfg.get("taken", []):
            if t.get("id") == wid:
                return t
        return None

    def _toon_detail(self):
        t = self._huidige()
        if not t:
            return
        pl = t.get("planning", {})
        soort = {"uit": T("pl_uit"), "interval": "%s %d %s" % (
            T("pl_interval"), pl.get("uren", 6), T("pl_uren")),
            "dagelijks": "%s %s" % (T("pl_dagelijks"), pl.get("tijd", "03:00"))
        }.get(pl.get("type", "uit"), T("pl_uit"))
        modus = T("modus_zip") if t.get("modus") == "zip" else T("modus_sync")
        ts = t.get("laatste_run_ts", 0)
        laatste = time.strftime("%d-%m-%Y %H:%M", time.localtime(ts)) if ts else T("nooit")
        regels = [
            "<b>%s</b>" % _esc(t.get("naam", "")),
            "<br><b>%s:</b><br>%s" % (T("d_bronnen"),
                                      "<br>".join(_esc(b) for b in t.get("bronnen", []))),
            "<b>%s:</b> %s" % (T("d_doel"), _esc(t.get("doel", ""))),
            "<b>%s:</b> %s" % (T("d_soort"), _esc(modus)),
            "<b>%s:</b> %s" % (T("d_planning"), _esc(soort)),
            "<b>%s:</b> %s" % (T("d_laatste"), _esc(laatste)),
        ]
        self.detail.setText("<div style='font-size:15px'>" + "<br>".join(regels) + "</div>")

    # ---- taak-acties ----
    def _nieuw(self):
        d = TaakDialoog(self)
        if d.exec():
            d.taak["id"] = "%x" % int(time.time() * 1000)
            self.cfg.setdefault("taken", []).append(d.taak)
            bewaar_config(self.cfg); self._ververs()

    def _bewerk(self):
        t = self._huidige()
        if not t:
            QMessageBox.information(self, APP_NAAM, T("geen_selectie")); return
        d = TaakDialoog(self, t)
        if d.exec():
            t.update(d.taak); bewaar_config(self.cfg); self._ververs(); self._toon_detail()

    def _verwijder(self):
        t = self._huidige()
        if not t:
            QMessageBox.information(self, APP_NAAM, T("geen_selectie")); return
        if QMessageBox.question(self, APP_NAAM,
                                T("verwijder_vraag").format(naam=t.get("naam", ""))
                                ) == QMessageBox.StandardButton.Yes:
            self.cfg["taken"].remove(t); bewaar_config(self.cfg); self._ververs()
            self.detail.setText("")

    # ---- uitvoeren ----
    def _bezig(self):
        return self._thread is not None and self._thread.isRunning()

    def _start(self, taken):
        if self._bezig() or not taken:
            return
        self.logvak.clear()
        self.balk.setVisible(True); self.balk.setRange(0, 100); self.balk.setValue(0)
        self.statusBar().showMessage(T("bezig"))
        self._thread = BackupThread(taken)
        self._thread.logregel.connect(self._log)
        self._thread.voortgang.connect(self._voortgang)
        self._thread.klaar.connect(self._run_klaar)
        self._thread.start()

    def _nu(self):
        t = self._huidige()
        if not t:
            QMessageBox.information(self, APP_NAAM, T("geen_selectie")); return
        self._start([t])

    def _alle(self):
        taken = self.cfg.get("taken", [])
        if taken:
            self._start(list(taken))

    def _log(self, tekst):
        self.logvak.append(tekst)

    def _voortgang(self, gedaan, totaal):
        if totaal > 0:
            self.balk.setValue(int(gedaan * 100 / totaal))

    def _run_klaar(self, zonder_fout):
        self.balk.setValue(100)
        self.statusBar().showMessage(T("klaar") if zonder_fout else T("klaar_fout"), 6000)
        bewaar_config(self.cfg)
        self._toon_detail()
        # logbestand wegschrijven
        try:
            pad = os.path.join(LOG_MAP, time.strftime("backup_%Y%m%d_%H%M%S.log"))
            with open(pad, "w", encoding="utf-8") as f:
                f.write(self.logvak.toPlainText())
        except Exception:
            pass

    # ---- planning ----
    def _controleer_planning(self):
        if self._bezig():
            return
        verschuldigd = [t for t in self.cfg.get("taken", [])
                        if taak_is_verschuldigd(t)]
        if verschuldigd:
            self._start(verschuldigd)

    # ---- systeemvak ----
    def _maak_tray(self):
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
        except Exception:
            return
        self._tray = QSystemTrayIcon(app_icoon(), self)
        menu = QMenu()
        menu.addAction(T("tray_tonen"), self._toon_venster)
        menu.addAction(T("tray_alle"), self._alle)
        menu.addSeparator()
        menu.addAction(T("tray_afsluiten"), self._echt_afsluiten)
        self._tray.setContextMenu(menu)
        self._tray.setToolTip("%s v%s" % (APP_NAAM, APP_VERSIE))
        self._tray.activated.connect(
            lambda r: self._toon_venster()
            if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self._tray.show()

    def _toon_venster(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def _instellingen(self):
        global _TAAL
        d = InstellingenDialoog(self, self.cfg)
        if d.exec():
            bewaar_config(self.cfg)
            zet_autostart_windows(self.cfg.get("start_met_windows", False))
            nieuw = self.cfg.get("taal", "auto")
            _TAAL = taal_detecteren() if nieuw == "auto" else nieuw
            QMessageBox.information(self, APP_NAAM, T("herstart_taal"))

    def _over(self):
        QMessageBox.information(self, T("over"), T("over_tekst").format(
            versie=APP_VERSIE, contact=CONTACT, donatie=DONATIE_URL))

    def _echt_afsluiten(self):
        self._afsluiten = True
        self.close()

    def closeEvent(self, ev):
        if getattr(self, "_afsluiten", False) or not self.cfg.get("naar_systeemvak", True) \
                or self._tray is None:
            if self._bezig():
                self._thread.wait(3000)
            ev.accept()
            QApplication.instance().quit()
            return
        # naar systeemvak
        ev.ignore()
        self.hide()
        if self._tray:
            if not self.cfg.get("tray_uitleg_getoond", False):
                QMessageBox.information(self, APP_NAAM, T("tray_uitleg"))
                self.cfg["tray_uitleg_getoond"] = True
                bewaar_config(self.cfg)
            else:
                try:
                    self._tray.showMessage(APP_NAAM, T("tray_actief"), app_icoon(), 4000)
                except Exception:
                    pass


def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main():
    global _TAAL
    zorg_voor_mappen()
    cfg = laad_config()
    taal = cfg.get("taal", "auto")
    _TAAL = taal_detecteren() if taal == "auto" else (taal if taal in ("nl", "en")
                                                      else taal_detecteren())
    if WINDOWS:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Dravenlock.DraveBackup")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAAM)
    app.setWindowIcon(app_icoon())
    app.setStyleSheet(STIJL())

    venster = Hoofdvenster(cfg)
    verborgen_start = ("--systeemvak" in sys.argv) and cfg.get("naar_systeemvak", True) \
        and venster._tray is not None
    if verborgen_start:
        app.setQuitOnLastWindowClosed(False)
    else:
        venster.showMaximized()
    if venster._tray is not None and cfg.get("naar_systeemvak", True):
        app.setQuitOnLastWindowClosed(False)
    try:  # Dravenlock: stille update-check (uit te zetten; Ctrl+Shift+U = met de hand)
        import drave_update
        drave_update.start(venster, 'DraveBackup', APP_VERSIE)
    except Exception:
        pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
