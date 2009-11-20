import random
import time; now=time.time()
import datetime; 
timestamp=datetime.datetime.today()
today=datetime.date.today()

T.force('pt-br')

db=SQLDB("sqlite://main.db")

db.define_table('user',
                SQLField('firstname'),
                SQLField('lastname'),
                SQLField('username'),
                SQLField('email'),
                SQLField('password','password'),
                SQLField('verification',default=''),
                SQLField('member', 'boolean'),
                SQLField('last_attempt_time','integer',default=0),
                SQLField('failed_attempts','integer',default=0),
                SQLField('member_since', 'date'),
                SQLField('cell_phone', 'string'),
                SQLField('email_gmail', 'string'),
                SQLField('nrousp', 'string'),
                SQLField('course', 'string'),
                SQLField('course_year', 'string'),
                SQLField('current_area', 'string'),
                )

db.user.username.requires=IS_NOT_EMPTY()
db.user.email.requires=[IS_EMAIL(),IS_NOT_IN_DB(db,'user.email')]

db.define_table('ticket',
                SQLField('ctime','integer',default=now),
                SQLField('url'),
                SQLField('code'),
                SQLField('user',db.user))

VALID_USER=IS_IN_DB(db(db.user.verification==''),'user.id','%(id)s:%(name)s')
