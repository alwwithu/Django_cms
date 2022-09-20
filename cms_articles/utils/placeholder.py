# -*- coding: utf-8 -*-
import warnings

from cms.exceptions import DuplicatePlaceholderWarning
from cms.utils.placeholder import _get_nodelist, _scan_placeholders, validate_placeholder_name
from django.template.loader import get_template


def get_placeholders(template):
    from ..templatetags.cms_articles import ArticlePlaceholder

    compiled_template = get_template(template)

    placeholders = []
    nodes = _scan_placeholders(_get_nodelist(compiled_template), ArticlePlaceholder)
    clean_placeholders = []

    for node in nodes:
        placeholder = node.get_declaration()
        slot = placeholder.slot

        if slot in clean_placeholders:
            warnings.warn(
                'Duplicate {{% placeholder "{0}" %}} ' "in template {1}.".format(slot, template),
                DuplicatePlaceholderWarning,
            )
        else:
            validate_placeholder_name(slot)
            placeholders.append(placeholder)
            clean_placeholders.append(slot)
    return placeholders
