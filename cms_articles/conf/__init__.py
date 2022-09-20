from django.conf import settings as wrapped_settings

from . import default_settings as default_settings


class LazySettings(object):
    def __dir__(self):
        return dir(wrapped_settings) + dir(default_settings)

    def __getattr__(self, name):
        try:
            value = getattr(wrapped_settings, name)
        except AttributeError:
            value = getattr(default_settings, name)
        setattr(self, name, value)
        return value


settings = LazySettings()
