# django-cms-articles
the best django CMS application for managing articles

This application provides full featured articles management for django CMS.
It is heavily inspired by (and partially copied from) the page management in django CMS itself.

## Features

 * intuitive admin UI inspired by django CMS page UI
 * intuitive front-end editing using placeholders and toolbar menu
 * supports multiple languages (the same way as django CMS does)
 * publisher workflow from django CMS
 * flexible plugins to render article outside django CMS page

## Installation and usage

Installation and usage is quite traightforward.
 * install (using pip) django-cms-articles
 * add "cms_articles" into your settings.INSTALLED_APPS
 * check cms_articles.conf.default_settings for values you may want to override in your settings
 * add "Articles Category" apphook to any django CMS page, which should act as category for articles
 * add "Articles" plugin to placeholder of your choice to show articles belonging to that page / category

## Bugs and Feature requests

Should you encounter any bug or have some feature request,
create an issue at https://github.com/misli/django-cms-articles/issues.
