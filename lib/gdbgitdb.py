# DB-like with git

from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.steps.shell import ShellCommand
from sumfiles import get_web_base
import os.path
import git

class SaveGDBResults (ShellCommand):
    name = 'save build results'
    description = 'saving build results'
    descriptionDone = 'saved build results'
    command = ['true']

    def __init__ (self, **kwargs):
        ShellCommand.__init__ (self, **kwargs)

    def evaluateCommand (self, cmd):
        rev = self.getProperty ('got_revision')
        builder = self.getProperty ('buildername')
        istry = self.getProperty ('isTryBuilder')
        branch = self.getProperty ('branch')
        repodir = os.path.join (get_web_base (), builder)
        if branch is None:
            branch = 'master'
        if istry and istry == 'yes':
            # Do nothing
            return SUCCESS
        repo = git.Repo.init (path = repodir)
        if repo.is_dirty ():
            repo.index.add (['gdb.sum', 'gdb.log', '%s/baseline' % branch])
            repo.index.commit ('Log files for %s' % rev)
            repo.index.write ()
        repo.create_tag (rev)
        return SUCCESS
