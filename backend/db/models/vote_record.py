"""Vote record collection model (§5)."""

from db.models.common import MongoDocument, PyObjectId
from db.models.enums import Vote


class VoteRecord(MongoDocument):
    action_id: PyObjectId
    office_tenure_id: PyObjectId | None = None
    person_id: PyObjectId | None = None
    vote: Vote
