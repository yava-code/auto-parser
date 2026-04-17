"""Tests for UserUsage DB model and usage tracking logic."""
import pytest
from db.models import UserUsage, RawListing


class TestUserUsageModel:
    def test_create_new_user(self, db_session):
        u = UserUsage(telegram_id=100001, free_uses_left=5, paid_uses=0)
        db_session.add(u)
        db_session.flush()

        fetched = db_session.query(UserUsage).filter_by(telegram_id=100001).first()
        assert fetched is not None
        assert fetched.free_uses_left == 5
        assert fetched.paid_uses == 0
        assert fetched.total_uses == 0

    def test_decrement_free_uses(self, db_session):
        u = UserUsage(telegram_id=100002, free_uses_left=3, paid_uses=0)
        db_session.add(u)
        db_session.flush()

        u.free_uses_left -= 1
        u.total_uses += 1
        db_session.flush()

        fetched = db_session.query(UserUsage).filter_by(telegram_id=100002).first()
        assert fetched.free_uses_left == 2
        assert fetched.total_uses == 1

    def test_add_paid_uses(self, db_session):
        u = UserUsage(telegram_id=100003, free_uses_left=0, paid_uses=0)
        db_session.add(u)
        db_session.flush()

        u.paid_uses += 10
        db_session.flush()

        fetched = db_session.query(UserUsage).filter_by(telegram_id=100003).first()
        assert fetched.paid_uses == 10

    def test_unique_telegram_id(self, db_session):
        u1 = UserUsage(telegram_id=100004, free_uses_left=5)
        db_session.add(u1)
        db_session.flush()

        u2 = UserUsage(telegram_id=100004, free_uses_left=5)
        db_session.add(u2)
        with pytest.raises(Exception):
            db_session.flush()

    def test_exhausted_free_no_paid_is_zero(self, db_session):
        u = UserUsage(telegram_id=100005, free_uses_left=0, paid_uses=0)
        total = u.free_uses_left + u.paid_uses
        assert total == 0


class TestRawListingExtendedFields:
    def test_new_fields_nullable(self, db_session):
        r = RawListing(
            url="https://example.com/car/1",
            brand="BMW",
            model="X5",
            year=2020,
            price_eur=25000.0,
        )
        db_session.add(r)
        db_session.flush()

        fetched = db_session.query(RawListing).filter_by(url="https://example.com/car/1").first()
        assert fetched.color is None
        assert fetched.body_type is None
        assert fetched.location is None
        assert fetched.engine_cc is None
        assert fetched.doors is None

    def test_new_fields_populated(self, db_session):
        r = RawListing(
            url="https://example.com/car/2",
            brand="Audi",
            model="A4",
            year=2019,
            price_eur=18000.0,
            color="Black",
            body_type="Sedan",
            location="Warsaw",
            engine_cc=1984.0,
            doors=4,
        )
        db_session.add(r)
        db_session.flush()

        fetched = db_session.query(RawListing).filter_by(url="https://example.com/car/2").first()
        assert fetched.color == "Black"
        assert fetched.body_type == "Sedan"
        assert fetched.location == "Warsaw"
        assert fetched.engine_cc == 1984.0
        assert fetched.doors == 4
