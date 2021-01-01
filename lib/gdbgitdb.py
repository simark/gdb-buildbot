# DB-like with git

from buildbot.status.builder import SUCCESS
from buildbot.steps.shell import ShellCommand
from sumfiles import get_web_base
import os.path
from datetime import datetime
import git
import re


def get_builder_commit_id(builder, commit, branch):
    """Get the commit hash in the BUILDER's repository which points to the
    log files of the COMMIT that was tested."""
    repodir = os.path.join(get_web_base(), builder)
    repo = git.Repo.init(path=repodir)
    commit_id_re = re.compile(r"^\d{8}-\d{6}-%s-%s$" % (commit, branch))

    for t in repo.tags:
        m = commit_id_re.match(t.name)
        if not m:
            continue
        return t.commit.__str__()

    return None


def switch_to_branch(builder, branch, force_switch=False):
    """Switch (or create) to BRANCH on BUILDER repo."""
    repodir = os.path.join(get_web_base(), builder)
    repo = git.Repo.init(path=repodir)

    if "master" not in repo.heads:
        with open(os.path.join(repodir, "README"), "w") as f:
            f.write("git repo for GDB test results")
        with open(os.path.join(repodir, ".gitignore"), "w") as f:
            f.write("*xfails*\n")
        repo.index.add(["README", ".gitignore"])
        repo.index.commit("Initial commit")
        repo.index.write()

    if branch not in repo.heads:
        myhead = repo.create_head(branch)
    else:
        myhead = repo.heads[branch]

    myhead.checkout(force=force_switch)


class SaveGDBResults(ShellCommand):
    name = "save build results"
    description = "saving build results"
    descriptionDone = "saved build results"
    command = ["true"]

    def __init__(self, **kwargs):
        ShellCommand.__init__(self, **kwargs)

    def _evaluateCommand_builder_branch(self, cmd):
        rev = self.getProperty("got_revision")
        builder = self.getProperty("buildername")
        istry = self.getProperty("isTryBuilder")
        branch = self.getProperty("branch")
        repodir = get_web_base()
        builder_dir = os.path.join(repodir, builder)
        # TODO: Include timestamp in the tag name?
        full_tag = "%s-%s-%s" % (builder, rev, branch)

        if branch is None:
            branch = "master"
        if istry and istry == "yes":
            # Do nothing
            return SUCCESS

        repo = git.Repo.init(path=repodir)
        if not os.path.exists(builder_dir):
            os.mkdir(builder_dir)

        if "master" not in repo.heads:
            with open(os.path.join(repodir, "README"), "w") as f:
                f.write("git repo for GDB test results")
            with open(os.path.join(repodir, ".gitignore"), "w") as f:
                f.write("*xfail*\n")
            repo.index.add(["README", ".gitignore"])
            repo.index.commit("Initial commit")
            repo.index.write()

        if builder not in repo.heads:
            myhead = repo.create_head(builder)
        else:
            myhead = repo.heads[builder]

        if full_tag not in repo.tags:
            myhead.checkout()
            repo.index.add(
                [
                    "%s/gdb.sum" % builder,
                    "%s/gdb.log" % builder,
                    "%s/baseline" % builder,
                ]
            )
            if repo.is_dirty():
                repo.index.commit("Log files for %s -- branch %s" % (full_tag, branch))
                repo.index.write()
            repo.create_tag(full_tag)
        return SUCCESS

    def _evaluateCommand_single_repo(self, cmd):
        rev = self.getProperty("got_revision")
        builder = self.getProperty("buildername")
        istrysched = self.getProperty("isTrySched")
        isrebuild = self.getProperty("isRebuild")
        branch = self.getProperty("branch")
        repodir = os.path.join(get_web_base(), builder)
        full_tag = "%s-%s-%s" % (datetime.now().strftime("%Y%m%d-%H%M%S"), rev, branch)

        if istrysched and istrysched == "yes":
            full_tag += "-TRY_BUILD"

        if branch is None:
            branch = "master"

        repo = git.Repo.init(path=repodir)

        if isrebuild and isrebuild == "yes":
            # Do nothing
            if branch in repo.heads:
                # We have to clean the branch because otherwise this
                # can confuse other builds
                repo.git.execute(["git", "checkout", "*"])
            return SUCCESS

        if "master" not in repo.heads:
            with open(os.path.join(repodir, "README"), "w") as f:
                f.write("git repo for GDB test results -- %s" % builder)
            with open(os.path.join(repodir, ".gitignore"), "w") as f:
                f.write("*xfail*\n")
            repo.index.add(["README", ".gitignore"])
            repo.index.commit("Initial commit")
            repo.index.write()

        if branch not in repo.heads:
            myhead = repo.create_head(branch)
        else:
            myhead = repo.heads[branch]

        myhead.checkout()
        if full_tag not in repo.tags:
            repo.index.add(["gdb.sum", "gdb.log", "baseline"])
            if os.path.exists("%s/previous_gdb.sum" % repodir):
                repo.index.add(["previous_gdb.sum"])
            if os.path.exists("%s/trybuild_gdb.sum" % repodir):
                repo.index.add(["trybuild_gdb.sum"])
            if repo.is_dirty():
                if istrysched and istrysched == "yes":
                    repo.index.commit(
                        "TRY BUILD: Log files for %s -- branch %s" % (full_tag, branch)
                    )
                else:
                    repo.index.commit(
                        "Log files for %s -- branch %s" % (full_tag, branch)
                    )
                repo.index.write()
            repo.create_tag(full_tag)
            # Returning the HEAD to master
            repo.heads["master"].checkout()
        return SUCCESS

    def evaluateCommand(self, cmd):
        # We can change this scheme for the other one if needed

        # FIXME: the _evaluateCommand_builder_branch function needs
        # adjustment because of the multi-branch testing...
        return self._evaluateCommand_single_repo(cmd)
