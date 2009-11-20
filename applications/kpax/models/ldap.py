# coding: utf8

import ldap

fog_dn = 'dc=fog,dc=icmc,dc=usp,dc=br'
fog_hostname = 'fog.icmc.usp.br'

def in_ldap(username):
    con = ldap.initialize('ldap://' + fog_hostname)
    users_list = con.search_s('ou=people,' + fog_dn, ldap.SCOPE_SUBTREE, '(uid=%s)' % username)
    con.unbind()
    return T(str(len(users_list) > 0))

def sync_ldap():
    con = ldap.initialize('ldap://' + fog_hostname)
    con.simple_bind_s('cn=admin,' + fog_dn, 'f0gs3rv3r')
    ldap_users = con.search_s('ou=people,' + fog_dn, ldap.SCOPE_SUBTREE, '(objectClass=posixAccount)', 
        attrlist=['uid', 'uidNumber', 'cn', 'sn', 'userPassword'])
    ldap_names = {}
    for ldap_dn, ldap_attrs in ldap_users:
        ldap_attrs['dn'] = [ldap_dn]
        ldap_names[ldap_attrs['uid'][0]] = ldap_attrs
    names_added = []
    names_in_db = {}
    users = []
    for user in db(db.user.id>0).select():
        users.append(user.username)
        if user.username not in ldap_names:
            names_added.append(user.username)
            uid_list = con.search_s('ou=people,' + fog_dn, ldap.SCOPE_SUBTREE, '(objectClass=posixAccount)', attrlist=['uidNumber'])
            uid = max([int(user_attrs.get('uidNumber', [1000])[0]) for user_dn, user_attrs in uid_list]) + 1
            con.add_s('uid=%s,ou=people,%s' %  (user.username, fog_dn),
                [('uid', user.username),
                 ('objectClass', ['posixAccount', 'inetOrgPerson']),
                 ('cn', user.firstname),
                 ('sn', user.lastname), 
                 ('uidNumber', str(uid)),
                 ('gidNumber', '1000'), 
                 ('homeDirectory', '')])  
        else:
            attrs = []
            adding = []
            mod_list = []
            for ldap_attr, db_attr in [('cn', 'firstname'), 
                                       ('sn', 'lastname'),
                                       ('userPassword', 'password')]:
                op_type = False
                if ldap_attr not in ldap_names[user.username]:
                    adding.append(ldap_attr)
                    op_type = ldap.MOD_ADD
                elif ldap_names[user.username][ldap_attr][0] != getattr(user, db_attr):
                    attrs.append((db_attr, str(ldap_names[user.username][ldap_attr]), getattr(user, db_attr)))
                    op_type = ldap.MOD_REPLACE
                if op_type is not False:
                    mod_list.append((op_type, ldap_attr, str(getattr(user, db_attr))))
            if mod_list:
                con.modify_s(ldap_names[user.username]['dn'][0], mod_list)
            names_in_db[user.username] = {'adding': adding, 'modifying': attrs}
    extra_users = [uid for uid in ldap_names if uid not in users]
    for user in extra_users:
        con.delete_s(ldap_names[user]['dn'][0])
    con.unbind()
