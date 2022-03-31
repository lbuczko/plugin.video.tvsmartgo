import sys
import routing
from .helper import Helper
from urllib.parse import parse_qsl

base_url = sys.argv[0]
handle = int(sys.argv[1])
params = dict(parse_qsl(sys.argv[2][1:]))
helper = Helper(base_url, handle)
plugin = routing.Plugin()


class Addon(Helper):
	def __init__(self):
		super().__init__()
		self.log(f'======== VECTRA TV SMART GO ================ ARGV : {sys.argv}')
