# -*- python -*-
# ex: set syntax=python:


# TODO:
#
# - Add comments on every function/class
# - License stuff (on all files)
# - Cross testing (needed?)
# - Improve way to store and compare testcases


import os
import re
import smtplib
import sqlite3
import uuid
from email.mime.text import MIMEText
from json import load
from time import strftime

from buildbot.changes.filter import ChangeFilter
from buildbot.changes.gitpoller import GitPoller
from buildbot.changes.gerritchangesource import GerritChangeSource
from buildbot.interfaces import IEmailLookup
from buildbot.plugins import schedulers, steps, util
from buildbot.steps.source import gerrit
from buildbot.process import factory
from buildbot.process.results import SUCCESS
from buildbot.schedulers.trysched import Try_Jobdir
from buildbot.worker import Worker
from buildbot.manhole import PasswordManhole
from twisted.protocols.basic import NetstringReceiver
from zope.interface import implements

# GDB BuildBot Configuration

# General Configuration


NetstringReceiver.MAX_LENGTH = 1000000000

# This is the dictionary that the buildmaster pays attention to. We
# also use a shorter alias to save typing.
c = BuildmasterConfig = {}

c["buildbotNetUsageData"] = "full"


def make_master_path(rel):
    return os.path.expanduser(os.path.join(basedir, rel))


# Base directory for the web server.  This is needed in order to
# compare the test results.
gdb_web_base = make_master_path("results")

# set_web_base(gdb_web_base)

GDB_MAIL_FROM = "simark@simark.ca"
GDB_MAIL_TO = "simark@simark.ca"

# 'protocols' contains information about protocols which master will use for
# communicating with slaves.
c["protocols"] = {"pb": {"port": 9989}}

# the 'change_source' setting tells the buildmaster how it should find out
# about source code changes.

# RE representing which branches to track on the GDB repository
# branches_to_watch = re.compile(r"(refs/heads/)?(master|gdb-\d+\.\d+-branch)")
branches_to_watch = re.compile(r"(refs/heads/)?(master)")


# Function which decides whether BRANCH should be used or not
def should_watch_branch(branch):
    if re.match(branches_to_watch, branch):
        return True
    else:
        return False


# GIT_REPO_URL = "https://github.com/simark/binutils-gdb.git"
# GIT_REPO_URL = "https://github.com/bminor/binutils-gdb.git"
GIT_REPO_URL = "git://sourceware.org/git/binutils-gdb.git"

c["change_source"] = []
c["change_source"].append(
    GitPoller(
        repourl=GIT_REPO_URL,
        branches=should_watch_branch,
        pollinterval=60,
        pollAtLaunch=True,
    )
)


class MyGerritChangeSource(GerritChangeSource):
    def __init__(self):
        super().__init__(
            gerritserver="10.0.0.214",
            gerritport=29418,
            username="buildbot",
            identity_file="/home/buildbot/master/buildbot-gerrit.key",
            handled_events=["comment-added"],
            get_files=True,
            debug=True,
        )

    def eventReceived_comment_added(self, properties, event):
        print(">>> properties:", properties)
        print(">>> event:", event)

        # Check if "CI-Build" went from 0 to 1.
        if "approvals" not in event:
            print('>>> comment-added: "approvals" not in event')
            return

        ci_build_label = None
        for approval in event["approvals"]:
            if "type" in approval and approval["type"] == "CI-Build":
                ci_build_label = approval
                break

        if ci_build_label is None:
            print(">>> comment-added: CI-Build label not found")
            return

        if "value" not in ci_build_label:
            print('>>> comment-added: "value" not in label')
            return

        if ci_build_label["value"] != "1":
            print('>>> comment-added: ci_build_label["value"] is not "1"')
            return

        if "oldValue" not in ci_build_label:
            print('>>> comment-added: "oldValue" not in label')
            return

        if ci_build_label["oldValue"] != "0":
            print('>>> comment-added: ci_build_label["oldValue"] is not "0"')
            return

        print(">>> comment-added: adding change")

        properties["try"] = True
        self.addChangeFromEvent(properties, event)


c["change_source"].append(MyGerritChangeSource())

# Catch things like PR gdb/42, PR16, PR 16 or bug #11,
# and turn them into gdb bugzilla URLs.
cc_re_tuple = (
    r"(PR [a-z]+/|PR ?|#)(\d+)",
    r"http://sourceware.org/bugzilla/show_bug.cgi?id=\2",
)

# The following class is a hack.  It is needed because Builbot's
# webserver treats everything it doesn't know as text/html.  Sigh...
#
# class WebStatusWithTextDefault(html.WebStatus):
#     def __init__ (self, http_port, authz, **kwargs):
#         html.WebStatus.__init__ (self, http_port = http_port,
#                                  authz = authz, **kwargs)
#
#     def setupSite(self):
#         result = html.WebStatus.setupSite(self)
#         self.site.resource.defaultType = r"text/plain"
#         return result

# authz_cfg = authz.Authz(
# change any of these to True to enable; see the manual for more
# options
#    auth=auth.BasicAuth([("t","t")]),
#    gracefulShutdown=False,
#    forceBuild=True,  # use this to test your slave once it is set up
#    forceAllBuilds=True,  # ..or this
#    pingBuilder=False,
#    stopBuild=True,
#    stopAllBuilds=True,
#    cancelPendingBuild=True,
# )
# c['status'].append(WebStatusWithTextDefault (http_port=8010, authz=authz_cfg))
# c['status'].append (html.WebStatus (http_port = 8010, authz = authz_cfg))

# c['status'].append(html.WebStatus(http_port=8010,
# 				  forceBuild = True,
# 				  allowForce=False,
# 				  order_console_by_time=True,
# 				  changecommentlink=cc_re_tuple))

c["www"] = {
    "port": 8010,
    "plugins": {
        "waterfall_view": True,
        "console_view": True,
        "grid_view": True,
    },
}

# from buildbot.status import words
# c['status'].append(words.IRC(host="irc.yyz.redhat.com", nick="sdj-gdbbot",
# 			     channels=["#gdbbuild"]))


