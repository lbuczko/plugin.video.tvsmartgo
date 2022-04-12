import ast
import json
import sys
import routing
import xbmcvfs

from .helper import Helper
from datetime import datetime, timedelta

base_url = sys.argv[0]
handle = int(sys.argv[1])
helper = Helper(base_url, handle)
plugin = routing.Plugin()


@plugin.route('/')
def root():
    if not helper.user_logged_in():
        helper.add_item('Zaloguj', plugin.url_for(login))
        helper.add_item('Ustawienia', plugin.url_for(open_settings))
        helper.eod(cache=False)
    else:
        helper.add_item('Wyloguj', plugin.url_for(logout))
        helper.add_item('Telewizja', plugin.url_for(live))
        helper.add_item('Ulubione', plugin.url_for(list_favorites))
        helper.add_item('Filmy', plugin.url_for(vod, 'VOD_WEB'))
        helper.add_item('Seriale', plugin.url_for(vod, 'SERIES_WEB'))
        helper.add_item('Dla dzieci', plugin.url_for(vod, 'KIDS_WEB'))
        helper.add_item('Szukaj', plugin.url_for(search))
        helper.add_item('Ustawienia', plugin.url_for(open_settings))
        helper.eod(cache=False)


@plugin.route('/login')
def login():
    helper.user_login()


@plugin.route('/logout')
def logout():
    helper.user_logout()


@plugin.route('/live')
def live():
    live_tv()


@plugin.route('/live/list_favorites')
def list_favorites():
    favorites()


@plugin.route('/live/add_favorite')
def add_favorite():
    helper.add_favorite(channel_name=plugin.args['channel_name'][0], channel_id=plugin.args['channel_id'][0],
                        channel_logo=plugin.args['channel_logo'][0])


@plugin.route('/live/read_favorites/<channel_id>')
def read_favorites(channel_id):
    get_data(product_id=channel_id, channel_type='channel')


@plugin.route('/live/remove_favorites')
def remove_favorites():
    helper.remove_favorites()


@plugin.route('/channel_data/<channel_id>')
def channel_data(channel_id):
    get_data(product_id=channel_id, channel_type='channel')


@plugin.route('/catchup_week')
def catchup_week():
    get_catchup(channel_uuid=plugin.args['uuid'][0], channel_name=plugin.args['title'][0],
                channel_logo=plugin.args['url'][0])


@plugin.route('/catchup_programs/<channel_uuid>/<day>')
def catchup_programs(channel_uuid, day):
    list_catchup_programs(channel_uuid, day)


@plugin.route('/play_program/<channel_id>/<video_id>')
def play_program(channel_id, video_id):
    get_data(product_id=channel_id, channel_type='channel', videoid=video_id, catchup=True)


@plugin.route('/vod/<section>')
def vod(section):
    vod_categories(section=section)


@plugin.route('/vod_items/<vod_id>/<page>')
def vod_items(vod_id, page):
    vod_movies(vod_id, page)


@plugin.route('/series_items/<vod_id>/<page>')
def series_items(vod_id, page):
    tv_shows(vod_id, page)


@plugin.route('/show_movie/<uuid>')
def show_item(uuid):
    show_movie(uuid)


@plugin.route('/show_seasons/<uuid>')
def show_seasons(uuid):
    show_season_items(uuid)


@plugin.route('/show_episodes/<uuid>')
def show_episodes(uuid):
    episode_items(uuid)


@plugin.route('/play_trailer/<uuid>/<ch_type>/<video_id>')
def play_trailer(uuid, ch_type, video_id):
    get_data(uuid, ch_type, video_id)


@plugin.route('/search')
def search():
    start_search()


@plugin.route('/search_result')
def search_result():
    get_search_results()


@plugin.route('/settings')
def open_settings():
    helper.open_settings()


@plugin.route('/build_m3u')
def build_m3u():
    helper.export_m3u_playlist()


