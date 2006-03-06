#!/usr/bin/python
# -*- coding: ISO-8859-15 -*-
#
# Copyright (C) 2005-2006 David Guerizec <david@guerizec.net>
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


import simple
import MySQLdb
from SSHproxy.config import MySQLConfig

cfg = MySQLConfig()

db = MySQLdb.connect(
        host=cfg.host,
        port=cfg.port,
        db=cfg.db,
        user=cfg.user,
        passwd=cfg.password)


def Q(str):
    """Safe quote mysql values"""
    if str is None:
        return ''
    return str.replace("'", "\\'")

class MySQLPwDB(simple.SimplePwDB):
    """MySQL Password DataBase connector class"""
    def __init__(self):
        self.db = db
        self.login = None
        q_sites = """
            select id, name, ip_address, port, location
                from site order by name
            """
        q_users = """
            select id, site_id, uid, password, `primary`
                from user where site_id = %d
            """
        site_list = []
        sites = db.cursor()
        sites.execute(q_sites)
        for id, name, ip_address, port, location in sites.fetchall():
            user_list = []
            users = db.cursor()
            users.execute(q_users % id)
            for id, site_id, uid, password, primary in users.fetchall():
                user_list.append(simple.UserEntry(uid, password, primary))
            site_list.append(simple.SiteEntry(sid=name,
                                              ip_address=ip_address,
                                              port=port,
                                              location=location,
                                              user_list=user_list))
        simple.SimplePwDB.__init__(self, site_list)

    #def __del__(self):
    #   db.close()

################## miscellaneous functions ##############################

    def set_user_key(self, key, user=None, force=0):
        if not user:
            user = self.login
        if not user:
            raise ValueError("Missing user and not authenticated")
        if not force and len(self.get_login(user)['key']):
            # Don't overwrite an existing key
            return True
        q_setkey = """
            update login set `key` = '%s' where uid = '%s'
        """
        setkey = db.cursor()
        ret = setkey.execute(q_setkey % (Q(key), Q(user)))
        setkey.close()
        return ret

    def is_admin(self, user=None):
        if user is None:
            user = self.login

        q_admin = """
            select 1 from login, login_profile, profile
            where login.uid = '%s'
              and login.id = login_profile.login_id 
              and login_profile.profile_id = profile.id
              and profile.admin = 1
        """

        admin = db.cursor()
        admin.execute(q_admin % Q(user))
        admin = admin.fetchone()
        if not admin or not len(admin):
            return False
        return True


################## functions for script/add_profile #####################

    def list_profiles(self):
        q_getprofile = """
            select id, name from profile
        """
        profile = db.cursor()
        profile.execute(q_getprofile)
        p = []
        for id, name in profile.fetchall():
            p.append({ 'id': id, 'name': name })
        profile.close()
        return p

    def get_profile(self, name):
        q_getprofile = """
            select id, name from profile where name = '%s'
        """
        profile = db.cursor()
        profile.execute(q_getprofile % Q(name))
        p = profile.fetchone()
        if not p or not len(p):
            return None
        profile.close()
        return { 'id': p[0], 'name': p[1] }

    def add_profile(self, name):
        q_addprofile = """
            insert into profile (name) values ('%s')
        """
        if self.get_profile(name):
            return None
        profile = db.cursor()
        profile.execute(q_addprofile % Q(name))
        profile.close()
        return 1

    def remove_profile(self, name):
        q = """
            delete from profile where name = '%s'
        """
        profile_id = self.get_id('profile', name)
        if not profile_id:
            return False
        self.unlink_login_profile(None, profile_id)
        self.unlink_profile_group(profile_id, None)
        profile = db.cursor()
        profile.execute(q % Q(name))
        profile.close()
        return True

################ functions for scripts/add_group ########################

    def list_groups(self, site=None):
        q_getgroup = """
            select sgroup.id,
                   sgroup.name
                from sgroup
        """
        if site:
            q_getgroup = q_getgroup.strip() + """,
                     sgroup_site,
                     site
                where site.name = '%s' and
                      site.id = sgroup_site.site_id and
                      sgroup_site.sgroup_id = sgroup.id""" % Q(site)
        group = db.cursor()
        group.execute(q_getgroup)
        p = []
        for id, name in group.fetchall():
            p.append({ 'id': id, 'name': name })
        group.close()
        return p

    def get_group(self, name):
        q_getgroup = """
            select id, name from sgroup where name = '%s'
        """
        group = db.cursor()
        group.execute(q_getgroup % Q(name))
        p = group.fetchone()
        if not p or not len(p):
            return None
        group.close()
        return { 'id': p[0], 'name': p[1] }

    def add_group(self, name):
        q_addgroup = """
            insert into sgroup (name) values ('%s')
        """
        if self.get_group(name):
            return None
        group = db.cursor()
        group.execute(q_addgroup % Q(name))
        group.close()
        return 1

    def remove_group(self, name):
        q = """
            delete from sgroup where name = '%s'
        """
        group_id = self.get_id('group', name)
        if not group_id:
            return False
        self.unlink_profile_group(None, group_id)
        self.unlink_group_site(group_id, None)
        group = db.cursor()
        group.execute(q % Q(name))
        group.close()
        return True

