import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, cast

import aiohttp
import requests
from marshmallow import Schema, fields

DEFAULT_CLIENT_VERSION = "7.2.2.4"
DEFAULT_IOS_VERSION = "17.4.1"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# todo: перейти на https://github.com/lovasoa/marshmallow_dataclass
# а то выходит, что поля приходится дублировать


class TimeStamp(fields.DateTime):
    def __init__(self, *args, **kwargs):
        super().__init__(format='timestamp')

    def _deserialize(self, value, attr, data, **kwargs) -> datetime:
        if isinstance(value, int) and value == 0:
            return datetime(1970, 1, 1)
        return super()._deserialize(value, attr, data, **kwargs)


class EpicSchema(Schema):
    id = fields.Int()
    icon = fields.URL()
    cover = fields.URL()
    name = fields.Str()


class UserSchema(Schema):
    id = fields.Int(allow_none=True)  # сообщения от системы имеют null
    name = fields.Str()
    avatar = fields.Str()  # fields.URL()
    level = fields.Int()
    planets_count = fields.Int()
    replicators_count = fields.Int()
    energy_productivity = fields.Int()
    population = fields.Int()
    spaceship = fields.Str()
    contribution = fields.Int()
    title = fields.Str(allow_none=True)
    role = fields.Str()
    rsvp = fields.Str()
    score = fields.Int()

    # todo: надо ли автоматически выплёвывать тут orm юзера?


class FleetSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    country_code = fields.Str()
    privacy = fields.Str()  # private|public ?
    is_invitable = fields.Bool()
    members_count = fields.Int()
    players_count = fields.Int()
    members_max = fields.Int()
    members_min = fields.Int()
    weight = fields.Float()
    invited = fields.Bool()
    created_at = TimeStamp()
    started_at = TimeStamp()
    event_status = fields.Str()  # path|event ?
    contribution_amount = fields.Int()
    energy = fields.Int()
    consumed_energy = fields.Int()
    last_consumed_at = TimeStamp()
    value_a = fields.Int()
    value_b = fields.Int()
    value_c = fields.Int()
    badge_front = fields.URL()
    badge_back = fields.URL()
    epic = fields.Nested(EpicSchema())
    captain = fields.Nested(UserSchema(only=('name', 'avatar')))


class UrlContainerSchema(Schema):
    url = fields.URL()


class EventSchema(Schema):
    id = fields.Int()
    epic_id = fields.Int()
    cover = fields.Nested(UrlContainerSchema())
    event_type = fields.Str()
    resource_a = fields.Int()
    resource_b = fields.Int(allow_none=True)
    resource_c = fields.Int(allow_none=True)
    created_at = fields.DateTime(format='%Y-%m-%d %H:%M:%S')
    updated_at = fields.DateTime(format='%Y-%m-%d %H:%M:%S')
    attachment = fields.URL(allow_none=True)
    name = fields.Str()
    description = fields.Str()
    label_a = fields.Str(allow_none=True)
    label_b = fields.Str(allow_none=True)
    label_c = fields.Str(allow_none=True)


class EventHistorySchema(Schema):
    """very similar to Event"""
    id = fields.Int()
    name = fields.Str()
    description = fields.Str()
    cover = fields.URL()
    event_type = fields.Str()
    attachment = fields.URL(allow_none=True)
    label_a = fields.Str(allow_none=True)
    label_b = fields.Str(allow_none=True)
    label_c = fields.Str(allow_none=True)
    value_a = fields.Int()
    value_b = fields.Int()
    value_c = fields.Int()
    solved_at = TimeStamp()


class PathSchema(Schema):
    id = fields.Int()
    epic_event_id = fields.Int()
    target_id = fields.Int()
    time = fields.Int()
    required_energy = fields.Int()
    created_at = fields.DateTime(format='%Y-%m-%d %H:%M:%S')
    updated_at = fields.DateTime(format='%Y-%m-%d %H:%M:%S')


class HitpointsSchema(Schema):
    value_a = fields.Int()
    value_b = fields.Int()
    value_c = fields.Int()
    hitpoints = fields.Int()
    next_hitpoint_at = TimeStamp()
    next_hitpoint_countdown = fields.Int(allow_none=True)


class FleetsApiAnswerSchema(Schema):
    success = fields.Boolean()
    fleet = fields.Nested(FleetSchema(), allow_none=True)
    event_status = fields.String()
    event = fields.Nested(EventSchema())
    path = fields.Nested(PathSchema())
    members = fields.List(fields.Nested(UserSchema()))
    fleet_histories = fields.List(fields.Nested(EventHistorySchema()))
    hitpoints = fields.Nested(HitpointsSchema())
    now = TimeStamp()


def _get_headers(
        auth_token: str,
        client_version: str = DEFAULT_CLIENT_VERSION,
        ios_version: str = DEFAULT_IOS_VERSION,
        **additional_params
) -> dict[str, str]:
    client_version = '.'.join(client_version.split('.')[:3])
    headers = {
        'Accept': '*/*',
        'User-Agent': f'Walkr/{client_version} (iPhone; iOS {ios_version}; Scale/3.00)',
        'Accept-Language': 'en-US;q=1, ru-RU;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'authorization': f'Bearer {auth_token}',
    }
    headers.update(additional_params)
    return headers


