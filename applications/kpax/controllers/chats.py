if not session.token and not request.function=='rss': redirect(LOGIN)

import cgi

def index():
    chats=accessible('chat_line',('read','read/chat'))(db.chat_line.owner==db.user.id).select(orderby=db.chat_line.name,groupby=db.chat_line.id)
    return dict(chats=find_groups(chats))

def create_chat():
    form=SQLFORM(db.chat_line,fields=db.chat_line.public_fields)
    form.vars.owner=user_id
    if form.accepts(request.vars,session):
        id=db.access.insert(users_group=g_tuple[1],table_name='chat_line',\
                            record_id=form.vars.id,access_type='read/chat')
        session.flash='chat line created'
        redirect_change_permissions(db.chat_line,form.vars.id)
    return dict(form=form)

def edit_chat():
    if len(request.args)<1: redirect(URL(r=request,f='index'))
    rows=db(db.chat_line.id==request.args[0])\
           (db.chat_line.owner==user_id).select()
    if not len(rows): redirect(URL(r=request,f='index'))
    form=SQLFORM(db.chat_line,rows[0],deletable=True,\
                 fields=db.chat_line.public_fields,showid=False)
    if form.accepts(request.vars,session):
        if request.vars.delete_this_record=='on':
            session.flash='chat line deleted for good'
        else:
            session.flash='chat line info saved'
        redirect(URL(r=request,f='index'))
    return dict(form=form)

def open_chat():
    if len(request.args)<1: redirect(URL(r=request,f='index'))
    chat_id=request.args[0]
    access=has_access(user_id,'chat_line',chat_id,('read','read/chat'))
    if not access:
        session.flash='access denied'
        redirect(URL(r=request,f='index'))    
    chat_line=db(db.chat_line.id==chat_id).select()[0]
    readonly=access.access_type=='read'
    return dict(readonly=readonly,chat_line=chat_line)

def clear():
    chat_id=request.args[0]
    if len(db(db.chat_line.id==chat_id)(db.chat_line.owner==user_id).select()):
        db(db.message.chat_line==chat_id).delete()
    redirect(URL(r=request,f='index'))

def post():
    chat_id=request.args[0]
    access=has_access(user_id,'chat_line',chat_id,('read','read/chat'))
    if not access: raise HTTP(400)
    if request.vars.message and access.access_type=='read/chat':
        db.message.insert(body=request.vars.message.strip(),\
                          posted_by=user_id,chat_line=chat_id)
    messages=db(db.message.chat_line==chat_id)\
               (db.message.posted_by==db.user.id)\
               (db.message.id>request.vars.last)\
               .select(orderby=db.message.posted_on)
    posts=[[m.message.id,str(m.message.posted_on),\
            cgi.escape(m.user.name),m.user.email,
            cgi.escape(m.message.body).replace('//','<br/>')] \
           for m in messages]
    import gluon.contrib.simplejson as sj
    return sj.dumps(posts)

"""
def rss():
    response.headers['Content-Type']='application/rss+xml'
    import gluon.contrib.rss2 as rss2
    requested_groups=request.vars.groups or '1'
    try: requested_groups=tuple([int(i) for i in requested_groups.split(',')])
    except: return ''
    entries=db(db.announcement.id==db.access.record_id)\
            (db.access.table_name=='announcement')\
            (db.access.users_group.belongs(requested_groups))\
            (db.announcement.to_rss==True)\
            (db.user.id==db.announcement.owner)\
            .select(groupby=db.announcement.id)
    items = [rss2.RSSItem(
               title=entry.announcement.title,
               link=MAIN,
               author=entry.user.email,
               description = entry.announcement.body,
               pubDate = entry.announcement.posted_on) for entry in entries]
    rss = rss2.RSS2(title='public rss for '+str(requested_groups),
       link = MAIN,
       description = str(requested_groups),
       lastBuildDate = datetime.datetime.now(),
       items=items)
    return rss2.dumps(rss)
"""