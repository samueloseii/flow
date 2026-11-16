import enum
import uuid

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class RelationType(str, enum.Enum):
    PARENT = "parent"
    CHILD = "child"


class EntityLevel(str, enum.Enum):
    ORGANIZATION = "organization"
    PARTNER = "partner"
    WATER_COMMITTEE = "water_committee"
    COMMUNITY = "community"  # a grouping of connections; CHILD rows only
    CONNECTION = "connection"


class UserRelation(Base):
    """Attaches a user to one entity.

    Every non-super-admin user has exactly one PARENT row: the entity the account
    belongs to.  With access_all_children the user sees everything below it; otherwise
    CHILD rows list the sub-entities (communities, connections) they may see.
    """

    __tablename__ = "user_relations"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN organization_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN partner_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN water_committee_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN community_id IS NULL THEN 0 ELSE 1 END)"
            " + (CASE WHEN connection_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="one_entity_per_relation",
        ),
        CheckConstraint(
            "relation_type = 'PARENT' OR access_all_children = false",
            name="all_children_only_on_parent",
        ),
        CheckConstraint(
            "relation_type = 'CHILD' OR community_id IS NULL",
            name="community_is_a_grouping_not_a_parent",
        ),
        Index(
            "one_parent_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("relation_type = 'PARENT'"),
            sqlite_where=text("relation_type = 'PARENT'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    relation_type: Mapped[RelationType] = mapped_column(
        Enum(RelationType), default=RelationType.CHILD
    )
    access_all_children: Mapped[bool] = mapped_column(Boolean, default=False)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("partners.id", ondelete="CASCADE"), nullable=True
    )
    water_committee_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("water_committees.id", ondelete="CASCADE"), nullable=True
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("communities.id", ondelete="CASCADE"), nullable=True
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("connections.id", ondelete="CASCADE"), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="relations")  # noqa: F821

    @property
    def level(self) -> EntityLevel:
        if self.organization_id:
            return EntityLevel.ORGANIZATION
        if self.partner_id:
            return EntityLevel.PARTNER
        if self.water_committee_id:
            return EntityLevel.WATER_COMMITTEE
        if self.community_id:
            return EntityLevel.COMMUNITY
        return EntityLevel.CONNECTION

    @property
    def entity_id(self) -> uuid.UUID:
        return (
            self.organization_id
            or self.partner_id
            or self.water_committee_id
            or self.community_id
            or self.connection_id
        )

    @classmethod
    def for_entity(
        cls,
        level: EntityLevel,
        entity_id: uuid.UUID,
        relation_type: RelationType = RelationType.CHILD,
        access_all_children: bool = False,
    ) -> "UserRelation":
        rel = cls(relation_type=relation_type, access_all_children=access_all_children)
        setattr(rel, f"{level.value}_id", entity_id)
        return rel