# def make_try_build_lockfile_name(msgid):
#    return "/tmp/gdb-buildbot-%s-try.lock" % msgid
#
#
# def SendRootMessageGDBTesters(
#    branch,
#    change,
#    rev,
#    istrysched=False,
#    try_to=None,
#    try_count="0",
#    try_msgid=None,
#    try_comment=None,
# ):
#    global GDB_MAIL_TO, GDB_MAIL_FROM
#
#    if istrysched:
#        f = make_try_build_lockfile_name(try_msgid)
#    else:
#        f = "/tmp/gdb-buildbot-%s.lock" % rev
#
#    if os.path.exists(f):
#        # The message has already been sent
#        return
#
#    # WE HAVE TO REMEMBER TO CLEAN THESE FILES REGULARLY
#    open(f, "w").close()
#
#    if not istrysched:
#        text = ""
#        text += "*** TEST RESULTS FOR COMMIT %s ***\n\n" % rev
#
#        text += "Author: %s\n" % change.who
#        text += "Branch: %s\n" % branch
#        text += "Commit: %s\n\n" % rev
#
#        text += change.comments.split("\n")[0] + "\n\n"
#        text += "\n".join(change.comments.split("\n")[1:])
#
#        chg_title = change.comments.split("\n")[0]
#        text = text.encode("ascii", "ignore").decode("ascii")
#    else:
#        text = ""
#        text += "*** TEST RESULTS FOR TRY BUILD ***\n\n"
#
#        text += "Branch: %s\n" % branch
#        text += "Commit tested against: %s\n\n" % rev
#
#        text += try_comment
#
#        text += "\n"
#
#        text += "Patch tested:\n\n"
#        text += change
#
#        chg_title = "Try Build against commit %s" % rev
#        text = text.encode("ascii", "ignore").decode("ascii")
#
#    mail = MIMEText(text)
#    if branch == "master":
#        sbj = "[binutils-gdb] %s" % chg_title
#    else:
#        sbj = "[binutils-gdb/%s] %s" % (branch, chg_title)
#
#    mail["Subject"] = sbj
#    mail["From"] = GDB_MAIL_FROM
#    if not istrysched:
#        mail["To"] = GDB_MAIL_TO
#        mailto = GDB_MAIL_TO
#        mail["Message-Id"] = "<%s@gdb-build>" % rev
#    else:
#        mail["To"] = try_to
#        mailto = try_to
#        mail["Message-Id"] = try_msgid
#
#    s = smtplib.SMTP("localhost")
#    s.sendmail(GDB_MAIL_FROM, [mailto], mail.as_string())
#    s.quit()
#
#
# def make_breakage_lockfile_name(branch, builder):
#    return "/tmp/gdb-buildbot-breakage-report-%s-%s" % (branch, builder)
#
#
# def make_breakage_root_message_id_filename(rev, branch):
#    return "/tmp/gdb-buildbot-message-id-breakage-%s-%s" % (rev, branch)
#
#
# def make_breakage_root_message_id(rev, branch):
#    mid_file = make_breakage_root_message_id_filename(rev, branch)
#    mid = "%s-%s-breakage@gdb-build" % (rev, branch)
#    if not os.path.exists(mid_file):
#        mf = open(mid_file, "w")
#        mf.write(mid)
#        mf.close()
#    return mid
#
#
# def SendRootBreakageMessage(builder, branch, change):
#    """Send the root message that will contain the breakage emails."""
#    global GDB_MAIL_FROM
#
#    rev = change.revision
#
#    if os.path.exists(make_breakage_root_message_id_filename(rev, branch)):
#        # Already sent
#        return
#
#    message_id = make_breakage_root_message_id(rev, branch)
#    to = change.who.encode("ascii", "ignore").decode("ascii")
#    to += ", gdb-patches@sourceware.org"
#    to_list = [to]
#    to_list.append("gdb-patches@sourceware.org")
#    title = change.comments.split("\n")[0]
#
#    sbj = (
#        "Oh dear.  I regret to inform you that commit %s might be unfortunate"
#        % change.revision
#    )
#    if branch != "master":
#        sbj += " [%s]" % branch
#
#    text = "My lords, ladies, gentlemen, members of the public.\n\n"
#    text += "It is a matter of great regret and sadness to inform you that commit:\n\n"
#    text += "\t%s\n" % title
#    text += "\t%s\n\n" % rev
#    text += "might have made GDB unwell.  Since I am just your Butler BuildBot,\n"
#    text += "I kindly ask that a human superior officer double-check this.\n\n"
#    text += (
#        "Please note that if you are reading this message on gdb-patches, there might\n"
#    )
#    text += "be other builders broken.\n\n"
#    text += "You can find more details about the unfortunate breakage in the next messages.\n\n"
#    text += "Cheers,\n\n"
#    text += "Your GDB BuildBot."
#
#    mail = MIMEText(text)
#    mail["Subject"] = sbj
#    mail["From"] = "gdb-buildbot@sergiodj.net"
#    mail["To"] = to
#    mail["Message-Id"] = "<" + message_id + ">"
#
#    s = smtplib.SMTP("localhost")
#    s.sendmail(GDB_MAIL_FROM, to_list, mail.as_string())
#    s.quit()
#
#
# def SendAuthorBreakageMessage(name, branch, change, text_prepend):
#    """Send a message to the author of the commit if it broke GDB.
#
#    We use a lock file to avoid reporting the breakage to different
#    people.  This may happen, for example, if a commit X breaks GDB, but
#    subsequent commits are made after X, by different people."""
#    global GDB_MAIL_FROM
#
#    lockfile = make_breakage_lockfile_name(branch, name)
#
#    if os.path.exists(lockfile):
#        # This means we have already reported this failure for this
#        # builder to the author.
#        return
#
#    # This file will be cleaned the next time we run
#    # MessageGDBTesters, iff the build breakage has been fixed.
#    bf = open(lockfile, "w")
#    bf.write("Commit: %s\n" % change.revision)
#    bf.close()
#
#    SendRootBreakageMessage(name, branch, change)
#    root_message_id = make_breakage_root_message_id(change.revision, branch)
#
#    rev = change.revision
#    to = change.who.encode("ascii", "ignore").decode("ascii")
#    to += ", gdb-patches@sourceware.org"
#    to_list = [to]
#    to_list.append("gdb-patches@sourceware.org")
#    title = change.comments.split("\n")[0]
#
#    sbj = "Breakage on builder %s, revision %s" % (name, rev)
#    if branch != "master":
#        sbj += " [%s]" % branch
#
#    text = "Unfortunately it seems that there is a breakage on GDB.\n\n"
#    text += "Commit title: '%s'\n" % title
#    text += "Revision: %s\n\n" % rev
#    text += "You can find more details below:\n\n"
#    text += "+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+\n\n"
#    text += text_prepend
#
#    mail = MIMEText(text)
#    mail["Subject"] = sbj
#    mail["From"] = "gdb-buildbot@sergiodj.net"
#    mail["To"] = to
#    mail["In-Reply-To"] = "<" + root_message_id + ">"
#
#    s = smtplib.SMTP("localhost")
#    s.sendmail(GDB_MAIL_FROM, to_list, mail.as_string())
#    s.quit()
#
#
# def MessageGDBTesters(mode, name, build, results, master_status):
#    """This function is responsible for composing the message that will be
#    send to the gdb-testers mailing list."""
#    res_url = "http://gdb-build.sergiodj.net/results"
#    sourcestamp = build.getSourceStamps()[0]
#    branch = build.getSourceStamps()[0].branch
#    cur_change = build.getSourceStamps()[0].changes[0]
#    properties = build.getProperties()
#    isrebuild = properties.getProperty("isRebuild")
#
#    # Sending the root message to gdb-testers.
#    SendRootMessageGDBTesters(branch, cur_change, cur_change.revision)
#
#    # Subject
#    subj = "Failures on %s, branch %s" % (name, branch)
#
#    # Body
#    text = ""
#
#    # Buildslave name, useful for knowing the exact configuration.
#    text += "Buildslave:\n"
#    text += "\t%s\n" % build.getSlavename()
#
#    # Including the link for the full build
#    text += "\nFull Build URL:\n"
#    text += "\t<%s>\n" % master_status.getURLForThing(build)
#
#    # Commits that were tested.  Usually we should be dealing with
#    # only one commit
#    text += "\nCommit(s) tested:\n"
#    ss_list = build.getSourceStamps()
#    for ss in ss_list:
#        for chg in ss.changes:
#            text += "\t%s\n" % chg.revision
#
#    # Who's to blame?
#    text += "\nAuthor(s) (in the same order as the commits):\n"
#    for ss in ss_list:
#        for chg in ss.changes:
#            text += "\t%s\n" % chg.who
#
#    # Subject of the changes
#    text += "\nSubject:\n"
#    text += "\t%s\n" % cur_change.comments.split("\n")[0]
#
#    # URL to find more info about what went wrong.
#    text += "\nTestsuite log (gdb.sum and gdb.log) URL(s):\n"
#    text += "\t<%s/%s/%s/%s/>\n" % (
#        res_url,
#        name,
#        sourcestamp.revision[:2],
#        sourcestamp.revision,
#    )
#
#    # for ss in ss_list:
#    #     commit_id = get_builder_commit_id (name, ss.revision, ss.branch)
#    #     if commit_id:
#    #         text += "\t<%s/%s/.git/tree/?h=%s&id=%s>\n" % (git_url, name, quote (ss.branch),
#    #                                                        commit_id)
#    #     else:
#    #         text += "\t<Error fetching commit ID for %s>\n" % ss.revision
#
#    # Including the 'regressions' log.  This is the 'diff' of what
#    # went wrong.
#    text += "\n"
#    if isrebuild and isrebuild == "yes":
#        text += "\n*** WARNING: This was a REBUILD request! ***\n"
#        text += (
#            "*** The previous build (build #%s) MAY NOT BE the ancestor of the current build! ***\n\n"
#            % properties.getProperty("buildnumber")
#        )
#
#    # report_build_breakage will be True if we see a build breakage,
#    # i.e., if the 'configure' or the 'compile' steps fail.  In this
#    # case, we use this variable to know if we must report the
#    # breakage directly to the author.
#    report_build_breakage = False
#
#    # found_regressions will be True if the 'regressions' log is not
#    # empty.
#    found_regressions = False
#
#    for log in build.getLogs():
#        st = log.getStep()
#        if st.getResults()[0] == FAILURE:
#            n = st.getName()
#            if "No space left on device" in log.getText():
#                text += (
#                    "*** Internal error on buildslave (no space left on device). ***\n"
#                )
#                text += (
#                    "*** Please report this to the buildslave owner (see <%s/buildslaves/%s>) ***\n\n"
#                    % (master_status.getBuildbotURL(), build.getSlavename())
#                )
#                continue
#            elif n == "update gdb master repo":
#                text += "*** Failed to update master GDB git repository.  The build can continue. ***\n\n"
#                continue
#            elif n == "update gdb repo":
#                text += "*** Failed to update GDB git repository.  This is probably a timeout problem. ***\n\n"
#                break
#            elif n == "configure gdb":
#                text += "*** Failed to configure GDB. ***\n"
#                text += "============================\n"
#                text += log.getText()
#                text += "============================\n"
#                subj = "*** COMPILATION FAILED *** " + subj
#                report_build_breakage = True
#                break
#            elif n == "compile gdb":
#                text += "*** Failed to compiled GDB.  ***\n"
#                text += "============================\n"
#                ct = log.getText().decode("ascii", "ignore")
#                if len(ct) > 100000:
#                    text += "\n+++ The full log is too big to be posted here."
#                    text += "\n+++ These are the last 100 lines of it.\n\n"
#                    ctt = ct.split("\n")[-100:]
#                    ct = "\n".join(ctt)
#                    text += ct
#                else:
#                    text += ct
#                text += "============================\n"
#                subj = "*** COMPILATION FAILED *** " + subj
#                report_build_breakage = True
#                break
#            elif n == "make tags":
#                # We do not want to break here, because if this step
#                # fails the test will continue.
#                text += "*** Failed to make TAGS ***\n"
#                text += "Log URL: <%s/steps/%s/logs/%s>\n\n" % (
#                    master_status.getURLForThing(build),
#                    quote(n),
#                    quote(log.getName()),
#                )
#                continue
#            elif n == "regressions" and log.getName() == "regressions":
#                text += "*** Diff to previous build ***\n"
#                text += "============================\n"
#                text += log.getText()
#                text += "============================\n"
#                found_regressions = True
#                break
#
#    # Including the 'xfail' log.  It is important to say which tests
#    # we are ignoring.
#    if found_regressions:
#        if os.path.exists(os.path.join(gdb_web_base, name)):
#            xfail_commit = os.path.join(
#                gdb_web_base, name, "xfails", branch, ".last-commit"
#            )
#            text += "\n\n*** Complete list of XFAILs for this builder ***\n\n"
#            if os.path.exists(xfail_commit):
#                with open(xfail_commit, "r") as f:
#                    com = f.read().strip("\n")
#                    text += (
#                        "To obtain the list of XFAIL tests for this builder, go to:\n\n"
#                    )
#                    text += (
#                        "\t<https://git.sergiodj.net/gdb-xfails.git/tree/xfails/%s/xfails/%s/xfail?id=%s>\n\n"
#                        % (name, branch, com)
#                    )
#                    text += "You can also see a pretty-printed version of the list, with more information\n"
#                    text += "about each XFAIL, by going to:\n\n"
#                    text += (
#                        "\t<https://git.sergiodj.net/gdb-xfails.git/tree/xfails/%s/xfails/%s/xfail.table?id=%s>\n"
#                        % (name, branch, com)
#                    )
#            else:
#                text += "FAILURE TO OBTAIN THE COMMIT FOR THE XFAIL LIST.  PLEASE CONTACT THE BUILDBOT ADMIN.\n"
#    text += "\n"
#
#    if report_build_breakage:
#        subj += " *** BREAKAGE ***"
#        SendAuthorBreakageMessage(name, branch, cur_change, text)
#    else:
#        # There is no build breakage anymore!  Yay!  Now, let's see if
#        # we need to clean up any lock file from previous breaks.
#        lockfile = make_breakage_lockfile_name(branch, name)
#        rev_broke = None
#        mid_file = None
#        if os.path.exists(lockfile):
#            with open(lockfile, "r") as f:
#                rev_broke = f.readline().lstrip("Commit: ")
#            mid_file = make_breakage_root_message_id_filename(rev_broke, branch)
#            # We need to clean the lockfile.  Garbage-collect it here.
#            try:
#                os.remove(lockfile)
#            except OSError as e:
#                print("Failed with: ", e.strerror)
#                print("Error code: ", e.code)
#        if mid_file and os.path.exists(mid_file):
#            # Garbage-collect the Message-Id file
#            try:
#                os.remove(mid_file)
#            except OSError as e:
#                print("Failed with: ", e.strerror)
#                print("Error code: ", e.code)
#
#    return {"body": text, "type": "plain", "subject": subj}
#
#
# def MessageGDBTestersTryBuild(mode, name, build, results, master_status):
#    """This function is responsible for composing the message that will be
#    send to the gdb-testers mailing list."""
#    res_url = "http://gdb-build.sergiodj.net/results"
#    branch = build.getSourceStamps()[0].branch
#    sourcestamp = build.getSourceStamps()[0]
#    cur_change = sourcestamp.patch[1]
#    properties = build.getProperties()
#    try_count = properties.getProperty("try_count")
#    try_msgid = properties.getProperty("root_message_id")
#    try_comment = sourcestamp.patch_info[1]
#
#    try_to = build.getReason().strip("'try' job by user ")
#    # Sending the root message to gdb-testers.
#    SendRootMessageGDBTesters(
#        branch,
#        cur_change,
#        properties.getProperty("revision"),
#        istrysched=True,
#        try_to=try_to,
#        try_count=try_count,
#        try_msgid=try_msgid,
#        try_comment=try_comment,
#    )
#
#    # Subject
#    subj = "Try Build #%s on %s, branch %s" % (try_count, name, branch)
#
#    # Body
#    text = ""
#
#    # Buildslave name, useful for knowing the exact configuration.
#    text += "Buildslave:\n"
#    text += "\t%s\n" % build.getSlavename()
#
#    # Including the link for the full build
#    text += "\nFull Build URL:\n"
#    text += "\t<%s>\n" % master_status.getURLForThing(build)
#
#    # Commits that were tested.  Usually we should be dealing with
#    # only one commit
#    text += "\nLast commit(s) before Try Build:\n"
#    text += "\t%s\n" % sourcestamp.revision
#
#    # URL to find more info about what went wrong.
#    text += "\nTestsuite log (gdb.sum and gdb.log) URL(s):\n"
#    text += "\t<%s/%s/try/%s/%s/%s/>\n\n" % (
#        res_url,
#        name,
#        sourcestamp.revision[:2],
#        sourcestamp.revision,
#        try_count,
#    )
#
#    # commit_id = get_builder_commit_id (name, sourcestamp.revision,
#    #                                    sourcestamp.branch)
#    # if commit_id:
#    #     text += "\t<%s/%s/.git/tree/?h=%s&id=%s>\n" % (git_url, name,
#    #                                                    quote (sourcestamp.branch),
#    #                                                    commit_id)
#    # else:
#    #     text += "\t<Error fetching commit ID for %s>\n" % sourcestamp.revision
#
#    # found_regressions will be True if the 'regressions' log is not
#    # empty.
#    found_regressions = False
#
#    for log in build.getLogs():
#        st = log.getStep()
#        n = st.getName()
#        if st.getResults()[0] == SUCCESS or st.getResults()[0] == WARNINGS:
#            if n == "regressions":
#                text += (
#                    "\nCongratulations!  No regressions were found in this build!\n\n"
#                )
#                break
#        if st.getResults()[0] == FAILURE:
#            if "No space left on device" in log.getText():
#                text += (
#                    "*** Internal error on buildslave (no space left on device). ***\n"
#                )
#                text += (
#                    "*** Please report this to the buildslave owner (see <%s/buildslaves/%s>) ***\n\n"
#                    % (master_status.getBuildbotURL(), build.getSlavename())
#                )
#                continue
#            elif n == "update gdb master repo":
#                text += "*** Failed to update master GDB git repository.  The build can continue. ***\n\n"
#                continue
#            elif n == "update gdb repo":
#                text += "*** Failed to update GDB git repository.  This is probably a timeout problem. ***\n\n"
#                break
#            elif n == "configure gdb":
#                text += "*** Failed to configure GDB. ***\n"
#                text += "============================\n"
#                text += log.getText()
#                text += "============================\n"
#                subj = "*** COMPILATION FAILED *** " + subj
#                break
#            elif n == "compile gdb":
#                text += "*** Failed to compiled GDB.  ***\n"
#                text += "============================\n"
#                ct = log.getText().decode("ascii", "ignore")
#                if len(ct) > 100000:
#                    text += "\n+++ The full log is too big to be posted here."
#                    text += "\n+++ These are the last 100 lines of it.\n\n"
#                    ctt = ct.split("\n")[-100:]
#                    ct = "\n".join(ctt)
#                    text += ct
#                else:
#                    text += ct
#                text += "============================\n"
#                subj = "*** COMPILATION FAILED *** " + subj
#                break
#            elif n == "make tags":
#                # We do not want to break here, because if this step
#                # fails the test will continue.
#                text += "*** Failed to make TAGS ***\n"
#                text += "Log URL: <%s/steps/%s/logs/%s>\n\n" % (
#                    master_status.getURLForThing(build),
#                    quote(n),
#                    quote(log.getName()),
#                )
#                continue
#            elif n == "regressions" and log.getName() == "regressions":
#                text += "*** Diff to previous build ***\n"
#                text += "============================\n"
#                text += log.getText()
#                text += "============================\n"
#                found_regressions = True
#                break
#
#    # Including the 'xfail' log.  It is important to say which tests
#    # we are ignoring.
#    if found_regressions:
#        if os.path.exists(os.path.join(gdb_web_base, name)):
#            xfail_commit = os.path.join(
#                gdb_web_base, name, "xfails", branch, ".last-commit"
#            )
#            text += "\n\n*** Complete list of XFAILs for this builder ***\n\n"
#            if os.path.exists(xfail_commit):
#                with open(xfail_commit, "r") as f:
#                    com = f.read().strip("\n")
#                    text += (
#                        "To obtain the list of XFAIL tests for this builder, go to:\n\n"
#                    )
#                    text += (
#                        "\t<https://git.sergiodj.net/gdb-xfails.git/tree/xfails/%s/xfails/%s/xfail?id=%s>\n\n"
#                        % (name, branch, com)
#                    )
#                    text += "You can also see a pretty-printed version of the list, with more information\n"
#                    text += "about each XFAIL, by going to:\n\n"
#                    text += (
#                        "\t<https://git.sergiodj.net/gdb-xfails.git/tree/xfails/%s/xfails/%s/xfail.table?id=%s>\n"
#                        % (name, branch, com)
#                    )
#            else:
#                text += "FAILURE TO OBTAIN THE COMMIT FOR THE XFAIL LIST.  PLEASE CONTACT THE BUILDBOT ADMIN.\n"
#    text += "\n"
#
#    return {"body": text, "type": "plain", "subject": subj}
#
#
# class MyMailNotifier(mail.MailNotifier):
#    """Extend the regular MailNotifier class in order to filter e-mails by
#    scheduler."""
#
#    def isMailNeeded(self, build, results):
#        prop = build.properties.getProperty("scheduler")
#        if prop.startswith("racy"):
#            return False
#        elif prop.startswith("try"):
#            if "TRY" not in self.tags:
#                # This means we're dealing with mn.  We only send
#                # e-mail on mn_try.
#                return False
#        else:
#            if "TRY" in self.tags:
#                # We're dealing with mn_try.
#                return False
#        return mail.MailNotifier.isMailNeeded(self, build, results)
#
#
# mn = MyMailNotifier(
#    fromaddr=GDB_MAIL_FROM,
#    sendToInterestedUsers=False,
#    extraRecipients=[GDB_MAIL_TO],
#    mode=("failing"),
#    messageFormatter=MessageGDBTesters,
#    tags=["MAIL"],
#    extraHeaders={
#        "X-GDB-Buildbot": "1",
#        "In-Reply-To": util.Interpolate("<%(prop:got_revision)s@gdb-build>"),
#    },
# )
#
#
# class LookupEmailTryBuild(object):
#    implements(IEmailLookup)
#
#    def getAddress(self, name):
#        return name
#
#
# mn_try = MyMailNotifier(
#    fromaddr=GDB_MAIL_FROM,
#    sendToInterestedUsers=True,
#    mode=("failing", "passing", "warnings"),
#    messageFormatter=MessageGDBTestersTryBuild,
#    lookup=LookupEmailTryBuild(),
#    tags=["MAIL", "TRY"],
#    extraHeaders={
#        "X-GDB-Buildbot": "1",
#        "In-Reply-To": util.Interpolate("%(prop:root_message_id)s"),
#    },
# )

