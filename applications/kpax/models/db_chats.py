db.define_table('chat_line',
    SQLField('name'),
    SQLField('description','text',default=''),
    SQLField('created_on','datetime',default=timestamp),
    SQLField('owner',db.user))

db.chat_line.name.requires=IS_NOT_EMPTY()
db.chat_line.owner.requires=VALID_USER
db.chat_line.access_types=['none','read','read/chat']
db.chat_line.public_fields=['name','description']

db.define_table('message',
    SQLField('chat_line',db.chat_line),
    SQLField('body','text',default=''),
    SQLField('posted_on','datetime',default=timestamp),
    SQLField('posted_by',db.user))

db.message.body.requires=IS_NOT_EMPTY()
db.message.posted_by.requires=VALID_USER
