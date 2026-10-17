"""Sample data: a small tool library with every interesting situation represented once.

All people are invented. Phone numbers start with 0, which no Indian mobile or landline number
can, so none of them can belong to a real person. Timestamps are relative to the `now` passed in,
so a fresh seed always shows an overdue loan, a reservation about to expire, and so on.

Fees on returned loans are written by hand from the Problem 1 formula (₹10 per late day, capped at
₹200 and at the replacement value); tests/test_seed.py re-checks them once the rules exist.
"""

from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.domain.enums import ItemStatus, LoanStatus, MemberStatus
from app.domain.policy import LOAN_PERIOD
from app.models import Item, Loan, Member, MemberSuspension, Payment


def rupees(amount: int) -> int:
    """Whole rupees to paise."""
    return amount * 100


def is_seeded(session: Session) -> bool:
    return session.scalar(sa.select(sa.func.count(Member.id))) > 0


def delete_all_rows(session: Session) -> None:
    """Empty every table, children first."""
    for model in (Payment, Loan, MemberSuspension, Item, Member):
        session.execute(sa.delete(model))


def _loan_out(member, item, checked_out_at, *, returned_at=None, fee=0):
    """A loan that was checked out (and maybe returned). Reserved one hour before check-out."""
    return Loan(
        member=member,
        item=item,
        status=LoanStatus.RETURNED if returned_at else LoanStatus.CHECKED_OUT,
        reserved_at=checked_out_at - timedelta(hours=1),
        checked_out_at=checked_out_at,
        due_at=checked_out_at + LOAN_PERIOD,
        returned_at=returned_at,
        fee_charged_paise=fee,
    )


