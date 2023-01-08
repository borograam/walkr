import datetime
import logging
from zoneinfo import ZoneInfo

import aiohttp

import api
import meta
import orm

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def get_epic_info(auth_token: str, session: aiohttp.ClientSession):
    # todo: логически поделить это на отдельные controller и view
    # todo: коротко о следующих этапах

    try:
        fleet, event = await api.get_fleet(auth_token, session)
    except api.NotInEpic:
        return 'Сейчас не в эпопее'

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

    rest_members_count = len(fleet.members)
    sum_contribution_now = fleet.contribution_now

    def percent(n1: int, n2: int, format_str: str, default: str | None = None) -> str | None:
        if n2:
            return format_str.format(round(n1 / n2 * 100, 2))
        return default

    specify_voting = f' - {fleet.voting}' if fleet.voting else ''
    fleet_percent = percent(sum_contribution_now, max_contribution, ' [{}%]', default='')
    output_lines = [f'{fleet.name} ({fleet.epic_name}{specify_voting}){fleet_percent}']

    # event = Event.from_api_answer(result)
    cur_event_donation = ', '.join(
        f'{value}/{max_value}'
        for value, max_value in zip(event.current_values, event.max_values)
        if max_value
    )
    output_lines.append(f'{event.type} ({cur_event_donation}) -> {event.current_energy}/{event.max_energy}⚡\n')

    max_contribution_copy = max_contribution
    for member in fleet.members:
        contribution = member['contribution']
        now_percent_str = percent(contribution, sum_contribution_now, '{:.2f}%', '0%')
        end_percent_str = percent(contribution, max_contribution_copy, ' [{}%]', default='')
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


def _get_orm_request_progresses(
        session: orm.Session, api_requests: list[api.LabRequestWrapper]
) -> list[orm.LabRequestProgress]:
    ret = []
    for req in api_requests:
        user = orm.get_or_create(session, orm.User, {orm.User.id: req.user_id})
        user.name = req.user_name

        lab_planet = orm.get_or_create(
            session,
            orm.LabPlanet,
            {
                orm.LabPlanet.user: user,
                orm.LabPlanet.planet_name: req.planet_name,
                orm.LabPlanet.planet_requirements: req.requirements,
            }
        )

        lab_request = orm.get_or_create(
            session,
            orm.LabRequest,
            {
                orm.LabRequest.lab_planet: lab_planet,
                orm.LabRequest.requested_dt: req.last_requested_at,
            }
        )

        lab_request_progress = orm.get_or_create(
            session,
            orm.LabRequestProgress,
            {
                orm.LabRequestProgress.request: lab_request,
                orm.LabRequestProgress.total_donation: req.total_donation,
                orm.LabRequestProgress.current_donation: req.current_donation,
                orm.LabRequestProgress.donated_counter: req.donated_counter,
            }
        )
        ret.append(lab_request_progress)
        session.flush()

    return ret


async def get_current_lab_planets(
        http_session: aiohttp.ClientSession,
        db_session: orm.Session
) -> tuple[list[orm.LabRequestProgress], orm.Query]:
    auth_token: str = db_session.query(orm.Token).filter(orm.Token.active).first().value
    api_lab_requests = await api.get_lab_planets(auth_token, http_session)
    req_progresses = _get_orm_request_progresses(db_session, api_lab_requests)
    has_token_no_request_query = db_session.query(orm.User).join(orm.Token).filter(
        orm.User.id.notin_([r.request.lab_planet.user_id for r in req_progresses]))
    return req_progresses, has_token_no_request_query


async def make_lab_requests(
        http_session: aiohttp.ClientSession,
        db_session: orm.Session
) -> None:
    for token in db_session.query(orm.Token).filter(orm.Token.active):
        req = await api.get_user_request(token.value, http_session)
        if (
                req.last_requested_at.replace(tzinfo=ZoneInfo('UTC'))
                + datetime.timedelta(hours=6) < datetime.datetime.now().astimezone(ZoneInfo('UTC'))
                and req.total_donation != req.requirements
        ):
            await api.make_lab_request(token.value, http_session)
