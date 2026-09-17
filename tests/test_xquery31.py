#!/usr/bin/env python
#
# Copyright (c), 2018-2026, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Wolfgang Meier <wolfgangmm@gmail.com>
#
#
# Note: Many tests are built using the examples of the XQuery standards,
#       published by W3C under the W3C Document License.
#
#       References:
#           https://www.w3.org/TR/xquery-31/
#           https://www.w3.org/Consortium/Legal/2015/doc-license
#
import unittest
import xml.etree.ElementTree as ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from elementpath import select, ElementPathError, XPathContext, ElementNode, \
    CommentNode, ProcessingInstructionNode, TextNode, AttributeNode, NamespaceNode, \
    DocumentNode
from elementpath.xpath3 import XPath31Parser
from elementpath.xquery31 import XQuery31Parser


class XQuery31ConstructorsTest(unittest.TestCase):
    etree = ElementTree

    def setUp(self):
        self.root = self.etree.XML('<root><x a="1" b="2">t</x><y/></root>')

    def select(self, expression, root=None, **kwargs):
        return select(self.root if root is None else root, expression,
                      parser=XQuery31Parser, **kwargs)

    def evaluate(self, expression, **kwargs):
        """Evaluates returning XPath nodes instead of wrapped objects."""
        token = XQuery31Parser(**kwargs).parse(expression)
        return token.evaluate(XPathContext(self.root))

    def tostring(self, elem):
        return self.etree.tostring(elem, encoding='unicode').replace(' />', '/>')

    def check_xml(self, expression, expected, **kwargs):
        result = self.select(expression, **kwargs)
        self.assertIsInstance(result, list)
        self.assertEqual([self.tostring(e) for e in result], expected)

    def check_error(self, expression, code, **kwargs):
        with self.assertRaises(ElementPathError) as ctx:
            self.select(expression, **kwargs)
        self.assertIn(code, str(ctx.exception))

    ###
    # Direct element constructors
    def test_empty_element(self):
        self.check_xml('<a/>', ['<a/>'])
        self.check_xml('<a></a>', ['<a/>'])
        self.check_xml('<a  />', ['<a/>'])
        self.check_xml('<a:b xmlns:a="urn:a"></a:b >', [self.tostring(
            self.etree.XML('<a:b xmlns:a="urn:a"/>')
        )])

    def test_element_node(self):
        result = self.evaluate('<a>t</a>')
        self.assertIsInstance(result, ElementNode)
        self.assertIsNone(result.parent)
        self.assertEqual(result.string_value, 't')
        self.assertEqual(result.type_name, '{http://www.w3.org/2001/XMLSchema}untyped')

    def test_nested_elements_and_text(self):
        self.check_xml('<a>x<b>y</b>z<c/></a>', ['<a>x<b>y</b>z<c/></a>'])
        self.check_xml('<a><b><c>deep</c></b></a>', ['<a><b><c>deep</c></b></a>'])

    def test_attributes(self):
        self.check_xml('<a x="1" y=\'2\'/>', ['<a x="1" y="2"/>'])
        self.check_xml('<a x = "1"/>', ['<a x="1"/>'])
        self.check_xml("<a x='it''s' y=\"say \"\"hi\"\"\"/>",
                       ['<a x="it\'s" y="say &quot;hi&quot;"/>'])
        self.check_xml('<a x="{1 + 1}"/>', ['<a x="2"/>'])
        self.check_xml('<a x="a{1, 2}b{3}c"/>', ['<a x="a1 2b3c"/>'])
        self.check_xml('<a x="{()}"/>', ['<a x=""/>'])
        self.check_xml('<a x="{{}}"/>', ['<a x="{}"/>'])
        self.check_xml('<a x="{[1, [2, 3]]}"/>', ['<a x="1 2 3"/>'])
        self.check_xml('<a x="{/root/x/@a}"/>', ['<a x="1"/>'])

    def test_attribute_value_normalization(self):
        self.check_xml('<a x="a\tb\nc\r\nd"/>', ['<a x="a b c d"/>'])
        self.assertEqual(self.select('string(<a x="&#10;"/>/@x)'), '\n')

    def test_references(self):
        self.check_xml('<a>&lt;&gt;&amp;&quot;&apos;</a>', ['<a>&lt;&gt;&amp;"\'</a>'])
        self.check_xml('<a>&#65;&#x42;</a>', ['<a>AB</a>'])
        self.check_xml('<a x="&lt;&#65;"/>', ['<a x="&lt;A"/>'])
        self.check_error('<a>&nbsp;</a>', 'XPST0003')
        self.check_error('<a>&#0;</a>', 'XQST0090')
        self.check_error('<a x="&#xFFFE;"/>', 'XQST0090')

    def test_escaped_braces(self):
        self.check_xml('<a>{{x}}</a>', ['<a>{x}</a>'])
        self.check_error('<a>}</a>', 'XPST0003')
        self.check_error('<a x="}"/>', 'XPST0003')

    def test_cdata_sections(self):
        self.check_xml('<a><![CDATA[<b>&amp;</b>]]></a>', ['<a>&lt;b&gt;&amp;amp;&lt;/b&gt;</a>'])
        self.check_error('<a><![CDATA[x</a>', 'XPST0003')
        self.check_xml('<a><![CDATA[]]>{attribute x {1}}</a>', ['<a x="1"/>'])

    def test_enclosed_expressions(self):
        self.check_xml('<a>{1}</a>', ['<a>1</a>'])
        self.check_xml('<a>{1, 2, 3}</a>', ['<a>1 2 3</a>'])
        self.check_xml('<a>{1}{2}</a>', ['<a>12</a>'])
        self.check_xml('<a>{}</a>', ['<a/>'])
        self.check_xml('<a>{()}</a>', ['<a/>'])
        self.check_xml('<a>{""}</a>', ['<a/>'])
        self.check_xml('<a>{"}"}</a>', ['<a>}</a>'])
        self.check_xml('<a>{ (: comment :) 1 }</a>', ['<a>1</a>'])
        self.check_xml('<a>{ <b>{"}"}</b> }</a>', ['<a><b>}</b></a>'])
        self.check_xml('<a>{[1, 2]}</a>', ['<a>1 2</a>'])
        self.check_error('<a>{1</a>', 'XPST0003')
        self.check_error('<a>{map{1: 2}}</a>', 'XQTY0105')
        self.check_error('<a>{concat#2}</a>', 'XQTY0105')

    def test_copied_nodes(self):
        self.check_xml('<a>{/root/x}</a>', ['<a><x a="1" b="2">t</x></a>'])
        self.check_xml('<a>{/root/x/@*}</a>', ['<a a="1" b="2"/>'])
        self.check_xml('<a>{/root/x/@a}{"t"}</a>', ['<a a="1">t</a>'])
        self.check_xml('<a>{/root/x/text()}</a>', ['<a>t</a>'])
        result = self.select('<a>{/}</a>', root=self.etree.ElementTree(self.root))
        self.assertEqual([self.tostring(e) for e in result],
                         ['<a><root><x a="1" b="2">t</x><y/></root></a>'])

        # Copies are new nodes: changes don't affect the source
        result = self.evaluate('<a>{/root/y}</a>')
        self.assertIsNot(result.children[0].value, self.root[1])
        self.assertIsNone(result.children[0].value.tail)
        self.assertEqual(len(self.root), 2)

    def test_attributes_after_content(self):
        self.check_error('<a>x{/root/x/@a}</a>', 'XQTY0024')
        self.check_error('<a><b/>{/root/x/@a}</a>', 'XQTY0024')
        self.check_error('<a>{1, /root/x/@a}</a>', 'XQTY0024')
        self.check_error('<a x="1">{/root/x/@a}{/root/x/@a}</a>', 'XQDY0025')

    def test_boundary_whitespace(self):
        self.check_xml('<a>  </a>', ['<a/>'])
        self.check_xml('<a> <b/> </a>', ['<a><b/></a>'])
        self.check_xml('<a> {1} </a>', ['<a>1</a>'])
        self.check_xml('<a> x </a>', ['<a> x </a>'])
        self.check_xml('<a>&#32;</a>', ['<a> </a>'])
        self.check_xml('<a> &#32; </a>', ['<a>   </a>'])
        self.check_xml('<a> <![CDATA[]]> </a>', ['<a>  </a>'])
        self.check_xml('<a> {1} </a>', ['<a> 1 </a>'], boundary_space='preserve')
        self.check_xml('<a>\r\n</a>', ['<a>\n</a>'], boundary_space='preserve')

        with self.assertRaises(ValueError):
            XQuery31Parser(boundary_space='unknown')

    def test_comment_and_pi_constructors(self):
        self.check_xml('<a><!-- c --><?pi data?></a>', ['<a><!-- c --><?pi data?></a>'])
        self.assertEqual(self.select('<a><?pi?></a>/processing-instruction()/name()'), ['pi'])

        result = self.evaluate('<!-- hello -->')
        self.assertIsInstance(result, CommentNode)
        self.assertEqual(result.string_value, ' hello ')

        result = self.evaluate('<?target   some content?>')
        self.assertIsInstance(result, ProcessingInstructionNode)
        self.assertEqual(result.name, 'target')
        self.assertEqual(result.string_value, 'some content')

        self.check_error('<!-- a -- b -->', 'XPST0003')
        self.check_error('<!-- a --->', 'XPST0003')
        self.check_error('<!-- a ', 'XPST0003')
        self.check_error('<?xml data?>', 'XPST0003')
        self.check_error('<?pi', 'XPST0003')
        self.check_error('<?a:b data?>', 'XPST0003')

    def test_syntax_errors(self):
        self.check_error('<a>', 'XPST0003')
        self.check_error('<a', 'XPST0003')
        self.check_error('<a></b>', 'XQST0118')
        self.check_error('<a><b></a>', 'XQST0118')
        self.check_error('<a></ a>', 'XPST0003')
        self.check_error('< a/>', 'XPST0003')
        self.check_error('<a x=1/>', 'XPST0003')
        self.check_error('<a x"1"/>', 'XPST0003')
        self.check_error('<a x="1"y="2"/>', 'XPST0003')
        self.check_error('<a x="1/>', 'XPST0003')
        self.check_error('<a x="<"/>', 'XPST0003')
        self.check_error('<a x="1" x="2"/>', 'XQST0040')
        self.check_error('<a p:x="1" xmlns:p="urn:p" q:x="2" xmlns:q="urn:p"/>', 'XQST0040')

    ###
    # Namespaces
    def test_namespace_declarations(self):
        result = self.evaluate('<p:a xmlns:p="urn:p" p:x="1"><p:b/><c/></p:a>')
        self.assertEqual(result.name, '{urn:p}a')
        self.assertEqual(result.value.get('{urn:p}x'), '1')
        self.assertEqual([c.name for c in result], ['{urn:p}b', 'c'])
        self.assertEqual(result.nsmap.get('p'), 'urn:p')

        result = self.evaluate('<a xmlns="urn:d" x="1"><b/><c xmlns=""/></a>')
        self.assertEqual(result.name, '{urn:d}a')
        self.assertEqual(result.value.get('x'), '1')
        self.assertEqual([c.name for c in result], ['{urn:d}b', 'c'])

        result = self.evaluate('<a xmlns:x="urn:x">{x:foo}</a>')
        self.assertEqual(result.name, 'a')

        self.check_error('<p:a/>', 'XPST0081')
        self.check_error('<a p:x="1"/>', 'XPST0081')
        self.check_error('<a xmlns:p="u" xmlns:p="v"/>', 'XQST0071')
        self.check_error('<a xmlns="u" xmlns="v"/>', 'XQST0071')
        self.check_error('<a xmlns:p=""/>', 'XQST0085')
        self.check_error('<a xmlns:p="{1}"/>', 'XQST0022')
        self.check_error('<a xmlns:xml="urn:x"/>', 'XQST0070')
        self.check_error('<a xmlns:xmlns="urn:x"/>', 'XQST0070')
        self.check_error('<a xmlns:p="http://www.w3.org/XML/1998/namespace"/>', 'XQST0070')
        self.check_error('<xmlns:a/>', 'XQST0070')

    def test_namespaces_scope_of_enclosed_expressions(self):
        # The declaration applies also to preceding attributes
        self.assertEqual(
            self.select('string(<a x="{p:foo}" xmlns:p="urn:p"/>/@x)'), ''
        )
        self.check_error('<a x="{p:foo}"/>', 'XPST0081')
        self.assertEqual(
            self.select('string(<a x="{p:count((1, 2))}" '
                        'xmlns:p="http://www.w3.org/2005/xpath-functions"/>/@x)'), '2'
        )
        self.assertEqual(self.select('string(<a x="{ map{1: 2}(1) }" xmlns:p="urn:p"/>/@x)'), '2')
        self.check_error('<a xmlns:p="{}"/>', 'XQST0022')
        self.check_error('<a>{p:foo}</a>', 'XPST0081')

        root = self.etree.XML('<root xmlns="urn:d"><b>x</b></root>')
        self.assertEqual(self.select('<a xmlns="urn:d">{string(/root/b)}</a>/string()',
                                     root=root), ['x'])
        self.assertEqual(self.select('<a>{string(/*:root/*:b)}</a>/string()',
                                     root=root), ['x'])
        self.assertEqual(self.select('<a>{string(/root/b)}</a>/string()', root=root), [''])

        # Evaluation-time lookups of prefixes (e.g. casts)
        self.assertEqual(
            self.select('<a xmlns:p="urn:p">{namespace-uri-from-QName(xs:QName("p:b"))}</a>'
                        '/string()'), ['urn:p']
        )
        # The scope is restored after the constructor
        self.check_error('(<a xmlns:p="urn:p"/>, xs:QName("p:b"))', 'FONS0004')

    def test_xml_id_normalization(self):
        self.assertEqual(self.select('string(<a xml:id=" a{\'b  c\'} "/>/@xml:id)'), 'ab c')
        self.assertEqual(self.select('string(attribute xml:id { " a b " })'), 'a b')

    def test_string_literals(self):
        self.assertEqual(self.select('"a&amp;b&lt;&#65;&#x42;"'), 'a&b<AB')
        self.assertEqual(self.select("'it''s &apos;'"), "it's '")
        self.check_error('"a & b"', 'XPST0003')
        self.check_error('"&#0;"', 'XQST0090')
        self.assertEqual(select(self.root, '"a&amp;b"', parser=XPath31Parser), 'a&amp;b')

    def test_predeclared_namespaces(self):
        result = self.evaluate('<local:a/>')
        self.assertEqual(result.name, '{http://www.w3.org/2005/xquery-local-functions}a')
        result = self.evaluate('<xsi:a/>')
        self.assertEqual(result.name, '{http://www.w3.org/2001/XMLSchema-instance}a')

    def test_node_name_prefix(self):
        self.assertEqual(self.select('name(<p:a xmlns:p="urn:p"/>)'), 'p:a')
        self.assertEqual(self.select('local-name(<p:a xmlns:p="urn:p"/>)'), 'a')
        self.assertEqual(self.select('namespace-uri(<p:a xmlns:p="urn:p"/>)'), 'urn:p')

    ###
    # Integration with other expressions
    def test_expressions_with_constructors(self):
        self.assertEqual(self.select('1 < 2'), True)
        self.assertEqual(self.select('2<1'), False)
        self.assertEqual(self.select('<a>1</a> = 1'), True)
        self.assertEqual(self.select('<a>1</a> < 2'), True)
        self.assertEqual(self.select('<a/> is <a/>'), False)
        self.assertEqual(self.select('<a>{1}</a> (: a comment :)/string()'), ['1'])
        self.check_xml('(<a/>, <b/>)', ['<a/>', '<b/>'])
        self.check_xml('if (1) then <a/> else <b/>', ['<a/>'])
        self.check_xml('for $i in 1 to 2 return <i n="{$i}">{$i * 2}</i>',
                       ['<i n="1">2</i>', '<i n="2">4</i>'])
        self.check_xml('let $x := <x>1</x> return <a>{$x, $x}</a>',
                       ['<a><x>1</x><x>1</x></a>'])
        self.assertEqual(self.select('string-join(<a><b>x</b><b>y</b></a>/b, "-")'), 'x-y')
        self.assertEqual(self.select('count(<a><b/><c><b/></c></a>//b)'), 2)

    def test_path_steps_with_constructors(self):
        self.check_xml('<a><b>x</b><b>y</b></a>/b', ['<b>x</b>', '<b>y</b>'])
        self.check_xml('<a><b/><c/></a>/(c, b)', ['<c/>', '<b/>'])
        self.check_xml('/root/<a/>', ['<a/>'])
        self.check_xml('/root/*/<a>{name()}</a>', ['<a>x</a>', '<a>y</a>'])
        self.check_xml('<a><b/></a>//<c/>', ['<c/>', '<c/>'])
        self.check_xml('<a><b/></a>/b/..', ['<a><b/></a>'])
        self.assertEqual(self.select('<a><b/></a>/b/root() instance of element(a)'), True)

    def test_document_order(self):
        # Nodes of a constructed tree are before nodes of the trees constructed later
        self.check_xml('for $p in <p><a/><b/></p> return ($p/b | <c/> | $p/a)',
                       ['<a/>', '<b/>', '<c/>'])
        self.assertEqual(
            self.select('for $p in <p><a/><b/></p> return $p/a << $p/b'), [True]
        )

    def test_xpath_parsers_are_unchanged(self):
        with self.assertRaises(ElementPathError):
            select(self.root, '<a/>', parser=XPath31Parser)
        with self.assertRaises(ElementPathError):
            select(self.root, 'element a {}', parser=XPath31Parser)
        self.assertEqual(select(self.root, '1 < 2', parser=XPath31Parser), True)

    ###
    # Computed constructors
    def test_computed_element_constructor(self):
        self.check_xml('element a {}', ['<a/>'])
        self.check_xml('element a { "x" }', ['<a>x</a>'])
        self.check_xml('element a (: comment :) { 1, 2 }', ['<a>1 2</a>'])
        self.check_xml('element {"a"} { element b {} }', ['<a><b/></a>'])
        self.check_xml('element { "b" || "c" } {}', ['<bc/>'])
        self.check_xml('element a { attribute x { 1 }, "t" }', ['<a x="1">t</a>'])
        self.check_xml('<a>{ element b { 1 } }</a>', ['<a><b>1</b></a>'])

        result = self.evaluate('element xs:a {}')
        self.assertEqual(result.name, '{http://www.w3.org/2001/XMLSchema}a')
        result = self.evaluate('element { xs:QName("xs:a") } {}')
        self.assertEqual(result.name, '{http://www.w3.org/2001/XMLSchema}a')

        self.check_error('element p:a {}', 'XPST0081')
        self.check_error('element xmlns:a {}', 'XPST0081')
        self.check_error('element { "xmlns:a" } {}', 'XQDY0074')

        # EQNames
        result = self.evaluate('element Q{urn:x}a {}')
        self.assertEqual(result.name, '{urn:x}a')
        if self.etree is ElementTree:
            result = self.evaluate('element Q{z&#x20;z}a {}')
            self.assertEqual(result.name, '{z z}a')
        else:
            self.check_error('element Q{z&#x20;z}a {}', 'XQDY0074')  # lxml limit
        result = self.evaluate('element Q{}a {}')
        self.assertEqual(result.name, 'a')
        result = self.evaluate('element { "Q{urn:x}a" } {}')
        self.assertEqual(result.name, '{urn:x}a')
        result = self.evaluate('attribute Q{urn:x}a {}')
        self.assertEqual(result.name, '{urn:x}a')
        self.check_error('element { 1 } {}', 'XPTY0004')
        self.check_error('element { ("a", "b") } {}', 'XPTY0004')
        self.check_error('element { "1a" } {}', 'XQDY0074')
        self.check_error('element { "p:a" } {}', 'XQDY0074')
        self.check_error('element a { attribute x { 1 }, attribute x { 2 } }', 'XQDY0025')

    def test_computed_attribute_constructor(self):
        result = self.evaluate('attribute x { 1, 2 }')
        self.assertIsInstance(result, AttributeNode)
        self.assertEqual(result.name, 'x')
        self.assertEqual(result.string_value, '1 2')

        result = self.evaluate('attribute { "xs:y" } {}')
        self.assertEqual(result.name, '{http://www.w3.org/2001/XMLSchema}y')
        self.assertEqual(result.string_value, '')

        self.check_error('attribute xmlns {}', 'XQDY0044')
        self.check_error('attribute { "xmlns" } {}', 'XQDY0044')

    def test_computed_text_constructor(self):
        result = self.evaluate('text { 1, 2 }')
        self.assertIsInstance(result, TextNode)
        self.assertEqual(result.value, '1 2')
        self.assertEqual(self.evaluate('text { () }'), [])
        self.assertEqual(self.evaluate('text {}'), [])

    def test_computed_comment_constructor(self):
        result = self.evaluate('comment { "a", "b" }')
        self.assertIsInstance(result, CommentNode)
        self.assertEqual(result.string_value, 'a b')
        self.check_error('comment { "a--b" }', 'XQDY0072')
        self.check_error('comment { "a-" }', 'XQDY0072')

    def test_computed_pi_constructor(self):
        result = self.evaluate('processing-instruction pi { "  data" }')
        self.assertIsInstance(result, ProcessingInstructionNode)
        self.assertEqual(result.name, 'pi')
        self.assertEqual(result.string_value, 'data')

        result = self.evaluate('processing-instruction { "p" || "i" } {}')
        self.assertEqual(result.name, 'pi')

        self.check_error('processing-instruction xml {}', 'XQDY0064')
        self.check_error('processing-instruction { "a:b" } {}', 'XQDY0041')
        self.check_error('processing-instruction p { "?>" }', 'XQDY0026')

    def test_computed_namespace_constructor(self):
        result = self.evaluate('namespace p { "urn:p" }')
        self.assertIsInstance(result, NamespaceNode)
        self.assertEqual((result.prefix, result.uri), ('p', 'urn:p'))

        self.check_error('namespace xmlns { "urn:p" }', 'XQDY0101')
        self.check_error('namespace p { "" }', 'XQDY0101')
        self.check_error('namespace xml { "urn:p" }', 'XQDY0101')
        self.check_error('<a>x{namespace p { "urn:p" }}</a>', 'XQTY0024')

    def test_computed_document_constructor(self):
        result = self.evaluate('document { <a/> }')
        self.assertIsInstance(result, DocumentNode)
        self.assertEqual(len(result.children), 1)
        self.check_xml('document { <a><b/></a> }/a/b', ['<b/>'])
        self.assertEqual(self.select('count(document { <a/>, "x", <b/> }/node())'), 3)
        self.check_error('document { attribute x {} }', 'XPTY0004')

    def test_computed_keywords_as_names(self):
        root = self.etree.XML('<root><element>1</element><text>2</text></root>')
        self.assertEqual(self.select('string(/root/element)', root=root), '1')
        self.assertEqual(self.select('string(/root/text)', root=root), '2')
        self.assertEqual(self.select('/root/text()', root=root), [])
        self.assertEqual(self.select('count(/root/element(element))', root=root), 1)
        self.assertEqual(self.select('count(/root/*/attribute::*)', root=root), 0)

    def test_static_evaluation(self):
        # Constructors aren't evaluated at parse time, so dynamic errors are
        # raised only at evaluation.
        token = XQuery31Parser().parse('<a>{1, /root/x/@a}</a>')
        self.assertEqual(token.source, '<a>{1, /root/x/@a}</a>')
        with self.assertRaises(ElementPathError):
            token.evaluate(XPathContext(self.root))


