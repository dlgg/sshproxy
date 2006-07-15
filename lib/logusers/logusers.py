#!/usr/bin/env python
# -*- coding: ISO-8859-15 -*-
#
# Copyright (C) 2005-2006 David Guerizec <david@guerizec.net>
#
# Last modified: 2006 Jul 15, 11:15:09 by david
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA


import os.path

from sshproxy.config import get_config, Config, ConfigSection, path
from sshproxy import keys

class LogUsersConfigSection(ConfigSection):
    section_defaults = {
        'logdir': '@logusers',
        }
    types = {
        'logdir': path,
        }

Config.register_handler('logusers', LogUsersConfigSection)

class PluginLogUsers(object):
    tr_table = {}
    _tr_table = {
            '\r\n':         '\n',
            '\r':           '\n',
            '\n':           '\n',
            '<':            '<INF>',
            '>':            '<SUP>',
        }
    def __init__(self):
        conf = get_config('logusers')
        if not os.path.isdir(conf['logdir']):
            os.makedirs(conf['logdir'])
        
        self.path = conf['logdir']

        for key in dir(keys):
            if key[0] == '_' or not isinstance(getattr(keys, key), str):
                continue
            self.tr_table[getattr(keys, key)] = '<%s>' % key

        for key, value in self._tr_table.items():
            self.tr_table[key] = value

    def logusers(self, console, chan, tags, char):
        user = tags['client'].username
        path = os.path.join(self.path, user)
        if not os.path.isdir(path):
            os.makedirs(path)

        site = '%s@%s' % (tags['site'].login, tags['site'].name)
        logfile = os.path.join(path, site)
        log = open(logfile, 'a')
        log.write(self.translate(char))
        log.close()

    def translate(self, char):
        return self.tr_table.get(char, char)
        if self.tr_table.has_key(char):
            return self.tr_table[char]
        return char
        

