import xbmc
import xbmcaddon


class Helper:
    def __init__(self, base_url=None, handle=None):
        self.base_url = base_url
        self.handle = handle
        self.addon_name = xbmcaddon.Addon().getAddonInfo('id')
        self.addon_version = xbmcaddon.Addon().getAddonInfo('version')
        self.logging_prefix = f'===== [{self.addon_name} - {self.addon_version}] ====='

    def log(self, string):
        msg = f'{self.logging_prefix}: {string}'
        xbmc.log(msg=msg, level=1)