def live_tv():
    channels_list = []
    helper.headers.update({'authorization': f'Bearer {helper.get_setting("token")}'})
    query = {
        'offset': 0,
        'limit': 300,
        'platform': 'BROWSER',
        'system': 'tvonline'
    }
    req = helper.make_request(f'https://{helper.api_subject}/products/channel', method='get',
                              headers=helper.headers, params=query)
    if req.get('data'):
        for channel in req.get('data'):
            title = channel.get('title')
            avail_in = channel.get('available_in')
            channel_id = channel.get('uuid')
            channel_logo = channel.get('images').get('logo')[0].get('url')
            catch_up_active = channel.get('context').get('catch_up_active')
            for subscriber in helper.subscribers:
                if subscriber in avail_in:
                    _title = f'[B]{channel.get("title")}[/B]'
                    catchup_suffix = _title + ' [COLOR orange](catchup)[/COLOR]'
                    title = catchup_suffix if catch_up_active == 1 else _title
                    channels_list.append({
                        'title': channel.get('title'),
                        'id': channel_id,
                        'logo': channel_logo
                    })
                    break
                else:
                    _title = channel.get('title')
                    title_prefix = '[COLOR red][BRAK][/COLOR] ' + _title
                    catchup_suffix = title_prefix + ' (catchup)'
                    title = catchup_suffix if catch_up_active == 1 else title_prefix
            art = {
                'icon': channel_logo,
                'fanart': channel_logo
            }
            info = {
                'title': title
            }
            helper.add_item(title,
                            plugin.url_for(catchup_week, uuid=channel_id, title=channel.get('title'), url=channel_logo),
                            art=art, info=info, livetv=True)
        helper.eod()
    return channels_list


def favorites():
    file = xbmcvfs.translatePath(f'special://home/userdata/addon_data/{helper.addon_name}/favorites.txt')

    try:
        with xbmcvfs.File(file) as f:
            buffer = f.read()

        buffer = tuple(set(ast.literal_eval(buffer)))

        for item in buffer:
            channel = item[0]
            id = item[1]
            info = {
                'title': channel
            }
            art = {
                'icon': item[2],
                'fanart': item[2]
            }
            helper.add_item(channel, plugin.url_for(read_favorites, id), playable=True, info=info, art=art)
        helper.add_item('Wyczyść ulubione', plugin.url_for(remove_favorites))
        helper.eod()
    except SyntaxError:
        helper.add_item('Pusto', plugin.url_for(root))
        helper.eod()


def vod_categories(section):
    helper.headers.update({'authorization': f'Bearer {helper.token}'})
    url = f'https://{helper.api_subject}/sections/page/{section}?platform=BROWSER&system=tvonline'
    req = helper.make_request(url, method='get', headers=helper.headers)

    for category in req:
        title = category.get('name')
        category_id = category.get('id')
        if section == 'VOD_WEB':
            helper.add_item(title, plugin.url_for(vod_items, vod_id=category_id, page=1))
        elif section == 'SERIES_WEB':
            helper.add_item(title, plugin.url_for(series_items, vod_id=category_id, page=1))
        elif section == 'KIDS_WEB':
            helper.add_item(title, plugin.url_for(vod_items, vod_id=category_id, page=1))
    helper.eod()


def vod_movies(vod_id, page):
    helper.headers.update({'authorization': f'Bearer {helper.get_setting("token")}'})
    url = f'https://{helper.api_subject}/sections/{vod_id}/content?offset={page}&limit=24&platform=BROWSER&system=tvonline'

    if 'subtype' and 'genre' in vod_id:
        index = vod_id.replace('genre=', '').replace('subtype=', '')
        subtype, genre = index.split('&')
        url = f'https://{helper.api_subject}/products/{vod_id}?subtype={subtype}&genre={genre}&limit=24&offset={page}&platform=BROWSER&system=tvonline'
    elif 'query' in vod_id:
        query = vod_id.split('|')[-1]
        url = f'https://{helper.api_subject}/products/search?q={query}&limit=100&offset={page}&platform=BROWSER&system=tvonline'

    req = helper.make_request(url, method='get', headers=helper.headers)
    data = req.get('data')
    for item in data:
        uuid = item.get('uuid')
        title = item.get('title')
        short_desc = item.get('short_desc')
        if item.get('prices'):
            price = item.get('prices').get('rent').get('price')
            period = item.get('prices').get('rent').get('period')
            if price:
                title_prefix = f'[B][COLOR red][{price / 100}0zł][/COLOR][/B] '
                title_format = title_prefix + f'[B]{title}[/B]'
                period = f' [B][COLOR orange]({period}H)[/COLOR][/B]'
                title = title_format + period
            else:
                title = f'[B] {title} [/B]'

        if item['images'].get('poster'):
            poster = item['images']['poster'][0]['url']
            art = {
                'icon': poster,
                'fanart': poster
            }
        else:
            art = {
                'icon': helper.addon.getAddonInfo('icon')
            }
        info = {
            'title': item.get('title'),
            'plot': short_desc
        }
        helper.add_item(title, plugin.url_for(show_item, uuid), info=info, art=art, content='movies')
    helper.add_item('Następna strona', plugin.url_for(vod_items, vod_id=vod_id, page=int(page) + 1))
    helper.eod()