# c["status"].append(mn)
# c["status"].append(mn_try)

c["title"] = "GDB"
c["titleURL"] = "https://gnu.org/s/gdb"

c["buildbotURL"] = "http://10.0.0.214:8010/"

c["db"] = {
    "db_url": "sqlite:///state.sqlite",
}

# Build steps

# This is where we define our build steps.  A build step is some
# command/action that buildbot will perform while building GDB.  See
# the documentation on each build step class to understand what it
# does.


def doStepIfTryBuild(step):
    return step.hasProperty("try") and step.getProperty("try")


class CloneGDBRepo(steps.Git):
    def __init__(self):
        super().__init__(
            # Parameters common to all steps.
            name="clone/update GDB repo",
            description="cloning/updating",
            descriptionDone="clone/update",
            doStepIf=lambda s: not doStepIfTryBuild(s),
            # Parameters common to all source steps.
            mode="full",
            method="fresh",
            # Parameters specific to Git.
            repourl=GIT_REPO_URL,
            workdir=util.Interpolate("%(prop:builddir)s/src"),
        )


class CloneGDBRepoGerrit(gerrit.Gerrit):
    def __init__(self):
        super().__init__(
            name="clone/update GDB repo from Gerrit change",
            description="cloning/updating",
            descriptionDone="clone/update",
            doStepIf=doStepIfTryBuild,
            # mode="full",
            # method="fresh",
            # Use the anonymous HTTP(s) method, as this will run on the
            # worker, which won't have ssh access to Gerrit.
            repourl="http://10.0.0.214:8080/binutils-gdb",
            workdir=util.Interpolate("%(prop:builddir)s/src"),
        )