################ functions for scripts/add_site #######################

    def list_sites(self, group=None):
        q_listsite = """
            select site.id,
                   site.name,
                   site.ip_address,
                   site.port,
                   site.location
                from site
        """
        if group:
            q_listsite = q_listsite.strip() + """,
                     sgroup_site,
                     sgroup
                where sgroup.name = '%s' and
                      sgroup_site.sgroup_id = sgroup.id and
                      sgroup_site.site_id = site.id""" % Q(group)
        site = db.cursor()
        site.execute(q_listsite)
        p = []
        for id, name, ip_address, port, location in site.fetchall():
            p.append({ 'id': id,
                       'name': name,
                       'ip': ip_address,
                       'port': port,
                       'location': location })
        site.close()
        return p

    # XXX: rename this method
    def get_site(self, name):
        q_getsite = """
            select id,
                   name,
                   ip_address,
                   port,
                   location
                from site 
                where name = '%s'
        """
        site = db.cursor()
        site.execute(q_getsite % Q(name))
        p = site.fetchone()
        if not p or not len(p):
            return None
        site.close()
        return { 'id': p[0],
                 'name': p[1],
                 'ip': p[2],
                 'port': p[3],
                 'location': p[4] }

    def add_site(self, name, ip_address, port, location):
        q_addsite = """
            insert into site (
                    name,
                    ip_address,
                    port,
                    location)
                values ('%s','%s',%d,'%s')
        """
        if self.get_site(name):
            return None
        site = db.cursor()
        site.execute(q_addsite % (Q(name), Q(ip_address), port, Q(location)))
        site.close()
        return 1

    def remove_site(self, name):
        q = "delete from site where name = '%s'"
        site_id = self.get_id('site', name)
        if not site_id:
            return False
        for u in self.list_users(site_id):
            self.remove_user(u['uid'], site_id)
        self.unlink_group_site(None, site_id)
        site = db.cursor()
        site.execute(q % Q(name))
        site.close()
        return True

################## functions for scripts/add_user #####################

    def list_users(self, site_id=None):
        q_listuser = """
            select site_id, uid, password, `primary` from user
        """
        if site_id:
            q_listuser = q_listuser + " where site_id = %d" % site_id
        site = db.cursor()
        site.execute(q_listuser)
        p = []
        for site_id, uid, password, primary in site.fetchall():
            p.append({ 'uid': uid,
                       'site_id': site_id,
                       'password': password,
                       'primary': primary })
        site.close()
        return p

    def get_users(self, uid, site_id):
        q_getuser = """
            select site_id,
                   uid,
                   password,
                   `primary`
                from user where uid = '%s' and site_id = %d
        """
        if type(site_id) == type(""):
            site_id = self.get_id("site", site_id)
        user = db.cursor()
        user.execute(q_getuser % (Q(uid), site_id))
        p = user.fetchone()
        if not p or not len(p):
            return None
        user.close()
        return { 'site_id': p[0],
                 'uid': p[1],
                 'password': p[2],
                 'primary': p[3] }

    def add_user_to_site(self, uid, site, password, primary):
        site_id = self.get_id('site', site)
        if not site_id:
            return False
        return self.add_user(uid, site_id, password, primary)

    def add_user(self, uid, site_id, password, primary):
        q_adduser = """
            insert into user (
                    uid,
                    site_id,
                    password,
                    `primary`)
                values ('%s',%d,'%s',%d)
        """
        if self.get_users(uid, site_id):
            return None
        user = db.cursor()
        user.execute(q_adduser % (Q(uid), site_id, Q(password), primary))
        user.close()
        return 1

    def remove_user_from_site(self, uid, site):
        site_id = self.get_id('site', site)
        if not site_id:
            return False
        return self.remove_user(uid, site_id)

    def remove_user(self, uid, site_id):
        q = """
            delete from user where uid = '%s' and site_id = %d
        """
        if type(site_id) == type(""):
            site_id = self.get_id("site", site_id)
        if not self.get_users(uid, site_id):
            return False
        user = db.cursor()
        user.execute(q % (Q(uid), site_id))
        user.close()
        return True

