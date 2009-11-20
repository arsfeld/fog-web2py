# coding: utf8
if not session.token: redirect(LOGIN)

def index(): 
    return dict(message="hello from calendar.py")
