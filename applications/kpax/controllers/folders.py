if not session.token and not request.function in ['public','download']:
    redirect(LOGIN)

import os, re

def remove_tags(text): return re.sub('<.+?>',' ',text)

def index():
    myfolders=accessible('folder',('read','read/edit'))\
              (db.folder.owner==db.user.id)\
              .select(orderby=db.folder.name.upper())
    return dict(myfolders=find_groups(myfolders))


def create_folder():
    form=SQLFORM(db.folder,fields=db.folder.public_fields)
    form.vars.owner=user_id
    if form.accepts(request.vars,session):
        db.access.insert(users_group=g_tuple[1],table_name='folder',\
                         record_id=form.vars.id,access_type='read/edit')
        session.flash='folder created'
        redirect_change_permissions(db.folder,form.vars.id)
    return dict(form=form)

def edit_folder():
    if len(request.args)<1: redirect(URL(r=request,f='index'))
    rows=db(db.folder.id==request.args[0])\
           (db.folder.owner==user_id).select()
    if not len(rows): redirect(URL(r=request,f='index'))
    form=SQLFORM(db.folder,rows[0],fields=db.folder.public_fields,
                 deletable=True,showid=False)
    if form.accepts(request.vars,session):
        if request.vars.delete_this_record=='on':
            session.flash='folder deleted'
        else:
            session.flash='folder saved'
        redirect(URL(r=request,f='index'))
    return dict(form=form)

def open_folder():
    if not len(request.args) or \
       not has_access(user_id,'folder',request.args[0],('read','read/edit')):
         session.flash='not authorized'
         redirect(URL(r=request,f='index'))    
    folder=db(db.folder.id==request.args[0]).select()[0]
    return dict(folder=folder)

def compare():
    old_page_id=request.vars.id
    old_pages=db(db.old_page.id==old_page_id)\
                (db.old_page.modified_by==db.user.id).select()
    if not len(old_pages):
        session.flash='document does not exist'
        redirect(URL(r=request,f='index'))
    old_page=old_pages[0]
    page=db(db.page.id==old_page.old_page.page)\
           (db.page.modified_by==db.user.id).select()[0]
    if not has_access(user_id,'folder',page.page.folder,('read','read/edit')):
         session.flash='not authorized'
         redirect(URL(r=request,f='open_folder',args=[page.folder]))
    import difflib
    lines=difflib.ndiff(old_page.old_page.body.splitlines(),page.page.body.splitlines())
    trows=[]
    for line in lines:
        if line[:2]=='- ': trows.append(TR('DELETED:',line[2:]))
        if line[:2]=='+ ': trows.append(TR('ADDED:',line[2:]))
    return dict(page=page,old_page=old_page,diff=TABLE(*trows))


def show_page():
    if not len(request.args) or \
       not has_access(user_id,'folder',request.args[0],('read','read/edit')):
         redirect(URL(r=request,f='open_folder',args=request.args))
    folder=db(db.folder.id==request.args[0]).select()[0]
    pages=db(db.page.folder==folder.id).select(orderby=db.page.number)
    if len(pages)==0:
        if has_access(user_id,'folder',request.args[0],'read/edit'):
            redirect(URL(r=request,f='edit_page',args=request.args))
        else:
            session.flash='this folder is empty'
            redirect(URL(r=request,f='open_folder',args=request.args))
    page=pages[0]
    if len(request.args)>1:
        for row in pages:
            if row.id==int(request.args[1]): page=row
    if len(request.args)<2: request.args.append(page.id)
    form=SQLFORM(db.comment,fields=db.comment.public_fields,\
                 labels={'body':'Your comment:'})
    form.vars.page=page.id
    form.vars.author=user_id
    form.vars.posted_on=timestamp
    if form.accepts(request.vars,session):
        response.flash='commment posted'
    documents=db(db.document.page==page.id).select(orderby=db.document.title.lower())
    comments=db(db.comment.page==page.id)\
               (db.comment.author==db.user.id).select()
    old_pages=db(db.old_page.page==page.id)(db.old_page.modified_by==db.user.id).select(db.old_page.id,db.old_page.modified_on,db.user.name,db.user.id,orderby=~db.old_page.id)
    return dict(folder=folder,pages=pages,page=page,form=form,
                documents=documents,comments=comments,old_pages=old_pages)

def public():
    if not len(request.args): redirect(ERROR)
    folders=db(db.folder.id==request.args[0])(db.folder.is_open==True).select()
    if not len(folders): redirect(ERROR)
    folder=folders[0]
    pages=db(db.page.folder==folder.id).select(orderby=db.page.number)
    if len(pages)==0: redirect(ERROR)
    page=pages[0]
    if len(request.args)>1:
        for row in pages:
            if row.id==int(request.args[1]): page=row
    if len(request.args)<2: request.args.append(page.id)
    documents=db(db.document.page==page.id)\
              .select(orderby=db.document.title.lower())
    comments=db(db.comment.page==page.id)\
               (db.comment.author==db.user.id).select()
    response.title=folder.name
    response.description=remove_tags(folder.description)
    response.keywords=folder.keywords
    return dict(folder=folder,pages=pages,page=page,
                documents=documents,comments=comments)

