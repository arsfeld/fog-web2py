#!/bin/python
# -*- coding: utf-8 -*-

"""
This file is part of web2py Web Framework (Copyrighted, 2007-2009).
Developed by Massimo Di Pierro <mdipierro@cs.depaul.edu>.
License: GPL v2
"""

from storage import Storage, Settings, Messages
from validators import *
from html import *
from sqlhtml import *
from http import *

import base64
import uuid
import datetime
import re
import cPickle
import smtplib
import socket
import urllib

import sql
import serializers
import contrib.simplejson as simplejson

__all__ = ['Mail', 'Auth', 'Recaptcha', 'Crud', 'Service', 'fetch', 'geocode']

DEFAULT = lambda: None


def validators(*a):
    b = []
    for item in a:
        if isinstance(item, (list, tuple)):
            b = b + list(item)
        else:
            b.append(item)
    return b


class Mail(object):
    """
    Class for configuring and sending emails.
    Works with SMTP and Google App Engine

    Example::

        from contrib.utils import *
        mail=Mail()
        mail.settings.server='smtp.gmail.com:587'
        mail.settings.sender='you@somewhere.com'
        mail.settings.login=None or 'username:password'
        mail.send(to=['you@whatever.com'], subject='None', message='None')

    In Google App Engine use::

        mail.settings.server='gae'

    """

    def __init__(self):
        self.settings = Settings()
        self.settings.server = 'smtp.gmail.com:587'
        self.settings.sender = 'you@google.com'
        self.settings.login = None  # or 'username:password'
        self.settings.lock_keys = True

    def send(
        self,
        to,
        subject='None',
        message='None',
        ):
        """
        Sends an email. Returns True on success, False on failure.
        """

        if not isinstance(to, list):
            to = [to]
        try:
            if self.settings.server == 'gae':
                from google.appengine.api import mail
                mail.send_mail(sender=self.settings.sender, to=to,
                               subject=subject, body=message)
            else:
                msg = '''From: %s\r
To: %s\r
Subject: %s\r
\r
%s'''\
                     % (self.settings.sender, ', '.join(to), subject,
                        message)
                (host, port) = self.settings.server.split(':')
                server = smtplib.SMTP(host, port)
                if self.settings.login:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    (username, password) = self.settings.login.split(':')
                    server.login(username, password)
                server.sendmail(self.settings.sender, to, msg)
                server.quit()
        except Exception, e:
            return False
        return True


class Recaptcha(DIV):

    API_SSL_SERVER = 'https://api-secure.recaptcha.net'
    API_SERVER = 'http://api.recaptcha.net'
    VERIFY_SERVER = 'api-verify.recaptcha.net'

    def __init__(
        self,
        request,
        public_key='',
        private_key='',
        use_ssl=False,
        error=None,
        error_message='invalid',
        ):
        self.remote_addr = request.env.remote_addr
        self.public_key = public_key
        self.private_key = private_key
        self.use_ssl = use_ssl
        self.error = error
        self.errors = Storage()
        self.error_message = error_message
        self.components = []
        self.attributes = {}

    def _validate(self):

        # for local testing:

        import urllib2
        import urllib
        recaptcha_challenge_field = \
            self.request_vars.recaptcha_challenge_field
        recaptcha_response_field = \
            self.request_vars.recaptcha_response_field
        private_key = self.private_key
        remoteip = self.remote_addr
        if not (recaptcha_response_field and recaptcha_challenge_field
                 and len(recaptcha_response_field)
                 and len(recaptcha_challenge_field)):
            self.errors['captcha'] = self.error_message
            return False
        params = urllib.urlencode({
            'privatekey': private_key,
            'remoteip': remoteip,
            'challenge': recaptcha_challenge_field,
            'response': recaptcha_response_field,
            })
        request = urllib2.Request(
            url='http://%s/verify' % self.VERIFY_SERVER,
            data=params,
            headers={'Content-type': 'application/x-www-form-urlencoded',
                        'User-agent': 'reCAPTCHA Python'})
        httpresp = urllib2.urlopen(request)
        return_values = httpresp.read().splitlines()
        httpresp.close()
        return_code = return_values[0]
        if return_code == 'true':
            del self.request_vars.recaptcha_challenge_field
            del self.request_vars.recaptcha_response_field
            self.request_vars.captcha = ''
            return True
        self.errors['captcha'] = self.error_message
        return False

    def xml(self):
        public_key = self.public_key
        use_ssl = (self.use_ssl, )
        error_param = ''
        if self.error:
            error_param = '&error=%s' % self.error
        if use_ssl:
            server = self.API_SSL_SERVER
        else:
            server = self.API_SERVER
        captcha = \
            """<script type="text/javascript" src="%(ApiServer)s/challenge?k=%(PublicKey)s%(ErrorParam)s"></script>
<noscript>
<iframe src="%(ApiServer)s/noscript?k=%(PublicKey)s%(ErrorParam)s" height="300" width="500" frameborder="0"></iframe><br />
<textarea name="recaptcha_challenge_field" rows="3" cols="40"></textarea>
<input type='hidden' name='recaptcha_response_field' value='manual_challenge' />
</noscript>
"""\
             % {'ApiServer': server, 'PublicKey': public_key,
                'ErrorParam': error_param}
        if not self.errors.captcha:
            return captcha
        else:
            return captcha + DIV(self.errors['captcha'], _class='error').xml()


