if not session.token: redirect(LOGIN)

def change():
    if len(request.args)<2: redirect(MAIN)
    table_name=request.args[0]
    record_id=request.args[1]
    if not is_owner(user_id,table_name,record_id):
        session.flash="not authorized"
        redirect(MAIN)
    access_types=db[table_name].access_types
    rows=db(db.access.table_name==table_name)\
           (db.access.record_id==record_id)\
           (db.access.users_group==db.users_group.id)\
           .select(orderby=db.access.id)
    group_keys=dict([(r.users_group.id,r.access.access_type) for r in rows])
    keys=dict([(r.access.id,r.access.access_type) for r in rows])
    accesses=[]
    for g in session.groups:
        if table_name=='users_group' and g.id==int(record_id): continue
        item=Storage()
        item.group_id=g.id
        item.group_name=g.name
        item.membership_type=g.membership_type
        if group_keys.has_key(g.id): item.access_type=group_keys[g.id] 
        else: item.access_type='none'
        accesses.append(item)
    ch=False
    for key,value in request.vars.items():
        if key=='forward': continue
        ch=True
        g=int(key[1:])
        if g==g_tuple[1]: continue
        if g==g_tuple[0] and user_id!=1: continue
        if group_keys.has_key(g):
            s=db(db.access.users_group==g)\
                (db.access.record_id==record_id)\
                (db.access.table_name==table_name)
            if value=='none': 
                s.delete()
            elif value in access_types: 
                s.update(access_type=value)
        elif value!='none' and value in access_types:
            db.access.insert(users_group=g,
                             table_name=table_name,
                             record_id=record_id,
                             access_type=value)
    if ch: redirect(request.vars.forward)
    return dict(accesses=accesses,access_types=access_types)