def edit_page():
    if len(request.args)<1 or \
       not has_access(user_id,'folder',request.args[0],'read/edit'):
         session.flash="not authorized"
         redirect(URL(r=request,f='show_page',args=request.args))
    folder=db(db.folder.id==request.args[0]).select()[0]
    pages=db(db.page.folder==folder.id).select(orderby=db.page.number)
    if len(pages)==0:
        redirect(URL(r=request,f='append_page',args=[folder.id]))
    page=pages[0]
    if len(request.args)>1:
        for row in pages:
            if row.id==int(request.args[1]): page=row
    if page.locked_by!=user_id and page.locked_on+PAGE_LOCK_TIME>now:
        session.flash='page is locked by another user, please wait'
        redirect(URL(r=request,f='show_page',args=request.args))
    else:
        response.flash='mind that this page is now locked by you until move away form it'
        page.update_record(locked_on=now,locked_by=user_id)
    if folder.owner!=user_id and page.readonly==False:
        session.flash='page is readonly'
        redirect(URL(r=request,f='open_folder',args=request.args))
    if len(request.args)<2: request.args.append(page.id)
    form_page=SQLFORM(db.page,page,fields=db.page.public_fields,\
                      deletable=db.folder.owner==user_id,showid=False)
    form_page.vars.folder=folder.id
    form_page.vars.modified_on=timestamp
    form_page.vars.modified_by=user_id
    if form_page.accepts(request.vars,session):
        db.old_page.insert(page=page.id,title=page.title,\
                           body=page.body,modified_by=user_id)
        session.flash='page saved'
        redirect(URL(r=request,f='show_page',args=request.args))
    form_document=SQLFORM(db.document,fields=db.document.public_fields)
    form_document.vars.page=page.id
    if form_document.accepts(request.vars,session):
        response.flash='document uploaded'
    documents=db(db.document.page==page.id).select(orderby=db.document.title.lower())
    comments=db(db.comment.page==page.id)\
               (db.comment.author==db.user.id).select()
    return dict(folder=folder,pages=pages,form_page=form_page,
                form_document=form_document,page=page,
                documents=documents,comments=comments)

def relock():
    page_id=request.args[0]
    pages=db(db.page.id==page_id)(db.page.locked_by==user_id).select()
    if len(pages): pages[0].update_record(locked_on=now)
    return ''

def append_page():
    if not len(request.args) or\
       not has_access(user_id,'folder',request.args[0],'read/edit'):
        redirect(URL(r=request,f='open_folder',args=request.args))
    folder=db(db.folder.id==request.args[0]).select()[0]
    i=db.page.insert(title='Empty Page',folder=folder.id)
    session.flash='page created'
    redirect(URL(r=request,f='edit_page',args=[folder.id,i]))

def sort_pages():
    redirect(URL(r=request,f='open_folder',args=[folder.id]))

def download():
    if not len(request.args): redirect(URL(r=request,f='index'))
    documents=db(db.document.id==request.args[0]).select()
    if not len(documents): redirect(URL(r=request,f='index'))
    document=documents[0]
    pages=db(db.page.id==document.page).select()
    if not len(pages): redirect(URL(r=request,f='index'))
    page=pages[0]
    if len(db(db.folder.id==page.folder)(db.folder.is_open==True).select()):
        pass
    elif not has_access(user_id,'folder',page.folder,('read','read/edit')):
         session.flash='not authorized'
         redirect(URL(r=request,f='open_folder',args=[page.folder]))
    return response.stream(open(os.path.join(request.folder,'uploads',document.file),'rb'))

def delete_document():
    if not len(request.args): redirect(URL(r=request,f='index'))
    documents=db(db.document.id==request.args[0]).select()
    if not len(documents): redirect(URL(r=request,f='index'))
    document=documents[0]
    pages=db(db.page.id==document.page).select()
    if not len(pages): redirect(URL(r=request,f='index'))
    page=pages[0]
    if not has_access(user_id,'folder',page.folder,'read/edit'):
         session.flash='not authorized'
         redirect(URL(r=request,f='open_folder',args=[page.folder]))
    else:
         db(db.document.id==document.id).delete()
         session.flash='document deleted'
    redirect(URL(r=request,f='edit_page',args=[page.folder]))

def delete_comment():
    if not len(request.args): redirect(URL(r=request,f='index'))
    comments=db(db.comment.id==request.args[0]).select()
    if not len(comments): redirect(URL(r=request,f='index'))
    comment=comments[0]
    pages=db(db.page.id==comment.page).select()
    if not len(pages): redirect(URL(r=request,f='index'))
    page=pages[0]
    if not has_access(user_id,'folder',page.folder,'read/edit'):
         session.flash='not authorized'
         redirect(URL(r=request,f='open_folder',args=[page.folder]))
    else:
         db(db.comment.id==comment.id).delete()
         session.flash='comment deleted'
    redirect(URL(r=request,f='edit_page',args=[page.folder]))


def sort_pages():
    if not len(request.args): redirect(URL(r=request,f='index'))
    folder=request.args[0]
    if not has_access(user_id,'folder',folder,'read/edit'):
         session.flash='not authorized'
         redirect(URL(r=request,f='open_folder',args=[page.folder]))
    for i,item in enumerate(request.vars.order.split(',')[:-1]):
        db(db.page.id==item)(db.page.folder==folder).update(number=i)
    return 'done'