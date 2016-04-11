#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from setuptools import setup, find_packages

from cms_articles import __version__

setup(
    name            = 'django-cms-articles',
    version         = __version__,
    description     = 'django CMS application for managing articles',
    author          = 'Jakub Dorňák',
    author_email    = 'jakub.dornak@misli.cz',
    license         = 'BSD',
    url             = 'https://github.com/misli/django-cms-articles',
    packages        = find_packages(),
    include_package_data = True,
    install_requires=[
        'django-cms>=3.2',
        'django-filer',
    ],
    classifiers     = [
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
    ],
)
