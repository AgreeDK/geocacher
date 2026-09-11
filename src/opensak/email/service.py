"""
src/opensak/email/service.py — orchestrates a single "check for PQ
e-mail" pass (issue #443, session 2): connect, scan the mailbox for
zip attachments, hand each one to the existing importer, optionally
delete the e-mail on success.

This is the manual "Check now" flow. Scheduled/background checking is
tracked separately as #445 and is not implemented here.
"""

from __future__ import annotations

import email
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from opensak.email.connection import ImapConfig, connect
from opensak.email.parser import iter_zip_attachments, pq_name_from_filename

if TYPE_CHECKING:
    from opensak.importer import ImportResult
    from opensak.db.manager import DatabaseInfo


@dataclass
class PQImportOutcome:
    """Resultatet af ét fundet zip-vedhæftning i mailboksen."""
    zip_filename: str
    pq_name: str
    matched_db_name: str | None       # None hvis der slet ingen databaser findes
    imported: bool
    created: int = 0
    updated: int = 0
    waypoints: int = 0
    errors: list[str] = field(default_factory=list)
    deleted_email: bool = False


@dataclass
class PQScanResult:
    """Samlet resultat af én mailboks-gennemgang."""
    outcomes: list[PQImportOutcome] = field(default_factory=list)

    @property
    def any_imported(self) -> bool:
        return any(o.imported for o in self.outcomes)


def _match_database(pq_name: str) -> "DatabaseInfo | None":
    """Find en DatabaseInfo hvis navn matcher `pq_name` (case-insensitive),
    ellers den aktive database, ellers None hvis der slet ingen findes."""
    from opensak.db.manager import get_db_manager
    manager = get_db_manager()
    for db in manager.databases:
        if db.name.lower() == pq_name.lower():
            return db
    return manager.active


def _import_zip_bytes(zip_bytes: bytes, target_db_path: Path | None) -> "ImportResult":
    """
    Importér `zip_bytes` i den angivne database (eller den aktuelt
    aktive, hvis `target_db_path` er None), og gendan bagefter altid
    den oprindelige aktive database.

    Samme mønster som ImportWorker i import_dialog.py — se dens
    docstring for hvorfor: init_db() skifter en global session-factory,
    så den skal altid gendannes i en `finally`-blok, uanset resultatet.
    """
    from opensak.db.database import get_session, init_db
    from opensak.db.manager import get_db_manager
    from opensak.importer import import_zip

    manager = get_db_manager()
    original_path = manager.active_path
    switched = target_db_path is not None and target_db_path != original_path
    if switched:
        init_db(db_path=target_db_path)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "pq_email.zip"
            zip_path.write_bytes(zip_bytes)
            with get_session() as session:
                return import_zip(zip_path, session)
    finally:
        if switched and original_path is not None:
            init_db(db_path=original_path)


def scan_and_import(
    config: ImapConfig,
    password: str,
    *,
    delete_after_import: bool = False,
    timeout: float = 30.0,
) -> PQScanResult:
    """
    Log ind på mailboksen, gennemgå INBOX for zip-vedhæftninger, importér
    hver af dem, og markér e-mailen til sletning hvis importen lykkedes
    OG `delete_after_import` er sat.

    Rejser samme `ImapAuthError`/`ImapNetworkError` som
    `opensak.email.connection.connect()` hvis selve login fejler —
    kalderen (dialogen) viser disse som forbindelsesfejl, adskilt fra
    de per-mail resultater i det returnerede `PQScanResult`.
    """
    result = PQScanResult()
    conn = connect(config, password, timeout=timeout)
    try:
        conn.select("INBOX")
        typ, data = conn.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return result

        seq_numbers = [s.decode("ascii") for s in data[0].split()]
        to_delete: list[tuple[str, list[PQImportOutcome]]] = []

        for seq in seq_numbers:
            typ, msg_data = conn.fetch(seq, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            item = msg_data[0]
            if not isinstance(item, tuple) or not isinstance(item[1], bytes):
                continue
            raw = item[1]
            msg = email.message_from_bytes(raw)

            outcomes_for_this_email: list[PQImportOutcome] = []
            for zip_filename, zip_bytes in iter_zip_attachments(msg):
                pq_name = pq_name_from_filename(zip_filename)
                db_info = _match_database(pq_name)
                try:
                    import_result = _import_zip_bytes(
                        zip_bytes, db_info.path if db_info else None
                    )
                    fatal = bool(import_result.errors) and import_result.total == 0
                    outcome = PQImportOutcome(
                        zip_filename=zip_filename,
                        pq_name=pq_name,
                        matched_db_name=db_info.name if db_info else None,
                        imported=not fatal,
                        created=import_result.created,
                        updated=import_result.updated,
                        waypoints=import_result.waypoints,
                        errors=list(import_result.errors),
                    )
                except Exception as exc:
                    outcome = PQImportOutcome(
                        zip_filename=zip_filename,
                        pq_name=pq_name,
                        matched_db_name=db_info.name if db_info else None,
                        imported=False,
                        errors=[str(exc)],
                    )
                result.outcomes.append(outcome)
                outcomes_for_this_email.append(outcome)

            email_had_success = any(o.imported for o in outcomes_for_this_email)
            if email_had_success and delete_after_import:
                to_delete.append((seq, outcomes_for_this_email))

        for seq, outcomes_for_this_email in to_delete:
            try:
                conn.store(seq, "+FLAGS", "\\Deleted")
                for outcome in outcomes_for_this_email:
                    if outcome.imported:
                        outcome.deleted_email = True
            except Exception:
                pass  # kunne ikke markeres til sletning — mailen bliver bare liggende
        if to_delete:
            try:
                conn.expunge()
            except Exception:
                pass

        return result
    finally:
        try:
            conn.logout()
        except Exception:
            pass