################### functions for scripts/add_login   #############

    def list_logins(self):
        q_listlogin = """
            select uid, password, `key` from login
        """
        site = db.cursor()
        site.execute(q_listlogin)
        p = []
        for login, password, key in site.fetchall():
            p.append({ 'login': login, 'password': password, 'key': key })
        site.close()
        return p

    def get_login(self, uid):
        q_getlogin = """
            select uid, password, `key` from login where uid = '%s'
        """
        login = db.cursor()
        login.execute(q_getlogin % Q(uid))
        p = login.fetchone()
        if not p or not len(p):
            return None
        login.close()
        return { 'login': p[0], 'password': p[1], 'key': p[2] }

    def add_login(self, login, password, key=None):
        q_addlogin = """
            insert into login (uid, `password`, `key`) values ('%s','%s','%s')
        """
        if self.get_login(login):
            return None
        addlogin = db.cursor()
        addlogin.execute(q_addlogin % (Q(login), Q(password), Q(key)))
        addlogin.close()
        return True

    def remove_login(self, login):
        q = """
            delete from login where uid = '%s'
        """
        login_id = self.get_id('login', login)
        if not login_id:
            return False
        self.unlink_login_profile(login_id, None)
        removelogin = db.cursor()
        removelogin.execute(q % Q(login))
        removelogin.close()
        return True

######### functions for link scripts/add_login_profile ###############

    def list_login_profile(self):
        q_list = """
             select login_id, profile_id from login_profile
        """
        lists = db.cursor()
        lists.execute(q_list)
        p = []
        for login_id,profile_id in lists.fetchall():
            profile = self.get_name('profile', profile_id)
            login = self.get_name('login', login_id, name='uid')
            p.append({ 'login': login, 'profile': profile })
        lists.close()
        return p

    def add_login_profile(self, login_id, profile_id):
        q_addlogin = """
            replace into login_profile (login_id, profile_id) values (%d, %d)
        """
        login = db.cursor()
        login.execute(q_addlogin % (login_id, profile_id))
        login.close()
        return 1

    def unlink_login_profile(self, login_id, profile_id):
        q = """
            delete from login_profile where 
        """
        q_where = []
        if login_id is not None:
            q_where.append("login_id = %d" % login_id)
        if profile_id is not None:
            q_where.append("profile_id = %d" % profile_id)
        if not len(q_where):
            return False

        login = db.cursor()
        login.execute(q + ' and '.join(q_where))
        login.close()
        return True


######### functions for link scripts/add_profile_group ###############

    def list_profile_group(self):
        q_list = """
             select profile_id, sgroup_id from profile_sgroup
        """
        lists = db.cursor()
        lists.execute(q_list)
        p = []
        for profile_id,sgroup_id in lists.fetchall():
            profile = self.get_name('profile', profile_id)
            sgroup = self.get_name('sgroup', sgroup_id)
            p.append({'prof': profile, 'sgroup': sgroup})
        lists.close()
        return p

    def add_profile_group(self, profile_id, sgroup_id):
        q_addlogin = """
            replace into profile_sgroup (profile_id,sgroup_id) values (%d, %d)
        """
        login = db.cursor()
        login.execute(q_addlogin % (profile_id, sgroup_id))
        login.close()
        return 1

    def unlink_profile_group(self, profile_id, sgroup_id):
        q = """
            delete from profile_sgroup where 
        """
        q_where = []
        if profile_id is not None:
            q_where.append("profile_id = %d" % profile_id)
        if sgroup_id is not None:
            q_where.append("sgroup_id = %d" % sgroup_id)
        if not len(q_where):
            return False
        login = db.cursor()
        login.execute(q + ' and '.join(q_where))
        login.close()
        return True


