#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import xml.parsers.expat as expat

"""
This module should never be run by end user. It's purpose is developer
only: to ease the updates of MIME database in gluon.contenttype.py module.
"""


class MIMEParser():
    """
    Parses MIME database xml file from freedesktop.org and formats the result
    dictionary for easy copy to contenttype.py. Input file must be present in
    the local filesystem (may be obtained from most recent tarball at
    http://freedesktop.org/wiki/Software/shared-mime-info. File name in
    the archive is 'freedesktop.org.xml').
    """

    def __start_element_handler(self, name, attrs):
        """
        Tag open handler.
        """

        if name == 'mime-type':
            if self.type:
                for extension in self.extensions:
                    self.content_type[extension] = self.type
            self.type = attrs['type'].lower()
            self.extensions = []
        elif name == 'glob':
            pattern = attrs['pattern']
            if pattern.startswith('*.'):
                self.extensions.append(pattern[1:].lower())

    def output_type(self, fileobj=sys.stdout, pad=4):
        """
        Writes formatted extension -> MIME type dictionary to given file
        object (defaults to stdout). Will add pad leading space characters
        to each line in the file.
        """

        for key in sorted(self.content_type):
            fileobj.write('%s\'%s\': \'%s\',\n' % \
                (' ' * pad, key, self.content_type[key]))

    def __init__(self, fileobj='/usr/share/mime/packages/freedesktop.org.xml'):
        self.content_type = {}
        self.type = ''
        self.extensions = ''

        parser = expat.ParserCreate()
        parser.StartElementHandler = self.__start_element_handler
        parser.ParseFile(open(fileobj))
        self.content_type['.pdb'] = 'chemical/x-pdb'
        self.content_type['.xyz'] = 'chemical/x-pdb'
