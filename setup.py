#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from setuptools import find_packages, setup

setup(
    name = 'django-cms-articles',
    version = '1.2.2',
    description = 'django CMS application for managing articles',
    author = 'Jakub Dorňák',
    author_email = 'jakub.dornak@misli.cz',
    license = 'BSD',
    url = 'https://github.com/misli/django-cms-articles',
    packages = find_packages(),
    include_package_data = True,
    install_requires=[
        'django-cms>=3.5,<3.6',
        'django-filer',
        'python-dateutil',
    ],
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: Czech',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
    ],
)
