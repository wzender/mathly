"""The class AI budget's migration on real PostgreSQL: checks are taken atomically, never past the limit, even when
many are taken at once, and given back."""
import threading
import uuid
from pathlib import Path

import pytest

from scan_support import BOOTSTRAP, postgres_server  # noqa: F401  (a fixture)

MIGRATIONS = ["20261104090000_math_ai_requests.sql", "20261104230000_math_ai_requests_code.sql",
              "20261105090000_math_worksheets.sql", "20261106110000_math_worksheet_versions.sql", "20261106120000_math_ai_batches.sql"]


def test_concurrent_takes_never_pass_the_classs_limit_and_failures_are_given_back(postgres_server):  # noqa: F811
    psycopg = pytest.importorskip("psycopg")
    database = "aib_" + uuid.uuid4().hex
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute("create database " + database)
    uri = postgres_server.get_uri(database=database)
    try:
        with psycopg.connect(uri, autocommit=True) as c:
            c.execute(BOOTSTRAP)
            for name in MIGRATIONS:
                c.execute(Path("supabase/migrations/" + name).read_text())
            assert c.execute("select ai_daily_checks, auto_send_practice from classes where id=1").fetchone() == (None, False)
        granted = []

        def take():
            with psycopg.connect(uri, autocommit=True) as c:
                c.execute("set role service_role")
                for _ in range(10):
                    granted.append(c.execute("select math_take_class_checks(1, '2026-11-06', 3, 50)").fetchone()[0])
        threads = [threading.Thread(target=take) for _ in range(4)]   # 4 x 10 x 3 = 120 asked, 50 allowed
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert sum(granted) == 50
        with psycopg.connect(uri, autocommit=True) as c:
            c.execute("set role service_role")
            assert c.execute("select used from math_class_ai_budget").fetchone()[0] == 50
            assert c.execute("select math_give_class_checks(1, '2026-11-06', 2)").fetchone()[0] == 48
            assert c.execute("select math_take_class_checks(1, '2026-11-07', 5, 50)").fetchone()[0] == 5   # a new day
            c.execute("reset role")
            c.execute("set role authenticated")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute("select * from math_class_ai_budget")
    finally:
        with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
            c.execute("drop database " + database + " with (force)")
