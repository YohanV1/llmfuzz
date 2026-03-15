"""Typed async repository over SQLite."""

from __future__ import annotations

import json

import aiosqlite

from llmfuzz.models.coverage import CoverageSnapshot
from llmfuzz.models.execution import CrashReport, ExecutionResult
from llmfuzz.models.session import FuzzSession
from llmfuzz.models.target import FuzzTarget


class Repository:
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    async def save_session(self, session: FuzzSession, target: FuzzTarget) -> None:
        final_line = session.coverage_snapshots[-1].line_coverage_pct if session.coverage_snapshots else 0
        final_branch = session.coverage_snapshots[-1].branch_coverage_pct if session.coverage_snapshots else 0

        await self.conn.execute(
            """INSERT OR REPLACE INTO fuzz_sessions
               (session_id, target_id, target_json, started_at, completed_at,
                final_line_coverage, final_branch_coverage, total_inputs,
                total_iterations, plateau_detected)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.session_id,
                session.target_id,
                target.model_dump_json(),
                session.started_at.isoformat(),
                session.completed_at.isoformat() if session.completed_at else None,
                final_line,
                final_branch,
                session.inputs_generated,
                session.iteration,
                int(session.plateau_detected),
            ),
        )
        await self.conn.commit()

    async def save_coverage_snapshot(
        self, session_id: str, snapshot: CoverageSnapshot
    ) -> None:
        await self.conn.execute(
            """INSERT OR REPLACE INTO coverage_snapshots
               (session_id, target_id, iteration, lines_total, lines_covered,
                branches_total, branches_covered, line_coverage_pct, branch_coverage_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                snapshot.target_id,
                snapshot.iteration,
                snapshot.lines_total,
                snapshot.lines_covered,
                snapshot.branches_total,
                snapshot.branches_covered,
                snapshot.line_coverage_pct,
                snapshot.branch_coverage_pct,
            ),
        )
        await self.conn.commit()

    async def save_crash(self, session_id: str, crash: CrashReport) -> None:
        await self.conn.execute(
            """INSERT OR IGNORE INTO crash_reports
               (crash_id, session_id, target_id, input_id, exception_type,
                exception_message, traceback, reproducer_code, iteration, first_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                crash.crash_id,
                session_id,
                crash.target_id,
                crash.input.input_id,
                crash.exception_type,
                crash.exception_message,
                crash.traceback,
                crash.reproducer_code,
                crash.iteration,
                crash.first_seen_at.isoformat(),
            ),
        )
        await self.conn.commit()

    async def list_sessions(self) -> list[dict]:
        cursor = await self.conn.execute(
            "SELECT * FROM fuzz_sessions ORDER BY started_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_coverage_progression(self, session_id: str) -> list[dict]:
        cursor = await self.conn.execute(
            """SELECT iteration, line_coverage_pct, branch_coverage_pct
               FROM coverage_snapshots WHERE session_id = ?
               ORDER BY iteration""",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_crashes(self, session_id: str) -> list[dict]:
        cursor = await self.conn.execute(
            "SELECT * FROM crash_reports WHERE session_id = ? ORDER BY iteration",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