class ConfigureGDB(steps.ConfigureNewStyle):
    """This build step runs the GDB "configure" command, providing extra
    flags for it if needed."""

    def __init__(self, cc=None, cxx=None):
        cc = cc if cc is not None else "gcc"
        cxx = cxx if cxx is not None else "g++"
        super().__init__(
            command=[
                "../src/configure",
                "--disable-binutils",
                "--disable-ld",
                "--disable-gold",
                "--disable-gas",
                "--disable-sim",
                "--disable-gprof",
                "CC=ccache " + cc,
                "CXX=ccache " + cxx,
                "CFLAGS=-g3 -O2",
                "CXXFLAGS=-g3 -O2 -D_GLIBCXX_DEBUG",
            ]
        )


class CompileGDB(steps.CompileNewStyle):
    """This build step runs "make" to compile the GDB sources.  It
    provides extra "make" flags to "make" if needed.  It also uses the
    "jobs" properties to figure out how many parallel jobs we can use when
    compiling GDB; this is the "-j" flag for "make".  The value of the
    "jobs" property is set at the "config.json" file, for each
    buildslave."""

    def __init__(self):
        super().__init__(
            command=[
                "make",
                util.Interpolate("-j%(prop:jobs:-1)s"),
                "all",
            ],
            suppressionList=[
                (
                    None,  # fileRe
                    "-Wmissing-prototypes",  # warnRe
                    None,  # start
                    None,  # end
                )
            ],
        )


