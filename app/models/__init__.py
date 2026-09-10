"""StayEase SQLAlchemy models (Step 3).

Importing this package registers all 7 tables on ``Base.metadata``,
so ``Base.metadata.create_all(engine)`` (see ``app/database/init_db.py``)
creates the full schema. Re-exported here for convenient imports::

    from app.models import User, Hotel, Reservation
"""

from app.models.guest import Guest
from app.models.hotel import Hotel
from app.models.payment import Payment
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.room_type import RoomType
from app.models.user import User

__all__ = [
    "Guest",
    "Hotel",
    "Payment",
    "Reservation",
    "Room",
    "RoomType",
    "User",
]
