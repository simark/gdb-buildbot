#!/bin/bash

if test -z $1 ; then
    echo "You have to provide the branch name"
    exit 1
fi

B=$1

for d in `ls` ; do
    if test -d $d && test -d $d/xfails ; then
	mkdir $d/xfails/$B
	cp $d/xfails/master/xfail $d/xfails/$B/xfail
    fi
done
