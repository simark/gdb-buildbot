from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.steps.shell import ShellCommand
from sumfiles import DejaResults
import smtplib
import socket
from email.mime.text import MIMEText

class GDBAnalyzeRacyTests (ShellCommand):
    """Analyze the racy tests"""
    command = ['cat', 'racy.sum']

    def __init__ (self, **kwargs):
        ShellCommand.__init__ (self, **kwargs)

    def evaluateCommand (self, cmd):
        builder = self.getProperty('buildername')
        branch = self.getProperty('branch')

        p = DejaResults ()

        racy_tests = p.read_racy_sum_text (self.getLog ('stdio').getText ())
        xfails = p.read_xfail (builder, branch)

        if not racy_tests or not racy_tests[1]:
            return SUCCESS
        elif not xfails or not xfails[1]:
            unique_tests = racy_tests[1]['NONE']
        else:
            unique_tests = racy_tests[1]['NONE'] - xfails[1]['FAIL']

        msg = "*** Regressions found ***\n"
        msg += "============================\n"
        for t in unique_tests:
            msg += "FAIL: %s\n" % t
        msg += "============================\n"

        mail = MIMEText (msg)
        mail['Subject'] = 'Failures on %s, branch %s' % (builder, branch)
        mail['From'] = 'GDB BuildBot Racy Detector <gdb-buildbot@sergiodj.net>'
        mail['To'] = 'gdb-buildbot@sergiodj.net'

        s = smtplib.SMTP ('localhost')
        s.sendmail ('gdb-buildbot@sergiodj.net',
                    [ 'gdb-buildbot@sergiodj.net' ],
                    mail.as_string ())
        s.quit ()

        return SUCCESS