class Auth(object):
    """
    Class for authentication, authorization, role based access control.

    Includes:

    - registration and profile
    - login and logout
    - username and password retrieval
    - event logging
    - role creation and assignment
    - user defined group/role based permission

    Authentication Example::

        from contrib.utils import *
        mail=Mail()
        mail.settings.server='smtp.gmail.com:587'
        mail.settings.sender='you@somewhere.com'
        mail.settings.login='username:password'
        auth=Auth(globals(), db)
        auth.settings.mailer=mail
        # auth.settings....=...
        auth.define_tables()
        def authentication():
            return dict(form=auth())

    exposes:

    - http://.../{application}/{controller}/authentication/login
    - http://.../{application}/{controller}/authentication/logout
    - http://.../{application}/{controller}/authentication/register
    - http://.../{application}/{controller}/authentication/veryfy_email
    - http://.../{application}/{controller}/authentication/retrieve_username
    - http://.../{application}/{controller}/authentication/retrieve_password
    - http://.../{application}/{controller}/authentication/profile
    - http://.../{application}/{controller}/authentication/change_password

    On registration a group with role=new_user.id is created
    and user is given membership of this group.

    You can create a group with::

        group_id=auth.add_group('Manager', 'can access the manage action')
        auth.add_permission(group_id, 'access to manage')

    Here \"access to manage\" is just a user defined string.
    You can give access to a user::

        auth.add_membership(group_id, user_id)

    If user id is omitted, the logged in user is assumed

    Then you can decorate any action::

        @auth.requires_permission('access to manage')
        def manage():
            return dict()

    You can restrict a permission to a specific table::

        auth.add_permission(group_id, 'edit', db.sometable)
        @auth.requires_permission('edit', db.sometable)

    Or to a specific record::

        auth.add_permission(group_id, 'edit', db.sometable, 45)
        @auth.requires_permission('edit', db.sometable, 45)

    If authorization is not granted calls::

        auth.settings.on_failed_authorization

    Other options::

        auth.settings.mailer=None
        auth.settings.expiration=3600 # seconds

        ...

        ### these are messages that can be customized
        ...
    """


    def url(self, f=None, args=[], vars={}):
        return self.environment.URL(r=self.environment.request,
                                    c=self.settings.controller,
                                    f=f, args=args, vars=vars)

    def __init__(self, environment, db=None):
        """
        auth=Auth(globals(), db)

        - globals() has to be the web2py environment including
          request, response, session
        - db has to be the database where to create tables for authentication

        """

        self.environment = Storage(environment)
        self.db = db
        request = self.environment.request
        session = self.environment.session
        app = request.application
        auth = session.auth
        if auth and auth.last_visit and auth.last_visit\
             + datetime.timedelta(days=0, seconds=auth.expiration)\
             > request.now:
            self.user = auth.user
            auth.last_visit = request.now
        else:
            self.user = None
            session.auth = None
        self.settings = Settings()

        # ## what happens after login?

        # ## what happens after registration?

        self.settings.actions_disabled = []
        self.settings.registration_requires_verification = False
        self.settings.registration_requires_approval = False
        self.settings.alternate_requires_registration = False
        self.settings.create_user_groups = True

        self.settings.controller = 'default'
        self.settings.login_url = self.url('user', args='login')
        self.settings.logged_url = self.url('user', args='profile')
        self.settings.download_url = self.url('download')
        self.settings.mailer = None
        self.settings.captcha = None
        self.settings.expiration = 3600  # seconds
        self.settings.allow_basic_login = False

        self.settings.on_failed_authorization = self.url('user',
                                                         args='not_authorized')

        # ## table names to be used

        self.settings.password_field = 'password'
        self.settings.table_user_name = 'auth_user'
        self.settings.table_group_name = 'auth_group'
        self.settings.table_membership_name = 'auth_membership'
        self.settings.table_permission_name = 'auth_permission'
        self.settings.table_event_name = 'auth_event'

        # ## if none, they will be created

        self.settings.table_user = None
        self.settings.table_group = None
        self.settings.table_membership = None
        self.settings.table_permission = None
        self.settings.table_event = None

        # ##

        self.settings.showid = False

        # ## these should be functions or lambdas

        self.settings.login_next = self.url('index')
        self.settings.login_onvalidation = None
        self.settings.login_onaccept = None
        self.settings.login_methods = [self]
        self.settings.login_form = self

        self.settings.logout_next = self.url('index')

        self.settings.register_next = self.url('index')
        self.settings.register_onvalidation = None
        self.settings.register_onaccept = None

        self.settings.verify_email_next = self.url('user', args='login')
        self.settings.verify_email_onaccept = None

        self.settings.profile_next = self.url('index')
        self.settings.retrieve_username_next = self.url('index')
        self.settings.retrieve_password_next = self.url('index')
        self.settings.change_password_next = self.url('index')

        self.settings.hmac_key = None


        # ## these are messages that can be customized
        self.messages = Messages(None)
        self.messages.submit_button = 'Submit'
        self.messages.verify_password = 'Verify Password'
        self.messages.delete_label = 'Check to delete:'
        self.messages.function_disabled = 'Function disabled'
        self.messages.access_denied = 'Insufficient privileges'
        self.messages.registration_verifying = 'Registration needs verification'
        self.messages.registration_pending = 'Registration is pending approval'
        self.messages.login_disabled = 'Login disabled by administrator'
        self.messages.logged_in = 'Logged in'
        self.messages.email_sent = 'Email sent'
        self.messages.unable_to_send_email = 'Unable to send email'
        self.messages.email_verified = 'Email verified'
        self.messages.logged_out = 'Logged out'
        self.messages.registration_successful = 'Registration successful'
        self.messages.invalid_email = 'Invalid email'
        self.messages.unable_send_email = 'Unable to send email'
        self.messages.invalid_login = 'Invalid login'
        self.messages.invalid_user = 'Invalid user'
        self.messages.invalid_password = 'Invalid password'
        self.messages.is_empty = "Cannot be empty"
        self.messages.mismatched_password = "Password fields don't match"
        self.messages.verify_email = \
            'Click on the link http://...verify_email/%(key)s to verify your email'
        self.messages.verify_email_subject = 'Email verification'
        self.messages.username_sent = 'Your username was emailed to you'
        self.messages.new_password_sent = 'A new password was emailed to you'
        self.messages.password_changed = 'Password changed'
        self.messages.retrieve_username = 'Your username is: %(username)s'
        self.messages.retrieve_username_subject = 'Username retrieve'
        self.messages.retrieve_password = 'Your password is: %(password)s'
        self.messages.retrieve_password_subject = 'Password retrieve'
        self.messages.profile_updated = 'Profile updated'
        self.messages.new_password = 'New password'
        self.messages.old_password = 'Old password'
        self.messages.group_description = \
            'Group uniquely assigned to user %(first_name)s %(last_name)s'

        self.messages.register_log = 'User %(id)s Registered'
        self.messages.login_log = 'User %(id)s Logged-in'
        self.messages.logout_log = 'User %(id)s Logged-out'
        self.messages.profile_log = 'User %(id)s Profile updated'
        self.messages.verify_email_log = 'User %(id)s Verification email sent'
        self.messages.retrieve_username_log = 'User %(id)s Username retrieved'
        self.messages.retrieve_password_log = 'User %(id)s Password retrieved'
        self.messages.change_password_log = 'User %(id)s Password changed'
        self.messages.add_group_log = 'Group %(group_id)s created'
        self.messages.del_group_log = 'Group %(group_id)s deleted'
        self.messages.add_membership_log = None
        self.messages.del_membership_log = None
        self.messages.has_membership_log = None
        self.messages.add_permission_log = None
        self.messages.del_permission_log = None
        self.messages.has_permission_log = None
    
        self.messages.label_first_name = 'First name'
        self.messages.label_last_name = 'Last name'
        self.messages.label_email = 'E-mail'
        self.messages.label_password = 'Password'
        self.messages.label_registration_key = 'Registration key'
        self.messages.label_role = 'Role'
        self.messages.label_description = 'Description'
        self.messages.label_user_id = 'User ID'
        self.messages.label_group_id = 'Group ID'
        self.messages.label_name = 'Name'
        self.messages.label_table_name = 'Table name'
        self.messages.label_record_id = 'Record ID'
        self.messages.label_time_stamp = 'Timestamp'
        self.messages.label_client_ip = 'Client IP'
        self.messages.label_origin = 'Origin'
        self.messages['T'] = self.environment.T
        self.messages.lock_keys = True

    def _HTTP(self, *a, **b):
        """
        only used in lambda: self._HTTP(404)
        """

        raise HTTP(*a, **b)

    def __call__(self):
        """
        usage:

        def authentication(): return dict(form=auth())
        """

        request = self.environment.request
        args = request.args
        if not args:
            redirect(self.url(args='login'))
        elif args[0] in self.settings.actions_disabled:
            raise HTTP(404)
        if args[0] == 'login':
            return self.login()
        elif args[0] == 'logout':
            return self.logout()
        elif args[0] == 'register':
            return self.register()
        elif args[0] == 'verify_email':
            return self.verify_email()
        elif args[0] == 'retrieve_username':
            return self.retrieve_username()
        elif args[0] == 'retrieve_password':
            return self.retrieve_password()
        elif args[0] == 'change_password':
            return self.change_password()
        elif args[0] == 'profile':
            return self.profile()
        elif args[0] == 'groups':
            return self.groups()
        elif args[0] == 'impersonate':
            return self.impersonate()
        elif args[0] == 'not_authorized':
            return self.not_authorized()
        else:
            raise HTTP(404)

    def __get_migrate(self, tablename, migrate=True):

        if type(migrate).__name__ == 'str':
            return (migrate + tablename + '.table')
        elif migrate == False:
            return False
        else:
            return True

    def define_tables(self, migrate=True):
        """
        to be called unless tables are defined manually

        usages::

            # defines all needed tables and table files
            # 'myprefix_auth_user.table', ...
            auth.define_tables(migrate='myprefix_')

            # defines all needed tables without migration/table files
            auth.define_tables(migrate=False)

        """

        db = self.db
        if not self.settings.table_user:
            passfield = self.settings.password_field
            self.settings.table_user = db.define_table(
                self.settings.table_user_name,
                db.Field('first_name', length=128, default='',
                        label=self.messages.label_first_name),
                db.Field('last_name', length=128, default='',
                        label=self.messages.label_last_name),
                # db.Field('username', length=128, default=''),
                db.Field('email', length=512, default='',
                        label=self.messages.label_email),
                db.Field(passfield, 'password', length=512,
                         readable=False, label=self.messages.label_password),
                db.Field('registration_key', length=512,
                        writable=False, readable=False, default='',
                        label=self.messages.label_registration_key),
                migrate=\
                    self.__get_migrate(self.settings.table_user_name, migrate))
            table = self.settings.table_user
            table.first_name.requires = \
                IS_NOT_EMPTY(error_message=self.messages.is_empty)
            table.last_name.requires = \
                IS_NOT_EMPTY(error_message=self.messages.is_empty)
            table[passfield].requires = [CRYPT(key=self.settings.hmac_key)]
            table.email.requires = \
                [IS_EMAIL(error_message=self.messages.invalid_email),
                 IS_NOT_IN_DB(db, '%s.email'
                     % self.settings.table_user._tablename)]
            table.registration_key.default = ''
        if not self.settings.table_group:
            self.settings.table_group = db.define_table(
                self.settings.table_group_name,
                db.Field('role', length=512, default='',
                        label=self.messages.label_role),
                db.Field('description', 'text',
                        label=self.messages.label_description),
                migrate=self.__get_migrate(
                    self.settings.table_group_name, migrate))
            table = self.settings.table_group
            table.role.requires = IS_NOT_IN_DB(db, '%s.role'
                 % self.settings.table_group._tablename)
        if not self.settings.table_membership:
            self.settings.table_membership = db.define_table(
                self.settings.table_membership_name,
                db.Field('user_id', self.settings.table_user,
                        label=self.messages.label_user_id),
                db.Field('group_id', self.settings.table_group,
                        label=self.messages.label_group_id),
                migrate=self.__get_migrate(
                    self.settings.table_membership_name, migrate))
            table = self.settings.table_membership
            table.user_id.requires = IS_IN_DB(db, '%s.id' %
                    self.settings.table_user._tablename,
                    '%(id)s: %(first_name)s %(last_name)s')
            table.group_id.requires = IS_IN_DB(db, '%s.id' %
                    self.settings.table_group._tablename,
                    '%(id)s: %(role)s')
        if not self.settings.table_permission:
            self.settings.table_permission = db.define_table(
                self.settings.table_permission_name,
                db.Field('group_id', self.settings.table_group,
                        label=self.messages.label_group_id),
                db.Field('name', default='default', length=512,
                        label=self.messages.label_name),
                db.Field('table_name', length=512,
                        label=self.messages.label_table_name),
                db.Field('record_id', 'integer',
                        label=self.messages.label_record_id),
                migrate=self.__get_migrate(
                    self.settings.table_permission_name, migrate))
            table = self.settings.table_permission
            table.group_id.requires = IS_IN_DB(db, '%s.id' %
                    self.settings.table_group._tablename,
                    '%(id)s: %(role)s')
            table.name.requires = IS_NOT_EMPTY()
            table.table_name.requires = IS_IN_SET(self.db.tables)
            table.record_id.requires = IS_INT_IN_RANGE(0, 10 ** 9)
        if not self.settings.table_event:
            self.settings.table_event = db.define_table(
                self.settings.table_event_name,
                db.Field('time_stamp', 'datetime',
                        default=self.environment.request.now,
                        label=self.messages.label_time_stamp),
                db.Field('client_ip',
                        default=self.environment.request.client,
                        label=self.messages.label_client_ip),
                db.Field('user_id', self.settings.table_user, default=None,
                        label=self.messages.label_user_id),
                db.Field('origin', default='auth', length=512,
                        label=self.messages.label_origin),
                db.Field('description', 'text', default='',
                        label=self.messages.label_description),
                migrate=self.__get_migrate(
                    self.settings.table_event_name, migrate))
            table = self.settings.table_event
            table.user_id.requires = IS_IN_DB(db, '%s.id' %
                    self.settings.table_user._tablename,
                    '%(id)s: %(first_name)s %(last_name)s')
            table.origin.requires = IS_NOT_EMPTY()
            table.description.requires = IS_NOT_EMPTY()

    def log_event(self, description, origin='auth'):
        """
        usage::

            auth.log_event(description='this happened', origin='auth')
        """

        if self.is_logged_in():
            user_id = self.user.id
        else:
            user_id = None  # user unknown
        self.settings.table_event.insert(description=description,
                                         origin=origin, user_id=user_id)

    def get_or_create_user(self, keys):
        """
        Used for alternate login methods:
            If the user exists already then password is updated.
            If the user doesn't yet exist, then they are created.
        """
        if 'username' in keys:
            username = 'username'
        elif 'email' in keys:
            username = 'email'
        else:
            raise SyntaxError, "user must have username or email"
        table_user = self.settings.table_user
        passfield = self.settings.password_field
        users = self.db(table_user[username] == keys[username]).select()
        if users:
            user = users[0]
            if passfield in keys and keys[passfield]:
                user.update_record(**{passfield: keys[passfield],
                                      'registration_key': ''})
        else:
            d = {username: keys[username],
               'first_name': keys.get('first_name', keys[username]),
               'last_name': keys.get('last_name', ''),
               'registration_key': ''}
            keys = dict([(k, v) for (k, v) in keys.items() \
                           if k in table_user.fields])
            d.update(keys)
            user_id = table_user.insert(**d)
            if self.settings.create_user_groups:
                group_id = self.add_group("user_%s" % user_id)
                self.add_membership(group_id, user_id)
            user = table_user[user_id]
        return user

    def basic(self):
        request = self.environment.request
        if not self.settings.allow_basic_login:
            return False
        basic = self.environment.request.env.http_authorization
        if not basic or not basic[:6].lower() == 'basic ':
            return False
        (username, password) = base64.b64decode(basic[6:]).split(':')
        return self.login_bare(username, password)

    def login_bare(self, username, password):
        """
        logins user
        """

        request = self.environment.request
        session = self.environment.session
        table_user = self.settings.table_user
        if 'username' in table_user.fields:
            userfield = 'username'
        else:
            userfield = 'email'
        passfield = self.settings.password_field
        users = self.db(table_user[userfield] == username).select()
        password = table_user[passfield].validate(password)[0]
        if users:
            user = users[0]
            if not user.registration_key and user[passfield] == password:
                user = Storage(table_user._filter_fields(user, id=True))
                session.auth = Storage(user=user, last_visit=request.now,
                                       expiration=self.settings.expiration)
                self.user = user
                return user
        return False

    def login(
        self,
        next=DEFAULT,
        onvalidation=DEFAULT,
        onaccept=DEFAULT,
        log=DEFAULT,
        ):
        """
        returns a login form

        .. method:: Auth.login([next=DEFAULT [, onvalidation=DEFAULT
            [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """

        table_user = self.settings.table_user
        if 'username' in table_user.fields:
            username = 'username'
        else:
            username = 'email'
        old_requires = table_user[username].requires
        table_user[username].requires = IS_NOT_EMPTY()
        request = self.environment.request
        response = self.environment.response
        session = self.environment.session
        passfield = self.settings.password_field
        if next == DEFAULT:
            next = request.vars._next or self.settings.login_next
        if onvalidation == DEFAULT:
            onvalidation = self.settings.login_onvalidation
        if onaccept == DEFAULT:
            onaccept = self.settings.login_onaccept
        if log == DEFAULT:
            log = self.messages.login_log

        user = None # default

        # do we use our own login form, or from a central source?
        if self.settings.login_form == self:
            form = SQLFORM(
                table_user,
                fields=[username, passfield],
                hidden=dict(_next=request.vars._next),
                showid=self.settings.showid,
                submit_button=self.messages.submit_button,
                delete_label=self.messages.delete_label,
                )
            accepted_form = False
            if form.accepts(request.vars, session,
                            formname='login', dbio=False,
                            onvalidation=onvalidation):
                accepted_form = True
                # check for username in db
                users = self.db(table_user[username] == form.vars[username]).select()
                if users:
                    # user in db, check if registration pending or disabled
                    temp_user = users[0]
                    if temp_user.registration_key == 'pending':
                        response.flash = self.messages.registration_pending
                        return form
                    elif temp_user.registration_key == 'disabled':
                        response.flash = self.messages.login_disabled
                        return form
                    elif temp_user.registration_key.strip():
                        response.flash = \
                            self.messages.registration_verifying
                        return form
                    # try alternate logins 1st as these have the current version of the password
                    for login_method in self.settings.login_methods:
                        if login_method != self and \
                                login_method(request.vars[username],
                                             request.vars[passfield]):
                            if not self in self.settings.login_methods:
                                # do not store password in db
                                form.vars[passfield] = None
                            user = self.get_or_create_user(form.vars)
                            break
                    if not user:
                        # alternates have failed, maybe because service inaccessible
                        if self.settings.login_methods[0] == self:
                            # try logging in locally using cached credentials
                            if temp_user[passfield] == form.vars.get(passfield, ''):
                                # success
                                user = temp_user
                else:
                    # user not in db
                    if not self.settings.alternate_requires_registration:
                        # we're allowed to auto-register users from external systems
                        for login_method in self.settings.login_methods:
                            if login_method != self and \
                                    login_method(request.vars[username],
                                                 request.vars[passfield]):
                                if not self in self.settings.login_methods:
                                    # do not store password in db
                                    form.vars[passfield] = None
                                user = self.get_or_create_user(form.vars)
                                break
                if not user:
                    # invalid login
                    session.flash = self.messages.invalid_login
                    redirect(self.url(args=request.args))
        else:
            # use a central authentication server
            cas = self.settings.login_form
            cas_user = cas.get_user()
            if cas_user:
                cas_user[passfield] = None
                user = self.get_or_create_user(cas_user)
            else:
                # we need to pass through login again before going on
                next = URL(r=request) + '?_next=' + next
                redirect(cas.login_url(next))

        # process authenticated users
        if user:
            user = Storage(table_user._filter_fields(user, id=True))
            session.auth = Storage(user=user, last_visit=request.now,
                                   expiration=self.settings.expiration)
            self.user = user
            session.flash = self.messages.logged_in
        if log and self.user:
            self.log_event(log % self.user)

        # how to continue
        if self.settings.login_form == self:
            if accepted_form:
                if onaccept:
                    onaccept(form)
                if isinstance(next, (list, tuple)):
                    # fix issue with 2.6
                    next = next[0]
                if next and not next[0] == '/' and next[:4] != 'http':
                    next = self.url(next.replace('[id]', str(form.vars.id)))
                redirect(next)
            table_user[username].requires = old_requires
            return form
        else:
            redirect(next)

    def logout(self, next=DEFAULT, onlogout=DEFAULT, log=DEFAULT):
        """
        logout and redirects to login

        .. method:: Auth.logout ([next=DEFAULT[, onlogout=DEFAULT[,
            log=DEFAULT]]])

        """

        if next == DEFAULT:
            next = self.settings.logout_next
        if onlogout == DEFAULT:
            onlogout = self.settings.logout_onlogout
        if onlogout:
            onlogout(self.user)
        if log == DEFAULT:
            log = self.messages.logout_log
        if log and self.user:
            self.log_event(log % self.user)

        if self.settings.login_form != self:
            cas = self.settings.login_form
            cas_user = cas.get_user()
            if cas_user:
                next = cas.logout_url(next)

        self.environment.session.auth = None
        self.environment.session.flash = self.messages.logged_out
        if next:
            redirect(next)

    def register(
        self,
        next=DEFAULT,
        onvalidation=DEFAULT,
        onaccept=DEFAULT,
        log=DEFAULT,
        ):
        """
        returns a registration form

        .. method:: Auth.register([next=DEFAULT [, onvalidation=DEFAULT
            [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """

        request = self.environment.request
        response = self.environment.response
        session = self.environment.session
        if self.is_logged_in():
            redirect(self.settings.logged_url)
        if next == DEFAULT:
            next = request.vars._next or self.settings.register_next
        if onvalidation == DEFAULT:
            onvalidation = self.settings.register_onvalidation
        if onaccept == DEFAULT:
            onaccept = self.settings.register_onaccept
        if log == DEFAULT:
            log = self.messages.register_log
        user = self.settings.table_user
        passfield = self.settings.password_field
        form = SQLFORM(user, hidden=dict(_next=request.vars._next),
                       showid=self.settings.showid,
                       submit_button=self.messages.submit_button,
                       delete_label=self.messages.delete_label)
        for i, row in enumerate(form[0].components):
            item = row[1][0]
            if isinstance(item, INPUT) and item['_name'] == passfield:
                form[0].insert(i+1, TR(
                        LABEL(self.messages.verify_password + ':'),
                        INPUT(_name="password_two",
                              _type="password",
                              requires=IS_EXPR('value==%s' % \
                               repr(request.vars.get(passfield, None)),
                        error_message=self.messages.mismatched_password)),
                '', _class='%s_%s__row' % (user, 'password_two')))
        if self.settings.captcha != None:
            form[0].insert(-1, TR('', self.settings.captcha, ''))

        user.registration_key.default = key = str(uuid.uuid4())
        if form.accepts(request.vars, session, formname='register',
                        onvalidation=onvalidation):
            description = self.messages.group_description % form.vars
            if self.settings.create_user_groups:
                group_id = self.add_group("user_%s" % form.vars.id, description)
                self.add_membership(group_id, form.vars.id)
            if self.settings.registration_requires_verification:
                if not self.settings.mailer or \
                   not self.settings.mailer.send(to=form.vars.email,
                        subject=self.messages.verify_email_subject,
                        message=self.messages.verify_email
                         % dict(key=key)):
                    self.db.rollback()
                    response.flash = self.messages.unable_send_email
                    return form
                session.flash = self.messages.email_sent
            elif self.settings.registration_requires_approval:
                user[form.vars.id] = dict(registration_key='pending')
                session.flash = self.messages.registration_pending
            else:
                user[form.vars.id] = dict(registration_key='')
                session.flash = self.messages.registration_successful
                table_user = self.settings.table_user
                if 'username' in table_user.fields:
                    username = 'username'
                else:
                    username = 'email'
                users = self.db(table_user[username] == form.vars[username])\
                    .select()
                user = users[0]
                user = Storage(table_user._filter_fields(user, id=True))
                session.auth = Storage(user=user, last_visit=request.now,
                                   expiration=self.settings.expiration)
                self.user = user
                session.flash = self.messages.logged_in
            if log:
                self.log_event(log % form.vars)
            if onaccept:
                onaccept(form)
            if not next:
                next = self.url(args = request.args)
            elif isinstance(next, (list, tuple)): ### fix issue with 2.6
                next = next[0]
            elif next and not next[0] == '/' and next[:4] != 'http':
                next = self.url(next.replace('[id]', str(form.vars.id)))
            redirect(next)
        return form

    def is_logged_in(self):
        """
        checks if the user is logged in and returns True/False.
        if so user is in auth.user as well as in session.auth.user
        """

        if self.environment.session.auth:
            return True
        return False

    def verify_email(
        self,
        next=DEFAULT,
        onaccept=DEFAULT,
        log=DEFAULT,
        ):
        """
        action user to verify the registration email, XXXXXXXXXXXXXXXX

        .. method:: Auth.verify_email([next=DEFAULT [, onvalidation=DEFAULT
            [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """

        key = self.environment.request.args[-1]
        user = self.settings.table_user
        users = self.db(user.registration_key == key).select()
        if not users:
            raise HTTP(404)
        user = users[0]
        if self.settings.registration_requires_approval:
            user.update_record(registration_key = 'pending')
            self.environment.session.flash = self.messages.registration_pending
        else:
            user.update_record(registration_key = '')
            self.environment.session.flash = self.messages.email_verified
        if log == DEFAULT:
            log = self.messages.verify_email_log
        if next == DEFAULT:
            next = self.settings.verify_email_next
        if onaccept == DEFAULT:
            onaccept = self.settings.verify_email_onaccept
        if log:
            self.log_event(log % user)
        if onaccept:
            onaccept(user)
        redirect(next)

    def retrieve_username(
        self,
        next=DEFAULT,
        onvalidation=DEFAULT,
        onaccept=DEFAULT,
        log=DEFAULT,
        ):
        """
        returns a form to retrieve the user username
        (only if there is a username field)

        .. method:: Auth.retrieve_username([next=DEFAULT
            [, onvalidation=DEFAULT [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """

        user = self.settings.table_user
        if not 'username' in user.fields:
            raise HTTP(404)
        request = self.environment.request
        response = self.environment.response
        session = self.environment.session

        if not self.settings.mailer:
            response.flash = self.messages.function_disabled
            return ''
        if next == DEFAULT:
            next = request.vars._next or self.settings.retrieve_username_next
        if onvalidation == DEFAULT:
            onvalidation = self.settings.retrieve_username_onvalidation
        if onaccept == DEFAULT:
            onaccept = self.settings.retrieve_username_onaccept
        if log == DEFAULT:
            log = self.messages.retrieve_username_log
        old_requires = user.email.requires
        user.email.requires = [IS_IN_DB(self.db, user.email)]
        form = SQLFORM(
            user,
            fields=['email'],
            hidden=dict(_next=request.vars._next),
            showid=self.settings.showid,
            submit_button=self.messages.submit_button,
            delete_label=self.messages.delete_label,
            )
        if form.accepts(request.vars, session,
                        formname='retrieve_username', dbio=False,
                        onvalidation=onvalidation):
            users = self.db(user.email == form.vars.email).select()
            if not users:
                self.environment.session.flash = \
                    self.messages.invalid_email
                redirect(self.url(args=request.args))
            username = users[0].username
            self.settings.mailer.send(to=form.vars.email,
                    subject=self.messages.retrieve_username_subject,
                    message=self.messages.retrieve_username
                     % dict(username=username))
            session.flash = self.messages.email_sent
            if log:
                self.log_event(log % users[0])
            if onaccept:
                onaccept(form)
            if not next:
                next = self.url(args = request.args)
            elif isinstance(next, (list, tuple)): ### fix issue with 2.6
                next = next[0]
            elif next and not next[0] == '/' and next[:4] != 'http':
                next = self.url(next.replace('[id]', str(form.vars.id)))
            redirect(next)
        user.email.requires = old_requires
        return form

    def random_password(self):        
        import string
        import random
        password = ''
        specials=r'!#$*'         
        for i in range(0,3):
            password += random.choice(string.lowercase)
            password += random.choice(string.uppercase)
            password += random.choice(string.digits)
            password += random.choice(specials)            
        return ''.join(random.sample(password,len(password)))

    def retrieve_password(
        self,
        next=DEFAULT,
        onvalidation=DEFAULT,
        onaccept=DEFAULT,
        log=DEFAULT,
        ):
        """
        returns a form to retrieve the user password

        .. method:: Auth.retrieve_password([next=DEFAULT
            [, onvalidation=DEFAULT [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """

        user = self.settings.table_user
        request = self.environment.request
        response = self.environment.response
        session = self.environment.session

        if not self.settings.mailer:
            response.flash = self.messages.function_disabled
            return ''

        if next == DEFAULT:
            next = request.vars._next or self.settings.retrieve_password_next
        if onvalidation == DEFAULT:
            onvalidation = self.settings.retrieve_password_onvalidation
        if onaccept == DEFAULT:
            onaccept = self.settings.retrieve_password_onaccept
        if log == DEFAULT:
            log = self.messages.retrieve_password_log
        old_requires = user.email.requires
        user.email.requires = [IS_IN_DB(self.db, user.email,
            error_message=self.messages.invalid_email)]
        form = SQLFORM(
            user,
            fields=['email'],
            hidden=dict(_next=request.vars._next),
            showid=self.settings.showid,
            submit_button=self.messages.submit_button,
            delete_label=self.messages.delete_label,
            )
        if form.accepts(request.vars, session,
                        formname='retrieve_password', dbio=False,
                        onvalidation=onvalidation):
            users = self.db(user.email == form.vars.email).select()
            if not users:
                self.environment.session.flash = \
                    self.messages.invalid_email
                redirect(self.url(args=request.args))
            elif users[0].registration_key[:7] in ['pending', 'disabled']:
                self.environment.session.flash = \
                    self.messages.registration_pending
                redirect(self.url(args=request.args))
            password = self.random_password()
            passfield = self.settings.password_field
            d = {passfield: user[passfield].validate(password)[0],
                 'registration_key': ''}
            users[0].update_record(**d)
            if self.settings.mailer and \
               self.settings.mailer.send(to=form.vars.email,
                        subject=self.messages.retrieve_password_subject,
                        message=self.messages.retrieve_password \
                        % dict(password=password)):
                session.flash = self.messages.email_sent
            else:
                session.flash = self.messages.unable_to_send_email
            if log:
                self.log_event(log % users[0])
            if onaccept:
                onaccept(form)
            if not next:
                next = self.url(args = request.args)
            elif isinstance(next, (list, tuple)): ### fix issue with 2.6
                next = next[0]
            elif next and not next[0] == '/' and next[:4] != 'http':
                next = self.url(next.replace('[id]', str(form.vars.id)))
            redirect(next)
        old_requires = user.email.requires
        return form

    def change_password(
        self,
        next=DEFAULT,
        onvalidation=DEFAULT,
        onaccept=DEFAULT,
        log=DEFAULT,
        ):
        """
        returns a form that lets the user change password

        .. method:: Auth.change_password([next=DEFAULT[, onvalidation=DEFAULT[,
            onaccepet=DEFAULT[, log=DEFAULT]]]])
        """

        if not self.is_logged_in():
            redirect(self.settings.login_url)
        db = self.db
        user = self.settings.table_user
        usern = self.settings.table_user_name
        s = db(user.email == self.user.email)
        pass1 = self.environment.request.vars.new_password
        request = self.environment.request
        session = self.environment.session
        if next == DEFAULT:
            next = request.vars._next or self.settings.change_password_next
        if onvalidation == DEFAULT:
            onvalidation = self.settings.change_password_onvalidation
        if onaccept == DEFAULT:
            onaccept = self.settings.change_password_onaccept
        if log == DEFAULT:
            log = self.messages.change_password_log
        passfield = self.settings.password_field
        form = form_factory(sql.SQLField(
            'old_password',
            'password',
            label=self.messages.old_password,
            requires=validators(
                     self.settings.table_user[passfield].requires,
                     IS_IN_DB(s, '%s.%s' % (usern, passfield),
                              error_message=self.messages.invalid_password))),
            sql.SQLField('new_password', 'password',
            label=self.messages.new_password,
            requires=self.settings.table_user[passfield].requires),
            sql.SQLField('new_password2', 'password',
            label=self.messages.verify_password,
            requires=[IS_EXPR('value==%s' % repr(pass1),
                              self.messages.mismatched_password)]))
        if form.accepts(request.vars, session,
                        formname='change_password',
                        onvalidation=onvalidation):
            d = {passfield: form.vars.new_password}
            s.update(**d)
            session.flash = self.messages.password_changed
            if log:
                self.log_event(log % self.user)
            if onaccept:
                onaccept(form)
            if not next:
                next = self.url(args=request.args)
            elif isinstance(next, (list, tuple)): ### fix issue with 2.6
                next = next[0]
            elif next and not next[0] == '/' and next[:4] != 'http':
                next = self.url(next.replace('[id]', str(form.vars.id)))
            redirect(next)
        return form

    def profile(
        self,
        next=DEFAULT,
        onvalidation=DEFAULT,
        onaccept=DEFAULT,
        log=DEFAULT,
        ):
        """
        returns a form that lets the user change his/her profile

        .. method:: Auth.profile([next=DEFAULT [, onvalidation=DEFAULT
            [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """

        if not self.is_logged_in():
            redirect(self.settings.login_url)
        passfield = self.settings.password_field
        self.settings.table_user[passfield].writable = False
        request = self.environment.request
        session = self.environment.session
        if next == DEFAULT:
            next = request.vars._next or self.settings.profile_next
        if onvalidation == DEFAULT:
            onvalidation = self.settings.profile_onvalidation
        if onaccept == DEFAULT:
            onaccept = self.settings.profile_onaccept
        if log == DEFAULT:
            log = self.messages.profile_log
        form = SQLFORM(
            self.settings.table_user,
            self.user.id,
            hidden=dict(_next=request.vars._next),
            showid=self.settings.showid,
            submit_button=self.messages.submit_button,
            delete_label=self.messages.delete_label,
            upload=self.settings.download_url
            )
        if form.accepts(request.vars, session,
                        formname='profile',
                        onvalidation=onvalidation):
            self.user.update(form.vars)
            session.flash = self.messages.profile_updated
            if log:
                self.log_event(log % self.user)
            if onaccept:
                onaccept(form)
            if not next:
                next = self.url(args=request.args)
            elif isinstance(next, (list, tuple)): ### fix issue with 2.6
                next = next[0]
            elif next and not next[0] == '/' and next[:4] != 'http':
                next = self.url(next.replace('[id]', str(form.vars.id)))
            redirect(next)
        return form

    def is_impersonating(self):
        return self.environment.session.auth.impersonator

    def impersonate(self, user_id=DEFAULT):
        """
        usage: http://..../impersonate/[user_id]
        or:    http://..../impersonate/0 to restore impersonator

        requires impersonator is logged in and
        has_permission('impersonate', 'auth_user', user_id)
        """
        request = self.environment.request
        session = self.environment.session
        auth = session.auth
        if not self.is_logged_in():
            raise HTTP(401, "Not Authorized")
        if user_id == DEFAULT and self.environment.request.args:
            user_id = self.environment.request.args[1]
        if user_id and user_id != self.user.id and user_id != '0':
            if not self.has_permission('impersonate',
                                       self.settings.table_user_name,
                                       user_id):
                raise HTTP(403, "Forbidden")
            user = self.settings.table_user[request.args[1]]
            if not user:
                raise HTTP(401, "Not Authorized")
            auth.impersonator = cPickle.dumps(session)
            auth.user.update(
                self.settings.table_user._filter_fields(user, True))
            self.user = auth.user
            if self.settings.login_onaccept:
                form = Storage(dict(vars=self.user))
                self.settings.login_onaccept(form)
        elif user_id in [None, 0, '0'] and self.is_impersonating():
            session.clear()
            session.update(cPickle.loads(auth.impersonator))
            self.user = session.auth.user
        return self.user

    def groups(self):
        """
        displays the groups and their roles for the logged in user
        """

        if not self.is_logged_in():
            redirect(self.settings.login_url)
        memberships = self.db(self.settings.table_membership.user_id
                               == self.user.id).select()
        table = TABLE()
        for membership in memberships:
            groups = self.db(self.settings.table_group.id
                              == membership.group_id).select()
            if groups:
                group = groups[0]
                table.append(TR(H3(group.role, '(%s)' % group.id)))
                table.append(TR(P(group.description)))
        if not memberships:
            return None
        return table

    def not_authorized(self):
        """
        you can change the view for this page to make it look as you like
        """

        return 'ACCESS DENIED'

    def requires(self, condition):
        """
        decorator that prevents access to action if not logged in
        """

        def decorator(action):

            def f(*a, **b):

                if not condition: 
                    request = self.environment.request
                    next = URL(r=request,args=request.args,vars=request.get_vars)
                    redirect(self.settings.login_url + '?_next='+urllib.quote(next))
                return action(*a, **b)
            f.__doc__ = action.__doc__
            return f

        return decorator

    def requires_login(self):
        """
        decorator that prevents access to action if not logged in
        """

        def decorator(action):

            def f(*a, **b):

                if not self.basic() and not self.is_logged_in():
                    request = self.environment.request
                    next = URL(r=request,args=request.args,vars=request.get_vars)
                    redirect(self.settings.login_url + '?_next='+urllib.quote(next))
                return action(*a, **b)
            f.__doc__ = action.__doc__
            return f

        return decorator

    def requires_membership(self, role):
        """
        decorator that prevents access to action if not logged in or
        if user logged in is not a member of group_id.
        If role is provided instead of group_id then the group_id is calculated.
        """

        def decorator(action):
            group_id = self.id_group(role)

            def f(*a, **b):
                if not self.basic() and not self.is_logged_in():
                    request = self.environment.request
                    next = URL(r=request,args=request.args,vars=request.get_vars)
                    redirect(self.settings.login_url + '?_next='+urllib.quote(next))
                if not self.has_membership(group_id):
                    self.environment.session.flash = \
                        self.messages.access_denied
                    next = self.settings.on_failed_authorization
                    redirect(next)
                return action(*a, **b)
            f.__doc__ = action.__doc__
            return f

        return decorator

    def requires_permission(
        self,
        name,
        table_name='',
        record_id=0,
        ):
        """
        decorator that prevents access to action if not logged in or
        if user logged in is not a member of any group (role) that
        has 'name' access to 'table_name', 'record_id'.
        """

        def decorator(action):

            def f(*a, **b):
                if not self.basic() and not self.is_logged_in():
                    request = self.environment.request
                    next = URL(r=request,args=request.args,vars=request.get_vars)
                    redirect(self.settings.login_url + '?_next='+urllib.quote(next))
                if not self.has_permission(name, table_name, record_id):
                    self.environment.session.flash = \
                        self.messages.access_denied
                    next = self.settings.on_failed_authorization
                    redirect(next)
                return action(*a, **b)
            f.__doc__ = action.__doc__
            return f

        return decorator

    def add_group(self, role, description=''):
        """
        creates a group associated to a role
        """

        group_id = self.settings.table_group.insert(role=role,
                description=description)
        log = self.messages.add_group_log
        if log:
            self.log_event(log % dict(group_id=group_id, role=role))
        return group_id

    def del_group(self, group_id):
        """
        deletes a group
        """

        self.db(self.settings.table_group.id == group_id).delete()
        self.db(self.settings.table_membership.group_id
                 == group_id).delete()
        self.db(self.settings.table_permission.group_id
                 == group_id).delete()
        log = self.messages.del_group_log
        if log:
            self.log_event(log % dict(group_id=group_id))

    def id_group(self, role):
        """
        returns the group_id of the group specified by the role
        """
        rows = self.db(self.settings.table_group.role == role).select()
        if not rows:
            return None
        return rows[0].id

    def user_group(self, user_id = None):
        """
        returns the group_id of the group uniquely associated to this user
        i.e. role=user:[user_id]
        """
        if not user_id and self.user:
            user_id = self.user.id
        role = 'user_%s' % user_id
        return self.id_group(role)

    def has_membership(self, group_id, user_id=None):
        """
        checks if user is member of group_id
        """

        if not user_id and self.user:
            user_id = self.user.id
        membership = self.settings.table_membership
        if self.db((membership.user_id == user_id)
                    & (membership.group_id == group_id)).select():
            r = True
        else:
            r = False
        log = self.messages.has_membership_log
        if log:
            self.log_event(log % dict(user_id=user_id, 
                                      group_id=group_id, check=r))
        return r

    def add_membership(self, group_id, user_id=None):
        """
        gives user_id membership of group_id
        if group_id==None than user_id is that of current logged in user
        """

        if not user_id and self.user:
            user_id = self.user.id
        membership = self.settings.table_membership
        id = membership.insert(group_id=group_id, user_id=user_id)
        log = self.messages.add_membership_log
        if log:
            self.log_event(log % dict(user_id=user_id,
                                      group_id=group_id))
        return id

    def del_membership(self, group_id, user_id=None):
        """
        revokes membership from group_id to user_id
        if group_id==None than user_id is that of current logged in user
        """

        if not user_id and self.user:
            user_id = self.user.id
        membership = self.settings.table_membership
        log = self.messages.del_membership_log
        if log:
            self.log_event(log % dict(user_id=user_id,
                                      group_id=group_id))
        return self.db(membership.user_id
                       == user_id)(membership.group_id
                                   == group_id).delete()

    def has_permission(
        self,
        name='any',
        table_name='',
        record_id=0,
        user_id=None,
        ):
        """
        checks if user_id or current logged in user is member of a group
        that has 'name' permission on 'table_name' and 'record_id'
        """

        if not user_id and self.user:
            user_id = self.user.id
        membership = self.settings.table_membership
        rows = self.db(membership.user_id
                        == user_id).select(membership.group_id)
        groups = set([row.group_id for row in rows])
        permission = self.settings.table_permission
        rows = self.db(permission.name == name)(permission.table_name
                 == str(table_name))(permission.record_id
                 == record_id).select(permission.group_id)
        groups_required = set([row.group_id for row in rows])
        if record_id:
            rows = self.db(permission.name
                            == name)(permission.table_name
                     == str(table_name))(permission.record_id
                     == 0).select(permission.group_id)
            groups_required = groups_required.union(set([row.group_id
                    for row in rows]))
        if groups.intersection(groups_required):
            r = True
        else:
            r = False
        log = self.messages.has_permission_log
        if log:
            self.log_event(log % dict(user_id=user_id, name=name,
                           table_name=table_name, record_id=record_id))
        return r

    def add_permission(
        self,
        group_id,
        name='any',
        table_name='',
        record_id=0,
        ):
        """
        gives group_id 'name' access to 'table_name' and 'record_id'
        """

        permission = self.settings.table_permission
        if group_id == 0:
            group_id = self.user_group()
        id = permission.insert(group_id=group_id, name=name,
                               table_name=str(table_name),
                               record_id=long(record_id))
        log = self.messages.add_permission_log
        if log:
            self.log_event(log % dict(permission_id, group_id=group_id,
                           name=name, table_name=table_name,
                           record_id=record_id))
        return id

    def del_permission(
        self,
        group_id,
        name='any',
        table_name='',
        record_id=0,
        ):
        """
        revokes group_id 'name' access to 'table_name' and 'record_id'
        """

        permission = self.settings.table_permission
        log = self.messages.del_permission_log
        if log:
            self.log_event(log % dict(group_id=group_id, name=name,
                           table_name=table_name, record_id=record_id))
        return self.db(permission.group_id == group_id)(permission.name
                 == name)(permission.table_name
                           == str(table_name))(permission.record_id
                 == long(record_id)).delete()

    def accessible_query(self, name, table, user_id=None):
        """
        returns a query with all accessible records for user_id or
        the current logged in user
        this method does not work on GAE because uses JOIN and IN

        example::

           db(accessible_query('read', db.mytable)).select(db.mytable.ALL)

        """
        if not user_id:
            user_id = self.user.id
        if self.has_permission(name, table, 0, user_id):
            return table.id > 0
        db = self.db
        membership = self.settings.table_membership
        permission = self.settings.table_permission
        return table.id.belongs(db(membership.user_id == user_id)\
                           (membership.group_id == permission.group_id)\
                           (permission.name == name)\
                           (permission.table_name == table)\
                           ._select(permission.record_id))


