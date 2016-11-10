# DB-like with filesystem

from buildbot.plugins import util, steps
from sumfiles import get_web_base
import os

class SaveGDBResults (steps.MasterShellCommand):
    name = 'save build results'
    description = 'saving build results'
    descriptionDone = 'saved build results'

    def __init__ (self, **kwargs):
        steps.MasterShellCommand.__init__ (self, command = None, **kwargs)
        self.command = [ os.path.expanduser ("~/scripts/update-logs.sh"),
                         "--commit", util.Property ('got_revision'),
                         "--builder", util.Property ('buildername'),
                         "--base-directory", get_web_base (),
                         "--branch", util.Property ('branch'),
                         "--is-try-sched", util.Property ('isTrySched',
                                                          default = 'no') ]