######### functions for link scripts/add_group_site ###############

    def list_group_site(self):
        q_list = """
             select sgroup_id,site_id from sgroup_site
        """
        lists = db.cursor()
        lists.execute(q_list)
        p = []
        for sgroup_id,site_id in lists.fetchall():
            sgroup = self.get_name('sgroup', sgroup_id)
            site = self.get_name('site', site_id)
            p.append({'sgroup': sgroup, 'site': site})
        lists.close()
        return p

    def add_group_site(self, sgroup_id, site_id):
        q_addlogin = """
            replace into sgroup_site (sgroup_id, site_id) values (%d, %d)
        """
        login = db.cursor()
        login.execute(q_addlogin % (sgroup_id, site_id))
        login.close()
        return 1

    def unlink_group_site(self, sgroup_id, site_id):
        q = """
            delete from sgroup_site where 
        """
        q_where = []
        if sgroup_id is not None:
            q_where.append("sgroup_id = %d" % sgroup_id)
        if site_id is not None:
            q_where.append("site_id = %d" % site_id)
        if not len(q_where):
            return False

        login = db.cursor()
        login.execute(q + ' and '.join(q_where))
        login.close()
        return True

######################################################################

    def get_name(self, table, id, name='name'):
        query = """
        select %s from `%s` where id = '%d'
        """
        c= db.cursor()
        c.execute(query % (name, Q(table), int(id)))
        name = c.fetchone()
        c.close()
        return name[0]


    def get_id(self, table, name):
        id = None
        if table == 'group': # alias group to sgroup
            table = 'sgroup'
        if table == 'login':
            query = """
            select id from `%s` where uid = '%s' 
            """
        else:
            query = """
            select id from `%s` where name = '%s' 
            """
        c = db.cursor()
        c.execute(query % (Q(table), Q(name)))
        id = c.fetchone()
        c.close()
        if id and len(id):
            return id[0]
        else:
            return 0

    def is_allowed(self, username, password=None, key=None):
        """Check is a user is allowed to connect to the proxy."""
        if password is None and key is None:
            return None
        if key is None:
            q_access = """
                select 1 from login where uid = '%s' and `password` = '%s'
            """ % (Q(username), Q(password))
        else:
            q_access = """
                select 1 from login where uid = '%s' and `key` = '%s'
            """ % (Q(username), Q(key))
        logins = db.cursor()
        logins.execute(q_access)
        try:
            login = logins.fetchone()[0]
        except TypeError:
            return None
        logins.close()
        if login:
            self.login = username
        return login

    def get_user_site(self, sid):
        user = None
        if sid.find('@') >= 0:
            user, sid = sid.split('@')
        users = db.cursor()
        if not user:
            q_user = """
            select uid
                from site, user
                where site.id = user.site_id and site.name = '%s'
                order by `primary` desc            
"""
            users.execute(q_user % Q(sid))
        else:
            q_user = """
            select uid
                from site, user
                where site.id = user.site_id and site.name = '%s'
                  and user.uid = '%s'
                order by `primary` desc            
"""

            users.execute(q_user % (Q(sid), user))
        user = users.fetchone()
        if not user or not len(user):
            raise AttributeError("No such user")
            return None, None
        user = user[0]
        users.close()
        if not self.can_connect(user, sid):
            raise AttributeError(
                "You can't connect to %s@%s" % (user, sid))
            return None, None
        q_sites = """
            select id, name, ip_address, port, location
                from site
                where site.name = '%s'
                order by name limit 1
            """
        q_users = """
            select id, site_id, uid, password, `primary`
                from user where site_id = %d
            """
        sites = db.cursor()
        sites.execute(q_sites % Q(sid))
        id, name, ip_address, port, location = sites.fetchone()
        user_list = []
        users = db.cursor()
        users.execute(q_users % id)
        for id, site_id, uid, password, primary in users.fetchall():
            user_list.append(simple.UserEntry(uid, password, primary))
        site = simple.SiteEntry(sid=name,
                                ip_address=ip_address,
                                port=port,
                                location=location,
                                user_list=user_list)

        return user, site

    def can_connect(self, user, site):
        q_group = """
        select count(*) 
        from
            login,
            login_profile,
            profile,
            profile_sgroup,
            sgroup,
            sgroup_site,
            site,
            user 
        where login.uid = '%s' 
          and login.id = login_profile.login_id 
          and login_profile.profile_id = profile.id 
          and profile.id = profile_sgroup.profile_id 
          and profile_sgroup.sgroup_id = sgroup.id
          and sgroup.id = sgroup_site.sgroup_id
          and sgroup_site.site_id = site.id
          and site.name = '%s'
          and user.site_id = site.id
          and user.uid = '%s'  
        """
        group = db.cursor()
        group.execute(q_group % (Q(self.login), Q(site), Q(user)))
        gr = group.fetchone()[0]
        group.close()
        return gr