def seed_database(session: Session, now: datetime) -> bool:
    """Insert the sample data. Returns False (and changes nothing) if members already exist."""
    if is_seeded(session):
        return False

    def ago(**kwargs) -> datetime:
        return now - timedelta(**kwargs)

    def item(name, category, value_rupees, note="", status=ItemStatus.AVAILABLE) -> Item:
        return Item(
            name=name,
            category=category,
            replacement_value_paise=rupees(value_rupees),
            condition_note=note,
            status=status,
        )

    def member(name, phone, joined_days_ago) -> Member:
        return Member(
            name=name,
            phone=phone,
            join_date=ago(days=joined_days_ago).date(),
            status=MemberStatus.ACTIVE,
        )

    drill = item("Cordless Drill 18V", "Power Tools", 6500, "Two batteries and charger")
    saw = item("Circular Saw", "Power Tools", 5000, "Blade replaced Sept 2026")
    grinder = item("Angle Grinder", "Power Tools", 3500, "Guard fitted")
    ext_ladder = item("Extension Ladder 3.5 m", "Ladders", 9000, "Rubber feet worn on left side")
    step_ladder = item("Step Ladder 6 ft", "Ladders", 2800)
    tiller = item("Garden Tiller (petrol)", "Garden", 18000, "Check oil before lending")
    trimmer = item("Hedge Trimmer", "Garden", 4500)
    wheelbarrow = item(
        "Wheelbarrow",
        "Garden",
        3200,
        "Punctured tyre, awaiting replacement",
        status=ItemStatus.UNDER_MAINTENANCE,
    )
    washer = item("Pressure Washer", "Cleaning", 12000, "Hose has a small kink")
    vacuum = item("Wet/Dry Vacuum", "Cleaning", 5500)
    projector = item("LED Projector 1080p", "Electronics", 22000, "HDMI cable included")
    tile_cutter = item("Tile Cutter", "Workshop", 7500)
    # Cheap on purpose: a long delay hits the "never more than replacement value" cap (₹150).
    spirit_level = item("Spirit Level 1 m", "Workshop", 150)

    aarav = member("Aarav Menon", "+91 00000 10001", 400)
    priya = member("Priya Nair", "+91 00000 10002", 380)
    rohan = member("Rohan Deshpande", "+91 00000 10003", 300)
    meera = member("Meera Kulkarni", "+91 00000 10004", 280)
    kavita = member("Kavita Iyer", "+91 00000 10005", 250)
    imran = member("Imran Sheikh", "+91 00000 10006", 220)
    suresh = member("Suresh Pillai", "+91 00000 10007", 200)
    anjali = member("Anjali Verma", "+91 00000 10008", 150)
    dinesh = member("Dinesh Patel", "+91 00000 10009", 120)
    farah = member("Farah Qureshi", "+91 00000 10010", 90)
    dinesh.status = MemberStatus.SUSPENDED

    loans = [
        # Aarav: one loan out and on time; one returned on time long ago.
        _loan_out(aarav, drill, ago(days=2)),
        _loan_out(aarav, saw, ago(days=30), returned_at=ago(days=25)),
        # Priya: at the 3-loan limit (two checked out, one fresh reservation).
        _loan_out(priya, ext_ladder, ago(days=3)),
        _loan_out(priya, trimmer, ago(days=1)),
        Loan(member=priya, item=projector, status=LoanStatus.RESERVED, reserved_at=ago(hours=2)),
        # Rohan: overdue by 3 days (fee would be ₹30 if returned now).
        _loan_out(rohan, tiller, ago(days=10)),
        # Meera: two loans overdue by 16 days, so she is blocked (more than 14 days).
        # Returning the washer would cost ₹160; the spirit level is capped at its ₹150 value.
        _loan_out(meera, washer, ago(days=23)),
        _loan_out(meera, spirit_level, ago(days=23)),
        # Kavita: unpaid fees of ₹120 (₹80 + ₹50 late fees, ₹10 paid), so she is blocked.
        _loan_out(
            kavita,
            vacuum,
            ago(days=40),
            returned_at=ago(days=40) + LOAN_PERIOD + timedelta(days=8),
            fee=rupees(80),
        ),
        _loan_out(
            kavita,
            tile_cutter,
            ago(days=20),
            returned_at=ago(days=20) + LOAN_PERIOD + timedelta(days=5),
            fee=rupees(50),
        ),
        # Imran: balance of exactly ₹100 (10 days late), which is NOT blocked.
        _loan_out(
            imran,
            drill,
            ago(days=60),
            returned_at=ago(days=60) + LOAN_PERIOD + timedelta(days=10),
            fee=rupees(100),
        ),
        # Suresh: reservation made 47 hours ago; it expires in one hour.
        Loan(member=suresh, item=grinder, status=LoanStatus.RESERVED, reserved_at=ago(hours=47)),
        # Anjali: history of a cancelled and an expired reservation, nothing active.
        Loan(
            member=anjali,
            item=projector,
            status=LoanStatus.CANCELLED,
            reserved_at=ago(days=12),
            cancelled_at=ago(days=12) + timedelta(hours=1),
        ),
        Loan(member=anjali, item=step_ladder, status=LoanStatus.EXPIRED, reserved_at=ago(days=5)),
        # Farah: one late return (₹20), fully paid.
        _loan_out(
            farah,
            step_ladder,
            ago(days=15),
            returned_at=ago(days=15) + LOAN_PERIOD + timedelta(days=2),
            fee=rupees(20),
        ),
    ]
    # Items out on loan or held by a reservation.
    for borrowed in (drill, ext_ladder, trimmer, tiller, washer, spirit_level):
        borrowed.status = ItemStatus.CHECKED_OUT
    for held in (projector, grinder):
        held.status = ItemStatus.RESERVED

    payments = [
        Payment(member=kavita, amount_paise=rupees(10), paid_at=ago(days=7), note="Cash at desk"),
        Payment(member=farah, amount_paise=rupees(20), paid_at=ago(days=5), note="UPI"),
    ]
    suspensions = [
        MemberSuspension(
            member=dinesh,
            suspended_at=ago(days=60),
            lifted_at=ago(days=50),
            reason="Tools returned damaged",
        ),
        MemberSuspension(
            member=dinesh, suspended_at=ago(days=5), reason="Repeated missed reservation pickups"
        ),
    ]

    session.add_all(
        [
            *(drill, saw, grinder, ext_ladder, step_ladder, tiller, trimmer, wheelbarrow),
            *(washer, vacuum, projector, tile_cutter, spirit_level),
            *(aarav, priya, rohan, meera, kavita, imran, suresh, anjali, dinesh, farah),
            *loans,
            *payments,
            *suspensions,
        ]
    )
    session.flush()
    return True
