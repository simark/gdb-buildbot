# GDB .sum-fetching command.

from buildbot.process.results import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.steps.shell import ShellCommand
from sumfiles import DejaResults, get_web_base
from gdbgitdb import switch_to_branch
from shutil import copyfile

class CopyOldGDBSumFile (ShellCommand):
    """Copy the current gdb.sum file into the old_gdb.sum file."""
    name = "copy gdb.sum file"
    description = "copying previous gdb.sum file"
    descriptionDone = "copied previous gdb.sum file"
    command = [ 'true' ]

    def __init__ (self, **kwargs):
        ShellCommand.__init__ (self, **kwargs)

    def evaluateCommand (self, cmd):
        rev = self.getProperty('got_revision')
        builder = self.getProperty('buildername')
        istrybuilder = self.getProperty('isTryBuilder')
        isrebuild = self.getProperty ('isRebuild')
        branch = self.getProperty('branch')
        wb = get_web_base ()
        if branch is None:
            branch = 'master'

        if (istrybuilder and istrybuilder == 'yes') or (isrebuild and isrebuild == 'yes'):
            return SUCCESS

        # Switch to the right branch inside the BUILDER repo
        switch_to_branch (builder, branch, force_switch = True)

        try:
            copyfile ("%s/%s/gdb.sum" % (wb, builder),
                      "%s/%s/previous_gdb.sum" % (wb, builder))
        except IOError:
            # If the dest file does not exist, ignore
            pass

        return SUCCESS

class GdbCatSumfileCommand(ShellCommand):
    name = 'regressions'
    command = ['cat', 'gdb.sum']

    def __init__(self, **kwargs):
        ShellCommand.__init__(self, **kwargs)

    def evaluateCommand(self, cmd):
        rev = self.getProperty('got_revision')
        builder = self.getProperty('buildername')
        istry = self.getProperty('isTryBuilder')
        branch = self.getProperty('branch')
        if branch is None:
            branch = 'master'

        # Switch to the right branch inside the BUILDER repo
        switch_to_branch (builder, branch, force_switch = False)

        parser = DejaResults()
        cur_results = parser.read_sum_text(self.getLog('stdio').getText())
        if not istry or istry == 'no':
            baseline = parser.read_baseline (builder, branch)
            old_sum = parser.read_old_sum_file (builder, branch)
        else:
            baseline = parser.read_sum_file(builder, rev)
            old_sum = parser.read_old_sum_file (builder, rev)
        result = SUCCESS
        if baseline is not None:
            report = parser.compute_regressions (builder, branch,
                                                 cur_results, baseline)
            if report is not '':
                self.addCompleteLog ('baseline_diff', report)
                result = WARNINGS

        if old_sum is not None:
            report = parser.compute_regressions (builder, branch,
                                                 cur_results, old_sum)
            if report is not '':
                self.addCompleteLog ('regressions', report)
                result = FAILURE

        if not istry or istry == 'no':
            parser.write_sum_file (cur_results, builder, branch)
            # If there was no previous baseline, then this run
            # gets the honor.
            if baseline is None:
                baseline = cur_results
            parser.write_baseline (baseline, builder, branch, rev)

        return result
