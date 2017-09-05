#!/bin/bash

set -e

umask u=rw,g=r,o=r

usage ()
{
    cat > /dev/stderr <<EOF
$0 -- Update build logs for builder

Usage: $0 [-c|--commit COMMIT] [-b|--builder BUILDER] [--branch BRANCH] [-d|--base-directory DIR] [-t|--is-try-sched yes|no] [-h|--help]
EOF
}

err ()
{
    local msg=$1

    echo "ERROR: $msg" > /dev/stderr
    exit 1
}

msg ()
{
    local msg=$1

    echo ">>> INFO: $msg"
}

while test "$1" != "" ; do
    case "$1" in
	"-c"|"--commit")
	    COMMIT=$2
	    shift 2
	    ;;
	"-b"|"--builder")
	    BUILDER=$2
	    shift 2
	    ;;
	"-d"|"--base-directory")
	    BASE_DIR=$2
	    shift 2
	    ;;
	"-h"|"--help")
	    usage
	    exit 0
	    ;;
	"-t"|"--is-try-sched")
	    IS_TRY_SCHED=$2
	    shift 2
	    ;;
	"--branch")
	    BRANCH=$2
	    shift 2
	    ;;
	*)
	    usage
	    exit 1
	    ;;
    esac
done

DIR=$BASE_DIR/$BUILDER/

if test ! -d $DIR ; then
    msg "$DIR is not a valid directory.  Creeating it..."
    (umask 0022 && mkdir --verbose -p $DIR)
fi

cd $DIR

DB_NAME=$DIR/${BUILDER}.db

if test ! -f $DB_NAME ; then
    msg "Database $DB_NAME does not exist.  Creating it..."
    sqlite3 $DB_NAME "CREATE TABLE logs(commitid TEXT, branch TEXT DEFAULT 'master', trysched BOOLEAN DEFAULT 0, timestamp TIMESTAMP PRIMARY KEY DEFAULT (strftime('%s', 'now')) NOT NULL)"
fi

COMMIT_2_DIG=`echo $COMMIT | sed 's/^\(..\).*$/\1/'`

CDIR=$COMMIT_2_DIG/$COMMIT/
ISTRY=0
if test "$IS_TRY_SCHED" = "yes" ; then
    COUNT=`sqlite3 $DB_NAME "SELECT COUNT(*) FROM logs WHERE commitid = '${COMMIT}' AND trysched = 1"`
    CDIR=try/${CDIR}/${COUNT}
    ISTRY=1
fi

if test ! -d $CDIR ; then
    msg "Creating directory structure $CDIR..."
    (umask 0022 && mkdir --verbose -p $CDIR)
fi
cd $CDIR

TMP_DIR=$DIR/tmp/$COMMIT/

msg "Moving log files to $PWD..."
mv --verbose $TMP_DIR/* .
rmdir $TMP_DIR
msg "Compressing log files..."
find . -type f ! -name "*.xz" | xargs xz --verbose --compress

PREV_COMMIT=`sqlite3 $DB_NAME "SELECT commitid FROM logs WHERE branch = '$BRANCH' AND trysched = 0 ORDER BY timestamp DESC LIMIT 1"`

if test -n "$PREV_COMMIT" -a "$IS_TRY_SCHED" = "no" ; then
    PREV_2DIG=`echo $PREV_COMMIT | sed 's/^\(..\).*$/\1/'`
    ln -s $DIR/$PREV_2DIG/$PREV_COMMIT PREVIOUS_COMMIT
    ln -s $DIR/$CDIR $DIR/$PREV_2DIG/$PREV_COMMIT/NEXT_COMMIT
fi

msg "Update database..."
sqlite3 $DB_NAME "INSERT INTO logs(commitid, branch, trysched) VALUES('$COMMIT', '$BRANCH', $ISTRY)"

msg "Creating README.txt..."
cat > README.txt <<EOF
=== README ===

Logs for: $COMMIT

Branch tested: $BRANCH

Previous commit: $PREV_COMMIT

Patch: <http://sourceware.org/git/?p=binutils-gdb.git;a=commitdiff;h=${COMMIT}>
EOF

exit 0
