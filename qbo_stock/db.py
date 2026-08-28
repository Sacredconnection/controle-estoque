from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS connections (
                    slot TEXT PRIMARY KEY CHECK(slot IN ('A', 'B')),
                    realm_id TEXT NOT NULL,
                    company_name TEXT,
                    access_token TEXT,
                    refresh_token TEXT,
                    access_expires_at INTEGER,
                    refresh_expires_at INTEGER,
                    is_demo INTEGER NOT NULL DEFAULT 0,
                    connected_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS inventory (
                    slot TEXT NOT NULL CHECK(slot IN ('A', 'B')),
                    item_id TEXT NOT NULL,
                    sku TEXT,
                    normalized_sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    qty_on_hand REAL NOT NULL DEFAULT 0,
                    item_type TEXT,
                    track_qty_on_hand INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    synced_at TEXT NOT NULL,
                    PRIMARY KEY (slot, item_id),
                    FOREIGN KEY (slot) REFERENCES connections(slot) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_inventory_normalized_sku
                ON inventory(normalized_sku);

                CREATE TABLE IF NOT EXISTS sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    item_count INTEGER,
                    message TEXT
                );
                """
            )

    def get_connection(self, slot: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM connections WHERE slot = ?", (slot.upper(),)
            ).fetchone()
        return dict(row) if row else None

    def list_connections(self) -> dict[str, dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM connections ORDER BY slot").fetchall()
        return {row["slot"]: dict(row) for row in rows}

    def save_connection(
        self,
        *,
        slot: str,
        realm_id: str,
        company_name: str,
        access_token: str | None,
        refresh_token: str | None,
        access_expires_at: int | None,
        refresh_expires_at: int | None,
        is_demo: bool = False,
    ) -> None:
        slot = slot.upper()
        now = utc_now_iso()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT connected_at FROM connections WHERE slot = ?", (slot,)
            ).fetchone()
            connected_at = existing["connected_at"] if existing else now
            conn.execute(
                """
                INSERT INTO connections (
                    slot, realm_id, company_name, access_token, refresh_token,
                    access_expires_at, refresh_expires_at, is_demo,
                    connected_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slot) DO UPDATE SET
                    realm_id = excluded.realm_id,
                    company_name = excluded.company_name,
                    access_token = excluded.access_token,
                    refresh_token = excluded.refresh_token,
                    access_expires_at = excluded.access_expires_at,
                    refresh_expires_at = excluded.refresh_expires_at,
                    is_demo = excluded.is_demo,
                    updated_at = excluded.updated_at
                """,
                (
                    slot,
                    realm_id,
                    company_name,
                    access_token,
                    refresh_token,
                    access_expires_at,
                    refresh_expires_at,
                    int(is_demo),
                    connected_at,
                    now,
                ),
            )
            # When a demo slot is replaced by a real connection (or vice-versa),
            # remove the previous stock snapshot before the next sync.
            conn.execute("DELETE FROM inventory WHERE slot = ?", (slot,))

    def update_tokens(
        self,
        slot: str,
        *,
        access_token: str,
        refresh_token: str,
        access_expires_at: int,
        refresh_expires_at: int | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE connections
                SET access_token = ?, refresh_token = ?, access_expires_at = ?,
                    refresh_expires_at = ?, updated_at = ?
                WHERE slot = ?
                """,
                (
                    access_token,
                    refresh_token,
                    access_expires_at,
                    refresh_expires_at,
                    utc_now_iso(),
                    slot.upper(),
                ),
            )

    def delete_connection(self, slot: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM connections WHERE slot = ?", (slot.upper(),))

    def replace_inventory(self, slot: str, items: Iterable[Mapping]) -> int:
        slot = slot.upper()
        synced_at = utc_now_iso()
        rows = list(items)
        with self.connect() as conn:
            conn.execute("DELETE FROM inventory WHERE slot = ?", (slot,))
            conn.executemany(
                """
                INSERT INTO inventory (
                    slot, item_id, sku, normalized_sku, name, qty_on_hand,
                    item_type, track_qty_on_hand, active, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        slot,
                        str(item["item_id"]),
                        item.get("sku") or "",
                        item["normalized_sku"],
                        item["name"],
                        float(item.get("qty_on_hand", 0) or 0),
                        item.get("item_type") or "",
                        int(bool(item.get("track_qty_on_hand"))),
                        int(bool(item.get("active", True))),
                        synced_at,
                    )
                    for item in rows
                ],
            )
        return len(rows)

    def list_inventory(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM inventory ORDER BY normalized_sku, slot, name"
            ).fetchall()
        return [dict(row) for row in rows]

    def connection_summary(self, slot: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT c.*,
                       COUNT(i.item_id) AS item_count,
                       COALESCE(SUM(i.qty_on_hand), 0) AS qty_total,
                       MAX(i.synced_at) AS last_sync
                FROM connections c
                LEFT JOIN inventory i ON i.slot = c.slot
                WHERE c.slot = ?
                GROUP BY c.slot
                """,
                (slot.upper(),),
            ).fetchone()
        return dict(row) if row else None

    def record_sync(
        self,
        *,
        slot: str,
        started_at: str,
        success: bool,
        item_count: int | None,
        message: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_runs (
                    slot, started_at, finished_at, success, item_count, message
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    slot.upper(),
                    started_at,
                    utc_now_iso(),
                    int(success),
                    item_count,
                    message[:2000],
                ),
            )

    def load_demo(self, labels: dict[str, str], demo_items: dict[str, list[dict]]) -> None:
        for slot in ("A", "B"):
            self.save_connection(
                slot=slot,
                realm_id=f"DEMO-{slot}",
                company_name=f"{labels[slot]} — demonstração",
                access_token=None,
                refresh_token=None,
                access_expires_at=None,
                refresh_expires_at=None,
                is_demo=True,
            )
            self.replace_inventory(slot, demo_items[slot])

    def clear_demo(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM connections WHERE is_demo = 1")
