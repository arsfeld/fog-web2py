def player():
    filename=URL(r=request,c='folders',f='download',args=request.args)
    return dict(filename=filename)

def player_open():
    response.title="kpax"
    filename=URL(r=request,c='folders',f='download',args=request.args)
    return dict(filename=filename)