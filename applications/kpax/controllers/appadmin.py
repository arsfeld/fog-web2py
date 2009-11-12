###########################################################
### make sure administrator is on localhost
############################################################

import os, socket
import gluon.contenttype
import gluon.fileutils

http_host = request.env.http_host.split(':')[0]
remote_addr = request.env.remote_addr
if remote_addr not in (http_host, socket.gethostbyname(remote_addr)):
    raise HTTP(400)
if not gluon.fileutils.check_credentials(request):
    redirect('/admin')

response.view='appadmin.html'
response.menu=[['design',False,'/admin/default/design/%s' % request.application],
               ['db',False,'/%s/%s/index' % (request.application, request.controller)],
               ['state',False,'/%s/%s/state' % (request.application, request.controller)]]


###########################################################
### list all tables in database
############################################################

def index():
    import types as _types
    _dbs={}
    for _key,_value in globals().items():
        if isinstance(_value,SQLDB):
           tables=_dbs[_key]=[]
           for _tablename in _value.tables:
               tables.append((_key,_tablename))
    return dict(dbs=_dbs)

###########################################################
### insert a new record
############################################################

def insert():
    try:
        dbname=request.args[0]
        db=eval(dbname)
        table=db[request.args[1]]
    except:
        session.flash='invalid request'
        redirect(URL(r=request,f='index'))
    form=SQLFORM(table)
    if form.accepts(request.vars,session):
        response.flash='new record inserted'
    return dict(form=form)

###########################################################
### list all records in table and insert new record
############################################################

def download():
    import os
    filename=os.path.join(request.folder,'uploads/','%s' % request.args[0])
    return response.stream(open(filename,'rb'))

def csv():
    import gluon.contenttype
    response.headers['Content-Type']=gluon.contenttype.contenttype('.csv')
    try:
        dbname=request.vars.dbname
        db=eval(dbname)
        response.headers['Content-disposition']="attachment; filename=%s_%s.csv" % (request.vars.dbname, request.vars.query.split('.',1)[0])
        return str(db(request.vars.query).select())
    except:
        session.flash='unable to retrieve data'
        redirect(URL(r=request,f='index'))

def import_csv(table,file):
    import csv
    reader = csv.reader(file)
    colnames=None
    for line in reader:
        if not colnames: 
            colnames=[x[x.find('.')+1:] for x in line]
            c=[i for i in range(len(line)) if colnames[i]!='id']            
        else:
            items=[(colnames[i],line[i]) for i in c]
            table.insert(**dict(items))

def select():
    try:
        dbname=request.args[0]
        db=eval(dbname)
        if request.vars.query:
            query=request.vars.query
            orderby=None
            start=0
        elif request.vars.orderby:
            query=session.appadmin_last_query
            orderby=request.vars.orderby
            if orderby==session.appadmin_last_orderby:
                if orderby[-5:]==' DESC': oderby=orderby[:-5]
                else: orderby=orderby+' DESC'
            start=0
        elif request.vars.start!=None:
            query=session.appadmin_last_query
            orderby=session.appadmin_last_orderby
            start=int(request.vars.start)
        else:
            table=request.args[1]
            query='%s.id>0' % table    
            orderby=None
            start=0
        session.appadmin_last_query=query
        session.appadmin_last_orderby=orderby
        limitby=(start,start+100)
    except:
        session.flash='invalid request'
        redirect(URL(r=request,f='index'))
    if request.vars.csvfile!=None:        
        try:
            import_csv(db[table],request.vars.csvfile.file)
            response.flash='data uploaded'
        except: 
            response.flash='unable to parse csv file'
    if request.vars.delete_all and request.vars.delete_all_sure=='yes':
        try:
            db(query).delete()
            response.flash='records deleted'
        except:
            response.flash='invalid SQL FILTER'
    elif request.vars.update_string:
        try:
            env=dict(db=db,query=query)
            exec('db(query).update('+request.vars.update_string+')') in env
            response.flash='records updated'
        except:
            response.flash='invalid SQL FILTER or UPDATE STRING'
    try:
        records=db(query).select(limitby=limitby,orderby=orderby)
    except: 
        response.flash='invalid SQL FILTER'
        return dict(records='no records',nrecords=0,query=query,start=0)
    linkto=URL(r=request,f='update',args=[dbname])
    upload=URL(r=request,f='download')
    return dict(start=start,query=query,orderby=orderby, \
                nrecords=len(records),\
                records=SQLTABLE(records,linkto,upload,orderby=True,_class='sortable'))

###########################################################
### edit delete one record
############################################################

def update():
    try:
        dbname=request.args[0]
        db=eval(dbname)
        table=request.args[1]
    except:
        response.flash='invalid request'
        redirect(URL(r=request,f='index'))
    try:
        id=int(request.args[2])
        record=db(db[table].id==id).select()[0]
    except:
        session.flash='record does not exist'
        redirect(URL(r=request,f='select/%s/%s'%(dbname,table)))
    form=SQLFORM(db[table],record,deletable=True,
                 linkto=URL(r=request,f='select',args=[dbname]),
                 upload=URL(r=request,f='download'))
    if form.accepts(request.vars,session): 
        response.flash='done!'        
        redirect(URL(r=request,f='select/%s/%s'%(dbname,table)))
    return dict(form=form)

###########################################################
### get global variables
############################################################

def state():
    return dict(state=request.env)