class Crud(object):

    def url(self, f=None, args=[], vars={}):
        return self.environment.URL(r=self.environment.request,
                                    c=self.settings.controller,
                                    f=f, args=args, vars=vars)

    def __init__(self, environment, db):
        self.environment = Storage(environment)
        self.db = db
        request = self.environment.request
        self.settings = Settings()
        self.settings.auth = None
        self.settings.logger = None

        self.settings.create_next = None
        self.settings.update_next = None
        self.settings.controller = 'default'
        self.settings.delete_next = self.url()
        self.settings.download_url = self.url('download')
        self.settings.create_onvalidation = None
        self.settings.update_onvalidation = None
        self.settings.delete_onvalidation = None
        self.settings.create_onaccept = None
        self.settings.update_onaccept = None
        self.settings.update_ondelete = None
        self.settings.delete_onaccept = None
        self.settings.update_deletable = True
        self.settings.showid = False
        self.settings.keepvalues = False
        self.settings.lock_keys = True

        self.messages = Messages(self.environment.T)
        self.messages.submit_button = 'Submit'
        self.messages.delete_label = 'Check to delete:'
        self.messages.record_created = 'Record Created'
        self.messages.record_updated = 'Record Updated'
        self.messages.record_deleted = 'Record Deleted'

        self.messages.update_log = 'Record %(id)s updated'
        self.messages.create_log = 'Record %(id)s created'
        self.messages.read_log = 'Record %(id)s read'
        self.messages.delete_log = 'Record %(id)s deleted'

        self.messages.lock_keys = True

    def __call__(self):

        args = self.environment.request.args
        if len(args) < 1:
            redirect(self.url(args='tables'))
        elif args[0] == 'tables':
            return self.tables()
        elif args[0] == 'create':
            return self.create(args(1))
        elif args[0] == 'select':
            return self.select(args(1))
        elif args[0] == 'read':
            return self.read(args(1), args(2))
        elif args[0] == 'update':
            return self.update(args(1), args(2))
        elif args[0] == 'delete':
            return self.delete(args(1), args(2))
        else:
            raise HTTP(404)

    def log_event(self, message):
        if self.settings.logger:
            self.settings.logger.log_event(message, 'crud')

    def has_permission(self, name, table, record=0):
        if not self.settings.auth:
            return True
        try:
            record_id = record.id
        except:
            record_id = record
        return self.settings.auth.has_permission(name, str(table), record_id)

    def tables(self):
        request = self.environment.request
        return TABLE(*[TR(A(name, _href=self.url(args=('select',
                     name)))) for name in self.db.tables])

    def update(
        self,
        table,
        record,
        next=DEFAULT,
        onvalidation=DEFAULT,
        onaccept=DEFAULT,
        ondelete=DEFAULT,
        log=DEFAULT,
        message=DEFAULT,
        deletable=DEFAULT,
        ):
        """
        .. method:: Crud.update(table, record, [next=DEFAULT
            [, onvalidation=DEFAULT [, onaccept=DEFAULT [, log=DEFAULT
            [, message=DEFAULT[, deletable=DEFAULT]]]]]])

        """
        if not (isinstance(table, self.db.Table) or table in self.db.tables) \
                or (isinstance(record, str) and not str(record).isdigit()):
            raise HTTP(404)
        if not isinstance(table, self.db.Table):
            table = self.db[table]
        try:
            record_id = record.id
        except:
            record_id = record or 0
        if record_id and not self.has_permission('update', table, record_id):
            redirect(self.settings.auth.settings.on_failed_authorization)
        if not record_id \
                and not self.has_permission('create', table, record_id):
            redirect(self.settings.auth.settings.on_failed_authorization)

        request = self.environment.request
        response = self.environment.response
        session = self.environment.session
        if request.extension == 'json' and request.vars.json:
            request.vars.update(simplejson.loads(request.vars.json))
        if next == DEFAULT:
            next = request.vars._next or self.settings.update_next
        if onvalidation == DEFAULT:
            onvalidation = self.settings.update_onvalidation
        if onaccept == DEFAULT:
            onaccept = self.settings.update_onaccept
        if ondelete == DEFAULT:
            ondelete = self.settings.update_ondelete
        if log == DEFAULT:
            log = self.messages.update_log
        if deletable == DEFAULT:
            deletable = self.settings.update_deletable
        if message == DEFAULT:
            message = self.messages.record_updated
        form = SQLFORM(
            table,
            record,
            hidden=dict(_next=request.vars._next),
            showid=self.settings.showid,
            submit_button=self.messages.submit_button,
            delete_label=self.messages.delete_label,
            deletable=deletable,
            upload=self.settings.download_url,
            )
        if request.extension != 'html':
            (_session, _formname) = (None, None)
        else:
            (_session, _formname) = \
                (session, '%s/%s' % (table._tablename, form.record_id))
        if form.accepts(request.vars, _session, formname=_formname,
                        onvalidation=onvalidation,
                        keepvalues=self.settings.keepvalues):
            response.flash = message
            if log:
                self.log_event(log % form.vars)
            if request.vars.delete_this_record and ondelete:
                ondelete(form)
            if onaccept:
                onaccept(form)
            if request.extension != 'html':
                raise HTTP(200, 'RECORD CREATED/UPDATED')
            if isinstance(next, (list, tuple)): ### fix issue with 2.6
               next = next[0]
            if next: # Only redirect when explicit
                if next[0] != '/' and next[:4] != 'http':
                    next = self.url(next.replace('[id]', str(form.vars.id)))
                session.flash = response.flash
                redirect(next)
        elif request.extension != 'html':
            raise HTTP(401)
        return form

    def create(
        self,
        table,
        next=DEFAULT,
        onvalidation=DEFAULT,
        onaccept=DEFAULT,
        log=DEFAULT,
        message=DEFAULT,
        ):
        """
        .. method:: Crud.create(table, [next=DEFAULT [, onvalidation=DEFAULT
            [, onaccept=DEFAULT [, log=DEFAULT[, message=DEFAULT]]]]])
        """

        if next == DEFAULT:
            next = self.settings.create_next
        if onvalidation == DEFAULT:
            onvalidation = self.settings.create_onvalidation
        if onaccept == DEFAULT:
            onaccept = self.settings.create_onaccept
        if log == DEFAULT:
            log = self.messages.create_log
        if message == DEFAULT:
            message = self.messages.record_created
        return self.update(
            table,
            None,
            next=next,
            onvalidation=onvalidation,
            onaccept=onaccept,
            log=log,
            message=message,
            deletable=False,
            )

    def read(self, table, record):
        if not (isinstance(table, self.db.Table) or table in self.db.tables) \
                or (isinstance(record, str) and not str(record).isdigit()):
            raise HTTP(404)
        if not isinstance(table, self.db.Table):
            table = self.db[table]
        if not self.has_permission('read', table, record):
            redirect(self.settings.auth.settings.on_failed_authorization)
        request = self.environment.request
        session = self.environment.session
        form = SQLFORM(
            table,
            record,
            readonly=True,
            comments=False,
            upload=self.settings.download_url,
            showid=self.settings.showid,
            )
        if request.extension != 'html':
            return table._filter_fields(form.record, id=True)
        return form

    def delete(
        self,
        table,
        record_id,
        next=DEFAULT,
        message=DEFAULT,
        ):
        """
        .. method:: Crud.delete(table, record_id, [next=DEFAULT
            [, message=DEFAULT]])
        """
        if not (isinstance(table, self.db.Table) or table in self.db.tables) \
                or not str(record_id).isdigit():
            raise HTTP(404)
        if not isinstance(table, self.db.Table):
            table = self.db[table]
        if not self.has_permission('delete', table, record_id):
            redirect(self.settings.auth.settings.on_failed_authorization)
        request = self.environment.request
        session = self.environment.session
        if next == DEFAULT:
            next = request.vars._next or self.settings.delete_next
        if message == DEFAULT:
            message = self.messages.record_deleted
        record = table[record_id]
        if record:
            if self.settings.delete_onvalidation:
                self.settings.delete_onvalidation(record)
            del table[record_id]
            if self.settings.delete_onaccept:
                self.settings.delete_onaccept(record)
            session.flash = message
        redirect(next)

    def select(
        self,
        table,
        query=None,
        fields=None,
        orderby=None,
        limitby=None,
        headers={},
        **attr
        ):
        request = self.environment.request
        if not (isinstance(table, self.db.Table) or table in self.db.tables):
            raise HTTP(404)
        if not self.has_permission('select', table):
            redirect(self.settings.auth.settings.on_failed_authorization)
        #if record_id and not self.has_permission('select', table):
        #    redirect(self.settings.auth.settings.on_failed_authorization)
        if not isinstance(table, self.db.Table):
            table = self.db[table]
        if not query:
            query = table.id > 0
        if not fields:
            fields = [table.ALL]
        rows = self.db(query).select(*fields, **dict(orderby=orderby,
            limitby=limitby))
        if not rows:
            return None # Nicer than an empty table.
        if not 'linkto' in attr:
            attr['linkto'] = self.url(args='read')
        if not 'upload' in attr:
            attr['upload'] = self.url('download')
        if request.extension != 'html':
            return rows.as_list()
        return SQLTABLE(rows, headers=headers, **attr)


