import unittest
from unittest.mock import Mock, patch

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from pawpos.db import base


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        metadata = MetaData()
        self.records = Table(
            "records", metadata, Column("id", Integer, primary_key=True)
        )
        metadata.create_all(self.engine)
        factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session_patch = patch.object(base, "SessionLocal", factory)
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()

    def stored_ids(self):
        with self.engine.connect() as connection:
            return connection.execute(select(self.records.c.id)).scalars().all()

    def test_successful_operation_commits(self):
        with base.session_scope() as session:
            session.execute(insert(self.records).values(id=1))
        self.assertEqual(self.stored_ids(), [1])

    def test_operation_failure_rolls_back_every_write(self):
        with self.assertRaisesRegex(RuntimeError, "abort"):
            with base.session_scope() as session:
                session.execute(insert(self.records).values(id=1))
                raise RuntimeError("abort")
        self.assertEqual(self.stored_ids(), [])

    def test_database_failure_rolls_back_and_next_operation_works(self):
        with self.assertRaises(IntegrityError):
            with base.session_scope() as session:
                session.execute(insert(self.records).values(id=1))
                session.execute(insert(self.records).values(id=1))
        self.assertEqual(self.stored_ids(), [])
        with base.session_scope() as session:
            session.execute(insert(self.records).values(id=2))
        self.assertEqual(self.stored_ids(), [2])

    def test_connection_check_success(self):
        result = base.check_connection(self.engine)
        self.assertTrue(result.success)
        self.assertIn("successful", result.message)

    def test_connection_error_does_not_leak_driver_details(self):
        broken_engine = Mock()
        broken_engine.connect.side_effect = OperationalError(
            "SELECT 1", {}, Exception("sensitive driver details")
        )
        result = base.check_connection(broken_engine)
        self.assertFalse(result.success)
        self.assertIn(".env", result.message)
        self.assertNotIn("sensitive", result.message)

    def test_init_db_accepts_test_engine(self):
        base.init_db(self.engine)
