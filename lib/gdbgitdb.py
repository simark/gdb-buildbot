# DB-like with git

from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.steps.shell import ShellCommand
from sumfiles import get_web_base
import os.path
from datetime import datetime
import git
import re

def get_builder_commit_id (builder, commit):
    """Get the commit hash in the BUILDER's repository which points to the
log files of the COMMIT that was tested."""
    repodir = os.path.join (get_web_base (), builder)
    repo = git.Repo.init (path = repodir)
    commit_id_re = re.compile ("^\d{8}-\d{6}-%s$" % commit)

    for t in repo.tags:
        m = commit_id_re.match (t.name)
        if not m:
            continue
        return t.commit.__str__ ()

    return None

class SaveGDBResults (ShellCommand):
    name = 'save build results'
    description = 'saving build results'
    descriptionDone = 'saved build results'
    command = ['true']

    def __init__ (self, **kwargs):
        ShellCommand.__init__ (self, **kwargs)

    def _evaluateCommand_builder_branch (self, cmd):
        rev = self.getProperty ('got_revision')
        builder = self.getProperty ('buildername')
        istry = self.getProperty ('isTryBuilder')
        branch = self.getProperty ('branch')
        repodir = get_web_base ()
        builder_dir = os.path.join (repodir, builder)
        # TODO: Include timestamp in the tag name?
        full_tag = "%s-%s" % (builder, rev)

        if branch is None:
            branch = 'master'
        if istry and istry == 'yes':
            # Do nothing
            return SUCCESS

        repo = git.Repo.init (path = repodir)
        if not os.path.exists (builder_dir):
            os.mkdir (builder_dir)

        if 'master' not in repo.heads:
            with open (os.path.join (repodir, 'README'), 'w') as f:
                f.write ("git repo for GDB test results")
            repo.index.add (['README'])
            repo.index.commit ('Initial commit')
            repo.index.write ()

        if builder not in repo.heads:
            myhead = repo.create_head (builder)
        else:
            myhead = repo.heads[builder]

        if full_tag not in repo.tags:
            myhead.checkout ()
            repo.index.add (['%s/gdb.sum' % builder,
                             '%s/gdb.log' % builder,
                             '%s/%s/baseline' % (builder, branch)])
            if repo.is_dirty ():
                repo.index.commit ('Log files for %s' % full_tag)
                repo.index.write ()
            repo.create_tag (full_tag)
        return SUCCESS

    def _evaluateCommand_single_repo (self, cmd):
        rev = self.getProperty ('got_revision')
        builder = self.getProperty ('buildername')
        istry = self.getProperty ('isTryBuilder')
        branch = self.getProperty ('branch')
        repodir = os.path.join (get_web_base (), builder)
        full_tag = "%s-%s" % (datetime.now ().strftime ("%Y%m%d-%H%M%S"), rev)

        if branch is None:
            branch = 'master'
        if istry and istry == 'yes':
            # Do nothing
            return SUCCESS

        repo = git.Repo.init (path = repodir)

        if 'master' not in repo.heads:
            with open (os.path.join (repodir, 'README'), 'w') as f:
                f.write ("git repo for GDB test results -- %s" % builder)
            repo.index.add (['README'])
            repo.index.commit ('Initial commit')
            repo.index.write ()

        if full_tag not in repo.tags:
            repo.index.add (['gdb.sum',
                             'gdb.log',
                             '%s/baseline' % branch])
            if repo.is_dirty ():
                repo.index.commit ('Log files for %s' % full_tag)
                repo.index.write ()
            repo.create_tag (full_tag)
        return SUCCESS

    def evaluateCommand (self, cmd):
        # We can change this scheme for the other one if needed
        return self._evaluateCommand_single_repo (cmd)