def tv_shows(vod_id, page):
    helper.headers.update({'authorization': f'Bearer {helper.get_setting("token")}'})
    url = f'https://{helper.api_subject}/sections/{vod_id}/content?offset={page}&limit=24&platform=BROWSER&system=tvonline'

    if 'subtype' and 'genre' in vod_id:
        index = vod_id.replace('genre=', '').replace('subtype=', '')
        subtype, genre = index.split('&')
        url = f'https://{helper.api_subject}/products/{vod_id}?subtype={subtype}&genre={genre}&limit=24&offset={page}&platform=BROWSER&system=tvonline'
    elif 'query' in vod_id:
        query = vod_id.split('|')[-1]
        url = f'https://{helper.api_subject}/products/search?q={query}&limit=100&offset={page}&platform=BROWSER&system=tvonline'

    req = helper.make_request(url, method='get', headers=helper.headers)
    data = req.get('data')
    for item in data:
        uuid = item.get('uuid')
        title = item.get('title')
        summary_short = item.get('summary_short')
        if item.get('prices'):
            price = item.get('prices').get('rent').get('price')
            period = item.get('prices').get('rent').get('period')
            if price:
                title_prefix = f'[B][COLOR red][{price / 100}0zł][/COLOR][/B] '
                title_format = title_prefix + f'[B]{title}[/B]'
                period = f' [B][COLOR orange]({period}H)[/COLOR][/B]'
                title = title_format + period
            else:
                title = f'[B] {title} [/B]'
        info = {
            'title': title,
            'plot': summary_short
        }
        if item['images'].get('poster'):
            poster = item['images']['poster'][0]['url']
            art = {
                'icon': poster,
                'fanart': poster
            }
        else:
            art = {
                'icon': helper.addon.getAddonInfo('icon')
            }
        helper.add_item(title, plugin.url_for(show_seasons, uuid), info=info, art=art, content='tvshows')
    helper.add_item('Następna strona', plugin.url_for(series_items, vod_id=vod_id, page=int(page) + 1))
    helper.eod()


def show_season_items(uuid):
    helper.headers.update({'authorization': f'Bearer {helper.get_setting("token")}'})
    req_url = f'https://api.tvsmart.pl/products/series/{uuid}?platform=BROWSER&system=tvonline'
    req = helper.make_request(req_url, method='get', headers=helper.headers)

    for season in req['seasons']:
        uuid = season.get('uuid')
        title = season.get('title')
        if title.endswith(','):
            title = title[:-1] + ''
        number = str(season.get('number'))
        title = f'[B]{title}[/B] - sezon [{number}]'
        poster = req['images']['poster'][0]['url']
        summary_long = season.get('summary_long')
        info = {
            'title': title,
            'plot': summary_long
        }
        art = {
            'icon': poster,
            'fanart': poster
        }
        helper.add_item(title, plugin.url_for(show_episodes, uuid), info=info, art=art, content='seasons')
    helper.eod()


def episode_items(uuid):
    helper.headers.update({'authorization': f'Bearer {helper.get_setting("token")}'})
    req_url = f'https://api.tvsmart.pl/products/season/{uuid}?platform=BROWSER&system=tvonline'
    req = helper.make_request(req_url, method='get', headers=helper.headers)

    for episode in req['episodes']:
        uuid = episode.get('uuid')
        title = episode.get('title')
        summary_short = episode.get('summary_short')
        info = {
            'title': title,
            'plot': summary_short
        }
        helper.add_item(title, plugin.url_for(show_episodes, uuid), info=info, content='tvshows')
    helper.eod()