class MakeTAGSGDB(steps.ShellCommand):
    name = "make tags"
    description = "running make TAGS"
    descriptionDone = "ran make TAGS"

    def __init__(self, make_command="make", **kwargs):
        steps.ShellCommand.__init__(self, make_command="make", **kwargs)
        self.workdir = util.Interpolate("%(prop:builddir)s/build/gdb")
        self.command = ["%s" % make_command, "TAGS"]
        # We do not want to stop testing when this command fails.
        self.haltOnFailure = False
        self.flunkOnFailure = False
        self.flunkOnWarnings = False


class TestGDB(steps.ShellCommandNewStyle):
    """This build step runs the full testsuite for GDB.  It can run in
    parallel mode (see BuildAndTestGDBFactory below), and it will also
    provide any extra flags for "make" if needed.  Unfortunately, because
    our testsuite is not perfect (yet), this command must not make
    BuildBot halt on failure."""

    name = "test gdb"
    description = r"testing GDB"
    descriptionDone = r"tested GDB"

    def __init__(self, cc=None, cxx=None, target_board=None):
        command=["make", "-k", "check", "TS=1"]
        runtestflags = ''

        if cc is not None:
            runtestflags += f" CC_FOR_TARGET={cc}"

        if cxx is not None:
            runtestflags += f" CXX_FOR_TARGET={cxx}"

        if target_board is not None:
            runtestflags += f" --target_board={target_board}"

        if len(runtestflags) > 0:
            command.append(f"RUNTESTFLAGS={runtestflags}")

        super().__init__(
            command=command,
            decodeRC={0: SUCCESS, 1: SUCCESS, 2: SUCCESS},
            workdir=util.Interpolate("%(prop:builddir)s/build/gdb/testsuite"),
        )

        #        self.env = test_env
        # Needed because of dejagnu
        # self.haltOnFailure = False
        # self.flunkOnFailure = False
        # self.flunkOnWarnings = False


class TestRacyGDB(steps.ShellCommand):
    """This build step runs the full testsuite for GDB for racy testcases.
    It can run in parallel mode (see BuildAndTestGDBFactory below), and it
    will also provide any extra flags for "make" if needed.
    Unfortunately, because our testsuite is not perfect (yet), this
    command must not make BuildBot halt on failure."""

    name = "test racy gdb"
    description = r"testing GDB (racy)"
    descriptionDone = r"tested GDB (racy)"

    def __init__(
        self, make_command="make", extra_make_check_flags=[], test_env={}, **kwargs
    ):
        steps.ShellCommand.__init__(
            self, decodeRC={0: SUCCESS, 1: SUCCESS, 2: SUCCESS}, **kwargs
        )

        self.workdir = util.Interpolate("%(prop:builddir)s/build/gdb/testsuite")
        self.command = [
            "%s" % make_command,
            "-k",
            "check",
            "RACY_ITER=5",
        ] + extra_make_check_flags

        self.env = test_env
        # Needed because of dejagnu
        self.haltOnFailure = False
        self.flunkOnFailure = False
        self.flunkOnWarnings = False


class ComputeTryBuildCount(steps.BuildStep):
    def run(self):
        istry = self.getProperty("scheduler").startswith("try")

        if not istry:
            count = 0
        else:
            builder = self.getProperty("buildername")
            rev = self.getProperty("got_revision")
            branch = self.getProperty("branch")
            db_file = os.path.join(get_web_base(), builder, builder + ".db")

            con = sqlite3.connect(db_file)
            c = con.cursor()
            c.execute(
                'SELECT COUNT(*) FROM logs WHERE commitid = "%s" AND branch = "%s" AND trysched = 1'
                % (rev, branch)
            )
            count = str(c.fetchone()[0])
            con.close()

        self.setProperty("try_count", count, "ComputeTryBuildCount")

        return 0


def scheduler_is_racy(step):
    return step.getProperty("scheduler").startswith("racy")


def scheduler_is_try(step):
    return step.getProperty("scheduler").startswith("try")


def scheduler_is_not_try_hide(result, step):
    return not scheduler_is_try(step)


def scheduler_is_racy_hide(result, step):
    return scheduler_is_racy(step)


def scheduler_is_racy_try_hide(result, step):
    return scheduler_is_racy(step) and scheduler_is_try(step)


def scheduler_is_racy_do(step):
    return scheduler_is_racy(step)


def scheduler_is_not_racy(step):
    return not scheduler_is_racy(step)


def scheduler_is_not_try(step):
    return not scheduler_is_try(step)


def scheduler_is_not_racy_hide(result, step):
    return scheduler_is_not_racy(step)


def scheduler_is_not_racy_try_hide(result, step):
    return scheduler_is_not_racy(step) and scheduler_is_not_try(step)


def scheduler_is_not_racy_do(step):
    return scheduler_is_not_racy(step)


def scheduler_is_not_racy_try_do(step):
    return scheduler_is_not_racy(step) and scheduler_is_not_try(step)


# Build Factory

# This is where our Build Factory is defined.  A build factory is a
# description of the build process, which is made in terms of build
# steps.  The BuildAndTestGDBFactory is the main build factory for
# GDB; it is configurable and should be more than enough to describe
# most builds.


