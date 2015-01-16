#!/bin/bash

if test $# -ne 1 ; then
    echo "You must provide the directory of the builders' git repos"
    echo "Usually, this is the public_html/results directory inside the"
    echo "BuildBot directory"
    exit 1
fi

# The equivalent of the gdb_web_base (in the configuration files)
GDB_WEB_BASE=$1

for d in `ls` ; do
    if ! test -d $GDB_WEB_BASE/$d ; then
	continue
    fi

    if ! test -h $GDB_WEB_BASE/$d/xfail ; then
	ln -s $d/xfail $GDB_WEB_BASE/$d/xfail
    fi
done
