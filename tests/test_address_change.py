import pytest

from app.schemas import AddressChangeRequest
from app.services.order_service import init_database
from app.services.ticket_service import create_address_change_ticket


def test_create_address_change_ticket_for_in_transit_order(tmp_path):
    database_path = tmp_path / "address_change.db"
    init_database(database_path)

    request = AddressChangeRequest(
        order_id="ord1001",
        new_address="上海市浦东新区世纪大道100号",
        confirmed=True,
    )

    ticket = create_address_change_ticket(
        request,
        user_id="demo-user-001",
        database_path=database_path,
    )

    assert ticket["order_id"] == "ORD1001"
    assert ticket["type"] == "address_change"
    assert ticket["status"] == "pending"
    assert "上海市浦东新区世纪大道100号" in ticket["content"]


def test_delivered_order_cannot_change_address(tmp_path):
    database_path = tmp_path / "address_change.db"
    init_database(database_path)

    request = AddressChangeRequest(
        order_id="ORD1002",
        new_address="上海市静安区南京西路200号",
        confirmed=True,
    )

    with pytest.raises(ValueError, match="不允许改址"):
        create_address_change_ticket(
            request,
            user_id="demo-user-001",
            database_path=database_path,
        )


def test_address_change_requires_confirmation(tmp_path):
    database_path = tmp_path / "address_change.db"
    init_database(database_path)

    request = AddressChangeRequest(
        order_id="ORD1001",
        new_address="上海市浦东新区世纪大道100号",
        confirmed=False,
    )

    with pytest.raises(ValueError, match="尚未确认"):
        create_address_change_ticket(
            request,
            user_id="demo-user-001",
            database_path=database_path,
        )