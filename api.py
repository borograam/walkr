import requests
import json

DEFAULT_CLIENT_VERSION = "6.12.2.12"
DEFAULT_IOS_VERSION = "15.3.1"


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


def _get_data(
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
    url = 'https://production.sw.fourdesire.com/api/v2/labs/68334/request'
    headers = _get_headers(**{'Content-Type': 'application/json'})

    data = _get_data(auth_token)
    r = requests.post(url, json.dumps(data), headers=headers)
    # на автоматике перед этим пусть обязательно делается GET /api/v2/labs/68334 и удостоверяемся, что
    # 1) у меня не максимум
    # 2) now - last_requested_at > 6hours

    # если я смогу собрать токены окружающих...
    return r


def get_lab_info(auth_token: str):
    url = 'https://production.sw.fourdesire.com/api/v2/labs/current'
    data = _get_data(auth_token)
    headers = _get_headers()

    r = requests.get(url, data, headers=headers)
    result = r.json()
    lab_name = result['lab']['name']
    lab_score = result['lab']['score']
    members = [m for m in result['members'] if m['rsvp'] == 'member']

    output_lines = [f'{lab_name} ({lab_score})\n']
    for member in members:
        output_lines.append(f'{member["name"]} {member["planets_count"]}🌍 {member["population"]}👥 {member["score"]}⚡️')

    output = '\n'.join(output_lines)
    print(output)
    return output


def get_epic_info():
    url = 'https://production.sw.fourdesire.com/api/v2/fleets/current'
    data = {
        "auth_token": "",
        "client_version": "6.12.2.12",
        "country_code": "RU",
        "device_model": "iPhone13,2",
        "locale": "en",
        "os_version": "iOS 15.3.1",
        "platform": "ios",
        "timezone": "6",
    }
    headers = {
        'Accept': '*/*',
        'User-Agent': 'Walkr/6.11.4 (iPhone; iOS 15.3.1; Scale/3.00)',
        'Accept-Language': 'en-US;q=1, ru-RU;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
    }

    r = requests.get(url, data, headers=headers)

    """
    Meow (The Kidnapped Engineer)
    13.29% Nathalie Popova +20000💰 or 1000🍅/🌎 or 500⚡️
    """