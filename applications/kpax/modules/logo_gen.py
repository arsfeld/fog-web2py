#!/usr/bin/env python 
# coding: utf8 
from gluon.html import *
from gluon.http import *
from gluon.validators import *
from gluon.sqlhtml import *
# request, response, session, cache, T, db(s) 
# must be passed and cannot be imported!

import PIL
from PIL import Image
import ImageFilter
import ImageFont
import ImageDraw

import StringIO

def draw_logo(txt, size):
    #size = (390, 157)
    #txt = 'FuckYou2'

    font = ImageFont.truetype('/usr/share/fonts/TTF/VeraBd.ttf', 64)

    txt_size = font.getsize(txt)
    txt_pos = (size[0] / 2 - txt_size[0] / 2, size[1] / 2 - txt_size[1] / 2)

    i = Image.new('RGBA', size)
    draw = ImageDraw.Draw(i)
    draw.text(txt_pos, txt, font=font, fill=(0, 0, 0))

    for n in range(5):
        i = i.filter(ImageFilter.BLUR)
    draw = ImageDraw.Draw(i)

    draw.text(txt_pos, txt, font=font)

    output = StringIO.StringIO()

    i.save(output, 'PNG')
    
    return output
