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
    data = _get_params(auth_token)
    headers = _get_headers()

    logger.info('get %s data=%s headers=%s', url, data, headers)
    async with session.get(url, params=data, headers=headers, ssl=False) as response:
        logger.info('response %s status', response.status)
        result = await response.json()
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


def what_the_fleet(data: dict) -> Fleet:
    voting = None
    voting_events = [h for h in data['fleet_histories'] if h['event_type'] == 'voting']
    if voting_events:
        member_count = data['fleet']['players_count']
        for votes, option in zip(
                (voting_events[0]['value_a'], voting_events[0]['value_b']),
                (voting_events[0]['label_a'], voting_events[0]['label_b'])
        ):
            if 2 * votes >= member_count:
                voting = option
    return Fleet(
        name=data["fleet"]["name"],
        id=data["fleet"]["id"],
        epic_name=data["fleet"]["epic"]["name"],
        epic_id=data["fleet"]["epic"]["id"],
        voting=voting
    )


async def get_epic_info(auth_token: str, session: aiohttp.ClientSession):
    url = 'https://production.sw.fourdesire.com/api/v2/fleets/current'
    params = _get_params(auth_token)
    headers = _get_headers()

    logger.info('get %s params=%s headers=%s', url, params, headers)
    async with session.get(url, params=params, headers=headers, ssl=False) as response:
        logger.info('response %s status', response.status)
        result = await response.json()

    fleet = what_the_fleet(result)
    specify_voting = f' - {fleet.voting}' if fleet.voting else ''
    output_lines = [f'{fleet.name} ({fleet.epic_name}{specify_voting})\n']
    comments = []

    sum_contribution_now = result['fleet']['contribution_amount']

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

    rest_members_count = result['fleet']['members_count']

    for member in result["members"]:
        contribution = member['contribution']
        percent = round(contribution / sum_contribution_now * 100, 2)
        ideal_contr = round(max_contribution / rest_members_count)
        if contribution >= ideal_contr:  # слишком много закинул
            # больше не используем этого человека в расчётах
            max_contribution -= contribution
            rest_members_count -= 1
            need_more_str = ''
        else:
            need_more = ideal_contr - contribution
            need_more_str = f' +{need_more}💰 or {need_more // 20}🍅/🌎 or {need_more // 40}⚡'

        output_lines.append(f'{member["name"]} {percent}%{need_more_str}')

    if comments:
        output_lines.append('')
        output_lines.extend(comments)

    return '\n'.join(output_lines)
