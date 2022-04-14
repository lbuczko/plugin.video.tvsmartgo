import json
import uuid
from calendar import calendar
from datetime import datetime, timedelta

import iso8601
import requests
from urllib.parse import quote, unquote

import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import xbmcplugin


class Helper:
    def __init__(self, base_url=None, handle=None):
        self.base_url = base_url
        self.handle = handle
        self.addon = xbmcaddon.Addon()
        self.addon_name = xbmcaddon.Addon().getAddonInfo('id')
        self.addon_version = xbmcaddon.Addon().getAddonInfo('version')
        self.logging_prefix = f'===== [{self.addon_name} - {self.addon_version}] ====='
        # User data
        self.user_name = self.get_setting('username')
        self.user_password = self.get_setting('password')
        try:
            self.token = self.get_setting('token')
            self.uuid = self.get_setting('uuid')
            self.subscribers = self.get_setting('subscribers')
            self.subscribers = json.loads(unquote(self.subscribers)) if self.subscribers else ''
        except TypeError:
            self.token = self.set_setting('token', '')
            self.subscribers = self.set_setting('subscribers', '')
            self.uuid = self.create_device_id()
        # API
        self.api_subject = 'api.tvonline.vectra.pl'
        self.headers = {
            'Host': self.api_subject,
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'accept': 'application/json',
            'accept-language': 'pl,en-US;q=0.7,en;q=0.3',
            'content-type': 'application/json',
            'access-control-allow-origin': '*',
            'api-deviceuid': self.uuid,
            'api-device': 'Firefox; 90; Windows; 7; Windows; 7;',
            'origin': 'https://tvonline.vectra.pl',
            'referer': 'https://tvonline.vectra.pl/',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'te': 'trailers',
        }

    def log(self, string):
        msg = f'{self.logging_prefix}: {string}'
        xbmc.log(msg=msg, level=1)

    def get_setting(self, string):
        return xbmcaddon.Addon(self.addon_name).getSettingString(string)

    def set_setting(self, setting, string):
        return xbmcaddon.Addon(self.addon_name).setSettingString(id=setting, value=string)

    def open_settings(self):
        xbmcaddon.Addon(self.addon_name).openSettings()

    def add_item(self, title, url, playable=False, info=None, art=None, content=None, folder=True, livetv=False):
        list_item = xbmcgui.ListItem(label=title)
        if playable:
            list_item.setProperty('IsPlayable', 'true')
            folder = False
        if art:
            list_item.setArt(art)
        else:
            art = {
                'icon': self.addon.getAddonInfo('icon'),
                'fanart': self.addon.getAddonInfo('fanart')
            }
            list_item.setArt(art)
        if info:
            list_item.setInfo('Video', info)
        if content:
            xbmcplugin.setContent(self.handle, content)

        xbmcplugin.addDirectoryItem(self.handle, url, list_item, isFolder=folder)

        if livetv:
            xbmcplugin.addSortMethod(handle=self.handle, sortMethod=xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)

    def eod(self, cache=True):
        xbmcplugin.endOfDirectory(self.handle, cacheToDisc=cache)

    def coloring(self, text, color=None, bold=True):
        if color == 'red':
            if bold:
                return f'[B][COLOR red]{text}[/COLOR][/B]'
            else:
                return f'[COLOR red]{text}[/COLOR]'
        elif color == 'orange':
            if bold:
                return f'[B][COLOR orange]{text}[/COLOR][/B]'
            else:
                return f'[COLOR orange]{text}[/COLOR]'
        elif color == 'lightgreen':
            if bold:
                return f'[B][COLOR lightgreen]{text}[/COLOR][/B]'
            else:
                return f'[COLOR lightgreen]{text}[/COLOR]'
        elif color == 'white':
            if bold:
                return f'[B][COLOR white]{text}[/COLOR][/B]'
            else:
                return f'[COLOR white]{text}[/COLOR]'
        else:
            if bold:
                return f'[B]{text}[/B]'
            else:
                return text

    def notification(self, heading, message):
        xbmcgui.Dialog().notification(heading, message, time=7000)

    def dialog_choice(self, heading, message, agree, disagree):
        return xbmcgui.Dialog().yesno(heading, message, yeslabel=agree, nolabel=disagree)

    def dialog_search(self):
        return xbmcgui.Dialog().input('Wyszukiwanie')

    def error_message(self, msg):
        if msg == 'SUBSCRIBER_PARALLEL_STREAMS_LIMIT_EXCEEDED':
            return self.notification('Błąd', f'[B]Przekroczono ilość połączeń. Spróbuj ponownie za 10 minut.[/B]')
        elif msg == 'MUST_BE_IN_LOCAL':
            return self.notification('Błąd', f'[B]Niedostępne poza siecią Vectra.[/B]')
        elif msg == 'RESOURCE_NOT_IN_SUBSCRIBER_PRODUCTS':
            return self.notification('Błąd', f'[B]Nie subskrybujesz tego kanału.[/B]')
        else:
            return self.notification('Błąd', f'[B]{msg}[/B]')

    def add_favorite(self, channel_name, channel_id, channel_logo):
        file = xbmcvfs.translatePath(f'special://home/userdata/addon_data/{self.addon_name}/favorites.txt')
        append = str((channel_name, channel_id, channel_logo)) + ','

        with xbmcvfs.File(file) as f:
            buffer = f.read()

        with xbmcvfs.File(file, 'w') as f:
            f.write(buffer + append)

    def remove_favorites(self):
        file = xbmcvfs.translatePath(f'special://home/userdata/addon_data/{self.addon_name}/favorites.txt')
        xbmcvfs.delete(file)
        self.notification('Informacja', 'Ulubione usunięte.')
        return True

    def make_request(self, url, method, params=None, payload=None, headers=None, allow_redirects=None, verify=None,
                     json=True):
        self.log(f'Request URL: {url}')
        self.log(f'Method: {method}')
        if params:
            self.log(f'Params: {params}')
        if payload:
            self.log(f'Payload: {payload}')
        if headers:
            self.log(f'Headers: {headers}')

        if method == 'get':
            req = requests.get(url, params=params, headers=headers, allow_redirects=allow_redirects, verify=verify)
        elif method == 'put':
            req = requests.put(url, params=params, data=payload, headers=headers, verify=verify)
        else:  # post
            req = requests.post(url, params=params, json=payload, headers=headers)
        self.log(f'Response code: {req.status_code}')
        # self.log(f'Response: {req.content}')

        if json:
            return req.json()
        else:
            return req

    def create_device_id(self):
        dev_id = uuid.uuid1()
        return self.set_setting('uuid', str(dev_id))

    def user_logged_in(self):
        req_url = f'https://api.tvsmart.pl/subscriber/products/uuids?platform=BROWSER&system=tvonline'
        payload = {
            'platform': 'BROWSER',
            'system': 'tvonline'
        }
        self.headers.update({'authorization': f'Bearer {self.get_setting("token")}'})
        req = self.make_request(req_url, method='get', payload=payload, headers=self.headers)
        if req.get('data'):
            return True
        else:
            self.user_login()

    def user_login(self):
        req_url = f'https://{self.api_subject}/subscriber/login?platform=BROWSER'
        payload = {"os": "Windows", "osVersion": "7", "maker": "unknown", "agent": "Firefox", "login": self.user_name,
                   "password": self.user_password, "uid": self.uuid}

        if self.user_name and self.user_password:
            if self.get_setting('uuid'):
                req = self.make_request(req_url, method='post', payload=payload, headers=self.headers)
                if req.get('token'):
                    self.set_setting('token', str(req.get('token')))
                    if req['status'].get('deviceName'):
                        self.token = self.get_setting('token')
                        self.headers.update({'authorization': 'Bearer ' + self.token})
                        url = f'https://{self.api_subject}/subscriber/products/uuids?platform=BROWSER&system=tvonline'
                        req = self.make_request(url, method='get', headers=self.headers)
                        self.subscribers = req.get('data')
                        self.subscribers = quote(json.dumps(self.subscribers)) if self.subscribers else ''
                        self.subscribers = self.set_setting('subscribers', self.subscribers)
                        return True
                    else:
                        user_choice = self.dialog_choice('UWAGA',
                                                         'Maksymalna liczba urządzeń przypisanych do konta została wykorzystana. Proszę usunąć jedno z urządzeń, aby zastąpić je obecnie używanym. Pamiętaj, że liczba zmian urządzeń w danym miesiącu wynosi 4.',
                                                         agree='TAK', disagree='NIE')
                        if user_choice:
                            self.swap_devices()
                    return False

    def swap_devices(self):
        returned_data = []
        req_url = f'https://{self.api_subject}/subscriber/devices/active'
        self.token = self.get_setting('token')
        self.uuid = self.get_setting('uuid')
        params = {
            'order[0][column]': 9,
            'order[0][dir]': 'desc',
            'platform': 'BROWSER',
            'system': 'tvonline'
        }
        self.headers.update({'authorization': 'Bearer ' + self.token, 'api-deviceuid': self.uuid})

        req = self.make_request(req_url, method='get', params=params, headers=self.headers)
        for data in req.get("data"):
            device_id = data.get("device_id")
            device_name = data.get("device_name")
            last_login = data.get("last_login_date")
            data = '%s | %s' % (device_name, last_login)
            returned_data.append({'devid': device_id, 'devname': data})
        label = [x.get('devname') for x in returned_data]

        dialog = xbmcgui.Dialog()
        user_input = dialog.select('Które urządzenie chcesz zastąpić?', label)

        keyid = returned_data[user_input].get('devid') if user_input > -1 else ''
        if keyid:
            user_input = dialog.input('Podaj nazwę urządzenia:', type=xbmcgui.INPUT_ALPHANUM)
            user_input = user_input if user_input else 'Vectra User Kodi'

            url = f'https://{self.api_subject}/subscriber/device/toggle?platform=BROWSER&system=tvonline'
            data = {"uidOfDeviceToDelete": keyid, "nameOfNewDevice": user_input}
            req = self.make_request(url, method='put', params=data, headers=self.headers, verify=False)
            if 'errorCode' in req:
                if req.get('errorCode').lower() == 'subscriber_devices_changing_limit_exceeded':
                    self.set_setting('uuid', str(keyid))
                    self.user_login()
                    return True
            self.set_setting('token', str(req.get("token")))
            self.headers.update({'authorization': 'Bearer ' + self.get_setting('token')})

            req = self.make_request(
                url=f'https://{self.api_subject}/subscriber/products/uuids?platform=BROWSER&system=tvonline',
                method='get', headers=self.headers)
            self.subscribers = req.get('data')
            self.subscribers = quote(json.dumps(self.subscribers)) if self.subscribers else ''
            self.set_setting('subscribers', self.subscribers)
            return True
        return False

    def user_logout(self):
        req_url = f'https://{self.api_subject}/subscriber/logout?platform=BROWSER&system=tvonline'
        self.headers.update({'authorization': 'Bearer ' + self.token, 'api-deviceuid': self.uuid})
        req = self.make_request(req_url, method='post', headers=self.headers)
        if req.get('ok'):
            self.notification('Autoryzacja', 'Wylogowano')
            self.set_setting('password', '')

    def play_video(self, stream_url, drm_protocol, drm, license_url):
        from inputstreamhelper import Helper  # pylint: disable=import-outside-toplevel

        play_item = xbmcgui.ListItem(path=stream_url)
        if license_url:
            is_helper = Helper(drm_protocol, drm=drm)
            if is_helper.check_inputstream():
                play_item.setProperty('inputstream', is_helper.inputstream_addon)
                play_item.setMimeType('application/xml+dash')
                play_item.setProperty('inputstream.adaptive.max_bandwidth', '99999999')
                play_item.setProperty('inputstream.adaptive.manifest_type', drm_protocol)
                play_item.setProperty('inputstream.adaptive.license_type', drm)
                play_item.setProperty('inputstream.adaptive.license_key', license_url + '||R{SSM}|')
                play_item.setContentLookup(False)
                xbmcplugin.setResolvedUrl(self.handle, True, listitem=play_item)

    def return_channels(self):
        from resources.lib.addon import live
        return live()

    def export_m3u_playlist(self):
        file = None
        m3u_path = self.get_setting('vectra_m3u_path')
        file_name = self.get_setting('vectra_file_name')

        if not file_name or not m3u_path:
            self.notification('Vectra Smart TV GO', 'Ustaw nazwę pliku i ścieżkę')
            return

        self.notification('Vectra Smart TV GO', 'Generuje listę')
        data = '#EXTM3U\n'

        for item in self.return_channels():
            data += (
                f'#EXTINF:0 tvg-id="{item["id"]}" tvg-logo="{item["logo"]}" group-title="Vectra TV",{item["title"]}\n'
                f'plugin://plugin.video.tvsmartgo/channel_data/{item["id"]}\n')

        try:
            file = xbmcvfs.File(m3u_path + file_name, 'w')
            file.write(data)
        finally:
            file.close()
        self.notification('Vectra Smart TV GO', 'Lista m3u wygenerowana')

    def current_day(self):
        current_day = []
        date_now = datetime.today()

        start = (date_now - timedelta(days=0)).strftime('%Y%m%d') + '000000'
        end = (date_now - timedelta(days=-1)).strftime('%Y%m%d') + '000000'
        current_day.append({
            'start': start,
            'end': end
        })
        return current_day

    def last_week(self):
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

    def string_to_date(self, string, string_format):
        s_tuple = tuple([int(x) for x in string[:10].split('-')]) + tuple([int(x) for x in string[11:].split(':')])
        s_to_datetime = datetime(*s_tuple).strftime(string_format)
        return s_to_datetime

    def parse_datetime(self, iso8601_string, localize=False):
        """Parse ISO8601 string to datetime object."""
        datetime_obj = iso8601.parse_date(iso8601_string)
        if localize:
            return self.utc_to_local(datetime_obj)
        else:
            return datetime_obj

    @staticmethod
    def utc_to_local(utc_dt):
        # get integer timestamp to avoid precision lost
        timestamp = calendar.timegm(utc_dt.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        assert utc_dt.resolution >= timedelta(microseconds=1)
        return local_dt.replace(microsecond=utc_dt.microsecond)