class BuildAndTestGDBFactory(factory.BuildFactory):
    """This is the main build factory for the GDB project.  It was made to
    be very configurable, and should be enough to describe most builds.
    The parameters of the class are:

        - ConfigureClass: set this to be the class (i.e., build step) that
          will be called to configure GDB.  It needs to accept the same
          arguments as the ConfigureGDB class above.  The default is to
          use ConfigureGDB.

        - CompileClass: set this to be the class (i.e., build step) that
          will be called to compile GDB.  It needs to accept the same
          arguments as the CompileGDB class above.  The default is to use
          CompileGDB.

        - TestClass: set this to be the class (i.e., build step) that will
          be called to test GDB.  It needs to accept the same arguments as
          the TestGDB class above.  The default is to use TestGDB.

        - extra_conf_flags: extra configure flags to be passed to
          "configure".  Should be a list (i.e., []).  The default is None.
          Do not pass CFLAGS/CXXFLAGS here; use the variables below for
          that.

        - extra_CFLAGS: extra CFLAGS to be passed to "configure".
          Should be a list (i.e., []).  The default is None.

        - extra_CXXFLAGS: extra CXXFLAGS to be passed to "configure".
          Should be a list (i.e., []).  The default is None.

        - enable_targets_all: set this to True to pass
          '--enable-targets=all' to configure.  The default is True.

        - extra_make_flags: extra flags to be passed to "make", when
          compiling.  Should be a list (i.e., []).  The default is None.

        - extra_make_check_flags: extra flags to be passed to "make
          check", when testing.  Should be a list (i.e., []).  The default
          is None.

        - test_env: extra environment variables to be passed to "make
          check", when testing.  Should be a dictionary (i.e., {}).  The
          default is None.

        - test_parallel: set to True if the test shall be parallelized.
          Default is False.  Beware that parallelizing tests may cause
          some failures due to limited system resources.

        - make_command: set the command that will be called when running
          'make'.  This is needed because BSD systems need to run 'gmake'
          instead of make.  Default is 'make'.

        - use_system_debuginfo: set to False if GDB should be compiled
          with the "--with-separate-debug-dir" option set to
          "/usr/lib/debug".  Default is True.

        - system_debuginfo_location: Set this to the location of the
          debuginfo files in the system.  Default: "/usr/lib/debug"
    """

    TestRacyClass = TestRacyGDB

    # Set this to False to skip the test
    run_testsuite = True

    extra_CFLAGS = None
    extra_CXXFLAGS = None
    enable_targets_all = True

    extra_make_flags = None
    extra_make_check_flags = None
    test_env = None

    # Set this to false to disable parallel testing (i.e., do not use
    # FORCE_PARALLEL)
    test_parallel = True

    # Set this to the make command that you want to run in the "make"
    # steps.
    make_command = "make"

    # Set this to False to disable using system's debuginfo files
    # (i.e., do not use '--with-separate-debug-dir')
    use_system_debuginfo = True
    system_debuginfo_location = "/usr/lib/debug"

    def __init__(self, cc_for_build=None, cxx_for_build=None, cc_for_test=None, cxx_for_test=None, target_board=None):
        super().__init__()

        self.addStep(
            steps.RemoveDirectory(
                dir=util.Interpolate("%(prop:builddir)s/build"),
                name="remove old build dir",
                description="removing old build dir",
                descriptionDone="removed old build dir",
            )
        )

        # Only one of these is done, depending on whether the build is a try build or not.
        self.addStep(CloneGDBRepo())
        self.addStep(CloneGDBRepoGerrit())

        self.addStep(ConfigureGDB(cc=cc_for_build, cxx=cxx_for_build))
        self.addStep(CompileGDB())
        self.addStep(TestGDB(cc=cc_for_test, cxx=cxx_for_test, target_board=target_board))
        self.addStep(
            steps.ShellCommandNewStyle(
                name="compress gdb.{sum,log}",
                command=[
                    "xz",
                    util.Interpolate("%(prop:builddir)s/build/gdb/testsuite/gdb.sum"),
                    util.Interpolate("%(prop:builddir)s/build/gdb/testsuite/gdb.log"),
                ],
            )
        )

        self.addStep(
            steps.MultipleFileUpload(
                name="upload gdb.{sum,log}",
                workersrcs=[
                    util.Interpolate(
                        "%(prop:builddir)s/build/gdb/testsuite/gdb.sum.xz"
                    ),
                    util.Interpolate(
                        "%(prop:builddir)s/build/gdb/testsuite/gdb.log.xz"
                    ),
                ],
                masterdest=util.Interpolate(
                    "results/%(prop:buildername)s/%(prop:buildnumber)s"
                ),
                mode=0o644,
            )
        )
        self.addStep(
            steps.MasterShellCommand(
                name="fix results directory permissions",
                command=[
                    "find",
                    "results",
                    "-type",
                    "d",
                    "-exec",
                    "chmod",
                    "755",
                    "{}",
                    ";",
                ],
            )
        )
        self.addStep(
            steps.MasterShellCommand(
                name="compare to baseline",
                command=[
                    "./scripts/compare-baseline.sh",
                    util.Property("buildername"),
                    util.Interpolate("%(prop:buildnumber)s"),
                ],
            )
        )

        self.addStep(
            steps.MasterShellCommand(
                name="update baseline",
                doStepIf=lambda s: not doStepIfTryBuild(s),
                command=[
                    "./scripts/update-baseline.sh",
                    util.Property("buildername"),
                    util.Interpolate("%(prop:buildnumber)s"),
                ],
            )
        )

        return

        # Set the count of the try build
        if self.run_testsuite:
            self.addStep(
                ComputeTryBuildCount(doStepIf=scheduler_is_try, hideStepIf=True)
            )
            self.addStep(
                CopyOldGDBSumFile(
                    doStepIf=scheduler_is_not_racy_try_do, hideStepIf=False
                )
            )

        if not self.extra_CFLAGS:
            self.extra_CFLAGS = []

        if not self.extra_CXXFLAGS:
            self.extra_CXXFLAGS = []

        if self.enable_targets_all:
            self.extra_conf_flags.append("--enable-targets=all")

        if self.use_system_debuginfo:
            self.extra_conf_flags.append(
                "--with-separate-debug-dir=%s" % self.system_debuginfo_location
            )

        myCFLAGS = "CFLAGS=" + default_CFLAGS + " " + " ".join(self.extra_CFLAGS)
        myCXXFLAGS = (
            "CXXFLAGS=" + default_CXXFLAGS + " " + " ".join(self.extra_CXXFLAGS)
        )

        self.extra_conf_flags.append(myCFLAGS)
        self.extra_conf_flags.append(myCXXFLAGS)

        self.addStep(ConfigureGDB(self.extra_conf_flags, haltOnFailure=True))

        if not self.extra_make_flags:
            self.extra_make_flags = []
        self.addStep(
            self.CompileClass(
                self.make_command, self.extra_make_flags, haltOnFailure=True
            )
        )

        # This last will be executed when the build succeeds.  It is
        # needed in order to cleanup the breakage lockfile, if it
        # exists.
        self.addStep(
            steps.MasterShellCommand(
                command=[
                    "rm",
                    "-f",
                    util.Interpolate(
                        "/tmp/gdb-buildbot-breakage-report-%(prop:branch)s-%(prop:buildername)s"
                    ),
                ],
                hideStepIf=True,
                doStepIf=scheduler_is_not_racy_try_do,
            )
        )

        # Disabling this until we figure out how to properly run + test
        #        self.addStep (MakeTAGSGDB ())

        if not self.extra_make_check_flags:
            self.extra_make_check_flags = []

        if self.run_testsuite:
            if not self.test_env:
                self.test_env = {}

            if self.test_parallel:
                self.extra_make_check_flags.append(util.Interpolate("-j%(prop:jobs)s"))
                self.extra_make_check_flags.append(r"FORCE_PARALLEL=1")

            # Enable timestamp'ed output
            self.extra_make_check_flags.append("TS=1")

            self.addStep(
                self.TestClass(
                    self.make_command,
                    self.extra_make_check_flags,
                    self.test_env,
                    doStepIf=scheduler_is_not_racy_do,
                    hideStepIf=scheduler_is_racy_hide,
                )
            )

            self.addStep(
                GdbCatSumfileCommand(
                    workdir=util.Interpolate("%(prop:builddir)s/build/gdb/testsuite"),
                    description="analyzing test results",
                    descriptionDone="analyzed test results",
                    doStepIf=scheduler_is_not_racy_do,
                    hideStepIf=scheduler_is_racy_hide,
                )
            )
            self.addStep(
                steps.FileUpload(
                    slavesrc=util.Interpolate(
                        "%(prop:builddir)s/build/gdb/testsuite/gdb.log"
                    ),
                    masterdest=util.Interpolate(
                        make_master_path(
                            "results/%(prop:buildername)s/tmp/%(prop:got_revision)s/gdb.log"
                        )
                    ),
                    mode=0o644,
                    doStepIf=scheduler_is_not_racy_do,
                    hideStepIf=True,
                )
            )
            self.addStep(
                SaveGDBResults(
                    doStepIf=scheduler_is_not_racy_do, hideStepIf=scheduler_is_racy_hide
                )
            )

            # Racy

            self.addStep(
                self.TestRacyClass(
                    self.make_command,
                    self.extra_make_check_flags,
                    self.test_env,
                    doStepIf=scheduler_is_racy_do,
                    hideStepIf=scheduler_is_not_racy_hide,
                )
            )

            self.addStep(
                GDBAnalyzeRacyTests(
                    workdir=util.Interpolate("%(prop:builddir)s/build/gdb/testsuite"),
                    description="analyzing racy tests",
                    descriptionDone="analyzed racy tests",
                    doStepIf=scheduler_is_racy_do,
                    hideStepIf=scheduler_is_not_racy_hide,
                )
            )


