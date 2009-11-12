#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This file is part of web2py Web Framework (Copyrighted, 2007-2009).
Developed by Massimo Di Pierro <mdipierro@cs.depaul.edu>.
License: GPL v2

Thanks to ga2arch for help with IS_IN_DB and IS_NOT_IN_DB on GAE
"""

import os
import re
import copy
import sys
import types
import datetime
import time
import cgi
import hmac
import urllib
import struct
from cStringIO import StringIO
from storage import Storage
from utils import hash, get_digest


__all__ = [
    'IS_ALPHANUMERIC',
    'IS_DATE',
    'IS_DATETIME',
    'IS_EMAIL',
    'IS_EXPR',
    'IS_UPLOAD_FILENAME',
    'IS_FLOAT_IN_RANGE',
    'IS_IMAGE',
    'IS_INT_IN_RANGE',
    'IS_IN_SET',
    'IS_IPV4',
    'IS_LENGTH',
    'IS_LIST_OF',
    'IS_LOWER',
    'IS_MATCH',
    'IS_NOT_EMPTY',
    'IS_TIME',
    'IS_URL',
    'CLEANUP',
    'CRYPT',
    'IS_IN_DB',
    'IS_NOT_IN_DB',
    'IS_UPPER',
    'IS_EMPTY_OR',
    'IS_NULL_OR',
    'IS_STRONG',
    ]


class Validator(object):
    """
    Root for all validators, mainly for documentation purposes.

    Validators are classes used to validate input fields (including forms
    generated from database tables).

    Here is an example of using a validator with a FORM::

        INPUT(_name='a', requires=IS_INT_IN_RANGE(0, 10))

    Here is an example of how to require a validator for a table field::

        db.define_table('person', SQLField('name'))
        db.person.name.requires=IS_NOT_EMPTY()

    Validators are always assigned using the requires attribute of a field. A
    field can have a single validator or multiple validators. Multiple
    validators are made part of a list::

        db.person.name.requires=[IS_NOT_EMPTY(), IS_NOT_IN_DB(db, 'person.id')]

    Validators are called by the function accepts on a FORM or other HTML
    helper object that contains a form. They are always called in the order in
    which they are listed.

    Built-in validators have constructors that take the optional argument error
    message which allows you to change the default error message.
    Here is an example of a validator on a database table::

        db.person.name.requires=IS_NOT_EMPTY(error_message=T('fill this'))

    where we have used the translation operator T to allow for
    internationalization.

    Notice that default error messages are not translated.
    """

    def formatter(self, value):
        """
        For some validators returns a formatted version (matching the validator)
        of value. Otherwise just returns the value.
        """
        return value


class IS_MATCH(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_MATCH('.+'))

    the argument of IS_MATCH is a regular expression::

        >>> IS_MATCH('.+')('hello')
        ('hello', None)

        >>> IS_MATCH('.+')('')
        ('', 'invalid expression')
    """

    def __init__(self, expression, error_message='invalid expression'):
        self.regex = re.compile(expression)
        self.error_message = error_message

    def __call__(self, value):
        match = self.regex.match(value)
        if match:
            return (match.group(), None)
        return (value, self.error_message)


class IS_EXPR(Validator):
    """
    example::

        INPUT(_type='text', _name='name',
            requires=IS_EXPR('5 < int(value) < 10'))

    the argument of IS_EXPR must be python condition::

        >>> IS_EXPR('int(value) < 2')('1')
        ('1', None)

        >>> IS_EXPR('int(value) < 2')('2')
        ('2', 'invalid expression')
    """

    def __init__(self, expression, error_message='invalid expression'):
        self.expression = expression
        self.error_message = error_message

    def __call__(self, value):
        environment = {'value': value}
        exec '__ret__=' + self.expression in environment
        if environment['__ret__']:
            return (value, None)
        return (value, self.error_message)


class IS_LENGTH(Validator):
    """
    Checks if length of field's value fits between given boundaries. Works
    for both text and file inputs.

    Arguments:

    maxsize: maximum allowed length / size
    minsize: minimum allowed length / size

    Examples::

        #Check if text string is shorter than 33 characters:
        INPUT(_type='text', _name='name', requires=IS_LENGTH(32))

        #Check if password string is longer than 5 characters:
        INPUT(_type='password', _name='name', requires=IS_LENGTH(minsize=6))

        #Check if uploaded file has size between 1KB and 1MB:
        INPUT(_type='file', _name='name', requires=IS_LENGTH(1048576, 1024))

        >>> IS_LENGTH()('')
        ('', None)
        >>> IS_LENGTH()('1234567890')
        ('1234567890', None)
        >>> IS_LENGTH(maxsize=5, minsize=0)('1234567890')  # too long
        ('1234567890', 'enter from 0 to 5 characters')
        >>> IS_LENGTH(maxsize=50, minsize=20)('1234567890')  # too short
        ('1234567890', 'enter from 20 to 50 characters')
    """

    def __init__(self, maxsize=255, minsize=0, error_message='enter from %(min)s to %(max)s characters'):
        self.maxsize = maxsize
        self.minsize = minsize
        self.error_message = error_message % dict(min=minsize, max=maxsize)

    def __call__(self, value):
        if isinstance(value, cgi.FieldStorage):
            if value.file:
                value.file.seek(0, os.SEEK_END)
                length = value.file.tell()
                value.file.seek(0, os.SEEK_SET)
            else:
                val = value.value
                if val:
                    length = len(val)
                else:
                    length = 0
            if self.minsize <= length <= self.maxsize:
                return (value, None)
        elif isinstance(value, (str, unicode, list)):
            if self.minsize <= len(value) <= self.maxsize:
                return (value, None)
        elif self.minsize <= len(str(value)) <= self.maxsize:
            try:
                value.decode('utf8')
                return (value, None)
            except:
                pass
        return (value, self.error_message)


class IS_IN_SET(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_IN_SET(['max', 'john']))

    the argument of IS_IN_SET must be a list or set

        >>> IS_IN_SET(['max', 'john'])('max')
        ('max', None)
        >>> IS_IN_SET(['max', 'john'])('massimo')
        ('massimo', 'value not allowed')
        >>> IS_IN_SET(['max', 'john'], multiple=True)(('max', 'john'))
        ('|max|john|', None)
        >>> IS_IN_SET(['max', 'john'], multiple=True)(('bill', 'john'))
        (('bill', 'john'), 'value not allowed')
    """

    def __init__(
        self,
        theset,
        labels=None,
        error_message='value not allowed',
        multiple=False,
        zero=None
        ):
        self.multiple = multiple
        self.theset = [str(item) for item in theset]
        if isinstance(theset, dict):
            self.labels = theset.values()
        else:
            self.labels = labels
        self.error_message = error_message
        self.zero = zero

    def options(self):
        if not self.labels:
            items = [(k, k) for (i, k) in enumerate(self.theset)]
        else:
            items = [(k, self.labels[i]) for (i, k) in enumerate(self.theset)]
        if self.zero != None:
            items.insert(0,('',self.zero))
        return items

    def __call__(self, value):
        if self.multiple:
            values = re.compile("[\w\-:]+").findall(str(value))
        else:
            values = [value]
        failures = [x for x in values if not x in self.theset]
        if failures:
            if self.multiple and value == None:
                return (value, None)
            return (value, self.error_message)
        if self.multiple:
            return ('|%s|' % '|'.join(values), None)
        return (value, None)


regex1 = re.compile('[\w_]+\.[\w_]+')
regex2 = re.compile('%\((?P<name>[^\)]+)\)s')


class IS_IN_DB(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_IN_DB(db, db.table))

    used for reference fields, rendered as a dropbox
    """

    def __init__(
        self,
        dbset,
        field,
        label=None,
        error_message='value not in database',
        orderby=None,
        cache=None,
        multiple=False,
        zero=None,
        ):
        if hasattr(dbset, 'define_table'):
            self.dbset = dbset()
        else:
            self.dbset = dbset
        self.field = field
        (ktable, kfield) = str(self.field).split('.')
        if not label:
            label = '%%(%s)s' % kfield
        elif regex1.match(str(label)):
            label = '%%(%s)s' % str(label).split('.')[-1]
        ks = regex2.findall(label)
        if not kfield in ks:
            ks += [kfield]
        fields = ['%s.%s' % (ktable, k) for k in ks]
        self.fields = fields
        self.label = label
        self.ktable = ktable
        self.kfield = kfield
        self.ks = ks
        self.error_message = error_message
        self.theset = None
        self.orderby = orderby
        self.cache = cache
        self.multiple = multiple
        self.zero = zero

    def build_set(self):
        if self.dbset._db._dbname != 'gql':
            orderby = self.orderby or ', '.join(self.fields)
            dd = dict(orderby=orderby, cache=self.cache)
            records = self.dbset.select(*self.fields, **dd)
        else:
            import contrib.gql
            orderby = self.orderby\
                 or contrib.gql.SQLXorable('|'.join([k for k in self.ks
                    if k != 'id']))
            dd = dict(orderby=orderby, cache=self.cache)
            records = \
                self.dbset.select(self.dbset._db[self.ktable].ALL, **dd)
        self.theset = [str(r[self.kfield]) for r in records]
        self.labels = [self.label % dict(r) for r in records]

    def options(self):
        self.build_set()
        items = [(k, self.labels[i]) for (i, k) in enumerate(self.theset)]
        if self.zero != None:
            items.insert(0,('',self.zero))
        return items

    def __call__(self, value):
        if self.multiple:
            values = re.compile("[\w\-:]+").findall(str(value))
            if not [x for x in values if not x in self.theset]:
                return ('|%s|' % '|'.join(values), None)
        elif self.theset:
            if value in self.theset:
                return (value, None)
        else:
            (ktable, kfield) = str(self.field).split('.')
            field = self.dbset._db[ktable][kfield]
            if self.dbset(field == value).count():
                return (value, None)
        return (value, self.error_message)