def show_movie(uuid):
    helper.headers.update({'authorization': f'Bearer {helper.get_setting("token")}'})
    url = f'https://{helper.api_subject}/products/vod/{uuid}?platform=BROWSER&system=tvonline'
    req = helper.make_request(url, method='get', headers=helper.headers)
    if not req.get('trailers'):
        helper.notification('Informacja', 'Brak zwiastuna')
    else:
        poster = req.get("images").get("poster")[0].get("url")
        parent_uuid = req.get("parent_uuid")
        if parent_uuid:
            poster = f'https://api.tvonline.vectra.pl/assets/{parent_uuid}/poster'
        metadata = req.get("metadata")
        summary_long = metadata.get("summary_long")
        title = metadata.get("title")
        art = {
            'icon': poster,
            'fanart': poster
        }
        info = {
            'title': title,
            'plot': summary_long
        }
        helper.add_item(title + ' - [COLOR lightgreen][B]trailer[/B][/COLOR]',
                        plugin.url_for(play_trailer, uuid, 'vod', req['trailers'][0].get('videoId')), playable=True,
                        info=info, art=art)
        helper.eod()


def get_catchup(channel_uuid, channel_name, channel_logo):
    info = {
        'title': channel_name
    }
    art = {
        'icon': channel_logo,
        'fanart': channel_logo
    }
    helper.add_item(f'{channel_name} - [B][COLOR lightgreen]LIVE[/COLOR][/B]',
                    plugin.url_for(channel_data, channel_uuid), playable=True, info=info, art=art)
    helper.add_item('Dodaj kanał do ulubionych',
                    plugin.url_for(add_favorite, channel_name=channel_name, channel_id=channel_uuid,
                                   channel_logo=channel_logo), info=info, art=art)
    for index, day in enumerate(last_week()):
        helper.add_item(day['end'], plugin.url_for(catchup_programs, channel_uuid=channel_uuid, day=index))
    helper.eod()


def list_catchup_programs(channel_uuid, day):
    art = None
    last_days = last_week()
    if int(day) != 0:
        start_date = last_days[int(day) - 1]['start_parsed']
        end_date = last_days[int(day) - 1]['end_parsed']
    else:
        end_date = (datetime.today() + timedelta(hours=4)).strftime('%Y%m%d%H') + '0000'
        start_date = datetime.today().strftime('%Y%m%d') + '000000'

    helper.headers.update({'authorization': f'Bearer {helper.token}'})
    req_params = {
        'startDate': start_date,
        'endDate': end_date,
        'platform': 'BROWSER',
        'system': 'tvonline'
    }
    response = helper.make_request(f'https://{helper.api_subject}/epg', method='get', headers=helper.headers,
                                   params=req_params)

    for data in response:
        for program in data.get('programs'):
            if program.get('channel_uuid') == channel_uuid:
                since = string_to_date(program.get('since'), "%m-%d %H:%M")
                till = string_to_date(program.get('till'), "%H:%M")
                title_prefix = f'[B][COLOR orange][{since} - {till}][/COLOR][/B] '
                title = title_prefix + f'[B]{program.get("title")}[/B]'
                cover = program.get('images').get('cover')
                video_id = program.get('uuid')
                info = {
                    'title': program.get('title'),
                    'plot': program.get('description_short'),
                }
                if cover:
                    art = {
                        'icon': cover[0].get('url'),
                        'fanart': cover[0].get('url')
                    }
                helper.add_item(title,
                                plugin.url_for(play_program, channel_id=program.get('channel_uuid'), video_id=video_id),
                                playable=True, info=info, art=art)
    helper.eod()


