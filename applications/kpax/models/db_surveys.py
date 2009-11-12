
db.define_table('survey',
                SQLField('owner',db.user),
                SQLField('timestamp','datetime',default=timestamp),
                SQLField('start','date',default=today),
                SQLField('stop','date',default=today+datetime.timedelta(7)),
                SQLField('title'),
                SQLField('description','text',default=''),
                SQLField('is_assignment','boolean',default=True),
                SQLField('normalize_score_to','double',default=100.0),
                SQLField('anonymous','boolean',default=False))

db.survey.owner.requires=VALID_USER
db.survey.title.requires=IS_NOT_EMPTY()
db.survey.access_types=['none','take']
db.survey.public_fields=['title','description','is_assignment','normalize_score_to','start','stop','anonymous']

db.define_table('sa',
                SQLField('survey',db.survey),
                SQLField('owner',db.user),
                SQLField('anonymous','boolean',default=False),
                SQLField('timestamp','datetime',default=None),
                SQLField('score','double',default=0.0),
                SQLField('reviewer_comment','text',default=''),
                SQLField('completed','boolean'))

db.sa.survey.requires=IS_IN_DB(db,db.survey.id,db.survey.title)
db.sa.owner.requires=VALID_USER
db.sa.public_fields=['score','reviewer_comment']

db.define_table('question',
                SQLField('survey',db.survey),
                SQLField('number','integer'),
                SQLField('title','string'),
                SQLField('body','text',default=''),
                SQLField('type','string',default='short text'),
                SQLField('minimum','integer',default=0),
                SQLField('maximum','integer',default=5),
                SQLField('correct_answer'),
                SQLField('points','double',default=0),            
                SQLField('option_A','string',default=''),
                SQLField('points_for_option_A','double',default=0),
                SQLField('option_B','string',default=''),
                SQLField('points_for_option_B','double',default=0),
                SQLField('option_C','string',default=''),
                SQLField('points_for_option_C','double',default=0),
                SQLField('option_D','string',default=''),
                SQLField('points_for_option_D','double',default=0),
                SQLField('option_E','string',default=''),
                SQLField('points_for_option_E','double',default=0),
                SQLField('option_F','string',default=''),
                SQLField('points_for_option_F','double',default=0),
                SQLField('option_G','string',default=''),
                SQLField('points_for_option_G','double',default=0),
                SQLField('option_H','string',default=''),
                SQLField('points_for_option_H','double',default=0),
                SQLField('required','boolean',default=True),
                SQLField('comments_enabled','boolean',default=False))

question_fields=[x for x in db.question.fields if not x in ['id','number','survey']]

db.question.survey.requires=IS_IN_DB(db,'survey.id','survey.title')
db.question.title.requires=IS_NOT_EMPTY()
db.question.type.requires=IS_IN_SET(['short text','long text','long text verbatim','integer','float','date','multiple exclusive','multiple not exclusive','upload'])
db.question.points.requires=IS_FLOAT_IN_RANGE(0,100)
db.question.points_for_option_A.requires=IS_FLOAT_IN_RANGE(0,100)
db.question.points_for_option_B.requires=IS_FLOAT_IN_RANGE(0,100)
db.question.points_for_option_C.requires=IS_FLOAT_IN_RANGE(0,100)
db.question.points_for_option_D.requires=IS_FLOAT_IN_RANGE(0,100)
db.question.points_for_option_E.requires=IS_FLOAT_IN_RANGE(0,100)
db.question.points_for_option_F.requires=IS_FLOAT_IN_RANGE(0,100)
db.question.points_for_option_G.requires=IS_FLOAT_IN_RANGE(0,100)
db.question.points_for_option_H.requires=IS_FLOAT_IN_RANGE(0,100)

db.define_table('answer',
                SQLField('question',db.question),
                SQLField('sa',db.sa),
                SQLField('value','string'),
                SQLField('file','upload'),
                SQLField('grade','double',default=None),
                SQLField('comment','text',default=''))
                
db.answer.question.requires=IS_IN_DB(db,db.question.id,db.question.title)
db.sa.requires=IS_IN_DB(db,db.sa.id,db.sa.id)

def mysurvey():
    if len(request.args)<0: redirect(URL(r=request,f='index'))
    surveys=db(db.survey.id==request.args[0])(db.survey.owner==session.user_id).select()
    if len(surveys)<1:
        session.flash='your are not authorized'
        redirect(URL(r=request,f='index'))
    return surveys[0]

def thissurvey():
    if len(request.args)<1: redirect(URL(r=request,f='index'))
    survey_id=request.args[0]
    if not has_access(user_id,'survey',survey_id,'take'):
        session.flash='access denied'
        redirect(URL(r=request,f='index'))
    rows=db(db.survey.id==survey_id).select()    
    if not len(rows):
        session.flash='survey is missing'
        redirect(URL(r=request,f='index'))
    rows2=db(db.sa.owner==user_id)(db.sa.survey==survey_id).select()
    if not len(rows2):
       id=db.sa.insert(survey=survey_id,owner=user_id,completed=False,
                       anonymous=rows[0].anonymous)
       rows2=db(db.sa.id==id).select()
    return rows[0],rows2[0]