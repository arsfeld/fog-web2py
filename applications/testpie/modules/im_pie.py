# -*- coding: utf8 -*-
import math
import cairo
import StringIO


class PPart( object ):
    """ A part of pie circle.
        * have different parametrs ( color, sizes, position, label )
        * can draw itself to cairo context
    """
    def __init__( self, ctx ):
        """ Create pie part.
            ctx  : cairo context to draw to
        """
        self.ctx = ctx


    def draw( self ):
        """ Draw a part of pie with alredy setted parameters.
        """
        ctx = self.ctx
        r = self.r
        ang  = self.per * 2 * math.pi
        ang0 = self.ang0
        angl = self.angl
        bwth, rwth = self.bwth * r , self.rwth * r
        col, bcol  = self.col,  self.bcol

        ctx.save()
        ctx.translate( self.x, self.y )

        ctx.rotate( ang0 )

        #### draw pie
        ctx.move_to( 0, 0 )
        ctx.set_source_rgba( *col )
        ctx.arc( 0, 0, r, 0, ang )
        ctx.fill()

        #### draw cool dark border
        ctx.set_source_rgba( *bcol )
        ctx.set_line_width( bwth )
        ctx.arc( 0, 0, r - bwth / 2.0, 0, ang )
        ctx.stroke()

        #### draw two radial lines
        ctx.set_line_width( rwth )
        ctx.set_source_rgba( 1,1,1,1 )

        ctx.move_to( 0, 0 )
        ctx.line_to( r, 0 )
        ctx.stroke()
        ctx.rotate( ang )
        ctx.move_to( 0, 0 )
        ctx.line_to( r, 0 )
        ctx.stroke()

        ctx.restore()

        #### draw value label
        ctx.save()
        ctx.translate( self.x, self.y )

        vtxt = '%.2f' % self.val     ## format value

        ctx.select_font_face( "Georgia", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL )
        ctx.set_font_size( r * 0.075 )
        tx_b, ty_b, tw, th = ctx.text_extents( vtxt )[ :4 ]

        ## determine half of circle
        if self.isright:     ## draw on the right part of circle
            ctx.rotate( angl )
            xl = r - 0.3 * bwth      ## center of right label arc
        else:                        ## draw on the left part of circle
            ctx.rotate( - math.pi + angl )
            xl = -r + 0.3 * bwth + tw

        rl = 1.1 * th  ## radius of label arc

        ctx.arc( xl, 0, rl,  - math.pi / 2.0,  math.pi / 2.0 )
        ctx.line_to( xl - tw,  rl )
        ctx.arc( xl - tw, 0, rl, math.pi / 2.0,  - math.pi / 2.0 )
        ctx.line_to( xl, -rl )

        ctx.set_line_width( 0.8 )
        ctx.set_source_rgba( 1,1,1,1 )
        ctx.fill_preserve()
        ctx.set_source_rgba( 0,0,0,1 )
        ctx.stroke()

        ## draw dark dot for easy label reading
        ctx.arc( xl - tw - 0.3 * rl, 0, 0.24 * rl,  0,  2 * math.pi )
        ctx.fill()

        ctx.move_to( xl - tw - tx_b + 0.3 * rl, 0 - th / 2.0 - ty_b )
        ctx.show_text( vtxt )

        ctx.restore()

        #### draw text labels
        ctx.set_line_width( 1.0 )
        ctx.set_source_rgba( 0.7, 0.7, 0.7, 1 )
        rcv0 = r - 0.3 * bwth + rl  ## distance from center big circle to top of label arc
        rcv1 = 1.05 * r
        xcv = int( self.x + rcv1 * math.cos( angl ) ) + 0.5
        ycv = int( self.y + rcv1 * math.sin( angl ) ) + 0.5

        ctx.save()
        ctx.translate( self.x, self.y )
        ctx.rotate( angl )
        ctx.move_to( rcv0, 0 )
        ctx.line_to( rcv1, 0 )
        ctx.stroke()
        ctx.restore()

        ctx.move_to( xcv, ycv )
        ctx.line_to( self.lblx, self.lbly )
        ctx.stroke()

        ## below ( lblx, lbly ) -- special align point,
        ## which is calculated in IMPie.data_place_lbls()
        tx_b, ty_b, tw, th = ctx.text_extents( self.txt )[ :4 ]
        if self.isright:
            ctx.move_to( self.lblx + 4, self.lbly - th / 2.0 - ty_b )
        else:
            ctx.move_to( self.lblx - tw  - 6, self.lbly - th / 2.0 - ty_b )
        ctx.show_text( self.txt )


    def __repr__( self ):
        return "P( %s, %s, %s )" % ( None, self.per, self.txt )#( self.r, self.per, self.txt )