def last_week():
    days_list = []
    days_range = range(7)
    archive_day = []
    date_now = datetime.today()

    for day in days_range:
        end = (date_now - timedelta(days=day)).strftime('%Y%m%d') + '000000'
        start = (date_now - timedelta(days=day + 1)).strftime('%Y%m%d') + '000000'
        archive_day.append({
            'start': start,
            'end': end
        })

    start_days = [(date_now - timedelta(days=idx, hours=-5)).strftime('%Y-%m-%d') for idx in days_range]
    days = [(date_now - timedelta(days=idx)).strftime('%Y-%m-%d') for idx in days_range]
    for index in days_range:
        days_list.append({
            'day': index,
            'end': start_days[index],
            'end_parsed': archive_day[index]['end'],
            'start': days[index],
            'start_parsed': archive_day[index]['start']
        })
    return days_list


def string_to_date(string, string_format):
    s_tuple = tuple([int(x) for x in string[:10].split('-')]) + tuple([int(x) for x in string[11:].split(':')])
    s_to_datetime = datetime(*s_tuple).strftime(string_format)
    return s_to_datetime


def get_data(product_id, channel_type, videoid=None, catchup=None):
    helper.token = helper.get_setting('token')
    headers = {
        'Host': 'api.tvonline.vectra.pl',
        'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
        'accept': 'application/json',
        'accept-language': 'pl,en-US;q=0.7,en;q=0.3',
        'access-control-allow-origin': '*',
        'api-deviceuid': helper.uuid,
        'api-device': 'Firefox; 90; Windows; 7; Windows; 7;',
        'authorization': 'Bearer ' + helper.token,
        'origin': 'https://tvonline.vectra.pl',
        'referer': 'https://tvonline.vectra.pl/',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'te': 'trailers',
    }
    product_params = {
        'type': channel_type,
        'platform': 'BROWSER',
        'system': 'tvonline'
    }

    if channel_type == 'vod':
        product_params.update({'videoId': videoid})
    if catchup:
        product_params.update({'programId': videoid})

    url = 'https://api.tvonline.vectra.pl/player/product/%s/configuration' % product_id
    get_product = helper.make_request(url, method='get', headers=headers, params=product_params)

    video_session_id = get_product.get("videoSession")
    if 'errorCode' in get_product:
        msg = get_product.get('errorCode', None)
        helper.notification('Błąd', f'[B]{msg}[/B]')
    else:
        if video_session_id:
            video_session_id = video_session_id.get("videoSessionId")

        payload = {
            'type': 'channel',
            'videoSessionId': video_session_id
        }

        req_url = f'https://api.tvsmart.pl/player/product/{product_id}/playlist'
        get_playlist = helper.make_request(req_url, method='get', params=payload, headers=headers)
        if get_playlist:
            license_url = get_playlist['drm'].get('WIDEVINE')
            stream_url = get_playlist['sources']['DASH'][0]['src']
            stream_url = 'https:' + stream_url if stream_url.startswith('//') else stream_url
            stream_url = helper.make_request(stream_url, method='get', allow_redirects=True, verify=False, json=False)
            stream_url = stream_url.url

            if license_url:
                drm_protocol = 'mpd'
                drm = 'com.widevine.alpha'

                helper.play_video(stream_url=stream_url, drm_protocol=drm_protocol, drm=drm, license_url=license_url)


def start_search():
    helper.add_item('Nowe wyszukiwanie', plugin.url_for(search_result))
    helper.eod()


def get_search_results():
    query = helper.dialog_search()
    helper.headers.update({'authorization': f'Bearer {helper.get_setting("token")}'})
    req_url = f'https://api.tvsmart.pl/products/search'
    payload = {
        'q': query,
        'limit': 100,
        'offset': 0,
        'platform': 'BROWSER',
        'system': 'tvonline'
    }
    req = helper.make_request(req_url, method='get', params=payload, headers=helper.headers)
    for data in req.get('data'):
        data_type = data.get('type')
        uuid = data.get('uuid')
        _title = data.get('title')
        title = f'[B][COLOR orange][{data_type}][/COLOR][/B] {_title}'
        if data_type == 'channel':
            helper.add_item(title, plugin.url_for(channel_data, uuid), playable=True)
        elif data_type == 'vod':
            helper.add_item(title, plugin.url_for(show_item, uuid))
    helper.eod()


class Addon(Helper):
    def __init__(self):
        super().__init__()
        self.log(sys.argv)
        plugin.run()
