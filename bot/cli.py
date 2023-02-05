import argparse
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import api
import orm

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)

parser = argparse.ArgumentParser(
    prog='Walkr manipulator',
    description='Скрипты для ручного запуска'
)

parser.add_argument('--token', type=str, help='Добавить или обновить токен в системе')
parser.add_argument('--db_create_tables',
                    action='store_true', help='Завести в бд таблицы стандарным алхимийным инструментом')

if __name__ == '__main__':
    args = parser.parse_args()
    if args.db_create_tables:
        orm.Base.metadata.create_all(orm.engine)
        print('orm creating_all success!')

    if args.token:
        result = api.make_sync_request(
            'post',
            'https://production.sw.fourdesire.com/api/v2/players/extend_token',
            args.token
        )
        result = json.loads(result)
        if not result['success']:
            raise ValueError('api answer does not contain success:true')

        with orm.make_session() as session:
            user = session.query(orm.User).get(result['authorization']['player_id'])
            if not user:
                user = orm.User(id=result['authorization']['player_id'])
                session.add(user)
            user.name = result['authorization']['name']

            tokens = session.query(orm.Token).filter(orm.Token.user == user).all()
            if not tokens:
                token = orm.Token(user=user)
                session.add(token)
            else:
                token = tokens[0]
            token.update_dt = datetime.now(tz=ZoneInfo('UTC'))
            token.value = args.token
            token.active = True
            token.expired_dt = datetime.fromtimestamp(result['authorization']['token_expired_at'])

            session.commit()
