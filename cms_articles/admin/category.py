# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, generators, nested_scopes, print_function, unicode_literals, with_statement

from django.contrib import admin

from ..models import Category


class CategoryAdmin(admin.ModelAdmin):
    search_fields   = ('page__title_set__slug', 'page__title_set__title')


admin.site.register(Category, CategoryAdmin)

