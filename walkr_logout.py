import requests
import argparse

def action(email: str, password: str):
    r1 = requests.post(
        'https://core.sparkful.app/api/v1/auth/signIn',
        json={'email': email, 'password': password}
    )
    token1 = r1.headers['authorization'][7:]

    r2 = requests.post(
        'https://core.sparkful.app/api/v1/appUsages',
        json={
            "appIdentifier": "walkr",
            "platform": "ios",
            "auth_token": token1,
            "fd_identifier": "QF5UC5328DX",
            "version": "7.2.2"
        },
        headers={'authorization': f'BEARER {token1}'})
    token2 = r2.headers['authorization'][7:]

    r3 = requests.get(
        'https://production.sw.fourdesire.com/api/v2/friends',
        params={
            'client_version': '7.2.2.4',
            'country_code': 'ru',
            'device_model': 'iPhone13,2',
            'limit': '100',
            'locale': 'en',
            'offset': '0',
            'order_by': 'population',
            'os_version': 'iOS 17.4.1',
            'platform': 'ios',
            'timezone': '2'
        },
        headers={'authorization': f'BEARER {token2}'}
    )
    print(r3.text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('walkr logouter')
    parser.add_argument('email', type=str)
    parser.add_argument('password', type=str)

    args = parser.parse_args()

    action(args.email, args.password)
