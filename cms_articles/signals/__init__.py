from . import article, plugins, title
from django.dispatch import Signal

{article, plugins, title}

post_publish_article = Signal(providing_args=['instance', 'language'])
post_unpublish_article = Signal(providing_args=['instance', 'language'])