# Builders

# This section describes our builders.  The builders are instances of
# a build factory, and they will be used to do a specific build of
# the project.
#
# The nomenclature here is important.  Every builder should start
# with the prefix "RunTestGDB", and then be followed by the testing
# scenario that the build will test, followed by "_cXXtYY", where XX
# is the bitness of the compilation, and YY is the bitness of the
# testing.  So, for example, if we are specifically testing GDB
# running the native-gdbserver tests, compiling GDB on a 64-bit
# machine, but running the tests in 32-bit mode, our builder would be called:
#
#     RunTestGDBNativeGDBServer_c64t32


class RunTestGDBPlain_c64t64(BuildAndTestGDBFactory):
    """Compiling for 64-bit, testing on 64-bit."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class RunTestGDBPlain_c32t32(BuildAndTestGDBFactory):
    """Compiling on 32-bit, testing on 32-bit."""

    def __init__(self, **kwargs):
        self.extra_CFLAGS = ["-m32"]
        self.extra_CXXFLAGS = self.extra_CFLAGS
        self.extra_make_check_flags = [r"RUNTESTFLAGS=--target_board unix/-m32"]
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBm32_c64t32(BuildAndTestGDBFactory):
    """Compiling on 64-bit, testing on 32-bit."""

    def __init__(self, **kwargs):
        self.extra_make_check_flags = [r"RUNTESTFLAGS=--target_board unix/-m32"]
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBNativeGDBServer_c64t64(BuildAndTestGDBFactory):
    """Compiling on 64-bit, testing native-gdbserver on 64-bit."""

    def __init__(self):
        super().__init__(target_board='native-gdbserver')


class RunTestGDBNativeGDBServer_c64t32(BuildAndTestGDBFactory):
    """Compiling on 64-bit, testing native-gdbserver on 32-bit."""

    def __init__(self, **kwargs):
        self.extra_make_check_flags = [
            r"RUNTESTFLAGS=--target_board native-gdbserver/-m32"
        ]
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBNativeGDBServer_c32t32(BuildAndTestGDBFactory):
    """Compiling on 32-bit, testing native-gdbserver on 32-bit."""

    def __init__(self, **kwargs):
        self.extra_CFLAGS = ["-m32"]
        self.extra_CXXFLAGS = self.extra_CFLAGS
        self.extra_make_check_flags = [
            "RUNTESTFLAGS=--target_board native-gdbserver/-m32"
        ]
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBNativeExtendedGDBServer_c64t64(BuildAndTestGDBFactory):
    """Compiling on 64-bit, testing native-extended-gdbserver on 64-bit."""

    def __init__(self):
        super().__init__(target_board='native-extended-gdbserver')


class RunTestGDBNativeExtendedGDBServer_c64t32(BuildAndTestGDBFactory):
    """Compiling on 64-bit, testing native-extended-gdbserver on 32-bit."""

    def __init__(self, **kwargs):
        self.extra_make_check_flags = [
            r"RUNTESTFLAGS=--target_board native-extended-gdbserver/-m32"
        ]
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBNativeExtendedGDBServer_c32t32(BuildAndTestGDBFactory):
    """Compiling on 64-bit, testing native-extended-gdbserver on 32-bit."""

    def __init__(self, **kwargs):
        self.extra_CFLAGS = ["-m32"]
        self.extra_CXXFLAGS = self.extra_CFLAGS
        self.extra_make_check_flags = [
            r"RUNTESTFLAGS=--target_board native-extended-gdbserver/-m32"
        ]
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBIndexBuild(BuildAndTestGDBFactory):
    """Testing with the "cc-with-tweaks.sh" passing -i."""

    def __init__(self, **kwargs):
        self.test_env = {
            "RUNTESTFLAGS": util.Interpolate(
                "'CC_FOR_TARGET=/bin/sh %(prop:builddir)s/binutils-gdb/gdb/contrib/cc-with-tweaks.sh -i gcc' 'CXX_FOR_TARGET=/bin/sh %(prop:builddir)s/binutils-gdb/gdb/contrib/cc-with-tweaks.sh -i g++'"
            )
        }
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBIndexBuild_c32t32(BuildAndTestGDBFactory):
    """Testing with the "cc-with-tweaks.sh" passing -i.  32-bit version"""

    def __init__(self, **kwargs):
        self.extra_CFLAGS = ["-m32"]
        self.extra_CXXFLAGS = self.extra_CFLAGS
        self.test_env = {
            "RUNTESTFLAGS": util.Interpolate(
                "'CC_FOR_TARGET=/bin/sh %(prop:builddir)s/binutils-gdb/gdb/contrib/cc-with-tweaks.sh -i gcc' 'CXX_FOR_TARGET=/bin/sh %(prop:builddir)s/binutils-gdb/gdb/contrib/cc-with-tweaks.sh -i g++'"
            )
        }
        BuildAndTestGDBFactory.__init__(self, **kwargs)


# Class for only building GDB, without testing


class RunTestGDBPlainFedoraW64MingW32_c64notest(BuildAndTestGDBFactory):
    """Compiling on Fedora for 64-bit using MingW32, without tests."""

    def __init__(self, **kwargs):
        self.extra_conf_flags = [
            "--host=x86_64-w64-mingw32",
            "--target=x86_64-w64-mingw32",
            # Needed because the build is currently breaking.
            "--disable-intl",
        ]
        self.run_testsuite = False
        BuildAndTestGDBFactory.__init__(self, **kwargs)


# Classes needed for BSD systems


class RunTestGDBBSD_Common(BuildAndTestGDBFactory):
    """Common BSD test configurations"""

    def __init__(self, **kwargs):
        self.make_command = "gmake"
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBPlainBSD_c64t64(RunTestGDBPlain_c64t64, RunTestGDBBSD_Common):
    """Compiling for 64-bit, testing on 64-bit."""

    pass


class RunTestGDBIndexBuildBSD(RunTestGDBIndexBuild, RunTestGDBBSD_Common):
    """Testing with the "cc-with-tweaks.sh" passing -i.  FIXME: include bitness here."""

    pass


class RunTestGDBNetBSD_Common(BuildAndTestGDBFactory):
    """Common NetBSD test configurations"""

    def __init__(self, **kwargs):
        self.make_command = "gmake"
        self.run_testsuite = False
        self.system_debuginfo_location = "/usr/libdata/debug"
        self.enable_targets_all = False
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBPlainNetBSD_c64(RunTestGDBNetBSD_Common):
    """Compiling (but not testing) for 64-bit"""

    pass


# Classes needed for AIX systems


class RunTestGDBAIX_Common(BuildAndTestGDBFactory):
    """Common AIX test configurations"""

    def __init__(self, **kwargs):
        # Unfortunately we have to disable -Werror there...
        # ... and now we also have to disable Python.
        self.extra_conf_flags = ["--disable-werror", "--with-python=no"]
        self.enable_targets_all = False
        self.make_command = "gmake"
        self.extra_make_flags = ["MAKEINFO=true"]
        BuildAndTestGDBFactory.__init__(self, **kwargs)


class RunTestGDBPlainAIX(RunTestGDBAIX_Common, RunTestGDBPlain_c64t64):
    """Compiling for AIX"""

    pass


# Classes needed for Solaris systems

# class RunTestGDBSolaris_Common (BuildAndTestGDBFactory):
#     """Common Solaris test configurations"""
#     def __init__ (self, **kwargs):
#         self.enable_targets_all = False
#         self.make_command = 'gmake'
#         self.run_testsuite = False
#         # While a regular gdb build succeeds, a -g -D_GLIBCXX_DEBUG
#         # build as used by the buildbot fails as reported in PR
#         # build/23676.  This can be avoided either by performing a -g
#         # -O build or with --disable-unit-tests from Sergio's proposed
#         # patch.
#         self.extra_CFLAGS = [ '-O' ]
#         self.extra_CXXFLAGS = [ '-O' ]


class RunTestGDBPlainSolaris_c64(BuildAndTestGDBFactory):
    """Compiling for Solaris"""

    def __init__(self, **kwargs):
        self.extra_CFLAGS = ["-m64", "-O"]
        self.extra_CXXFLAGS = ["-m64", "-O"]
        self.enable_targets_all = False
        self.make_command = "gmake"
        self.run_testsuite = False
        BuildAndTestGDBFactory.__init__(self, **kwargs)


# This function prevents a builder to build more than one build at the
# same time.  This is needed because we do not have a way to lock the
# git repository containing the test results of the builder, so
# simultaneous builds can cause a mess when committing the test
# results.
#
# TODO: see
#
#   https://docs.buildbot.net/latest/manual/configuration/interlocks.html#interlocks
#
# See if it can be used to serialize just the result reporting step.
# def DefaultGDBCanStartBuild(builder, buildslave, buildrequest):
#    return not builder.building


files_ignored_re = re.compile(
    r"(binutils/|cpu/|elfcpp/|gas/|gold/|gprof/|ld/|texinfo/|gdb/doc/).*"
)


def DefaultGDBfileIsImportant(change):
    """Implementation of fileIsImportant method, in order to decide which
    changes to build on GDB."""
    only_changelog = True

    # Do not build the 'GDB Administrator' commits, that are used to
    # increment the date on some files.
    if "GDB Administrator" in change.who:
        return False

    # Filter out commits that only modify the ChangeLog files.
    for filename in change.files:
        if "ChangeLog" not in filename:
            only_changelog = False
            break

    if only_changelog:
        return False

    for filename in change.files:
        if not re.match(files_ignored_re, filename):
            return True

    return False


def prioritizeTryBuilds(builder, requests):
    for r in requests:
        if r.properties.getProperty("scheduler").startswith("try"):
            return r
    return requests[0]


class GDB_Try_Jobdir(Try_Jobdir):
    def parseJob(self, f):
        ret = Try_Jobdir.parseJob(self, f)
        root_msgid = "<%s-%s-try@gdb-build>" % (ret["baserev"], strftime("%H-%M-%S"))
        ret["properties"]["root_message_id"] = root_msgid
        return ret


# Configuration loading

# This is "the heart" of this file.  This function is responsible for
# loading the configuration present in the "lib/config.json" file,
# and initializing everything needed for BuildBot to work.  Most of
# this function was copied from WebKit's BuildBot configuration, with
# lots of tweaks.

# Workers

with open("./passwords.json") as f:
    passwords = load(f)


def make_worker(name, jobs=None):
    properties = {}

    if jobs is not None:
        properties["jobs"] = jobs

    return Worker(
        name,
        passwords[name],
        max_builds=2,
        properties=properties,
    )


worker_ubuntu_2004_x86_64_1 = make_worker(name="Ubuntu-2004-x86_64-1", jobs=4)

c["workers"] = [
    worker_ubuntu_2004_x86_64_1,
]

# Builders


def make_builder(name, workernames, factory):
    # Ensure a single build of this builder happens at any given time.
    lock = util.MasterLock(f"lock-{name}")
    return util.BuilderConfig(
        name=name,
        workernames=workernames,
        factory=factory,
        # canStartBuild=DefaultGDBCanStartBuild,
        collapseRequests=True,
        locks=[lock.access("exclusive")],
    )


x86_64_workers = [worker_ubuntu_2004_x86_64_1.name]

builder_ubuntu_2004_x86_64_m64 = make_builder(
    "Ubuntu-2004-x86_64-m64",
    x86_64_workers,
    RunTestGDBPlain_c64t64(),
)

builder_ubuntu_2004_x86_64_m64_dwarf5 = make_builder(
    "Ubuntu-2004-x86_64-m64-dwarf5",
    x86_64_workers,
    RunTestGDBPlain_c64t64(target_board="unix/gdb:debug_flags=-gdwarf-5"),
)

builder_ubuntu_2004_x86_64_m64_clang = make_builder(
    "Ubuntu-2004-x86_64-m64-clang",
    x86_64_workers,
    RunTestGDBPlain_c64t64(cc_for_build="clang", cxx_for_build="clang++", cc_for_test="clang", cxx_for_test="clang++"),
)

builder_ubuntu_2004_x86_64_m64_clang_dwarf5 = make_builder(
    "Ubuntu-2004-x86_64-m64-clang-dwarf5",
    x86_64_workers,
    RunTestGDBPlain_c64t64(cc_for_build="clang", cxx_for_build="clang++",
            cc_for_test="clang", cxx_for_test="clang++", target_board="unix/gdb:debug_flags=-gdwarf-5"),
)

builder_ubuntu_2004_x86_64_native_gdbserver_m64 = make_builder(
    "Ubuntu-2004-x86_64-native-gdbserver-m64",
    x86_64_workers,
    RunTestGDBNativeGDBServer_c64t64(),
)

builder_ubuntu_2004_x86_64_native_extended_gdbserver_m64 = make_builder(
    "Ubuntu-2004-x86_64-native-extended-gdbserver-m64",
    x86_64_workers,
    RunTestGDBNativeExtendedGDBServer_c64t64(),
)

c["builders"] = [
    builder_ubuntu_2004_x86_64_m64,
    builder_ubuntu_2004_x86_64_m64_dwarf5,
    builder_ubuntu_2004_x86_64_m64_clang,
    builder_ubuntu_2004_x86_64_m64_clang_dwarf5,
    builder_ubuntu_2004_x86_64_native_gdbserver_m64,
    builder_ubuntu_2004_x86_64_native_extended_gdbserver_m64,
]

# Schedulers


def is_try_change(change):
    return "try" in change.properties

def is_not_try_change(change):
    return not is_try_change(change)


post_commit_scheduler = schedulers.AnyBranchScheduler(
    name="post-commit",
    builderNames=[x.name for x in c['builders']]    ,
    change_filter=util.ChangeFilter(
        branch_fn=should_watch_branch, filter_fn=is_not_try_change
    ),
    fileIsImportant=DefaultGDBfileIsImportant,
    treeStableTimer=60 * 3,
)


gerrit_try_scheduler = schedulers.AnyBranchScheduler(
    name="gerrit-try",
    builderNames=[
        builder_ubuntu_2004_x86_64_m64.name,
    ],
    change_filter=util.ChangeFilter(filter_fn=is_try_change),
)

force_scheduler = schedulers.ForceScheduler(
    name="force",
    builderNames=[x.name for x in c['builders']],
    #properties=[
    #    util.StringParameter(
    #        name="gerrit_change",
    #        label="Gerrit change in the form change_number/patchset_number",
    #        default="",
    #        size=80,
    #        regex="^[0-9]+/[0-9]+$",
    #        required=True,
    #    ),
    #    util.FixedParameter(name="try", default=True),
    #],
)


c["schedulers"] = [post_commit_scheduler, force_scheduler, gerrit_try_scheduler]

# c['manhole'] = PasswordManhole(
#        port=12345,
#        username='buildbot',
#        password='buildbot',
#        ssh_hostkey_dir='/home/buildbot/master/manhole-ssh-host-keys',
#
#        )
