import sys
import re


def cleancss(text):
    text=re.compile('\s+').sub(' ', text)
    text=re.compile('\s*(?P<a>,|:)\s*').sub('\g<a> ', text)
    text=re.compile('\s*;\s*').sub(';\n    ', text)
    text=re.compile('\s*\{\s*').sub(' {\n    ', text)
    text=re.compile('\s*\}\s*').sub('\n}\n\n', text)
    return text


def cleanhtml(text):
    text=text.lower()
    r=re.compile('\<script.+?/script\>', re.DOTALL)
    scripts=r.findall(text)
    text=r.sub('<script />', text)
    r=re.compile('\<style.+?/style\>', re.DOTALL)
    styles=r.findall(text)
    text=r.sub('<style />', text)
    text=re.compile(
        '<(?P<tag>(input|meta|link|hr|br|img))(?P<any>[^\>]*)\s*(?<!/)>')\
        .sub('<\g<tag>\g<any> />', text)

    text=text.replace('\n', ' ')
    text=text.replace('>', '>\n')
    text=text.replace('<', '\n<')
    text=re.compile('\s*\n\s*').sub('\n', text)
    lines=text.split('\n')
    (indent, newlines)=(0, [])
    for line in lines:
        if line[:2]=='</': indent=indent-1
        newlines.append(indent*'  '+line)
        if not line[:2]=='</' and line[-1:]=='>' and \
                not line[-2:] in ['/>', '->']: indent=indent+1
    text='\n'.join(newlines)
    for script in scripts:
        text=text.replace('<script />', script, 1)
    for style in styles:
        text=text.replace('<style />', cleancss(style), 1)
    return text

file=sys.argv[1]
if file[-4:]=='.css':
    print cleancss(open(file, 'r').read())
if file[-5:]=='.html':
    print cleanhtml(open(file, 'r').read())
