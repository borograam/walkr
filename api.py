import json
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp
import requests

import meta

DEFAULT_CLIENT_VERSION = "6.12.2.12"
DEFAULT_IOS_VERSION = "15.3.1"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _get_headers(
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
    }
    headers.update(additional_params)
    return headers


def _get_params(
        auth_token: str,
        client_version: str = DEFAULT_CLIENT_VERSION,
        ios_version: str = DEFAULT_IOS_VERSION,
        **additional_params
) -> dict[str, str]:
    data = {
        "locale": "en",
        "client_version": client_version,
        "platform": "ios",
        "timezone": 6,
        "os_version": f"iOS {ios_version}",
        "auth_token": auth_token,
        "country_code": "RU",
        "device_model": "iPhone13,2"
    }
    data.update(additional_params)
    return data


async def _make_request(method: str, url: str, session: aiohttp.ClientSession, auth_token: str) -> dict:
    # todo: 1-2 second optional cache to prevent the same multiple requests (oh no, async)
    params = _get_params(auth_token)
    headers = _get_headers()

    logger.info('%s %s params=%s headers=%s', method, url, params, headers)
    if method == 'get':
        mng = session.get(url, params=params, headers=headers, ssl=False)
    elif method == 'post':
        mng = session.post(url, data=params, headers=headers, ssl=False)
    else:
        raise ValueError(f'unknown method - {method}')

    async with mng as response:
        result = await response.json()
        logger.info('response %s status, \ndata=%s', response.status, result)
        return result


def make_lab_request(auth_token: str):
    raise NotImplementedError
    url = 'https://production.sw.fourdesire.com/api/v2/labs/68334/request'
    headers = _get_headers(**{'Content-Type': 'application/json'})

    data = _get_params(auth_token)
    r = requests.post(url, json.dumps(data), headers=headers)
    # на автоматике перед этим пусть обязательно делается GET /api/v2/labs/68334 и удостоверяемся, что
    # 1) у меня не максимум
    # 2) now - last_requested_at > 6hours

    # если я смогу собрать токены окружающих...
    return r


async def get_lab_info(auth_token: str, session: aiohttp.ClientSession):
    url = 'https://production.sw.fourdesire.com/api/v2/labs/current'
    result = await _make_request('get', url, session, auth_token)

    lab_name = result['lab']['name']
    lab_score = result['lab']['score']
    members = [m for m in result['members'] if m['rsvp'] == 'member']

    output_lines = [f'{lab_name} ({lab_score})\n']
    for member in members:
        output_lines.append(
            f'{member["name"]} {member["planets_count"]}🌍 {member["population"]}👥 {member["score"]}⚡️')

    output = '\n'.join(output_lines)
    return output


@dataclass
class Fleet:
    name: str
    id: int
    epic_name: str
    epic_id: int
    voting: Optional[str]


def what_the_fleet(data: dict) -> Fleet:  # todo it in Fleet init?
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
    return Fleet(
        name=data["fleet"]["name"],
        id=data["fleet"]["id"],
        epic_name=data["fleet"]["epic"]["name"],
        epic_id=data["fleet"]["epic"]["id"],
        voting=voting
    )


@dataclass
class Event:
    status: str  # event/path
    type: str  # preparation/...
    current_values: tuple[int, int, int]
    max_values: tuple[Optional[int], Optional[int], Optional[int]]
    value_labels: tuple[Optional[str], Optional[str], Optional[str]]
    current_energy: int
    max_energy: int


def what_the_event(data: dict) -> Event:
    status = data['event_status']
    type = data['event']['event_type']
    current_values = tuple(data['fleet'][f'value_{c}'] for c in ('a', 'b', 'c'))
    max_values = tuple(data['event'][f'resource_{c}'] for c in ('a', 'b', 'c'))
    value_labels = tuple(data['event'][f'label_{c}'] for c in ('a', 'b', 'c'))
    if status == 'path':
        current_energy = data['fleet']['energy'] + data['fleet']['consumed_energy']
    else:  # there is energy from the last path
        current_energy = 0
    max_energy = data['path']['required_energy']
    return Event(status, type, current_values, max_values, value_labels, current_energy, max_energy)


async def get_epic_info(auth_token: str, session: aiohttp.ClientSession):
    # todo: коротко о следующих этапах

    url = 'https://production.sw.fourdesire.com/api/v2/fleets/current'
    result = await _make_request('get', url, session, auth_token)

    # result can be like {'success': True, 'fleet': None, 'now': 1667901025}
    # todo catch it

    fleet = what_the_fleet(result)
    comments = []

    if fleet.epic_id not in meta.epics:
        logger.error('we have no information about epic id=%s, name=%s', fleet.epic_id, fleet.epic_name)
        comments.append('у меня нет информации по поводу этого эпика, надо бы добавить')
        max_contribution = 0
    else:
        meta_epic = meta.epics[fleet.epic_id]['amounts']
        max_contribution = meta_epic.get(fleet.voting)
        if not max_contribution:
            will_use_voting, max_contribution = min(meta_epic.items(), key=lambda t: t[1])
            comments.append(f'пока не прошли все голосования, буду использовать итоговый вклад от {will_use_voting}')

    rest_members_count = len(result["members"])
    sum_contribution_now = result['fleet']['contribution_amount']

    def percent(n1: int, n2: int, format_str: str, default: str | None = None) -> str | None:
        if n2:
            return format_str.format(round(n1 / n2 * 100, 2))
        return default

    specify_voting = f' - {fleet.voting}' if fleet.voting else ''
    fleet_percent = percent(sum_contribution_now, max_contribution, ' [{}%]', default='')
    output_lines = [f'{fleet.name} ({fleet.epic_name}{specify_voting}){fleet_percent}']

    event = what_the_event(result)
    cur_event_donation = ', '.join(
        f'{value}/{max_value}'
        for value, max_value in zip(event.current_values, event.max_values)
        if max_value
    )
    output_lines.append(f'{event.type} ({cur_event_donation}) -> {event.current_energy}/{event.max_energy}⚡\n')

    for member in result["members"]:
        contribution = member['contribution']
        now_percent_str = percent(contribution, sum_contribution_now, '{.2f}%', '0%')
        end_percent_str = percent(contribution, max_contribution, ' [{}%]', default='')
        ideal_contr = round(max_contribution / rest_members_count)
        if contribution >= ideal_contr:  # слишком много закинул
            # больше не используем этого человека в расчётах
            max_contribution -= contribution
            rest_members_count -= 1
            need_more_str = ''
        else:
            need_more = ideal_contr - contribution
            need_more_str = f' more {need_more}💰 or {need_more // 20}🍅/🌎 or {need_more // 40}⚡'

        waiting = '🕐' if member['rsvp'] == 'waiting' else ''
        output_lines.append(f'{now_percent_str}{end_percent_str} {waiting}`{member["name"]}`{need_more_str}')

    if comments:
        output_lines.append('')
        output_lines.extend(comments)

    return '\n'.join(output_lines)