class IMPie( object ):
    """ Class wich draw pie chart and output it to
        string via self.draw().
    """
    def __init__( self, width, height ):
        """ Create painter instance:
            width, height : dimensions for picture
        """
        self.iw  = width
        self.ih  = height

        self.surface = surf = cairo.ImageSurface( cairo.FORMAT_ARGB32, width, height )
        self.ctx     = cairo.Context( surf )


    def data_set( self, pies ):
        """ Set data for working with.
            pies : [ (value1, 'name1'), (value2, 'name2'), ... ]
        """
        self.isjoined = False
        self.pies = [ ]
        for p in pies:
            pp = PPart( self.ctx )
            pp.val = p[ 0 ]
            pp.txt = p[ 1 ]
            self.pies.append( pp )

        sum =  0.0
        for p in self.pies:
            sum += p.val

        for p in self.pies:
            p.per  = p.val / sum


        self.pies.sort( key = lambda p: p.per, reverse = True )


    def data_join( self, min_per ):
        """ Join small parts together.
            min_per : minimal percent for part
        """
        self.isjoined = True
        more = filter( lambda p: p.per >= min_per, self.pies )
        less = filter( lambda p: p.per <  min_per, self.pies )

        self.pies = more
        if less:
            jp = less[ 0 ]
            for p in less[ 1: ]:
                jp.per += p.per
                jp.val += p.val
                jp.txt = 'other...'

            self.pies +=  [ jp ]


    def data_place( self ):
        """ Rotate whole cicle on angle wich
            positioning biggest part to look at east.
            Also set positions for all pies.
        """
        if self.isjoined:
            mp  = max( self.pies[ : -1 ], key = lambda p: p.per )
        else:
            mp  = max( self.pies, key = lambda p: p.per )

        ang = - mp.per * 2 * math.pi / 2.0
        #ang = - 0.1

        r = min( self.iw, self.ih ) / 2.0
        r -= 0.2 * r

        for p in self.pies:
            p.r    = r
            p.ang0 = ang
            dang   = p.per * 2 * math.pi
            p.angl = p.ang0 + dang / 2.0
            ang += dang
            p.isright = ( math.cos( p.angl ) > 0 )
            p.x, p.y = self.iw / 2.0, self.ih / 2.0


    def data_place_lbls( self ):
        """ Calculate positions for all text labels.
        """
        rparts = filter( lambda p: p.isright, self.pies )
        lparts = filter( lambda p: not p.isright, self.pies )

        ctx = self.ctx
        r   = self.pies[ 0 ].r
        ctx.select_font_face( "Georgia", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL )
        ctx.set_font_size( r * 0.075 )

        rwdths = map( lambda p: ctx.text_extents( p.txt )[ 2 ], rparts )
        lwdths = map( lambda p: ctx.text_extents( p.txt )[ 2 ], lparts )
        rwdth = max( rwdths ) + 0.05 * self.iw
        lwdth = max( lwdths ) + 0.05 * self.iw

        ## add align dots for labels : (lblx, lbly)
        ## for left and right circle halfs it has different mean
        for p in rparts:
            p.lblx = int( self.iw - rwdth ) + 0.5
            p.lbly = int( p.y + 1.05 * p.r * math.sin( p.angl ) ) + 0.5

        for p in lparts:
            p.lblx = int( lwdth ) + 0.5
            p.lbly = int( p.y + 1.05 * p.r * math.sin( p.angl ) ) + 0.5

        ## update position of big circle
        cw = self.iw - ( rwdth + lwdth )
        nx, ny = lwdth + cw / 2.0, self.ih / 2.0
        for p in self.pies:
            p.x, p.y = nx, ny


    def style_set( self, bcol, cols ):
        """ bcol : border color
            cols : colors
        """
        #self.pies.sort( key = lambda p: p.per, reverse = True )
        n = 0
        for p in self.pies:
            if n < len( cols ):
                p.col = cols[ n ]
            else:
                p.col = cols[ len( cols ) - 1 - ( n % 2 ) ]
            n += 1
            p.bcol = bcol
            p.bwth, p.rwth = 0.1, 0.015


    def draw( self ):
        """ Draw all parts and output result
            to string.
        """
        self.data_place()
        self.data_place_lbls()

        for p in self.pies:
            p.draw()

        ## write to pseudo-file
        out = StringIO.StringIO()
        self.surface.write_to_png( out )

        res = out.getvalue()
        out.close()

        return res



