#
# Copyright (c), 2018-2026, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Wolfgang Meier <wolfgangmm@gmail.com>
#
"""
XQuery 3.1 implementation - part 1 (parser class)

Refs:
  - https://www.w3.org/TR/xquery-31/
"""
from collections.abc import Iterator
from contextlib import contextmanager
import re
from typing import Any, ClassVar, Optional

from elementpath.exceptions import xpath_error
from elementpath.helpers import is_xml_codepoint
from elementpath.namespaces import XSI_NAMESPACE, XQUERY_LOCAL_FUNCTIONS_NAMESPACE
from elementpath.xpath31 import XPath31Parser

REFERENCE_PATTERN = re.compile(r'&(?:(lt|gt|amp|quot|apos)|#([0-9]+)|#x([0-9a-fA-F]+));|&')
PREDEFINED_ENTITIES = {'lt': '<', 'gt': '>', 'amp': '&', 'quot': '"', 'apos': "'"}


class XQuery31Parser(XPath31Parser):
    """
    XQuery 3.1 expression parser class. Currently, it extends the XPath 3.1 parser
    with direct and computed node constructors and with FLWOR expressions (except
    group by and window clauses). Accepts all XPath 3.1 options as
    keyword arguments.

    :param boundary_space: the boundary-space policy of the static context, \
    can be 'strip' (the default) or 'preserve'.
    :param kwargs: the same keyword arguments of class :class:`elementpath.XPath31Parser`.
    """
    version = '3.1'

    # https://www.w3.org/TR/xquery-31/#id-basics
    DEFAULT_NAMESPACES: ClassVar[dict[str, str]] = {
        'xsi': XSI_NAMESPACE,
        'local': XQUERY_LOCAL_FUNCTIONS_NAMESPACE,
        **XPath31Parser.DEFAULT_NAMESPACES
    }

    PATH_STEP_LABELS = (  # type: ignore[assignment]
        'axis', 'function', 'kind test', 'element constructor', 'attribute constructor',
        'text constructor', 'comment constructor', 'processing instruction constructor',
        'document constructor', 'namespace constructor',
    )
    PATH_STEP_SYMBOLS = {
        '(integer)', '(string)', '(float)', '(decimal)', '(name)',
        '*', '@', '..', '.', '(', '{', 'Q{', '$', '<',
    }

    boundary_space = 'strip'

    def __init__(self, *args: Any, boundary_space: Optional[str] = None,
                 **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if boundary_space is not None:
            if boundary_space not in ('strip', 'preserve'):
                raise ValueError("boundary_space must be 'strip' or 'preserve'")
            self.boundary_space = boundary_space

    @staticmethod
    def unescape(string_literal: str) -> str:
        """
        Unescapes an XQuery string literal: in addition to doubled delimiters,
        predefined entity references and character references are expanded.
        """
        value = XPath31Parser.unescape(string_literal)
        if '&' not in value:
            return value

        def replace(match: 're.Match[str]') -> str:
            entity, dec_ref, hex_ref = match.groups()
            if entity is not None:
                return PREDEFINED_ENTITIES[entity]
            elif dec_ref is None and hex_ref is None:
                msg = f"invalid entity reference in string literal {string_literal}"
                raise xpath_error('XPST0003', msg)

            codepoint = int(dec_ref) if dec_ref is not None else int(hex_ref, 16)
            if not is_xml_codepoint(codepoint):
                msg = f"character reference {match.group()!r} is not a valid XML character"
                raise xpath_error('XQST0090', msg)
            return chr(codepoint)

        return REFERENCE_PATTERN.sub(replace, value)

    @contextmanager
    def in_scope_namespaces(self, namespaces: dict[str, str]) -> Iterator[None]:
        """
        Temporarily replaces the statically known namespaces and the default element
        namespace of the parser, e.g. for parsing and evaluating the content of a
        direct element constructor that has namespace declaration attributes.
        """
        status = self.namespaces, self.default_namespace
        self.namespaces = namespaces
        self.default_namespace = namespaces.get('', self.default_namespace)
        try:
            yield
        finally:
            self.namespaces, self.default_namespace = status