class IS_NOT_IN_DB(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_NOT_IN_DB(db, db.table))

    makes the field unique
    """

    def __init__(
        self,
        dbset,
        field,
        error_message='value already in database',
        allowed_override=[],
        ):
        if hasattr(dbset, 'define_table'):
            self.dbset = dbset()
        else:
            self.dbset = dbset
        self.field = field
        self.error_message = error_message
        self.record_id = 0
        self.allowed_override = allowed_override

    def set_self_id(self, id):
        self.record_id = id

    def __call__(self, value):
        if value in self.allowed_override:
            return (value, None)
        (tablename, fieldname) = str(self.field).split('.')
        field = self.dbset._db[tablename][fieldname]
        rows = self.dbset(field == value).select(limitby=(0, 1))
        if len(rows) > 0 and str(rows[0].id) != str(self.record_id):
            return (value, self.error_message)
        return (value, None)


class IS_INT_IN_RANGE(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_INT_IN_RANGE(0, 10))

        >>> IS_INT_IN_RANGE(1,5)('4')
        (4, None)
        >>> IS_INT_IN_RANGE(1,5)(4)
        (4, None)
        >>> IS_INT_IN_RANGE(1,5)(1)
        (1, None)
        >>> IS_INT_IN_RANGE(1,5)(5)
        (5, 'enter an integer between 1 and 4')
        >>> IS_INT_IN_RANGE(1,5)(5)
        (5, 'enter an integer between 1 and 4')
        >>> IS_INT_IN_RANGE(1,5)(3.5)
        (3, 'enter an integer between 1 and 4')
    """

    def __init__(
        self,
        minimum,
        maximum,
        error_message = 'enter an integer between %(min)s and %(max)s',
        ):
        self.minimum = int(minimum)
        self.maximum = int(maximum)
        self.error_message = error_message % dict(min=self.minimum, max=self.maximum-1)

    def __call__(self, value):
        try:
            fvalue = float(value)
            value = int(value)
            if value == fvalue and self.minimum <= value < self.maximum:
                return (value, None)
        except ValueError:
            pass
        return (value, self.error_message)


class IS_FLOAT_IN_RANGE(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_FLOAT_IN_RANGE(0, 10))

        >>> IS_FLOAT_IN_RANGE(1,5)('4')
        (4.0, None)
        >>> IS_FLOAT_IN_RANGE(1,5)(4)
        (4.0, None)
        >>> IS_FLOAT_IN_RANGE(1,5)(1)
        (1.0, None)
        >>> IS_FLOAT_IN_RANGE(1,5)(5.1)
        (5.0999999999999996, 'enter a number between 1.0 and 5.0')
        >>> IS_FLOAT_IN_RANGE(1,5)(6.0)
        (6.0, 'enter a number between 1.0 and 5.0')
        >>> IS_FLOAT_IN_RANGE(1,5)(3.5)
        (3.5, None)
    """

    def __init__(
        self,
        minimum,
        maximum,
        error_message = 'enter a number between %(min)s and %(max)s',
        ):
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.error_message = error_message % dict(min=self.minimum, max=self.maximum)

    def __call__(self, value):
        try:
            value = float(value)
            if self.minimum <= value <= self.maximum:
                return (value, None)
        except (ValueError, TypeError):
            pass
        return (value, self.error_message)

def is_empty(value, empty_regex=None):
    "test empty field"
    if isinstance(value, (str, unicode)):
        value = value.strip()
        if empty_regex is not None and empty_regex.match(value):
            value = ''
    if value == None or value == '' or value == []:
        return (value, True)
    return (value, False)

class IS_NOT_EMPTY(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_NOT_EMPTY())

        >>> IS_NOT_EMPTY()(1)
        (1, None)
        >>> IS_NOT_EMPTY()(0)
        (0, None)
        >>> IS_NOT_EMPTY()('x')
        ('x', None)
        >>> IS_NOT_EMPTY()(' x ')
        ('x', None)
        >>> IS_NOT_EMPTY()(None)
        (None, 'enter a value')
        >>> IS_NOT_EMPTY()('')
        ('', 'enter a value')
        >>> IS_NOT_EMPTY()('  ')
        ('', 'enter a value')
        >>> IS_NOT_EMPTY()(' \\n\\t')
        ('', 'enter a value')
        >>> IS_NOT_EMPTY()([])
        ([], 'enter a value')
        >>> IS_NOT_EMPTY(empty_regex='def')('def')
        ('', 'enter a value')
        >>> IS_NOT_EMPTY(empty_regex='de[fg]')('deg')
        ('', 'enter a value')
        >>> IS_NOT_EMPTY(empty_regex='def')('abc')
        ('abc', None)
    """

    def __init__(self, error_message='enter a value', empty_regex=None):
        self.error_message = error_message
        if empty_regex is not None:
            self.empty_regex = re.compile(empty_regex)
        else:
            self.empty_regex = None

    def __call__(self, value):
        value, empty = is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return (value, self.error_message)
        return (value, None)


