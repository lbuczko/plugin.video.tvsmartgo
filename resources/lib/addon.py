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
		helper.add_item('Telewizja', plugin.url_for(login))
		helper.add_item('Filmy', plugin.url_for(login))
		helper.add_item('Seriale', plugin.url_for(login))
		helper.add_item('Dla dzieci', plugin.url_for(login))
		helper.add_item('Szukaj', plugin.url_for(login))
		helper.add_item('Ustawienia', plugin.url_for(open_settings))
		helper.eod(cache=False)


@plugin.route('/login')
def login():
	helper.user_login()


@plugin.route('/logout')
def logout():
	helper.user_logout()


@plugin.route('/settings')
def open_settings():
	helper.open_settings()


class Addon(Helper):
	def __init__(self):
		super().__init__()
		self.log(sys.argv)

		plugin.run()
