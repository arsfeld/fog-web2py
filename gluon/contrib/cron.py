#!/usr/bin/env python
# -*- coding: utf-8 -*-

__name__ = 'cron'
__version__ = (0, 1, 1)
__author__ = 'Attila Csipa <web2py@csipa.in.rs>'

_generator_name = __name__ + '-' + '.'.join(map(str, __version__))

import sys
import os
import threading
import logging
import time
import sched
import re
import datetime
from subprocess import Popen, PIPE

# crontype can be 'soft', 'hard', None, 'external'

#from gluon import cache
crontype = 'soft'


class extcron(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(False)
        self.basedir = os.getcwd()

    def run(self):
        logging.debug('External cron invocation')
        if tokenmaster(os.path.join(
                self.basedir, 'applications', 'admin', 'cron')):
            crondance(apppath({'web2py_path': self.basedir}), 'ext')
            tokenmaster(os.path.join(
                self.basedir, 'applications', 'admin', 'cron'),
            action = 'release')


class hardcron(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.basedir = os.getcwd()

    def launch(self):
        path = apppath({'web2py_path': self.basedir})
        if crontype =='hard' and tokenmaster(os.path.join(path, 'admin', 'cron')):

            crondance(path, 'hard')
            tokenmaster(os.path.join(path, 'admin', 'cron'), action = 'release')

    def run(self):
        s = sched.scheduler(time.time, time.sleep)
        logging.info('Hard cron daemon started')
        while True:
            now = time.time()
            s.enter(60 - now % 60, 1, self.launch, ())
            s.run()


class softcron(threading.Thread):

    def __init__(self, env):
        threading.Thread.__init__(self)
        self.env = env
        self.cronmaster = 0
        self.softwindow = 120

    def run(self):
        if crontype != 'soft':
            return

        path = apppath(self.env)
        now = time.time()
        # our own thread did a cron check less than a minute ago, don't even
        # bother checking the file
        if self.cronmaster and 60 > now - self.cronmaster:
            logging.debug("Don't bother with cron.master, it's only %s s old"
                           % (now - self.cronmaster))
            return

        logging.debug('Cronmaster stamp: %s, Now: %s'
                       % (self.cronmaster, now))
        if 60 <= now - self.cronmaster:  # new minute, do the cron dance
            self.cronmaster = tokenmaster(os.path.join(path, 'admin', 'cron'))
            if self.cronmaster:
                crondance(path, 'soft')
                self.cronmaster = \
                    tokenmaster(os.path.join(path, 'admin', 'cron'),
                        action = 'release')


def tokenmaster(path, db = None, action = 'claim'):
    token = os.path.join(path, 'cron.master')
    tokeninuse = os.path.join(path, 'cron.running')
    global crontype

    if action == 'release':
        logging.debug('WEB2PY CRON: Releasing cron lock')
        try:
            os.unlink(tokeninuse)
            return time.time()
        except:
            return 0

    try:
        tokentime = os.stat(token).st_mtime
        # already ran in this minute?
        if tokentime - (tokentime % 60) + 60 > time.time():
            return 0
    except:
        pass

    try:
        # running now?
        if os.path.exists(tokeninuse):
            logging.warning('alreadyrunning')
            # check if stale, just in case
            if os.stat(tokeninuse).st_mtime + 60 < time.time():
                logging.warning('WEB2PY CRON: Stale cron.master detected')
                os.unlink(tokeninuse)

        # no tokens, new install ? Need to regenerate anyho
        if not (os.path.exists(token) or os.path.exists(tokeninuse)):
            logging.warning(
                "WEB2PY CRON: cron.master not found at %s. Trying to re-create."
                % token)
            try:
                mfile = open(token, 'wb')
                mfile.close()
            except:
                crontype = ''
                logging.error(
                    'WEB2PY CRON: Unable to re-create cron.master, ' + \
                    'cron functionality likely not available')
                return 0

        # has unclaimed token and not running ?
        if os.path.exists(token) and not os.path.exists(tokeninuse):
            logging.debug('WEB2PY CRON: Trying to acquire lock')
            try:
                os.rename(token, tokeninuse)
                # can't rename, must recreate as we need a correct claim time
                mfile = open(token, 'wb')
                mfile.close()
                logging.debug('WEB2PY CRON: Locked')
                return os.stat(token).st_mtime

            except:
                logging.info('WEB2PY CRON: Failed to claim %s' % token)
                return 0
    except Exception, e:
        crontype = ''
        logging.error("WEB2PY CRON: Cron fail, reason: %s" % e)
        return 0

    logging.debug('WEB2PY CRON: already started from another process')
    return 0


def apppath(env=None):
    try:
        apppath = os.path.join(env.get('web2py_path'), 'applications')
    except:
        apppath = os.path.join(os.path.split(env.get('SCRIPT_FILENAME'))[0],
            'applications')
    return apppath


def rangetolist(str, period='min'):
    retval = []
    if str.startswith('*'):
        if period == 'min':
            str = str.replace('*', '0-59', 1)
        elif period == 'hr':
            str = str.replace('*', '0-23', 1)
        elif period == 'dom':
            str = str.replace('*', '1-31', 1)
        elif period == 'mon':
            str = str.replace('*', '1-12', 1)
        elif period == 'dow':
            str = str.replace('*', '0-6', 1)
    m = re.compile(r'(\d+)-(\d+)/(\d+)')
    match = m.match(str)
    if match:
        for i in range(int(match.group(1)), int(match.group(2)) + 1):
            if i % int(match.group(3)) == 0:
                retval.append(i)
    return retval


def parsecronline(line):
    task = {}
    if line.startswith('@reboot'):
        line=line.replace('@reboot', '-1 * * * *')
    elif line.startswith('@yearly'):
        line=line.replace('@yearly', '0 0 1 1 *')
    elif line.startswith('@annually'):
        line=line.replace('@annually', '0 0 1 1 *')
    elif line.startswith('@monthly'):
        line=line.replace('@monthly', '0 0 1 * *')
    elif line.startswith('@weekly'):
        line=line.replace('@weekly', '0 0 * * 0')
    elif line.startswith('@daily'):
        line=line.replace('@daily', '0 0 * * *')
    elif line.startswith('@midnight'):
        line=line.replace('@midnight', '0 0 * * *')
    elif line.startswith('@hourly'):
        line=line.replace('@hourly', '0 * * * *')
    params = line.split(None, 6)
    for (str, id) in zip(params[:5], ['min', 'hr', 'dom', 'mon', 'dow']):
        if not str in [None, '*']:
            task[id] = []
            vals = str.split(',')
            for val in vals:
                if val.find('/') > -1:
                    task[id] += rangetolist(val, id)
                else:
                    try:
                        task[id].append(int(val))
                    except ValueError:
                        pass
    if len(params) > 5:
        task['user'] = params[5]
        task['cmd'] = params[6].strip()
    return task


class cronlauncher(threading.Thread):
    def __init__(self, cmdline, shell=True):
        threading.Thread.__init__(self)
        self.cmd = cmdline
        self.shell = shell

    def run_popen(self):        
        if os.name == 'nt':
            proc = Popen(self.cmd, stdin=PIPE, stdout=PIPE,
                         stderr=PIPE, shell=self.shell)
        else:
            proc = Popen(
                self.cmd,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                shell=self.shell
                #close_fds=self.shell
                )        
        (stdoutdata,stderrdata) = proc.communicate()
        if proc.returncode != 0:
            logging.warning(
                'WEB2PY CRON Call returned code %s:\n%s' % \
                    (proc.returncode, stdoutdata+stderrdata))
        else:
            logging.debug('WEB2PY CRON Call retruned success:\n%s' % stdoutdata)


    def run(self):        
        try:
            self.run_popen()
        except KeyError, e:
            logging.error('WEB2PY CRON: Execution error for %s: %s' % (self.cmd, e))


def crondance(apppath, ctype='soft',startup=False):
    if os.path.exists('web2py.py'):
        mainrun = sys.executable+' web2py.py' # run from source
    else:
        mainrun = sys.executable # run windows binary
    try:
        now_s = time.localtime()
        for app in filter(lambda x: os.path.isdir(os.path.join(apppath, x)),
                os.listdir(apppath)):
            apath=os.path.join(apppath,app)
            cronpath = os.path.join(apath, 'cron')
            # If the cron folder does not exist, we will
            # create it
            if not os.path.exists(cronpath):
                os.mkdir(cronpath)

            crontab = os.path.join(cronpath, 'crontab')

            if os.path.exists(crontab):
                f = open(crontab, 'rt')
                cronlines = f.readlines()
                for cline in filter(lambda x: \
                                        not x.strip().startswith('#')\
                                        and len(x.strip()) > 0, cronlines):
                    task = parsecronline(cline)
                    go = True                  
                    if 'min' in task and not now_s.tm_min in task['min']:
                        if task['min'] > -1 or ctype == 'ext': 
                            go = False
                    elif 'hr' in task and not now_s.tm_hour in task['hr']:
                        go = False
                    elif 'mon' in task and not now_s.tm_mon in task['mon']:
                        go = False
                    elif 'dom' in task and not now_s.tm_mday in task['dom']:
                        go = False
                    elif 'dow' in task and not now_s.tm_wday in task['dow']:
                        go = False
                    if startup and task['min'] == -1:
                        go = True

                    if go and 'cmd' in task:
                        logging.info(
                            'WEB2PY CRON (%s): Application: %s executing %s in %s at %s' \
                                % (ctype, app, task.get('cmd'),
                                   os.getcwd(), datetime.datetime.now()))
                        try:
                            command = task['cmd']
                            if command.startswith('**'):
                                (action,models,command) = (True,'',command[2:])
                            elif command.startswith('*'):
                                (action,models,command) = (True,'-M',command[1:])
                            else:
                                action=False
                            if command.endswith('.py'):
                                shell_command = \
                                    '%s -P -N %s -S %s -a "<recycle>" -R %s' \
                                    % (mainrun,models,app,command)
                                cronlauncher(shell_command,
                                             shell=True).start()
                            elif action:
                                shell_command = \
                                    '%s -P -N %s -S %s/%s -a "<recycle>"' \
                                    % (mainrun,models,app,command)
                                cronlauncher(shell_command,
                                             shell=True).start()
                                
                            else:
                                cronlauncher(command).start()
                        except Exception, e:
                            logging.warning(
                                'WEB2PY CRON: Execution error for %s: %s' \
                                    % (task.get('cmd'), e))
    except Exception, e:

        import traceback
        logging.warning(traceback.format_exc())
        logging.warning('WEB2PY CRON: exception: %s', e)
