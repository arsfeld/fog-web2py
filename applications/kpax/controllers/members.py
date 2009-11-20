# coding: utf8
if not session.token: redirect(LOGIN)
    
def sync_ldap():
    return dict(names_added=names_added, names_in_db=names_in_db, extra_users=extra_users)

def import_csv():
    form=FORM(TABLE(TR(" ",TEXTAREA(_name="csv",value="write something here")),
                    TR("",INPUT(_type="submit",_value="SUBMIT"))))
    if form.accepts(request.vars,session):
        response.flash="form accepted"
        import csv
        names = [T('None')] + db.user.fields
        names.remove('id')
        #return dict(vars=[v for v in csv.DictReader(form.vars['csv'].split('\n'))])
        #csv_content = [line for line in csv.reader(form.vars['csv'].split('\n'))]
        csv_content = [line for line in csv.reader(form.vars['csv'].strip().split('\n'))]
        #html = TABLE(
        #    *([TR(*[TD(key,SELECT(*names,_name="column_name")) for key in csv_content[0]])
        #)
        #csv_content = [line for line in csv.reader(form.vars['csv'].split('\n'))]
        return dict(form=None, columns=csv_content[0], data=csv_content[1:], db_columns=names)
        #return dict(csv_content=[(var, line[0][i]) for i, var in enumerate(csv_content)])
    elif form.errors:
        response.flash="form is invalid"
    else:
        response.flash="please fill the form"
    return dict(form=form,vars=form.vars,items=db.user.fields)

def add():
    form=FORM(TABLE(
          TR(T("First name:"), INPUT(_name="firstname",requires=IS_NOT_EMPTY())),
          TR(T("Last name:"), INPUT(_name="lastname",requires=IS_NOT_EMPTY())),
          TR(T("Username:"), INPUT(_name="username", requires=IS_NOT_EMPTY())),
          TR(T("Email:"), INPUT(_name="email",requires=[IS_NOT_EMPTY(), IS_NOT_IN_DB(db,'user.email')])),
          TR("Password:", INPUT(_name="password",_type='password',requires=[IS_NOT_EMPTY(),CRYPT()])),\
                    TR("Password (again):",\
          INPUT(_name="password2",_type='password',requires=[IS_NOT_EMPTY(),CRYPT()])),\
                    TR("",INPUT(_type="submit",_value="register"))))
    if form.accepts(request.vars,session) and \
       form.vars.password==form.vars.password2:
        if EMAIL_VERIFICATION:
            key=md5.new(str(random.randint(0,9999))).hexdigest()
        else:
            key=''
        id=db.user.insert(firstname=form.vars.firstname,
                          lastname=form.vars.lastname,
                          username=form.vars.username,
                          email=form.vars.email,
                          password=form.vars.password,
                          verification=key)
                          
        response.flash='Registration completed, you may login now'
        redirect(URL(r=request,f='list'))
    else:
        return dict(form=form)

def index(): 
    return dict(table=db(db.user.id>0).select())
