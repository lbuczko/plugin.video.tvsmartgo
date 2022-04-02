import sys
import routing
from .helper import Helper
from urllib.parse import parse_qsl

base_url = sys.argv[0]
handle = int(sys.argv[1])
params = dict(parse_qsl(sys.argv[2][1:]))
helper = Helper(base_url, handle)
plugin = routing.Plugin()


@plugin.route('/')
def root():
    if not helper.user_login():
        helper.add_item('Zaloguj', plugin.url_for(login))
        helper.add_item('Ustawienia', plugin.url_for(open_settings))
        helper.eod(cache=False)
    else:
        helper.add_item('Wyloguj', plugin.url_for(logout))
        helper.add_item('Telewizja', plugin.url_for(live))
        helper.add_item('Filmy', plugin.url_for(vod, 'VOD_WEB'))
        helper.add_item('Seriale', plugin.url_for(vod, 'SERIES_WEB'))
        helper.add_item('Dla dzieci', plugin.url_for(vod, 'KIDS_WEB'))
        helper.add_item('Szukaj', plugin.url_for(login))
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


@plugin.route('/channel_data/<channel_id>')
def channel_data(channel_id):
    get_data(product_id=channel_id, channel_type='channel')


@plugin.route('/vod/<section>')
def vod(section):
    vod_categories(section=section)


@plugin.route('/vod_items/<vod_id>/<page>')
def vod_items(vod_id, page):
    vod_movies(vod_id, page)


@plugin.route('/show_movie/<uuid>')
def show_item(uuid):
    show_movie(uuid)


@plugin.route('/vod_data/<channel_id>')
def vod_data(channel_id):
    get_data(product_id=channel_id, channel_type='channel')


@plugin.route('/settings')
def open_settings():
    helper.open_settings()


def live_tv():
    title = None
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
            avail_in = channel.get('available_in')
            channel_id = channel.get('uuid')
            channel_logo = channel.get('images').get('logo')[0].get('url')
            catch_up_active = channel.get('context').get('catch_up_active')
            for subscriber in helper.subscribers:
                if subscriber in avail_in:
                    _title = f'[B]{channel.get("title")}[/B]'
                    catchup_suffix = _title + ' [COLOR orange](catchup)[/COLOR]'
                    title = catchup_suffix if catch_up_active == 1 else _title
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
            helper.add_item(title, plugin.url_for(channel_data, channel_id), playable=True, art=art, info=info)
        helper.eod()


def vod_categories(section):
    helper.headers.update({'authorization': f'Bearer {helper.token}'})
    url = f'https://{helper.api_subject}/sections/page/{section}?platform=BROWSER&system=tvonline'
    req = helper.make_request(url, method='get', headers=helper.headers)

    for category in req:
        title = category.get('name')
        id = category.get('id')
        helper.add_item(title, plugin.url_for(vod_items, vod_id=id, page=1))
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
    data = req.get("data")
    for item in data:
        uuid = item.get("uuid")
        title = item.get("title")
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

        helper.add_item(title, plugin.url_for(show_item, uuid))
    helper.eod()


def show_movie(uuid):
    helper.headers.update({'authorization': f'Bearer {helper.get_setting("token")}'})
    url = f'https://{helper.api_subject}/products/vod/{uuid}?platform=BROWSER&system=tvonline'
    req = helper.make_request(url, method='get', headers=helper.headers)
    if not req.get('trailers'):
        helper.notification('Informacja', 'Brak zwiastuna')
    else:
        get_data(product_id=uuid, channel_type='vod', videoid=req['trailers'][0].get('videoId'))


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
            stream_url = get_playlist['sources']['DASH'][0]['src']
            stream_url = 'https:' + stream_url if stream_url.startswith('//') else stream_url
            license_url = get_playlist['drm'].get('WIDEVINE')
            license_url = license_url + '|Content-Type=|R{SSM}|'
            stream_url = helper.make_request(stream_url, method='get', allow_redirects=False, verify=False, json=False)
            stream_url = stream_url.headers['Location']

            if license_url:
                drm_protocol = 'mpd'
                drm = 'widevine'
                helper.play_video(stream_url=stream_url, drm_protocol=drm_protocol, drm=drm, license_url=license_url)


class Addon(Helper):
    def __init__(self):
        super().__init__()
        self.log(sys.argv)
        plugin.run()