def fetch(url):
    try:
        from google.appengine.api.urlfetch import fetch
        if url.find('?') >= 0:
            (url, payload) = url.split('?')
            return fetch(url, payload=payload).content
        return fetch(url).content
    except:
        import urllib
        return urllib.urlopen(url).read()


regex_geocode = \
    re.compile('\<coordinates\>(?P<la>[^,]*),(?P<lo>[^,]*).*?\</coordinates\>')


def geocode(address):
    import re
    import urllib
    try:
        a = urllib.quote(address)
        txt = fetch('http://maps.google.com/maps/geo?q=%s&output=xml'
                     % a)
        item = regex_geocode.search(txt)
        (la, lo) = (float(item.group('la')), float(item.group('lo')))
        return (la, lo)
    except:
        return (0.0, 0.0)


def universal_caller(f, *a, **b):
    c = f.func_code.co_argcount
    n = f.func_code.co_varnames[:c]
    b = dict([(k, v) for k, v in b.items() if k in n])
    if len(b) == c:
        return f(**b)
    elif len(a) >= c:
        return f(*a[:c])
    raise HTTP(404, "Object does not exist")


class Service:

    def __init__(self, environment):
        self.environment = environment
        self.run_procedures = {}
        self.csv_procedures = {}
        self.xml_procedures = {}
        self.rss_procedures = {}
        self.json_procedures = {}
        self.jsonrpc_procedures = {}
        self.xmlrpc_procedures = {}
        self.amfrpc_procedures = {}
        self.amfrpc3_procedures = {}

    def run(self, f):
        """
        example::

            service = Service(globals())
            @service.run
            def myfunction(a, b):
                return a + b
            def call():
                return service()

        Then call it with::

            wget http://..../app/default/call/run/myfunc?a=3&b=4

        """
        self.run_procedures[f.__name__] = f
        return f

    def csv(self, f):
        """
        example::

            service = Service(globals())
            @service.csv
            def myfunction(a, b):
                return a + b
            def call():
                return service()

        Then call it with::

            wget http://..../app/default/call/csv/myfunc?a=3&b=4

        """
        self.run_procedures[f.__name__] = f
        return f

    def xml(self, f):
        """
        example::

            service = Service(globals())
            @service.xml
            def myfunction(a, b):
                return a + b
            def call():
                return service()

        Then call it with::

            wget http://..../app/default/call/xml/myfunc?a=3&b=4

        """
        self.run_procedures[f.__name__] = f
        return f

    def rss(self, f):
        """
        example::

            service = Service(globals())
            @service.rss
            def myfunction():
                return dict(title=..., link=..., description=...,
                    created_on=..., entries=[dict(title=..., link=...,
                        description=..., created_on=...])
            def call():
                return service()

        Then call it with::

            wget http://..../app/default/call/rss/myfunc

        """
        self.rss_procedures[f.__name__] = f
        return f

    def json(self, f):
        """
        example::

            service = Service(globals())
            @service.json
            def myfunction(a, b):
                return [{a: b}]
            def call():
                return service()

        Then call it with::

            wget http://..../app/default/call/json/myfunc?a=hello&b=world

        """
        self.json_procedures[f.__name__] = f
        return f

    def jsonrpc(self, f):
        """
        example::

            service = Service(globals())
            @service.jsonrpc
            def myfunction(a, b):
                return a + b
            def call():
                return service()

        Then call it with::

            wget http://..../app/default/call/jsonrpc/myfunc?a=hello&b=world

        """
        self.jsonrpc_procedures[f.__name__] = f
        return f

    def xmlrpc(self, f):
        """
        example::

            service = Service(globals())
            @service.xmlrpc
            def myfunction(a, b):
                return a + b
            def call():
                return service()

        The call it with::

            wget http://..../app/default/call/xmlrpc/myfunc?a=hello&b=world

        """
        self.xmlrpc_procedures[f.__name__] = f
        return f

    def amfrpc(self, f):
        """
        example::

            service = Service(globals())
            @service.amfrpc
            def myfunction(a, b):
                return a + b
            def call():
                return service()

        The call it with::

            wget http://..../app/default/call/amfrpc/myfunc?a=hello&b=world

        """
        self.amfrpc_procedures[f.__name__] = f
        return f

    def amfrpc3(self, domain='default'):
        """
        example::

            service = Service(globals())
            @service.amfrpc3('domain')
            def myfunction(a, b):
                return a + b
            def call():
                return service()

        The call it with::

            wget http://..../app/default/call/amfrpc/myfunc?a=hello&b=world

        """
        if not isinstance(domain, str):
            raise SyntaxError, "AMF3 requires a domain for function"

        def _amfrpc3(f):
            if domain:
                self.amfrpc3_procedures[domain+'.'+f.__name__] = f
            else:
                self.amfrpc3_procedures[f.__name__] = f
            return f
        return _amfrpc3

    def serve_run(self, args=None):
        request = self.environment['request']
        if not args:
            args = request.args
        if args and args[0] in self.run_procedures:
            return universal_caller(self.run_procedures[args[0]],
                                    *args[1:], **dict(request.vars))
        self.error()

    def serve_csv(self, args=None):
        request = self.environment['request']
        response = self.environment['response']
        response.headers['Content-Type'] = 'text/x-csv'
        if not args:
            args = request.args

        def none_exception(value):
            if isinstance(value, unicode):
                return value.encode('utf8')
            if hasattr(value, 'isoformat'):
                return value.isoformat()[:19].replace('T', ' ')
            if value == None:
                return '<NULL>'
            return value
        if args and args[0] in self.run_procedures:
            r = universal_caller(self.run_procedures[args[0]],
                                 *args[1:], **dict(request.vars))
            s = cStringIO.StringIO()
            if hasattr(r, 'export_to_csv_file'):
                r.export_to_csv_file(s)
            elif r and isinstance(r[0], (dict, Storage)):
                import csv
                writer = csv.writer(s)
                writer.writerow(r[0].keys())
                for line in r:
                    writer.writerow([none_exception(v) \
                                     for v in line.values()])
            else:
                import csv
                writer = csv.writer(s)
                for line in r:
                    writer.writerow(line)
            return s.getvalue()
        self.error()

    def serve_xml(self, args=None):
        request = self.environment['request']
        response = self.environment['response']
        response.headers['Content-Type'] = 'text/xml'
        if not args:
            args = request.args
        if args and args[0] in self.run_procedures:
            s = universal_caller(self.run_procedures[args[0]],
                                 *args[1:], **dict(request.vars))
            if hasattr(s, 'as_list'):
                s = s.as_list()
            return serializers.xml(s)
        self.error()

    def serve_rss(self, args=None):
        request = self.environment['request']
        response = self.environment['response']
        if not args:
            args = request.args
        if args and args[0] in self.rss_procedures:
            feed = universal_caller(self.rss_procedures[args[0]],
                                    *args[1:], **dict(request.vars))
        else:
            self.error()
        response.headers['Content-Type'] = 'application/rss+xml'
        return serializers.rss(feed)

    def serve_json(self, args=None):
        request = self.environment['request']
        response = self.environment['response']
        response.headers['Content-Type'] = 'text/x-json'
        if not args:
            args = request.args
        d = dict(request.vars)
        if args and args[0] in self.json_procedures:
            s = universal_caller(self.json_procedures[args[0]],
                                 *args[1:], **dict(request.vars))
            if hasattr(s, 'as_list'):
                s = s.as_list()
            return response.json(s)
        self.error()

    def serve_jsonrpc(self):
        import contrib.simplejson as simplejson
        import types
        import sys

        def return_response(id, result):
            return simplejson.dumps({'version': '1.1',
                'id': id, 'result': result, 'error': None})

        def return_error(id, code, message):
            return simplejson.dumps({'id': id,
                                     'version': '1.1',
                                     'error': {'name': 'JSONRPCError',
                                        'code': code, 'message': message}
                                     })

        request = self.environment['request']
        response = self.environment['response']
        methods = self.jsonrpc_procedures
        data = simplejson.loads(request.body.read())
        id, method, params = data["id"], data["method"], data["params"]
        if not method in methods:
            return return_error(id, 100, 'method "%s" does not exist' % method)
        try:
            s = methods[method](*params)
            if hasattr(s, 'as_list'):
                s = s.as_list()
            return return_response(id, s)
        except BaseException:
            etype, eval, etb = sys.exc_info()
            return return_error(id, 100, '%s: %s' % (etype.__name__, eval))
        except:
            etype, eval, etb = sys.exc_info()
            return return_error(id, 100, 'Exception %s: %s' % (etype, eval))

    def serve_xmlrpc(self):
        request = self.environment['request']
        response = self.environment['response']
        services = self.xmlrpc_procedures.values()
        return response.xmlrpc(request, services)

    def serve_amfrpc(self, version=0):
        try:
            import pyamf
            import pyamf.remoting.gateway
        except:
            return "pyamf not installed or not in Python sys.path"
        request = self.environment['request']
        response = self.environment['response']
        if version == 3:
            services = self.amfrpc3_procedures
            base_gateway = pyamf.remoting.gateway.BaseGateway(services)
            pyamf_request = pyamf.remoting.decode(request.body)
        else:
            services = self.amfrpc_procedures        
            base_gateway = pyamf.remoting.gateway.BaseGateway(services)
            context = pyamf.get_context(pyamf.AMF0)
            pyamf_request = pyamf.remoting.decode(request.body, context)
        pyamf_response = pyamf.remoting.Envelope(pyamf_request.amfVersion,
                                                 pyamf_request.clientType)
        for name, message in pyamf_request:
            pyamf_response[name] = base_gateway.getProcessor(message)(message)
        response.headers['Content-Type'] = pyamf.remoting.CONTENT_TYPE
        if version==3:
            return pyamf.remoting.encode(pyamf_response).getvalue()
        else:
            return pyamf.remoting.encode(pyamf_response, context).getvalue()

    def __call__(self):
        """
        register services with:
        service = Service(globals())
        @service.run
        @service.rss
        @service.json
        @service.jsonrpc
        @service.xmlrpc
        @service.jsonrpc
        @service.amfrpc
        @service.amfrpc3('domain')

        expose services with

        def call(): return service()

        call services with
        http://..../app/default/call/run?[parameters]
        http://..../app/default/call/rss?[parameters]
        http://..../app/default/call/json?[parameters]
        http://..../app/default/call/jsonrpc
        http://..../app/default/call/xmlrpc
        http://..../app/default/call/amfrpc
        http://..../app/default/call/amfrpc3
        """

        request = self.environment['request']
        if len(request.args) < 1:
            raise HTTP(400, "Bad request")
        arg0 = request.args(0)
        if arg0 == 'run':
            return self.serve_run(request.args[1:])
        elif arg0 == 'rss':
            return self.serve_rss(request.args[1:])
        elif arg0 == 'csv':
            return self.serve_csv(request.args[1:])
        elif arg0 == 'xml':
            return self.serve_xml(request.args[1:])
        elif arg0 == 'json':
            return self.serve_json(request.args[1:])
        elif arg0 == 'jsonrpc':
            return self.serve_jsonrpc()
        elif arg0 == 'xmlrpc':
            return self.serve_xmlrpc()
        elif arg0 == 'amfrpc':
            return self.serve_amfrpc()
        elif arg0 == 'amfrpc3':
            return self.serve_amfrpc(3)
        else:
            self.error()

    def error(self):
        raise HTTP(404, "Object does not exist")
