# coding: utf8

#########################################################################
## This is a samples controller
## - index is the default action of any application
## - user is required for authentication and authorization
## - download is for downloading files uploaded in the db (does streaming)
## - call exposes all registered services (none by default)
#########################################################################

def index():
    """
    example action using the internationalization operator T and flash
    rendered by views/default/index.html or views/generic.html
    """
    response.flash = T('Welcome to web2py')
    return dict(message=T('Hello World'))


def pie():
    ## load module for draw pie
    from applications.testpie.modules.im_pie import IMPie

    def rgb( r,g,b, a=1.0 ):
        """ This function convert color to cairo format
        """
        return ( r / 255.0, g / 255.0, b / 255.0, a )


    ## some data to draw
    data = [ ( 33.4, 'Label 1' ),
             ( 13.4, 'Label 2' ),
             ( 43.4, 'Label 3' ),
             ( 13.4, 'Label 4' ),
             ( 23.4, 'Label 5' ),
             (  1.1, 'for join...' ),
             (  1.1, 'for join...' ),
             (  1.1, 'for join...' ),
             ( 73.4, 'Label 8' ) ]


    ## create pie chart image 800x330 pixels
    p = IMPie( 800, 330 )

    p.data_set( data )   ## set data to draw
    p.data_join( 0.028 ) ## remove very small pies

    p.style_set(
        rgb( 150,150,0, 0.3 ),   ## border color
        [  rgb( 95,90,97 ),      ## first pie color
           rgb( 227,215,9 ),     ## ... second one
           rgb( 239,253,238 ),   ## ...
           rgb( 201,222,174 ),   ## ...
           rgb( 201,222,174 )    ## ... last pie color
        ]
    )

    response.headers['Content-Type']= "image/png"
    return  p.draw( )



def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """
    return dict(form=auth())


def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request,db)


def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()
