clean:
	rm -f httpserver.log 
	rm -f parameters*.py 
	rm -f -r applications/*/compiled     	
	find ./ -name '*~' -exec rm -f {} \; 
	find ./ -name '#*' -exec rm -f {} \; 
	find ./gluon/ -name '.*' -exec rm -f {} \; 
	find ./applications/admin/ -name '.*' -exec rm -f {} \; 
	find ./applications/examples/ -name '.*' -exec rm -f {} \; 
	find ./applications/welcome/ -name '.*' -exec rm -f {} \; 
	find ./ -name '*.pyc' -exec rm -f {} \;
all:
	echo "The Makefile is used to build the distribution."
	echo "In order to run web2py you do not need to make anything."
	echo "just run web2py.py"
epydoc:
	### build epydoc
	rm -f -r applications/examples/static/epydoc/ 
	epydoc --config epydoc.conf
	cp applications/examples/static/title.png applications/examples/static/epydoc
src:
	echo 'Version 1.71.2 ('`date +%Y-%m-%d\ %H:%M:%S`')' > VERSION
	### rm -f all junk files
	make clean
	### clean up baisc apps
	rm -f routes.py 
	rm -f applications/*/sessions/*       
	rm -f applications/*/errors/* | echo 'too many files'
	rm -f applications/*/cache/*                  
	rm -f applications/admin/databases/*                 
	rm -f applications/welcome/databases/*               
	rm -f applications/examples/databases/*             
	rm -f applications/admin/uploads/*                 
	rm -f applications/welcome/uploads/*               
	rm -f applications/examples/uploads/*             
	### make admin layout and appadmin the default
	cp applications/admin/views/appadmin.html applications/welcome/views
	cp applications/admin/views/appadmin.html applications/examples/views
	cp applications/admin/controllers/appadmin.py applications/welcome/controllers
	cp applications/admin/controllers/appadmin.py applications/examples/controllers	
	### update the license
	cp ABOUT applications/admin/
	cp ABOUT applications/examples/
	cp LICENSE applications/admin/
	cp LICENSE applications/examples/
	### build the basic apps
	cd applications/admin/ ; tar zcvf admin.w2p *
	mv applications/admin/admin.w2p ./
	cd applications/welcome/ ; tar zcvf welcome.w2p *
	mv applications/welcome/welcome.w2p ./
	cd applications/examples/ ; tar zcvf examples.w2p *
	mv applications/examples/examples.w2p ./
	### build web2py_src.zip
	mv web2py_src.zip web2py_src_old.zip | echo 'no old'
	cd ..; zip -r web2py/web2py_src.zip web2py/gluon/*.py web2py/gluon/contrib/* web2py/*.py web2py/*.w2p web2py/ABOUT  web2py/LICENSE web2py/README web2py/VERSION web2py/Makefile web2py/epydoc.css web2py/epydoc.conf web2py/app.yaml web2py/scripts/*.sh web2py/scripts/*.py

mdp:
	make epydoc
	make src
	make app
	make win
app:
	python2.5 -c 'import compileall; compileall.compile_dir("gluon/")'
	#python web2py.py -S welcome -R __exit__.py
	find gluon -path '*.pyc' -exec cp {} ../web2py_osx/site-packages/{} \;
	cd ../web2py_osx/site-packages/; zip -r ../site-packages.zip *
	mv ../web2py_osx/site-packages.zip ../web2py_osx/web2py/web2py.app/Contents/Resources/lib/python2.5
	cp *.w2p ../web2py_osx/web2py/web2py.app/Contents/Resources
	cp ABOUT ../web2py_osx/web2py/web2py.app/Contents/Resources
	cp LICENSE ../web2py_osx/web2py/web2py.app/Contents/Resources
	cp VERSION ../web2py_osx/web2py/web2py.app/Contents/Resources
	cp README ../web2py_osx/web2py/web2py.app/Contents/Resources
	cd ../web2py_osx; zip -r web2py_osx.zip web2py
	mv ../web2py_osx/web2py_osx.zip .
win:
	python2.5 -c 'import compileall; compileall.compile_dir("gluon/")'
	find gluon -path '*.pyc' -exec cp {} ../web2py_win/library/{} \;
	cd ../web2py_win/library/; zip -r ../library.zip *
	mv ../web2py_win/library.zip ../web2py_win/web2py
	cp *.w2p ../web2py_win/web2py/
	cp ABOUT ../web2py_win/web2py/
	cp LICENSE ../web2py_win/web2py/
	cp VERSION ../web2py_win/web2py/
	cp README ../web2py_win/web2py/
	cd ../web2py_win; zip -r web2py_win.zip web2py
	mv ../web2py_win/web2py_win.zip .
war:
	python2.5 -c 'import compileall; compileall.compile_dir("gluon/")'
	cp -r gluon ../web2py_war/web2py/
	cp *.py ../web2py_war/web2py/
	cp *.w2p ../web2py_win/web2py/
	cp ABOUT ../web2py_win/web2py/
	cp LICENSE ../web2py_win/web2py/
	cp VERSION ../web2py_win/web2py/
	cp README ../web2py_win/web2py/
	cd ../web2py_war; zip -r web2py.war web2py
	mv ../web2py_war/web2py.war .
post:
	rsync -avz --partial --progress -e ssh web2py_src.zip web2py_osx.zip web2py_win.zip user@www.web2py.com:~/
run:
	python2.5 web2py.py -a hello
launchpad:
	bzr push bzr+ssh://mdipierro@bazaar.launchpad.net/~mdipierro/web2py/devel --use-existing-dir
svn:
	make clean
	find gluon -path '*.py' -exec cp {} ../web2py_svn/{} \;
	cp Makefile ../web2py_svn/
	cp welcome.w2p ../web2py_svn/
	cp VERSION ../web2py_svn/
	cp LICENSE ../web2py_svn/
	cp ABOUT ../web2py_svn/
	cp README ../web2py_svn/
	cp *.yaml ../web2py_svn/
	cp *.py ../web2py_svn/
	cp epydoc.conf ../web2py_svn/
	cp epydoc.css ../web2py_svn/
	cp scripts/* ../web2py_svn/scripts/
	cp -r doc/* ../web2py_svn/doc/
	cp -r applications/examples/* ../web2py_svn/applications/examples
	cp -r applications/welcome/* ../web2py_svn/applications/welcome
	cp -r applications/admin/* ../web2py_svn/applications/admin
