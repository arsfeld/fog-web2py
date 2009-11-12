APP='%s/%s' %(HOST,request.application)
CAS.login_url=APP+'/cas/login'
CAS.check_url=APP+'/cas/check'
CAS.logout_url=APP+'/cas/logout'
CAS.my_url=APP+'/default/login'

def login():
    session.token=CAS.login(request)
    print session.token
    if session.token:
        id,email,name=session.token ### specific for web2py CAS service
        redirect(MAIN)
    return dict()

def logout():
    session.token=None
    CAS.logout()

def index():
    if not session.token: 
        redirect(LOGIN)
    else:
        redirect(MAIN)

def menu_image():
    import PIL
    from PIL import Image
    import ImageFilter
    import ImageFont
    import ImageDraw

    import StringIO
    
    aa_factor = 1
    
    if request.args[0] == 'small':
        small_size = (100, 41)
        size = (100 * aa_factor, 41 * aa_factor)
        font_size = 16
    else:
        small_size = (390, 157)
        size = (390 * aa_factor, 157 * aa_factor)
        font_size = 64
    
    txt = request.args[1]
    if txt.lower().endswith('.png'):
        txt = txt[:-4]
    
    font = ImageFont.truetype('/usr/share/fonts/TTF/VeraBd.ttf', font_size * aa_factor)

    txt_size = font.getsize(txt)
    txt_pos = (size[0] / 2 - txt_size[0] / 2, size[1] / 2 - txt_size[1] / 2)

    i = Image.new('RGBA', size)
    draw = ImageDraw.Draw(i)
    draw.text(txt_pos, txt, font=font, fill=(0, 0, 0))

    for n in range(5 * aa_factor):
        i = i.filter(ImageFilter.BLUR)
    draw = ImageDraw.Draw(i)

    draw.text(txt_pos, txt, font=font)

    if aa_factor != 1:
        i = i.resize(small_size, Image.ANTIALIAS)

    output = StringIO.StringIO()

    i.save(output, 'PNG')
    
    response.headers['Content-Type']= "image/png"
    return output.getvalue()
