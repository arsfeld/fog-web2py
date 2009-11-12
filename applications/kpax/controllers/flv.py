def player():
    filename=URL(r=request,c='folders',f='download',args=request.args)
    return dict(filename=filename)