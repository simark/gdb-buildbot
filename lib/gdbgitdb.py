# DB-like with git

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
        BuildStep.__init__ (self, **kwargs)

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
        try:
            repo = git.Repo (path = repodir)
        except git.InvalidGitRepositoryError:
            repo = git.Repo.init (path = repodir)
        git.index.add (['gdb.sum', 'gdb.log', '%s/baseline' % branch])
        git.index.commit ('Log files for %s' % rev)
        git.create_tag (rev)
        return SUCCESS
