if not session.token: redirect(LOGIN)

def index():
    form=FORM(INPUT(_name='group',requires=IS_MATCH('(g|G)\d+')),
              INPUT(_type='submit',_value='join!'))
    if form.accepts(request.vars,formname='join_group'):
        users_group=int(form.vars.group[1:])
        groups=db(db.users_group.id==users_group).select()
        if users_group in g_tuple:
            response.flash='you are already a member of the group'
        elif len(groups)==0:
            response.flash='unkown group'
        elif has_access(user_id,'users_group',users_group,'see/join') or \
             groups[0].open==True:
            db.membership.insert(user=user_id,users_group=users_group)
            session.groups=get_groups(user_id)              
            session.g_tuple=tuple([g.id for g in session.groups])
            response.flash='group joined'
        else:
            db.membership_request.insert(user=user_id,users_group=users_group)
            session.groups=get_groups(user_id)
            session.g_tuple=tuple([g.id for g in session.groups])
            response.flash='your request to join was submitted'
    mygroups=db(db.users_group.id.belongs(session.g_tuple))\
               (db.users_group.owner==db.user.id).select(orderby=db.users_group.name.upper())
    return dict(mygroups=mygroups,form=form)

def unjoin():
    if len(request.args) and \
       not int(request.args[0]) in [g_tuple[0],g_tuple[1]]:
        db(db.membership.users_group==request.args[0]).delete()
    redirect(URL(r=request,f='index'))

def members():
    members=db(db.membership.users_group==request.args[0])\
              (db.membership.user==db.user.id).select()
    return dict(members=members)

def approve():
    if len(request.args) and len(db(db.users_group.id==request.args[0])(db.users_group.owner==user_id).select()):
       for item in request.vars.items():
           if item[1]=='approve':
                req=db(db.membership_request.id==item[0]).select()[0]
                db(db.membership_request.id==item[0]).delete()
                db.membership.insert(users_group=req.users_group,user=req.user)
           elif item[1]=='deny':
                db(db.membership_request.id==item[0]).delete()         
    pending=db(db.membership_request.users_group==request.args[0])\
              (db.membership_request.user==db.user.id).select()
    if len(pending)==0:
        session.flash='no pending applications for membership'
        redirect(URL(r=request,f='index'))
    return dict(pending=pending)

def create_group():
    form=SQLFORM(db.users_group,fields=db.users_group.public_fields)
    form.vars.owner=user_id
    if form.accepts(request.vars,session):
        db.membership.insert(user=user_id,users_group=form.vars.id)
        session.flash='group created'
        redirect_change_permissions(db.users_group,form.vars.id)
    return dict(form=form)

def edit_group():
    if len(request.args)<1: redirect(URL(r=request,f='index'))
    rows=db(db.users_group.id==request.args[0])\
           (db.users_group.owner==user_id).select()
    if not len(rows): redirect(URL(r=request,f='index'))
    form=SQLFORM(db.users_group,rows[0],fields=db.users_group.public_fields,
                 deletable=True)
    if form.accepts(request.vars,session):
        if request.vars.delete_this_record=='on':
            session.flash='group deleted'
        else:
            session.flash='group saved'
        redirect(URL(r=request,f='index'))
    return dict(form=form)
