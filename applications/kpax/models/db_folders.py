db.define_table('folder',
    SQLField('name'),
    SQLField('description','text',default=''),
    SQLField('keywords','string',length=128,default=''),
    SQLField('is_open','boolean',default=False),
    SQLField('created_on','datetime',default=timestamp),
    SQLField('owner',db.user))

db.folder.name.requires=IS_NOT_EMPTY()
db.folder.owner.requires=VALID_USER
db.folder.access_types=['none','read','read/edit']
db.folder.public_fields=['name','description','keywords','is_open']

db.define_table('page',
    SQLField('folder',db.folder),
    SQLField('number','integer',default=0),
    SQLField('locked_on','integer',default=0),
    SQLField('locked_by','integer',default=0),
    SQLField('title'),
    SQLField('body','text',default=''),
    SQLField('readonly','boolean',default=False),
    SQLField('comments_enabled','boolean',default=False),
    SQLField('modified_on','datetime',default=timestamp),
    SQLField('modified_by',db.user))

db.page.folder.requires=IS_IN_DB(db,'folder.id','%(id)s:%(name)s')
db.page.title.requires=IS_NOT_EMPTY()
db.page.modified_by.requires=VALID_USER
db.page.public_fields=['title','body','readonly','comments_enabled']

db.define_table('old_page',
    SQLField('page',db.page),
    SQLField('title'),
    SQLField('body','text',default=''),
    SQLField('modified_on','datetime',default=timestamp),
    SQLField('modified_by',db.user))

db.define_table('document',
    SQLField('page',db.page),
    SQLField('title'),
    SQLField('file','upload'),
    SQLField('uploaded_by',db.user),
    SQLField('uploaded_on','datetime',default=timestamp))

db.document.uploaded_by.requires=VALID_USER
db.document.page.requires=IS_IN_DB(db,'page.id','%(id)s:%(title)s')
db.document.title.requires=IS_NOT_EMPTY()
db.document.public_fields=['title','file']

db.define_table('comment',
    SQLField('page',db.page),
    SQLField('posted_on','datetime',default=timestamp),
    SQLField('author',db.user),
    SQLField('disabled',default=False),
    SQLField('body','text',default=''))

db.comment.page.requires=IS_IN_DB(db,'page.id','%(id)s:%(title)s')
db.comment.body.requires=IS_NOT_EMPTY()
db.comment.author.requires=VALID_USER
db.comment.public_fields=['body']