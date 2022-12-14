from datetime import datetime
from typing import List, Type, Any, TypeVar

import sqlalchemy
from sqlalchemy import func, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, Query

engine = sqlalchemy.create_engine('sqlite+pysqlite:///walkr.db')


# todo: переделать всё в async


def make_session():
    return Session(engine)


class Base(DeclarativeBase):
    pass


T = TypeVar('T')


def get_or_create(
        session: Session,
        class_: Type[T],
        filters: dict[sqlalchemy.orm.attributes.InstrumentedAttribute, Any],
        allow_many: bool = False
) -> T | list[T]:
    norm_filters: dict[str, Any] = {k.key: v for k, v in filters.items()}
    query = session.query(class_).filter_by(**norm_filters)
    found = query.count()
    if found == 0:
        obj = class_(**norm_filters)
        session.add(obj)
        return obj
    elif found == 1 or not allow_many:
        return query.one()

    return query.all()


class Token(Base):
    __tablename__ = "token"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str]
    active: Mapped[bool]
    create_dt: Mapped[datetime] = mapped_column(insert_default=func.now())
    update_dt: Mapped[datetime]
    expired_dt: Mapped[datetime]

    user_id = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="token", uselist=False)


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    create_dt: Mapped[datetime] = mapped_column(insert_default=func.now())

    token: Mapped[Token] = relationship(back_populates="user")
    lab_planets: Mapped[List['LabPlanet']] = relationship(back_populates="user")


class LabPlanet(Base):
    __tablename__ = 'lab_planet'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    planet_name: Mapped[str]
    planet_requirements: Mapped[int]
    create_dt: Mapped[datetime] = mapped_column(insert_default=func.now())

    user: Mapped[User] = relationship(back_populates='lab_planets')
    lab_requests: Mapped[List['LabRequest']] = relationship(back_populates='lab_planet')


class LabRequest(Base):
    __tablename__ = 'lab_request'

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_planet_id: Mapped[int] = mapped_column(ForeignKey("lab_planet.id"))
    requested_dt: Mapped[datetime]
    create_dt: Mapped[datetime] = mapped_column(insert_default=func.now())

    lab_planet: Mapped[LabPlanet] = relationship(back_populates='lab_requests')
    progresses: Mapped[List['LabRequestProgress']] = relationship(back_populates='request')


class LabRequestProgress(Base):
    __tablename__ = 'lab_request_progress'

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_request_id: Mapped[int] = mapped_column(ForeignKey("lab_request.id"))
    create_dt: Mapped[datetime] = mapped_column(insert_default=func.now())
    total_donation: Mapped[int]
    current_donation: Mapped[int]
    donated_counter: Mapped[str]

    request: Mapped[LabRequest] = relationship(back_populates='progresses')