@unittest.skipIf(lxml_etree is None, "The lxml library is not installed")
class LxmlXQuery31ConstructorsTest(XQuery31ConstructorsTest):
    etree = lxml_etree

    def test_lxml_namespace_prefixes(self):
        self.check_xml('<p:a xmlns:p="urn:p" p:x="1"><p:b/><c xmlns="urn:c"/></p:a>',
                       ['<p:a xmlns:p="urn:p" p:x="1"><p:b/><c xmlns="urn:c"/></p:a>'])
        self.check_xml('<a>{namespace p { "urn:p" }}</a>', ['<a xmlns:p="urn:p"/>'])


class XQuery31FLWORTest(unittest.TestCase):
    etree = ElementTree

    def setUp(self):
        self.root = self.etree.XML(
            '<root><item n="2">b</item><item n="1">c</item><item>a</item></root>'
        )

    def select(self, expression, **kwargs):
        return select(self.root, expression, parser=XQuery31Parser, **kwargs)

    def check_error(self, expression, code, **kwargs):
        with self.assertRaises(ElementPathError) as ctx:
            self.select(expression, **kwargs)
        self.assertIn(code, str(ctx.exception))

    def test_for_and_let_clauses(self):
        self.assertEqual(self.select('for $x in 1 to 3 return $x * 2'), [2, 4, 6])
        self.assertEqual(self.select('let $x := (1, 2) return count($x)'), 2)
        self.assertEqual(self.select('for $x in 1 to 3 let $y := $x * 2 return $y'), [2, 4, 6])
        self.assertEqual(self.select('let $x := 2 for $y in 1 to $x return $x + $y'), [3, 4])
        self.assertEqual(self.select('let $a := 1 let $b := $a let $c := $a + $b return $c'), 2)
        self.assertEqual(
            self.select('for $x in (1, 2), $y in ("a", "b") return $x || $y'),
            ['1a', '1b', '2a', '2b']
        )
        self.assertEqual(
            self.select('for $x in (1, 2) for $y in ("a", "b") return $x || $y'),
            ['1a', '1b', '2a', '2b']
        )
        self.assertEqual(self.select('let $x := 1, $y := $x + 1 return $y'), 2)
        self.assertEqual(self.select('for $x in 1 return $x'), [1])

    def test_variable_shadowing(self):
        self.assertEqual(self.select('let $x := 1 for $x in ($x, 2) return $x'), [1, 2])
        self.assertEqual(self.select('for $x in (1, 2) let $x := $x * 10 return $x'), [10, 20])
        self.assertEqual(self.select('for $x in (1, 2) return $x', variables={'x': 5}), [1, 2])

    def test_positional_variables(self):
        self.assertEqual(self.select('for $x at $i in ("a", "b") return $i || $x'),
                         ['1a', '2b'])
        self.assertEqual(self.select('for $x at $i in /root/item return $i'), [1, 2, 3])
        self.check_error('for $x at $x in (1, 2) return $x', 'XQST0089')

    def test_allowing_empty(self):
        self.assertEqual(self.select('for $x in () return 1'), [])
        self.assertEqual(self.select('for $x allowing empty in () return count($x)'), [0])
        self.assertEqual(self.select('for $x allowing empty at $i in () return $i'), [0])
        self.assertEqual(self.select('for $x allowing empty in (5, 6) return $x'), [5, 6])

    def test_type_declarations(self):
        self.assertEqual(self.select('for $x as xs:integer in (1, 2) return $x'), [1, 2])
        self.assertEqual(self.select('let $x as xs:string* := ("a", "b") return $x'), ['a', 'b'])
        self.assertEqual(self.select('for $x as element(item) in /root/item return 1'), [1, 1, 1])
        self.check_error('for $x as xs:string in (1, 2) return $x', 'XPTY0004')
        self.check_error('let $x as xs:integer := (1, 2) return $x', 'XPTY0004')
        self.check_error('for $x as xs:integer allowing empty in () return $x', 'XPTY0004')
        self.check_error('for $x as xs:unknownType in (1, 2) return $x', 'XPST0051')

    def test_where_clause(self):
        self.assertEqual(self.select('for $x in 1 to 5 where $x mod 2 = 0 return $x'), [2, 4])
        self.assertEqual(
            self.select('for $x in 1 to 3 let $y := $x * 2 where $y > 2 return $y'), [4, 6]
        )
        self.assertEqual(
            self.select('for $i in /root/item where $i/@n return string($i)'), ['b', 'c']
        )
        self.assertEqual(
            self.select('for $x in 1 to 5 where $x > 1 where $x < 4 return $x'), [2, 3]
        )

    def test_count_clause(self):
        self.assertEqual(self.select('for $x in ("a", "b") count $c return $c'), [1, 2])
        self.assertEqual(
            self.select('for $x in 1 to 6 where $x mod 2 = 0 count $c return $c'), [1, 2, 3]
        )
        self.assertEqual(
            self.select('for $x in (3, 1, 2) count $c order by $x return $c'), [2, 3, 1]
        )
        self.assertEqual(
            self.select('for $x in (3, 1, 2) order by $x count $c return $c'), [1, 2, 3]
        )

    def test_order_by_clause(self):
        self.assertEqual(self.select('for $x in (3, 1, 2) order by $x return $x'), [1, 2, 3])
        self.assertEqual(
            self.select('for $x in (3, 1, 2) order by $x descending return $x'), [3, 2, 1]
        )
        self.assertEqual(
            self.select('for $x in ("b", "a", "c") order by $x ascending return $x'),
            ['a', 'b', 'c']
        )
        self.assertEqual(
            self.select('for $x in (1.5, 1, xs:double(0.5)) stable order by $x return $x'),
            [0.5, 1, 1.5]
        )
        self.assertEqual(
            self.select('for $i in /root/item order by string($i) return string($i/@n)'),
            ['', '2', '1']
        )

    def test_order_by_multiple_keys(self):
        self.assertEqual(
            self.select('for $p in ([1, "b"], [2, "a"], [1, "a"]) '
                        'order by $p(1) descending, $p(2) return $p(1) || $p(2)'),
            ['2a', '1a', '1b']
        )
        self.assertEqual(
            self.select('for $x in (1, 2, 3, 4) order by $x mod 2 return $x'), [2, 4, 1, 3]
        )

    def test_order_by_empty_and_nan(self):
        query = 'for $i in /root/item order by $i/@n {} return string($i)'
        self.assertEqual(self.select(query.format('')), ['a', 'c', 'b'])
        self.assertEqual(self.select(query.format('empty least')), ['a', 'c', 'b'])
        self.assertEqual(self.select(query.format('empty greatest')), ['c', 'b', 'a'])
        self.assertEqual(self.select(query.format('descending')), ['b', 'c', 'a'])
        self.assertEqual(self.select(query.format('descending empty greatest')),
                         ['a', 'b', 'c'])

        query = 'for $x in ([2], [xs:double("NaN")], [], [1]) order by $x?* %s ' \
                'return if (empty($x?*)) then "empty" else string($x?*)'
        self.assertEqual(self.select(query % ''), ['empty', 'NaN', '1', '2'])
        self.assertEqual(self.select(query % 'empty greatest'), ['1', '2', 'NaN', 'empty'])
        self.assertEqual(self.select(query % 'descending'), ['2', '1', 'NaN', 'empty'])

    def test_order_by_collation(self):
        uca = "http://www.w3.org/2013/collation/UCA?strength=primary"
        codepoint = "http://www.w3.org/2005/xpath-functions/collation/codepoint"
        query = 'for $x in ("b", "B", "a") order by $x collation "{}" return $x'
        self.assertEqual(self.select(query.format(codepoint)), ['B', 'a', 'b'])
        try:
            self.assertEqual(self.select(query.format(uca))[0], 'a')
        except ElementPathError:
            pass  # UCA collation not supported on this platform
        self.check_error(query.format('http://example.com/unknown'), 'XQST0076')

    def test_order_by_errors(self):
        self.check_error('for $x in (1, "a") order by $x return $x', 'XPTY0004')
        self.check_error('for $x in (1, true()) order by $x return $x', 'XPTY0004')
        self.check_error('for $x in (1, 2) order by ($x, $x) return $x', 'XPTY0004')
        self.check_error('for $x in 1 order by ($x, $x) return $x', 'XPTY0004')
        self.check_error('for $x in (1, 2) order $x return $x', 'XPST0003')
        self.check_error('for $x in (1, 2) stable by $x return $x', 'XPST0003')

    def test_syntax_errors(self):
        self.check_error('for $x in (1, 2)', 'XPST0003')
        self.check_error('for $x in (1, 2) where $x', 'XPST0003')
        self.check_error('let $x = 1 return $x', 'XPST0003')
        self.check_error('for $x in (1, 2) let return $x', 'XPST0003')
        self.check_error('for $x in (1, 2) count return $x', 'XPST0003')
        self.check_error('for $x in (1, 2) allowing $y in (1) return $x', 'XPST0003')
        self.check_error('1 for $x in (1, 2) return $x', 'XPST0003')

    def test_unsupported_clauses(self):
        self.check_error('for $x in (1, 2) group by $k := $x return $x', 'XPST0003')
        self.check_error('for tumbling window $w in (1, 2) start when true() return $w',
                         'XPST0003')
        self.check_error('for sliding window $w in (1, 2) start when true() return $w',
                         'XPST0003')

    def test_keywords_as_names(self):
        root = self.etree.XML('<root><for>1</for><order>2</order><where>3</where></root>')
        self.assertEqual(select(root, 'string(/root/order)', parser=XQuery31Parser), '2')
        self.assertEqual(select(root, 'string(/root/where)', parser=XQuery31Parser), '3')
        self.assertEqual(select(root, 'count(/root/for)', parser=XQuery31Parser), 1)
        self.assertEqual(
            select(root, 'for $x in /root/* order by string($x) descending '
                         'return name($x)', parser=XQuery31Parser),
            ['where', 'order', 'for']
        )

    def test_flwor_with_constructors(self):
        result = self.select('<ul>{for $i in /root/item order by string($i) '
                             'return <li>{string($i)}</li>}</ul>')
        self.assertEqual(
            self.etree.tostring(result[0], encoding='unicode'),
            '<ul><li>a</li><li>b</li><li>c</li></ul>'
        )
        self.assertEqual(
            self.select('for $x in (1, 2) let $e := <e>{$x}</e> return string($e)'), ['1', '2']
        )

    def test_source(self):
        query = 'for $x at $i in (1, 2) let $y := $x where $y > 0 ' \
                'order by $y descending count $c return $c'
        token = XQuery31Parser().parse(query)
        self.assertEqual(token.source, query)
        self.assertEqual(XQuery31Parser().parse(f'({query})').source, f'({query})')

    def test_xpath_parsers_are_unchanged(self):
        with self.assertRaises(ElementPathError):
            select(self.root, 'for $x in (1, 2) where $x > 1 return $x', parser=XPath31Parser)
        with self.assertRaises(ElementPathError):
            select(self.root, 'let $a := 1 let $b := 2 return $a', parser=XPath31Parser)
        self.assertEqual(select(self.root, 'for $x in 1 to 2 return $x', parser=XPath31Parser),
                         [1, 2])


@unittest.skipIf(lxml_etree is None, "The lxml library is not installed")
class LxmlXQuery31FLWORTest(XQuery31FLWORTest):
    etree = lxml_etree


if __name__ == '__main__':
    unittest.main()
