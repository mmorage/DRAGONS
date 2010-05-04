#!/bin/bash

echo "building html, see html.build.log"
/usr/bin/python /usr/bin/sphinx-build -b html source build &>html.build.log

echo "building latex, see latex.build.log"

/usr/bin/python /usr/bin/sphinx-build -b latex source build/_latex_build &>latex.build.log

echo "making pdf in build/_latex_build, see makepdf.build.log"
cd build/_latex_build 
make &> makepdf.build.log
