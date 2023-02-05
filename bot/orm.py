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


# todo: таблица с айдишниками отправленных сообщений для их автообновления из крона, подтягивающий инфу о прогрессе

# todo: или в токен, или в юзера прикопать telegram id для отправки личных нотификаций
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
    # todo: добавить критерий докачанности планеты (ну или же динамически селектить последний прогресс реквестов)
    # todo: реализовать какие-нибудь хуки на факт докачки планеты (для возможности отправки уведомления)
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
    # todo: новая колонка finished - bool, для отфильтровывания добитых раньше времени, а для этого alembic бы воткнуть


# todo: новая таблица lab_request_donation, стобцы lab_request_id, energy, from_user, update_dt
#  наполняется путём парсинга donated_counter из прогресса (поиск по юзеру, обновление в случае существования)
#  опасно: если донативший ни разу не ставил планету, упадёт на FK - надо перезапросить весь список лабы и заполнить
#  недостающих
#  плюс: нужна миграция по заполнению таблицы на основании уже существующих прогрессов


class LabRequestProgress(Base):
    __tablename__ = 'lab_request_progress'

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_request_id: Mapped[int] = mapped_column(ForeignKey("lab_request.id"))
    create_dt: Mapped[datetime] = mapped_column(insert_default=func.now())
    total_donation: Mapped[int]
    current_donation: Mapped[int]
    donated_counter: Mapped[str]

    request: Mapped[LabRequest] = relationship(back_populates='progresses')