def _get_params(
        client_version: str = DEFAULT_CLIENT_VERSION,
        ios_version: str = DEFAULT_IOS_VERSION,
        **additional_params
) -> dict[str, str]:
    data = {
        "locale": "en",
        "client_version": client_version,
        "platform": "ios",
        "timezone": 2,
        "os_version": f"iOS {ios_version}",
        "country_code": "RU",
        "device_model": "iPhone13,2"
    }
    data.update(additional_params)
    return data


async def make_async_request(
        method: str,
        url: str,
        session: aiohttp.ClientSession,
        auth_token: str,
        additional_params: dict = None,
        additional_headers: dict = None
) -> str:
    # todo: 1-2 second optional cache to prevent the same multiple requests (oh no, async)
    additional_params = additional_params or {}
    additional_headers = additional_headers or {}
    params = _get_params(**additional_params)
    headers = _get_headers(auth_token, **additional_headers)

    logger.info('async %s %s params=%s headers=%s', method, url, params, headers)
    cookies = session.cookie_jar.filter_cookies(session._build_url(url))
    logger.debug(f'cookies: {cookies}')

    if method == 'get':
        mng = session.get(url, params=params, headers=headers, ssl=False)
    elif method == 'post':
        data = json.dumps(params)
        mng = session.post(url, data=data, headers=headers, ssl=False)
    else:
        raise ValueError(f'unknown method - {method}')

    async with mng as response:
        result = await response.text()
        if response.status == 401:
            # токен устарел
            # todo: а вот тут надо выставить active=0 токену в бд
            raise ValueError('response code is 401, token is invalid: %s url: %s\ndata=%s', response.status, url,
                             result)
        elif response.status != 200:
            raise ValueError(f'response code is not 200: {response.status} url: {url}\ndata={result}')
        logger.info('response %s status, \ndata=%s', response.status, result)
        return result


def make_sync_request(
        method: str,
        url: str,
        auth_token: str,
        additional_params: dict = None,
        additional_headers: dict = None
) -> str:
    # отдельный метод добавляю для cli, чтобы async там не городить
    # todo: объединить два этих метода как-нибудь
    additional_params = additional_params or {}
    additional_headers = additional_headers or {}
    params = _get_params(**additional_params)
    headers = _get_headers(auth_token, **additional_headers)

    logger.info('sync %s %s params=%s headers=%s', method, url, params, headers)
    if method == 'get':
        resp = requests.get(url, params=params, headers=headers)
    elif method == 'post':
        resp = requests.post(url, data=params, headers=headers)
    else:
        raise ValueError(f'unknown method - {method}')

    result = resp.text
    if resp.status_code != 200:
        raise ValueError('response code is not 200: %s url: %s\ndata=%s', resp.status_code, url, result)
    logger.info('response %s status, \ndata=%s', resp.status_code, result)
    return result


@dataclass
class FleetWrapper:
    name: str
    id: int
    epic_name: str
    epic_id: int
    voting: Optional[str]
    members: list[dict]
    contribution_now: int

    @classmethod
    def from_api_answer(cls, data: dict) -> Optional['FleetWrapper']:
        if not data['fleet']:  # not in fleet now
            return None

        voting = None
        voting_events = [h for h in data['fleet_histories'] if h['event_type'] == 'voting']
        if voting_events:
            member_count = data['fleet']['players_count']
            vote_results = []
            for vote_event in voting_events:
                for votes, option in zip(
                        (vote_event['value_a'], vote_event['value_b']),
                        (vote_event['label_a'], vote_event['label_b'])
                ):
                    if 2 * votes >= member_count:
                        vote_results.append(option)
                        break
            voting = '|'.join(vote_results)
        return cls(
            name=data["fleet"]["name"],
            id=data["fleet"]["id"],
            epic_name=data["fleet"]["epic"]["name"],
            epic_id=data["fleet"]["epic"]["id"],
            voting=voting,
            members=data['members'],
            contribution_now=data['fleet']['contribution_amount']
        )


@dataclass
class EventWrapper:
    status: str  # event/path
    type: str  # preparation/...
    current_values: tuple[int, int, int]
    max_values: tuple[Optional[int], Optional[int], Optional[int]]
    value_labels: tuple[Optional[str], Optional[str], Optional[str]]
    current_energy: int
    max_energy: int

    @classmethod
    def from_api_answer(cls, data: dict) -> 'EventWrapper':
        status = data['event_status']
        type_ = data['event']['event_type']
        current_values = cast(
            tuple[int, int, int],
            tuple(data['fleet'][f'value_{c}'] for c in ('a', 'b', 'c'))
        )
        max_values = cast(
            tuple[int | None, int | None, int | None],
            tuple(data['event'][f'resource_{c}'] for c in ('a', 'b', 'c'))
        )
        value_labels = cast(
            tuple[int | None, int | None, int | None],
            tuple(data['event'][f'label_{c}'] for c in ('a', 'b', 'c'))
        )
        if status == 'path':
            current_energy = data['fleet']['energy'] + data['fleet']['consumed_energy']
        else:  # there is energy from the last path
            current_energy = 0
        max_energy = data['path']['required_energy']
        return cls(status, type_, current_values, max_values, value_labels, current_energy, max_energy)


