from gluon.storage import Storage

db.define_table('users_group',
   SQLField('name'),
   SQLField('description','text',default='No group description'),
   SQLField('owner',db.user),
   SQLField('open','boolean',default=False),
   SQLField('created_on','datetime',default=timestamp))

db.users_group.name.requires=IS_NOT_EMPTY()
db.users_group.owner.requires=VALID_USER
db.users_group.access_types=['none','see','see/join']
db.users_group.public_fields=['name','description','open']

db.define_table('membership',
   SQLField('user',db.user),
   SQLField('users_group',db.users_group),
   SQLField('membership_type',default='regular member'))

db.define_table('membership_request',
   SQLField('user',db.user),
   SQLField('users_group',db.users_group),
   SQLField('membership_type',default='regular member'))

db.membership.user.requires=VALID_USER
db.membership.users_group.requires=IS_IN_DB(db,'users_group.id','%(id)s:(name)s')

db.define_table('access',
   SQLField('users_group',db.users_group),
   SQLField('table_name'),
   SQLField('record_id','integer'),
   SQLField('access_type'))

db.access.users_group.requires=IS_IN_DB(db,'users_group.id')
db.access.access_type.requires=IS_IN_SET(['read','edit'])

db.define_table('announcement',
   SQLField('title'),
   SQLField('body','text',default=''),
   SQLField('owner',db.user),
   SQLField('to_rss','boolean',default=False),
   SQLField('posted_on','datetime',default=timestamp),
   SQLField('expires_on','date',default=today+datetime.timedelta(30)))

db.announcement.title.requires=IS_NOT_EMPTY()
db.announcement.owner.requires=VALID_USER
db.announcement.access_types=['none','read']
db.announcement.public_fields=['title','body','expires_on','to_rss']

db.define_table('ignore_announcement',
   SQLField('user',db.user),
   SQLField('announcement',db.announcement))

db.ignore_announcement.user.requires=VALID_USER
db.ignore_announcement.announcement.requires=IS_IN_DB(db,'announcement.id')

def get_groups(user_id):
    rows=db(db.users_group.id==db.membership.users_group)\
           (db.membership.user==user_id).select()
    rows=[Storage(dict(id=row.users_group.id,\
                       name=row.users_group.name,\
                       membership_type=row.membership.membership_type))\
          for row in rows]
    return rows

def is_owner(user_id,table_name,record_id):
    if not db.has_key(table_name): return False
    return len(db(db[table_name].id==record_id)(db[table_name].owner==user_id).select())

def has_access(user_id,table_name,record_id,access_types):
    if not isinstance(access_types,tuple): access_types=(access_types,)
    rows=db(db.access.table_name==table_name)\
           (db.access.record_id==record_id)\
           (db.access.access_type.belongs(access_types))\
           (db.access.users_group.belongs(g_tuple)).select()     
    if not len(rows): return None
    return rows[0]

if len(db(db.users_group.id>0).select())==0:
    db.users_group.insert(name='Everybody',description='All registered users belong to this group',owner=1) ## must be group 1

if session.token:
    session.user_id=user_id=int(session.token[0])
    session.user_email=user_email=session.token[1]
    session.user_name=user_name=session.token[2]
    session.groups=groups=get_groups(user_id)
    session.g_tuple=g_tuple=tuple([group.id for group in groups])
    if len(session.groups)==0:
        group_id=db.users_group.insert(name=user_name,owner=user_id,description='This group is just for yourself and for people you want to give access to everything you have access to')
        db.membership.insert(users_group=1,user=user_id)
        db.membership.insert(users_group=group_id,user=user_id)
        session.groups=groups=get_groups(user_id)
        session.g_tuple=g_tuple=tuple([group.id for group in groups])
else:
    session.user_id=None
    session.user_email=None
    session.user_name=None
    session.groups=None
    session.g_tuple=None
"""
note g_tuple[0] is always (1), the group everybody
     g_tuple[1] is always the group identified by user_id
"""


def accessible(table_name,access_types=('read',)):
    return db(db.access.users_group.belongs(g_tuple))\
             (db.access.table_name==table_name)\
             (db.access.access_type.belongs(access_types))\
             (db[table_name].id==db.access.record_id)

def find_groups(items):
    new_items=[]
    last=None
    for item in items:
        if item.access.record_id!=last:
            last=item.access.record_id
            new_items.append(item)
            item.accessible_to=[item.access.users_group]
        else:
            new_items[-1].accessible_to.append(item.access.users_group)
    return new_items

def redirect_change_permissions(table_name,id):
    redirect(URL(r=request,c='access',f='change',args=[table_name,id],\
      vars=dict(forward=URL(r=request,f='index'))))

def change_permissions(table_name):
    return A(IMG(_src=URL(r=request,c='static',f='main_images/change_permissions.png')),
      _href=URL(r=request,c='access',f='change',\
      args=[table_name,request.args[0]],vars=dict(forward=URL(r=request,f='index'))))