class IS_ALPHANUMERIC(IS_MATCH):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_ALPHANUMERIC())

        >>> IS_ALPHANUMERIC()('1')
        ('1', None)
        >>> IS_ALPHANUMERIC()('')
        ('', None)
        >>> IS_ALPHANUMERIC()('A_a')
        ('A_a', None)
        >>> IS_ALPHANUMERIC()('!')
        ('!', 'enter only letters, numbers, and underscore')
    """

    def __init__(self, error_message='enter only letters, numbers, and underscore'):
        IS_MATCH.__init__(self, '^[\w]*$', error_message)


class IS_EMAIL(Validator):
    """
    Checks if field's value is a valid email address. Can be set to disallow
    or force addresses from certain domain(s).

    Email regex adapted from 
    http://haacked.com/archive/2007/08/21/i-knew-how-to-validate-an-email-address-until-i.aspx,
    generally following the RFCs, except that we disallow quoted strings
    and permit underscores and leading numerics in subdomain labels

    Arguments:

    - banned: regex text for disallowed address domains
    - forced: regex text for required address domains

    Both arguments can also be custom objects with a match(value) method.

    Examples::

        #Check for valid email address:
        INPUT(_type='text', _name='name',
            requires=IS_EMAIL())

        #Check for valid email address that can't be from a .com domain:
        INPUT(_type='text', _name='name',
            requires=IS_EMAIL(banned='^.*\.com(|\..*)$'))

        #Check for valid email address that must be from a .edu domain:
        INPUT(_type='text', _name='name',
            requires=IS_EMAIL(forced='^.*\.edu(|\..*)$'))

        >>> IS_EMAIL()('a@b.com')
        ('a@b.com', None)
        >>> IS_EMAIL()('abc@def.com')
        ('abc@def.com', None)
        >>> IS_EMAIL()('abc@3def.com')
        ('abc@3def.com', None)
        >>> IS_EMAIL()('abc@def.us')
        ('abc@def.us', None)
        >>> IS_EMAIL()('abc@d_-f.us')
        ('abc@d_-f.us', None)
        >>> IS_EMAIL()('@def.com')           # missing name
        ('@def.com', 'enter a valid email address')
        >>> IS_EMAIL()('"abc@def".com')      # quoted name
        ('"abc@def".com', 'enter a valid email address')
        >>> IS_EMAIL()('abc+def.com')        # no @
        ('abc+def.com', 'enter a valid email address')
        >>> IS_EMAIL()('abc@def.x')          # one-char TLD
        ('abc@def.x', 'enter a valid email address')
        >>> IS_EMAIL()('abc@def.12')         # numeric TLD
        ('abc@def.12', 'enter a valid email address')
        >>> IS_EMAIL()('abc@def..com')       # double-dot in domain
        ('abc@def..com', 'enter a valid email address')
        >>> IS_EMAIL()('abc@.def.com')       # dot starts domain
        ('abc@.def.com', 'enter a valid email address')
        >>> IS_EMAIL()('abc@def.c_m')        # underscore in TLD
        ('abc@def.c_m', 'enter a valid email address')
        >>> IS_EMAIL()('NotAnEmail')         # missing @
        ('NotAnEmail', 'enter a valid email address')
        >>> IS_EMAIL()('abc@NotAnEmail')     # missing TLD
        ('abc@NotAnEmail', 'enter a valid email address')
        >>> IS_EMAIL()('customer/department@example.com')
        ('customer/department@example.com', None)
        >>> IS_EMAIL()('$A12345@example.com')
        ('$A12345@example.com', None)
        >>> IS_EMAIL()('!def!xyz%abc@example.com')
        ('!def!xyz%abc@example.com', None)
        >>> IS_EMAIL()('_Yosemite.Sam@example.com')
        ('_Yosemite.Sam@example.com', None)
        >>> IS_EMAIL()('~@example.com')
        ('~@example.com', None)
        >>> IS_EMAIL()('.wooly@example.com')       # dot starts name
        ('.wooly@example.com', 'enter a valid email address')
        >>> IS_EMAIL()('wo..oly@example.com')      # adjacent dots in name
        ('wo..oly@example.com', 'enter a valid email address')
        >>> IS_EMAIL()('pootietang.@example.com')  # dot ends name
        ('pootietang.@example.com', 'enter a valid email address')
        >>> IS_EMAIL()('.@example.com')            # name is bare dot
        ('.@example.com', 'enter a valid email address')
        >>> IS_EMAIL()('Ima.Fool@example.com')
        ('Ima.Fool@example.com', None)
        >>> IS_EMAIL()('Ima Fool@example.com')     # space in name
        ('Ima Fool@example.com', 'enter a valid email address')
    """

    regex = re.compile('''
        ^(?!\.)                            # name may not begin with a dot
        (
          [-a-z0-9!\#$%&'*+/=?^_`{|}~]     # all legal characters except dot
          |
          (?<!\.)\.                        # single dots only
        )+
        (?<!\.)                            # name may not end with a dot
        @
        (
          [a-z0-9]                         # [sub]domain begins with alphanumeric
          (
            [-\w]*                         # alphanumeric, underscore, dot, hyphen
            [a-z0-9]                       # ending alphanumeric
          )?
          \.                               # ending dot
        )+
        [a-z]{2,}$                         # TLD alpha-only
    ''', re.VERBOSE|re.IGNORECASE)

    def __init__(self,
                 banned=None,
                 forced=None,
                 error_message='enter a valid email address'):
        if isinstance(banned, str):
            banned = re.compile(banned)
        if isinstance(forced, str):
            forced = re.compile(forced)
        self.banned = banned
        self.forced = forced
        self.error_message = error_message

    def __call__(self, value):
        match = self.regex.match(value)
        if match:
            domain = value.split('@')[1]
            if (not self.banned or not self.banned.match(domain)) \
                    and (not self.forced or self.forced.match(domain)):
                return (value, None)
        return (value, self.error_message)


# URL scheme source:
# <http://en.wikipedia.org/wiki/URI_scheme> obtained on 2008-Nov-10

official_url_schemes = [
    'aaa',
    'aaas',
    'acap',
    'cap',
    'cid',
    'crid',
    'data',
    'dav',
    'dict',
    'dns',
    'fax',
    'file',
    'ftp',
    'go',
    'gopher',
    'h323',
    'http',
    'https',
    'icap',
    'im',
    'imap',
    'info',
    'ipp',
    'iris',
    'iris.beep',
    'iris.xpc',
    'iris.xpcs',
    'iris.lws',
    'ldap',
    'mailto',
    'mid',
    'modem',
    'msrp',
    'msrps',
    'mtqp',
    'mupdate',
    'news',
    'nfs',
    'nntp',
    'opaquelocktoken',
    'pop',
    'pres',
    'prospero',
    'rtsp',
    'service',
    'shttp',
    'sip',
    'sips',
    'snmp',
    'soap.beep',
    'soap.beeps',
    'tag',
    'tel',
    'telnet',
    'tftp',
    'thismessage',
    'tip',
    'tv',
    'urn',
    'vemmi',
    'wais',
    'xmlrpc.beep',
    'xmlrpc.beep',
    'xmpp',
    'z39.50r',
    'z39.50s',
    ]
unofficial_url_schemes = [
    'about',
    'adiumxtra',
    'aim',
    'afp',
    'aw',
    'callto',
    'chrome',
    'cvs',
    'ed2k',
    'feed',
    'fish',
    'gg',
    'gizmoproject',
    'iax2',
    'irc',
    'ircs',
    'itms',
    'jar',
    'javascript',
    'keyparc',
    'lastfm',
    'ldaps',
    'magnet',
    'mms',
    'msnim',
    'mvn',
    'notes',
    'nsfw',
    'psyc',
    'paparazzi:http',
    'rmi',
    'rsync',
    'secondlife',
    'sgn',
    'skype',
    'ssh',
    'sftp',
    'smb',
    'sms',
    'soldat',
    'steam',
    'svn',
    'teamspeak',
    'unreal',
    'ut2004',
    'ventrilo',
    'view-source',
    'webcal',
    'wyciwyg',
    'xfire',
    'xri',
    'ymsgr',
    ]
all_url_schemes = [None] + official_url_schemes + unofficial_url_schemes
http_schemes = [None, 'http', 'https']


# This regex comes from RFC 2396, Appendix B. It's used to split a URL into
# its component parts
# Here are the regex groups that it extracts:
#    scheme = group(2)
#    authority = group(4)
#    path = group(5)
#    query = group(7)
#    fragment = group(9)

url_split_regex = \
    re.compile('^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?')

# Defined in RFC 3490, Section 3.1, Requirement #1
# Use this regex to split the authority component of a unicode URL into
# its component labels
label_split_regex = re.compile(u'[\u002e\u3002\uff0e\uff61]')


def escape_unicode(string):
    '''
    Converts a unicode string into US-ASCII, using a simple conversion scheme.
    Each unicode character that does not have a US-ASCII equivalent is
    converted into a URL escaped form based on its hexadecimal value.
    For example, the unicode character '\u4e86' will become the string '%4e%86'

    :param string: unicode string, the unicode string to convert into an
        escaped US-ASCII form
    :returns: the US-ASCII escaped form of the inputted string
    :rtype: string

    @author: Jonathan Benn
    '''
    returnValue = StringIO()

    for character in string:
        code = ord(character)
        if code > 0x7F:
            hexCode = hex(code)
            returnValue.write('%' + hexCode[2:4] + '%' + hexCode[4:6])
        else:
            returnValue.write(character)

    return returnValue.getvalue()


def unicode_to_ascii_authority(authority):
    '''
    Follows the steps in RFC 3490, Section 4 to convert a unicode authority
    string into its ASCII equivalent.
    For example, u'www.Alliancefran\xe7aise.nu' will be converted into
    'www.xn--alliancefranaise-npb.nu'

    :param authority: unicode string, the URL authority component to convert,
                      e.g. u'www.Alliancefran\xe7aise.nu'
    :returns: the US-ASCII character equivalent to the inputed authority,
             e.g. 'www.xn--alliancefranaise-npb.nu'
    :rtype: string
    :raises Exception: if the function is not able to convert the inputed
        authority

    @author: Jonathan Benn
    '''
    #RFC 3490, Section 4, Step 1
    #The encodings.idna Python module assumes that AllowUnassigned == True

    #RFC 3490, Section 4, Step 2
    labels = label_split_regex.split(authority)

    #RFC 3490, Section 4, Step 3
    #The encodings.idna Python module assumes that UseSTD3ASCIIRules == False

    #RFC 3490, Section 4, Step 4
    #We use the ToASCII operation because we are about to put the authority
    #into an IDN-unaware slot
    asciiLabels = []
    try:
        import encodings.idna
        for label in labels:
            if label:
                asciiLabels.append(encodings.idna.ToASCII(label))
            else:
                 #encodings.idna.ToASCII does not accept an empty string, but
                 #it is necessary for us to allow for empty labels so that we
                 #don't modify the URL
                asciiLabels.append('')
    except:
        asciiLabels=[str(label) for label in labels]
    #RFC 3490, Section 4, Step 5
    return str(reduce(lambda x, y: x + unichr(0x002E) + y, asciiLabels))


def unicode_to_ascii_url(url, prepend_scheme):
    '''
    Converts the inputed unicode url into a US-ASCII equivalent. This function
    goes a little beyond RFC 3490, which is limited in scope to the domain name
    (authority) only. Here, the functionality is expanded to what was observed
    on Wikipedia on 2009-Jan-22:

       Component    Can Use Unicode?
       ---------    ----------------
       scheme       No
       authority    Yes
       path         Yes
       query        Yes
       fragment     No

    The authority component gets converted to punycode, but occurrences of
    unicode in other components get converted into a pair of URI escapes (we
    assume 4-byte unicode). E.g. the unicode character U+4E2D will be
    converted into '%4E%2D'. Testing with Firefox v3.0.5 has shown that it can
    understand this kind of URI encoding.

    :param url: unicode string, the URL to convert from unicode into US-ASCII
    :param prepend_scheme: string, a protocol scheme to prepend to the URL if
        we're having trouble parsing it.
        e.g. "http". Input None to disable this functionality
    :returns: a US-ASCII equivalent of the inputed url
    :rtype: string

    @author: Jonathan Benn
    '''
    #convert the authority component of the URL into an ASCII punycode string,
    #but encode the rest using the regular URI character encoding

    groups = url_split_regex.match(url).groups()
    #If no authority was found
    if not groups[3]:
        #Try appending a scheme to see if that fixes the problem
        scheme_to_prepend = prepend_scheme or 'http'
        groups = url_split_regex.match(
            unicode(scheme_to_prepend) + u'://' + url).groups()
    #if we still can't find the authority
    if not groups[3]:
        raise Exception('No authority component found, '+ \
            'could not decode unicode to US-ASCII')

    #We're here if we found an authority, let's rebuild the URL
    scheme = groups[1]
    authority = groups[3]
    path = groups[4] or ''
    query = groups[5] or ''
    fragment = groups[7] or ''

    if prepend_scheme:
        scheme = str(scheme) + '://'
    else:
        scheme = ''
    return scheme + unicode_to_ascii_authority(authority) +\
        escape_unicode(path) + escape_unicode(query) + str(fragment)


class IS_GENERIC_URL(Validator):
    """
    Rejects a URL string if any of the following is true:
       * The string is empty or None
       * The string uses characters that are not allowed in a URL
       * The URL scheme specified (if one is specified) is not valid

    Based on RFC 2396: http://www.faqs.org/rfcs/rfc2396.html

    This function only checks the URL's syntax. It does not check that the URL
    points to a real document, for example, or that it otherwise makes sense
    semantically. This function does automatically prepend 'http://' in front
    of a URL if and only if that's necessary to successfully parse the URL.
    Please note that a scheme will be prepended only for rare cases
    (e.g. 'google.ca:80')

    The list of allowed schemes is customizable with the allowed_schemes
    parameter. If you exclude None from the list, then abbreviated URLs
    (lacking a scheme such as 'http') will be rejected.

    The default prepended scheme is customizable with the prepend_scheme
    parameter. If you set prepend_scheme to None then prepending will be
    disabled. URLs that require prepending to parse will still be accepted,
    but the return value will not be modified.

    @author: Jonathan Benn
    """

    def __init__(
        self,
        error_message='enter a valid URL',
        allowed_schemes=None,
        prepend_scheme=None,
        ):
        """
        :param error_message: a string, the error message to give the end user
            if the URL does not validate
        :param allowed_schemes: a list containing strings or None. Each element
            is a scheme the inputed URL is allowed to use
        :param prepend_scheme: a string, this scheme is prepended if it's
            necessary to make the URL valid
        """

        self.error_message = error_message
        if allowed_schemes == None:
            self.allowed_schemes = all_url_schemes
        else:
            self.allowed_schemes = allowed_schemes
        self.prepend_scheme = prepend_scheme
        if self.prepend_scheme not in self.allowed_schemes:
            raise SyntaxError, \
                "prepend_scheme='%s' is not in allowed_schemes=%s" \
                % (self.prepend_scheme, self.allowed_schemes)

    def __call__(self, value):
        """
        :param value: a string, the URL to validate
        :returns: a tuple, where tuple[0] is the inputed value (possible
            prepended with prepend_scheme), and tuple[1] is either
            None (success!) or the string error_message
        """
        try:
            # if the URL does not misuse the '%' character
            if not re.compile(
                r"%[^0-9A-Fa-f]{2}|%[^0-9A-Fa-f][0-9A-Fa-f]|%[0-9A-Fa-f][^0-9A-Fa-f]|%$|%[0-9A-Fa-f]$|%[^0-9A-Fa-f]$"
                              ).search(value):
                # if the URL is only composed of valid characters
                if re.compile(
                    r"[A-Za-z0-9;/?:@&=+$,\-_\.!~*'\(\)%#]+$").match(value):
                    # Then split up the URL into its components and check on
                    # the scheme
                    scheme = url_split_regex.match(value).group(2)
                    # Clean up the scheme before we check it
                    if scheme != None:
                        scheme = urllib.unquote(scheme).lower()
                    # If the scheme really exists
                    if scheme in self.allowed_schemes:
                        # Then the URL is valid
                        return (value, None)
                    else:
                        # else, for the possible case of abbreviated URLs with
                        # ports, check to see if adding a valid scheme fixes
                        # the problem (but only do this if it doesn't have
                        # one already!)
                        if not re.compile('://').search(value) and None\
                             in self.allowed_schemes:
                            schemeToUse = self.prepend_scheme or 'http'
                            prependTest = self.__call__(schemeToUse
                                     + '://' + value)
                            # if the prepend test succeeded
                            if prependTest[1] == None:
                                # if prepending in the output is enabled
                                if self.prepend_scheme:
                                    return prependTest
                                else:
                                    # else return the original,
                                    #  non-prepended value
                                    return (value, None)
        except:
            pass
        # else the URL is not valid
        return (value, self.error_message)

# Sources (obtained 2008-Nov-11):
#    http://en.wikipedia.org/wiki/Top-level_domain
#    http://www.iana.org/domains/root/db/

official_top_level_domains = [
    'ac',
    'ad',
    'ae',
    'aero',
    'af',
    'ag',
    'ai',
    'al',
    'am',
    'an',
    'ao',
    'aq',
    'ar',
    'arpa',
    'as',
    'asia',
    'at',
    'au',
    'aw',
    'ax',
    'az',
    'ba',
    'bb',
    'bd',
    'be',
    'bf',
    'bg',
    'bh',
    'bi',
    'biz',
    'bj',
    'bl',
    'bm',
    'bn',
    'bo',
    'br',
    'bs',
    'bt',
    'bv',
    'bw',
    'by',
    'bz',
    'ca',
    'cat',
    'cc',
    'cd',
    'cf',
    'cg',
    'ch',
    'ci',
    'ck',
    'cl',
    'cm',
    'cn',
    'co',
    'com',
    'coop',
    'cr',
    'cu',
    'cv',
    'cx',
    'cy',
    'cz',
    'de',
    'dj',
    'dk',
    'dm',
    'do',
    'dz',
    'ec',
    'edu',
    'ee',
    'eg',
    'eh',
    'er',
    'es',
    'et',
    'eu',
    'example',
    'fi',
    'fj',
    'fk',
    'fm',
    'fo',
    'fr',
    'ga',
    'gb',
    'gd',
    'ge',
    'gf',
    'gg',
    'gh',
    'gi',
    'gl',
    'gm',
    'gn',
    'gov',
    'gp',
    'gq',
    'gr',
    'gs',
    'gt',
    'gu',
    'gw',
    'gy',
    'hk',
    'hm',
    'hn',
    'hr',
    'ht',
    'hu',
    'id',
    'ie',
    'il',
    'im',
    'in',
    'info',
    'int',
    'invalid',
    'io',
    'iq',
    'ir',
    'is',
    'it',
    'je',
    'jm',
    'jo',
    'jobs',
    'jp',
    'ke',
    'kg',
    'kh',
    'ki',
    'km',
    'kn',
    'kp',
    'kr',
    'kw',
    'ky',
    'kz',
    'la',
    'lb',
    'lc',
    'li',
    'lk',
    'localhost',
    'lr',
    'ls',
    'lt',
    'lu',
    'lv',
    'ly',
    'ma',
    'mc',
    'md',
    'me',
    'mf',
    'mg',
    'mh',
    'mil',
    'mk',
    'ml',
    'mm',
    'mn',
    'mo',
    'mobi',
    'mp',
    'mq',
    'mr',
    'ms',
    'mt',
    'mu',
    'museum',
    'mv',
    'mw',
    'mx',
    'my',
    'mz',
    'na',
    'name',
    'nc',
    'ne',
    'net',
    'nf',
    'ng',
    'ni',
    'nl',
    'no',
    'np',
    'nr',
    'nu',
    'nz',
    'om',
    'org',
    'pa',
    'pe',
    'pf',
    'pg',
    'ph',
    'pk',
    'pl',
    'pm',
    'pn',
    'pr',
    'pro',
    'ps',
    'pt',
    'pw',
    'py',
    'qa',
    're',
    'ro',
    'rs',
    'ru',
    'rw',
    'sa',
    'sb',
    'sc',
    'sd',
    'se',
    'sg',
    'sh',
    'si',
    'sj',
    'sk',
    'sl',
    'sm',
    'sn',
    'so',
    'sr',
    'st',
    'su',
    'sv',
    'sy',
    'sz',
    'tc',
    'td',
    'tel',
    'test',
    'tf',
    'tg',
    'th',
    'tj',
    'tk',
    'tl',
    'tm',
    'tn',
    'to',
    'tp',
    'tr',
    'travel',
    'tt',
    'tv',
    'tw',
    'tz',
    'ua',
    'ug',
    'uk',
    'um',
    'us',
    'uy',
    'uz',
    'va',
    'vc',
    've',
    'vg',
    'vi',
    'vn',
    'vu',
    'wf',
    'ws',
    'xn--0zwm56d',
    'xn--11b5bs3a9aj6g',
    'xn--80akhbyknj4f',
    'xn--9t4b11yi5a',
    'xn--deba0ad',
    'xn--g6w251d',
    'xn--hgbk6aj7f53bba',
    'xn--hlcj6aya9esc7a',
    'xn--jxalpdlp',
    'xn--kgbechtv',
    'xn--zckzah',
    'ye',
    'yt',
    'yu',
    'za',
    'zm',
    'zw',
    ]


class IS_HTTP_URL(Validator):
    """
    Rejects a URL string if any of the following is true:
       * The string is empty or None
       * The string uses characters that are not allowed in a URL
       * The string breaks any of the HTTP syntactic rules
       * The URL scheme specified (if one is specified) is not 'http' or 'https'
       * The top-level domain (if a host name is specified) does not exist

    Based on RFC 2616: http://www.faqs.org/rfcs/rfc2616.html

    This function only checks the URL's syntax. It does not check that the URL
    points to a real document, for example, or that it otherwise makes sense
    semantically. This function does automatically prepend 'http://' in front
    of a URL in the case of an abbreviated URL (e.g. 'google.ca').

    The list of allowed schemes is customizable with the allowed_schemes
    parameter. If you exclude None from the list, then abbreviated URLs
    (lacking a scheme such as 'http') will be rejected.

    The default prepended scheme is customizable with the prepend_scheme
    parameter. If you set prepend_scheme to None then prepending will be
    disabled. URLs that require prepending to parse will still be accepted,
    but the return value will not be modified.

    @author: Jonathan Benn
    """

    def __init__(
        self,
        error_message='enter a valid URL',
        allowed_schemes=None,
        prepend_scheme='http',
        ):
        """
        :param error_message: a string, the error message to give the end user
            if the URL does not validate
        :param allowed_schemes: a list containing strings or None. Each element
            is a scheme the inputed URL is allowed to use
        :param prepend_scheme: a string, this scheme is prepended if it's
            necessary to make the URL valid
        """

        self.error_message = error_message
        if allowed_schemes == None:
            self.allowed_schemes = http_schemes
        else:
            self.allowed_schemes = allowed_schemes
        self.prepend_scheme = prepend_scheme

        for i in self.allowed_schemes:
            if i not in http_schemes:
                raise SyntaxError, \
                    "allowed_scheme value '%s' is not in %s" % \
                    (i, http_schemes)

        if self.prepend_scheme not in self.allowed_schemes:
            raise SyntaxError, \
                "prepend_scheme='%s' is not in allowed_schemes=%s" % \
                (self.prepend_scheme, self.allowed_schemes)

    def __call__(self, value):
        """
        :param value: a string, the URL to validate
        :returns: a tuple, where tuple[0] is the inputed value
            (possible prepended with prepend_scheme), and tuple[1] is either
            None (success!) or the string error_message
        """

        try:
            # if the URL passes generic validation
            x = IS_GENERIC_URL(error_message=self.error_message,
                               allowed_schemes=self.allowed_schemes,
                               prepend_scheme=self.prepend_scheme)
            if x(value)[1] == None:
                componentsMatch = url_split_regex.match(value)
                authority = componentsMatch.group(4)
                # if there is an authority component
                if authority:
                    # if authority is a valid IP address
                    if re.compile(
                        '\d+\.\d+\.\d+\.\d+(:\d*)*$').match(authority):
                        # Then this HTTP URL is valid
                        return (value, None)
                    else:
                        # else if authority is a valid domain name
                        domainMatch = \
                            re.compile(
                                '(([A-Za-z0-9]+[A-Za-z0-9\-]*[A-Za-z0-9]+\.)*([A-Za-z0-9]+\.)*)*([A-Za-z]+[A-Za-z0-9\-]*[A-Za-z0-9]+)\.?(:\d*)*$'
                                ).match(authority)
                        if domainMatch:
                            # if the top-level domain really exists
                            if domainMatch.group(4).lower()\
                                 in official_top_level_domains:
                                # Then this HTTP URL is valid
                                return (value, None)
                else:
                    # else this is a relative/abbreviated URL, which will parse
                    # into the URL's path component
                    path = componentsMatch.group(5)
                    # relative case: if this is a valid path (if it starts with
                    # a slash)
                    if re.compile('/').match(path):
                        # Then this HTTP URL is valid
                        return (value, None)
                    else:
                        # abbreviated case: if we haven't already, prepend a
                        # scheme and see if it fixes the problem
                        if not re.compile('://').search(value):
                            schemeToUse = self.prepend_scheme or 'http'
                            prependTest = self.__call__(schemeToUse
                                     + '://' + value)
                            # if the prepend test succeeded
                            if prependTest[1] == None:
                                # if prepending in the output is enabled
                                if self.prepend_scheme:
                                    return prependTest
                                else:
                                    # else return the original, non-prepended
                                    # value
                                    return (value, None)
        except:
            pass
        # else the HTTP URL is not valid
        return (value, self.error_message)


class IS_URL(Validator):
    """
    Rejects a URL string if any of the following is true:
       * The string is empty or None
       * The string uses characters that are not allowed in a URL
       * The string breaks any of the HTTP syntactic rules
       * The URL scheme specified (if one is specified) is not 'http' or 'https'
       * The top-level domain (if a host name is specified) does not exist

    (These rules are based on RFC 2616: http://www.faqs.org/rfcs/rfc2616.html)

    This function only checks the URL's syntax. It does not check that the URL
    points to a real document, for example, or that it otherwise makes sense
    semantically. This function does automatically prepend 'http://' in front
    of a URL in the case of an abbreviated URL (e.g. 'google.ca').

    If the parameter mode='generic' is used, then this function's behavior
    changes. It then rejects a URL string if any of the following is true:
       * The string is empty or None
       * The string uses characters that are not allowed in a URL
       * The URL scheme specified (if one is specified) is not valid

    (These rules are based on RFC 2396: http://www.faqs.org/rfcs/rfc2396.html)

    The list of allowed schemes is customizable with the allowed_schemes
    parameter. If you exclude None from the list, then abbreviated URLs
    (lacking a scheme such as 'http') will be rejected.

    The default prepended scheme is customizable with the prepend_scheme
    parameter. If you set prepend_scheme to None then prepending will be
    disabled. URLs that require prepending to parse will still be accepted,
    but the return value will not be modified.

    IS_URL is compatible with the Internationalized Domain Name (IDN) standard
    specified in RFC 3490 (http://tools.ietf.org/html/rfc3490). As a result,
    URLs can be regular strings or unicode strings.
    If the URL's domain component (e.g. google.ca) contains non-US-ASCII
    letters, then the domain will be converted into Punycode (defined in
    RFC 3492, http://tools.ietf.org/html/rfc3492). IS_URL goes a bit beyond
    the standards, and allows non-US-ASCII characters to be present in the path
    and query components of the URL as well. These non-US-ASCII characters will
    be escaped using the standard '%20' type syntax. e.g. the unicode
    character with hex code 0x4e86 will become '%4e%86'

    Code Examples::

        INPUT(_type='text', _name='name', requires=IS_URL())
        INPUT(_type='text', _name='name', requires=IS_URL(mode='generic'))
        INPUT(_type='text', _name='name',
            requires=IS_URL(allowed_schemes=['https']))
        INPUT(_type='text', _name='name',
            requires=IS_URL(prepend_scheme='https'))
        INPUT(_type='text', _name='name',
            requires=IS_URL(mode='generic', allowed_schemes=['ftps', 'https'],
                prepend_scheme='https'))

    @author: Jonathan Benn
    """

    def __init__(
        self,
        error_message='enter a valid URL',
        mode='http',
        allowed_schemes=None,
        prepend_scheme='http',
        ):
        """
        :param error_message: a string, the error message to give the end user
            if the URL does not validate
        :param allowed_schemes: a list containing strings or None. Each element
            is a scheme the inputed URL is allowed to use
        :param prepend_scheme: a string, this scheme is prepended if it's
            necessary to make the URL valid
        """

        self.error_message = error_message
        self.mode = mode.lower()
        if not self.mode in ['generic', 'http']:
            raise SyntaxError, "invalid mode '%s' in IS_URL" % self.mode
        self.allowed_schemes = allowed_schemes

        if self.allowed_schemes:
            if prepend_scheme not in self.allowed_schemes:
                raise SyntaxError, \
                    "prepend_scheme='%s' is not in allowed_schemes=%s" \
                    % (prepend_scheme, self.allowed_schemes)

        # if allowed_schemes is None, then we will defer testing
        # prepend_scheme's validity to a sub-method

        self.prepend_scheme = prepend_scheme

    def __call__(self, value):
        """
        :param value: a unicode or regular string, the URL to validate
        :returns: a (string, string) tuple, where tuple[0] is the modified
            input value and tuple[1] is either None (success!) or the
            string error_message. The input value will never be modified in the
            case of an error. However, if there is success then the input URL
            may be modified to (1) prepend a scheme, and/or (2) convert a
            non-compliant unicode URL into a compliant US-ASCII version.
        """

        if self.mode == 'generic':
            subMethod = IS_GENERIC_URL(error_message=self.error_message,
                                       allowed_schemes=self.allowed_schemes,
                                       prepend_scheme=self.prepend_scheme)
        elif self.mode == 'http':
            subMethod = IS_HTTP_URL(error_message=self.error_message,
                                    allowed_schemes=self.allowed_schemes,
                                    prepend_scheme=self.prepend_scheme)
        else:
            raise SyntaxError, "invalid mode '%s' in IS_URL" % self.mode

        if type(value) != unicode:
            return subMethod(value)
        else:
            try:
                asciiValue = unicode_to_ascii_url(value, self.prepend_scheme)
            except Exception, e:
                #If we are not able to convert the unicode url into a
                # US-ASCII URL, then the URL is not valid
                return (value, self.error_message)

            methodResult = subMethod(asciiValue)
            #if the validation of the US-ASCII version of the value failed
            if methodResult[1] != None:
                # then return the original input value, not the US-ASCII version
                return (value, methodResult[1])
            else:
                return methodResult


regex_time = re.compile(
    '((?P<h>[0-9]+))([^0-9 ]+(?P<m>[0-9 ]+))?([^0-9ap ]+(?P<s>[0-9]*))?((?P<d>[ap]m))?')


class IS_TIME(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_TIME())

    understands the following formats
    hh:mm:ss [am/pm]
    hh:mm [am/pm]
    hh [am/pm]

    [am/pm] is optional, ':' can be replaced by any other non-space non-digit

        >>> IS_TIME()('21:30')
        (datetime.time(21, 30), None)
        >>> IS_TIME()('21-30')
        (datetime.time(21, 30), None)
        >>> IS_TIME()('21.30')
        (datetime.time(21, 30), None)
        >>> IS_TIME()('21:30:59')
        (datetime.time(21, 30, 59), None)
        >>> IS_TIME()('5:30')
        (datetime.time(5, 30), None)
        >>> IS_TIME()('5:30 am')
        (datetime.time(5, 30), None)
        >>> IS_TIME()('5:30 pm')
        (datetime.time(17, 30), None)
        >>> IS_TIME()('5:30 whatever')
        ('5:30 whatever', 'enter time as hh:mm:ss (seconds, am, pm optional)')
        >>> IS_TIME()('5:30 20')
        ('5:30 20', 'enter time as hh:mm:ss (seconds, am, pm optional)')
        >>> IS_TIME()('24:30')
        ('24:30', 'enter time as hh:mm:ss (seconds, am, pm optional)')
        >>> IS_TIME()('21:60')
        ('21:60', 'enter time as hh:mm:ss (seconds, am, pm optional)')
        >>> IS_TIME()('21:30::')
        ('21:30::', 'enter time as hh:mm:ss (seconds, am, pm optional)')
        >>> IS_TIME()('')
        ('', 'enter time as hh:mm:ss (seconds, am, pm optional)')
    """

    def __init__(self, error_message='enter time as hh:mm:ss (seconds, am, pm optional)'):
        self.error_message = error_message

    def __call__(self, value):
        try:
            ivalue = value
            value = regex_time.match(value.lower())
            (h, m, s) = (int(value.group('h')), 0, 0)
            if value.group('m') != None:
                m = int(value.group('m'))
            if value.group('s') != None:
                s = int(value.group('s'))
            if value.group('d') == 'pm' and 0 < h < 12:
                h = h + 12
            if not (h in range(24) and m in range(60) and s
                     in range(60)):
                raise ValueError\
                    ('Hours or minutes or seconds are outside of allowed range')
            value = datetime.time(h, m, s)
            return (value, None)
        except AttributeError:
            pass
        except ValueError:
            pass
        return (ivalue, self.error_message)


class IS_DATE(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_DATE())

    date has to be in the ISO8960 format YYYY-MM-DD
    """

    def __init__(self, format='%Y-%m-%d',
                 error_message='enter date as %(format)s'):
        self.format = format
        self.error_message = error_message

    def __call__(self, value):
        try:
            (y, m, d, hh, mm, ss, t0, t1, t2) = \
                time.strptime(value, str(self.format))
            value = datetime.date(y, m, d)
            return (value, None)
        except:
            return (value, self.error_message % IS_DATETIME.nice(self.format))

    def formatter(self, value):
        return value.strftime(str(self.format))


class IS_DATETIME(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=IS_DATETIME())

    datetime has to be in the ISO8960 format YYYY-MM-DD hh:mm:ss
    """

    isodatetime = '%Y-%m-%d %H:%M:%S'

    @staticmethod
    def nice(format):
        code=(('%Y','1963'),
              ('%y','63'),
              ('%d','28'),
              ('%m','08'),
              ('%b','Aug'),
              ('%b','August'),
              ('%H','14'),
              ('%I','02'),
              ('%p','PM'),
              ('%M','30'),
              ('%S','59'))
        for (a,b) in code:
            format=format.replace(a,b)
        return dict(format=format)

    def __init__(self, format='%Y-%m-%d %H:%M:%S',
                 error_message='enter date and time as %(format)s'):
        self.format = format
        self.error_message = error_message

    def __call__(self, value):
        try:
            (y, m, d, hh, mm, ss, t0, t1, t2) = \
                time.strptime(value, str(self.format))
            value = datetime.datetime(y, m, d, hh, mm, ss)
            return (value, None)
        except:
            return (value, self.error_message % IS_DATETIME.nice(self.format))

    def formatter(self, value):
        return value.strftime(str(self.format))


class IS_LIST_OF(Validator):

    def __init__(self, other):
        self.other = other

    def __call__(self, value):
        ivalue = value
        if not isinstance(value, list):
            ivalue = [ivalue]
        new_value = []
        for item in ivalue:
            (v, e) = self.other(item)
            if e:
                return (value, e)
            else:
                new_value.append(v)
        return (new_value, None)


class IS_LOWER(Validator):
    """
    convert to lower case

    >>> IS_LOWER()('ABC')
    ('abc', None)
    >>> IS_LOWER()('Ñ')
    ('\\xc3\\xb1', None)
    """

    def __call__(self, value):
        return (value.decode('utf8').lower().encode('utf8'), None)


class IS_UPPER(Validator):
    """
    convert to upper case

    >>> IS_UPPER()('abc')
    ('ABC', None)
    >>> IS_UPPER()('ñ')
    ('\\xc3\\x91', None)
    """

    def __call__(self, value):
        return (value.decode('utf8').upper().encode('utf8'), None)


class IS_EMPTY_OR(Validator):
    """
    dummy class for testing IS_EMPTY_OR

    >>> IS_EMPTY_OR(IS_EMAIL())('abc@def.com')
    ('abc@def.com', None)
    >>> IS_EMPTY_OR(IS_EMAIL())('   ')
    (None, None)
    >>> IS_EMPTY_OR(IS_EMAIL(), null='abc')('   ')
    ('abc', None)
    >>> IS_EMPTY_OR(IS_EMAIL(), null='abc', empty_regex='def')('def')
    ('abc', None)
    >>> IS_EMPTY_OR(IS_EMAIL())('abc')
    ('abc', 'enter a valid email address')
    >>> IS_EMPTY_OR(IS_EMAIL())(' abc ')
    ('abc', 'enter a valid email address')
    """

    def __init__(self, other, null=None, empty_regex=None):
        (self.other, self.null) = (other, null)
        if empty_regex is not None:
            self.empty_regex = re.compile(empty_regex)
        else:
            self.empty_regex = None
        if hasattr(other, 'multiple'):
            self.multiple = other.multiple

    def set_self_id(self, id):
        if hasattr(self.other, 'set_self_id'):
            self.other.set_self_id(id)

    def __call__(self, value):
        value, empty = is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return (self.null, None)
        return self.other(value)

    def formatter(self, value):
        if hasattr(self.other, 'formatter'):
            return self.other.formatter(value)
        return value


IS_NULL_OR = IS_EMPTY_OR    # for backward compatibility


class CLEANUP(Validator):
    """
    example::

        INPUT(_type='text', _name='name', requires=CLEANUP())

    removes special characters on validation
    """

    def __init__(self, regex='[^ \n\w]'):
        self.regex = re.compile(regex)

    def __call__(self, value):        
        v = self.regex.sub('',str(value).strip())
        return (v, None)


class CRYPT(object):
    """
    example::

        INPUT(_type='text', _name='name', requires=CRYPT())

    encodes the value on validation with a digest.
    
    If no arguments are provided CRYPT uses the MD5 algorithm.
    If the key argument is provided the HMAC+MD5 algorithm is used.
    If the digest_alg is specified this is used to replace the
    MD5 with, for example, SHA512. The digest_alg can be
    the name of a hashlib algorithm as a string or the algorithm itself.
    """

    def __init__(self, key=None, digest_alg=None):
        if key and not digest_alg:
            if key.count(':')==1:
                (digest_alg, key) = key.split(':')
        if not digest_alg:
            digest_alg = 'md5' # for backward compatibility
        self.key = key
        self.digest_alg = digest_alg

    def __call__(self, value):
        if self.key:
            alg = get_digest(self.digest_alg)
            return (hmac.new(self.key, value, alg).hexdigest(), None)
        else:
            return (hash(value, self.digest_alg), None)


class IS_STRONG(object):
    """
    example::

        INPUT(_type='password', _name='passwd',
            requires=IS_STRONG(min=10, special=2, upper=2))

    enforces complexity requirements on a field
    """

    def __init__(self, min=8, max=20, upper=1, lower=1, number=1,
                 special=1, specials=r'~!@#$%^&*()_+-=?<>,.:;{}[]|',
                 invalid=' "', error_message=None):
        self.min = min
        self.max = max
        self.upper = upper
        self.lower = lower
        self.number = number
        self.special = special
        self.specials = specials
        self.invalid = invalid
        self.error_message = error_message

    def __call__(self, value):
        failures = []
        if type(self.min) == int and self.min > 0:
            if not len(value) >= self.min:
                failures.append("Minimum length is %s" % self.min)
        if type(self.max) == int and self.max > 0:
            if not len(value) <= self.max:
                failures.append("Maximum length is %s" % self.max)
        if type(self.special) == int:
            all_special = [ch in value for ch in self.specials]
            if self.special > 0:
                if not all_special.count(True) >= self.special:
                    failures.append("Must include at least %s of the following : %s" % (self.special, self.specials))
        if self.invalid:
            all_invalid = [ch in value for ch in self.invalid]
            if all_invalid.count(True) > 0:
                failures.append("May not contain any of the following: %s" \
                    % self.invalid)
        if type(self.upper) == int:
            all_upper = re.findall("[A-Z]", value)
            if self.upper > 0:
                if not len(all_upper) >= self.upper:
                    failures.append("Must include at least %s upper case" \
                        % str(self.upper))
            else:
                if len(all_upper) > 0:
                    failures.append("May not include any upper case letters")
        if type(self.lower) == int:
            all_lower = re.findall("[a-z]", value)
            if self.lower > 0:
                if not len(all_lower) >= self.lower:
                    failures.append("Must include at least %s lower case" \
                        % str(self.lower))
            else:
                if len(all_lower) > 0:
                    failures.append("May not include any lower case letters")
        if type(self.number) == int:
            all_number = re.findall("[0-9]", value)
            if self.number > 0:
                numbers = "number"
                if self.number > 1:
                    numbers = "numbers"
                if not len(all_number) >= self.number:
                    failures.append("Must include at least %s %s" \
                        % (str(self.number), numbers))
            else:
                if len(all_number) > 0:
                    failures.append("May not include any numbers")
        if len(failures) == 0:
            return (value, None)
        if not self.error_message:
            from gluon.html import XML
            return (value, XML('<br />'.join(failures)))
        else:
            return (value, self.error_message)


class IS_IN_SUBSET(IS_IN_SET):

    def __init__(self, *a, **b):
        IS_IN_SET.__init__(self, *a, **b)

    def __call__(self, value):
        values = re.compile("\w+").findall(str(value))
        failures = [x for x in values if IS_IN_SET.__call__(self, x)[1]]
        if failures:
            return (value, self.error_message)
        return (value, None)


class IS_IMAGE(Validator):
    """
    Checks if file uploaded through file input was saved in one of selected
    image formats and has dimensions (width and height) within given boundaries.

    Does *not* check for maximum file size (use IS_LENGTH for that). Returns
    validation failure if no data was uploaded.

    Supported file formats: BMP, GIF, JPEG, PNG.

    Code parts taken from
    http://mail.python.org/pipermail/python-list/2007-June/617126.html

    Arguments:

    extensions: iterable containing allowed *lowercase* image file extensions
    ('jpg' extension of uploaded file counts as 'jpeg')
    maxsize: iterable containing maximum width and height of the image
    minsize: iterable containing minimum width and height of the image

    Use (-1, -1) as minsize to pass image size check.

    Examples::

        #Check if uploaded file is in any of supported image formats:
        INPUT(_type='file', _name='name', requires=IS_IMAGE())

        #Check if uploaded file is either JPEG or PNG:
        INPUT(_type='file', _name='name',
            requires=IS_IMAGE(extensions=('jpeg', 'png')))

        #Check if uploaded file is PNG with maximum size of 200x200 pixels:
        INPUT(_type='file', _name='name',
            requires=IS_IMAGE(extensions=('png'), maxsize=(200, 200)))
    """

    def __init__(self,
                 extensions=('bmp', 'gif', 'jpeg', 'png'),
                 maxsize=(10000, 10000),
                 minsize=(0, 0),
                 error_message='invalid image'):

        self.extensions = extensions
        self.maxsize = maxsize
        self.minsize = minsize
        self.error_message = error_message

    def __call__(self, value):
        try:
            extension = value.filename.rfind('.')
            assert extension >= 0
            extension = value.filename[extension + 1:].lower()
            if extension == 'jpg':
                extension = 'jpeg'
            assert extension in self.extensions
            if extension == 'bmp':
                width, height = self.__bmp(value.file)
            elif extension == 'gif':
                width, height = self.__gif(value.file)
            elif extension == 'jpeg':
                width, height = self.__jpeg(value.file)
            elif extension == 'png':
                width, height = self.__png(value.file)
            else:
                width = -1
                height = -1
            assert self.minsize[0] <= width <= self.maxsize[0] \
                and self.minsize[1] <= height <= self.maxsize[1]
            value.file.seek(0)
            return (value, None)
        except:
            return (value, self.error_message)

    def __bmp(self, stream):
        if stream.read(2) == 'BM':
            stream.read(16)
            return struct.unpack("<LL", stream.read(8))
        return (-1, -1)

    def __gif(self, stream):
        if stream.read(6) in ('GIF87a', 'GIF89a'):
            stream = stream.read(5)
            if len(stream) == 5:
                return tuple(struct.unpack("<HHB", stream)[:-1])
        return (-1, -1)

    def __jpeg(self, stream):
        if stream.read(2) == '\xFF\xD8':
            while True:
                (marker, code, length) = struct.unpack("!BBH", stream.read(4))
                if marker != 0xFF:
                    break
                elif code >= 0xC0 and code <= 0xC3:
                    return tuple(reversed(
                        struct.unpack("!xHH", stream.read(5))))
                else:
                    stream.read(length - 2)
        return (-1, -1)

    def __png(self, stream):
        if stream.read(8) == '\211PNG\r\n\032\n':
            stream.read(4)
            if stream.read(4) == "IHDR":
                return struct.unpack("!LL", stream.read(8))
        return (-1, -1)


class IS_UPLOAD_FILENAME(Validator):
    """
    Checks if name and extension of file uploaded through file input matches
    given criteria.

    Does *not* ensure the file type in any way. Returns validation failure
    if no data was uploaded.

    Arguments::

    filename: filename (before dot) regex
    extension: extension (after dot) regex
    lastdot: which dot should be used as a filename / extension separator:
             True means last dot, eg. file.png -> file / png
             False means first dot, eg. file.tar.gz -> file / tar.gz
    case: 0 - keep the case, 1 - transform the string into lowercase (default),
          2 - transform the string into uppercase

    If there is no dot present, extension checks will be done against empty
    string and filename checks against whole value.

    Examples::

        #Check if file has a pdf extension (case insensitive):
        INPUT(_type='file', _name='name',
            requires=IS_UPLOAD_FILENAME(extension='pdf'))

        #Check if file has a tar.gz extension and name starting with backup:
        INPUT(_type='file', _name='name',
            requires=IS_UPLOAD_FILENAME(filename='backup.*',
                extension='tar.gz', lastdot=False))

        #Check if file has no extension and name matching README
        #(case sensitive):
        INPUT(_type='file', _name='name',
            requires=IS_UPLOAD_FILENAME(filename='^README$',
                extension='^$', case=0))
    """

    def __init__(self, filename=None, extension=None, lastdot=True, case=1,
            error_message='enter valid filename'):
        if isinstance(filename, str):
            filename = re.compile(filename)
        if isinstance(extension, str):
            extension = re.compile(extension)
        self.filename = filename
        self.extension = extension
        self.lastdot = lastdot
        self.case = case
        self.error_message = error_message

    def __call__(self, value):
        try:
            string = value.filename
        except:
            return (value, self.error_message)
        if self.case == 1:
            string = string.lower()
        elif self.case == 2:
            string = string.upper()
        if self.lastdot:
            dot = string.rfind('.')
        else:
            dot = string.find('.')
        if dot == -1:
            dot = len(string)
        if self.filename and not self.filename.match(string[:dot]):
            return (value, self.error_message)
        elif self.extension and not self.extension.match(string[dot + 1:]):
            return (value, self.error_message)
        else:
            return (value, None)


class IS_IPV4(Validator):
    """
    Checks if field's value is an IP version 4 address in decimal form. Can
    be set to force addresses from certain range.

    IPv4 regex taken from: http://regexlib.com/REDetails.aspx?regexp_id=1411

    Arguments:

    minip: lowest allowed address; accepts:
           str, eg. 192.168.0.1
           iterable of numbers, eg. [192, 168, 0, 1]
           int, eg. 3232235521
    maxip: highest allowed address; same as above

    All three example values are equal, since addresses are converted to
    integers for inclusion check with following function:

    number = 16777216 * IP[0] + 65536 * IP[1] + 256 * IP[2] + IP[3]

    Examples::

        #Check for valid IPv4 address:
        INPUT(_type='text', _name='name', requires=IS_IPV4())

        #Check for valid private network IPv4 address:
        INPUT(_type='text', _name='name',
            requires=IS_IPV4(minip='192.168.0.1', maxip='192.168.255.255'))
    """

    regex = re.compile(
        '^(([1-9]?\d|1\d\d|2[0-4]\d|25[0-5]).){3}([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])$')
    numbers = (16777216, 65536, 256, 1)

    def __init__(self, minip='0.0.0.0', maxip='255.255.255.255',
            error_message='enter valid IPv4 address'):
        if isinstance(minip, str):
            minip = map(int, minip.split('.'))
        if isinstance(minip, (list, tuple)):
            self.minip = 0
            for i, j in zip(self.numbers, minip):
                self.minip += i * j
        else:
            self.minip = minip
        if isinstance(maxip, str):
            maxip = map(int, maxip.split('.'))
        if isinstance(maxip, (list, tuple)):
            self.maxip = 0
            for i, j in zip(self.numbers, maxip):
                self.maxip += i * j
        else:
            self.maxip = maxip
        self.error_message = error_message

    def __call__(self, value):
        if self.regex.match(value):
            ip = 0
            for i, j in zip(self.numbers, value[:15].split('.')):
                ip += i * int(j)
            if self.minip <= ip <= self.maxip:
                return (value, None)
        return (value, self.error_message)

if __name__ == '__main__':
    import doctest
    doctest.testmod()