class NotInEpic(Exception):
    pass


async def get_fleet(auth_token: str, session: aiohttp.ClientSession) -> tuple[FleetWrapper, EventWrapper]:
    url = 'https://production.sw.fourdesire.com/api/v2/fleets/current'
    result: str = await make_async_request('get', url, session, auth_token)
    result: dict = FleetsApiAnswerSchema().loads(result)

    fleet = FleetWrapper.from_api_answer(result)
    if not fleet:
        raise NotInEpic

    fleet = FleetWrapper.from_api_answer(result)
    event = EventWrapper.from_api_answer(result)

    return fleet, event


class CommentContentSchema(Schema):
    type = fields.Str()  # donation | sticker | text
    donation_type = fields.Str()  # energy
    donation_value = fields.Int()  # 500
    max_donation_count = fields.Int()  # 5
    colony_type = fields.Str()  # planet
    identifier = fields.Str()  # какая планета
    requirements = fields.Int()  # сколько надо для прокачки
    total_donation = fields.Int()  # сколько уже прокачано
    current_donation = fields.Int()  # сколько прокачано этим запросом
    donated_counter = fields.Str()  # кто в этом запросе сколько вкинул. 271306|500+500+500+500+500,1599163|500+500
    last_requested_at = TimeStamp()
    text = fields.Str()  # для текста и стикера
    level = fields.Int()  # в research в lab api добавлено


class CommentSchema(Schema):
    id = fields.Int()
    comment = fields.Nested(CommentContentSchema())
    created_at = TimeStamp()
    blocked = fields.Bool()
    user = fields.Nested(UserSchema())
    raw_comment = fields.Str()


class CommentsAnswerSchema(Schema):
    success = fields.Bool()
    comments = fields.List(fields.Nested(CommentSchema()))
    now = TimeStamp()


@dataclass
class LabRequestWrapper:
    created_at: datetime
    user_id: int
    user_name: str
    planet_name: str
    requirements: int
    total_donation: int
    current_donation: int
    last_requested_at: datetime
    donated_counter: str


async def get_lab_planets(auth_token: str, session: aiohttp.ClientSession) -> list[LabRequestWrapper]:
    result = await make_async_request(
        'get',
        'https://production.sw.fourdesire.com/api/v2/comments',
        session,
        auth_token,
        {
            'commentable_id': 68334,
            'commentable_type': 'lab',
            'limit': 3000,
            'queried_at': 2147483647,
            'since_id': 0,

        }
    )
    result = CommentsAnswerSchema().loads(result)

    lab_requests = [c for c in result['comments'] if c['comment']['type'] == 'donation']
    ret = []
    for req in lab_requests:
        ret.append(LabRequestWrapper(
            created_at=req['created_at'],
            user_id=req['user']['id'],
            user_name=req['user']['name'],
            planet_name=req['comment']['identifier'],
            requirements=req['comment']['requirements'],
            total_donation=req['comment']['total_donation'],
            current_donation=req['comment']['current_donation'],
            last_requested_at=req['comment']['last_requested_at'],
            donated_counter=req['comment']['donated_counter'],
        ))
    return ret


class LabSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    description = fields.Str()
    country_code = fields.Str()
    privacy = fields.Str()  # private|public ?
    tag = fields.Str()
    planet_limit = fields.Int()
    score = fields.Int()
    badge_front = fields.URL()
    badge_back = fields.URL()
    members_count = fields.Int()
    members_max = fields.Int()
    leader = fields.Nested(UserSchema(only=('id', 'name', 'avatar')))
    invited = fields.Bool()


class LabAnswerSchema(Schema):
    success = fields.Bool()
    lab = fields.Nested(LabSchema())
    research = fields.Nested(CommentContentSchema())
    members = fields.List(fields.Nested(UserSchema()))
    now = TimeStamp()


async def get_user_request(auth_token: str, session: aiohttp.ClientSession) -> LabRequestWrapper:
    result = await make_async_request(
        'get',
        'https://production.sw.fourdesire.com/api/v2/labs/current',
        session,
        auth_token
    )
    result = LabAnswerSchema().loads(result)

    return LabRequestWrapper(
        created_at=None,
        user_id=None,
        user_name=None,
        planet_name=result['research']['identifier'],
        requirements=result['research']['requirements'],
        total_donation=result['research']['total_donation'],
        current_donation=result['research']['current_donation'],
        last_requested_at=result['research']['last_requested_at'],
        donated_counter=result['research']['donated_counter'],
    )


async def make_lab_request(auth_token: str, session: aiohttp.ClientSession) -> None:
    await make_async_request(
        'post',
        'https://production.sw.fourdesire.com/api/v2/labs/68334/request',
        session,
        auth_token,
        additional_headers={'Content-Type': 'application/json'}
    )
