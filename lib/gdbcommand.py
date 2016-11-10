# GDB .sum-fetching command.

from buildbot.status.results import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.plugins import steps, util
from sumfiles import DejaResults, get_web_base
from gdbgitdb import switch_to_branch
import os
import sqlite3

@util.renderer
def create_copy_command (props):
    rev = props.getProperty ('got_revision')
    builder = props.getProperty ('buildername')
    istry = props.getProperty ('isTrySched')
    branch = props.getProperty ('branch')
    command = [ 'cp', '-a' ]

    db_file = os.path.join (get_web_base (), builder, builder + '.db')
    if not os.path.exists (db_file):
        # This is probably the first commit being tested.  Don't do anything.
        return [ 'true' ]

    con = sqlite3.connect (db_file)
    c = con.cursor ()
    c.execute ('SELECT commitid FROM logs WHERE branch = "%s" AND trysched = 0 ORDER BY timestamp DESC LIMIT 1' % branch)
    comm = c.fetchone ()
    con.close ()

    if comm:
        commit = comm[0]
    else:
        return [ 'true' ]

    from_path = os.path.join (get_web_base (), builder, commit[:2], commit, 'gdb.sum.xz')
    if istry and istry == 'yes':
        to_path = os.path.join (get_web_base (), builder, 'try', rev[:2], rev)
    else:
        to_path = os.path.join (get_web_base (), builder, rev[:2], rev)

    if not os.path.exists (to_path):
        old_umask = os.umask (0022)
        os.makedirs (to_path)
        os.umask (old_umask)

    to_path = os.path.join (to_path, 'previous_gdb.sum.xz')

    command += [ from_path, to_path ]

    return command

class CopyOldGDBSumFile (steps.MasterShellCommand):
    """Copy the current gdb.sum file into the old_gdb.sum file."""
    name = "copy gdb.sum file"
    description = "copying previous gdb.sum file"
    descriptionDone = "copied previous gdb.sum file"

    def __init__ (self, **kwargs):
        steps.MasterShellCommand.__init__ (self, command = create_copy_command, **kwargs)

class GdbCatSumfileCommand(steps.ShellCommand):
    name = 'regressions'
    command = ['cat', 'gdb.sum']

    def __init__(self, **kwargs):
        steps.ShellCommand.__init__(self, **kwargs)

    def evaluateCommand(self, cmd):
        rev = self.getProperty('got_revision')
        builder = self.getProperty('buildername')
        istrysched = self.getProperty('isTrySched')
        branch = self.getProperty('branch')
        db_file = os.path.join (get_web_base (), builder, builder + '.db')
        parser = DejaResults()
        cur_results = parser.read_sum_text(self.getLog('stdio').getText())
        baseline = None

        if branch is None:
            branch = 'master'

        if not os.path.exists (db_file):
            # This takes care of our very first build.
            parser.write_sum_file (cur_results, builder, branch, rev)
            # If there was no previous baseline, then this run
            # gets the honor.
            if baseline is None:
                baseline = cur_results
            parser.write_baseline (baseline, builder, branch, rev)
            return SUCCESS

        con = sqlite3.connect (db_file)
        c = con.cursor ()
        c.execute ('SELECT commitid WHERE branch = "%s" AND trysched = 0 FROM logs ORDER BY timestamp DESC LIMIT 1' % branch)
        prev = c.fetchone ()
        con.close ()

        if prev:
            prevcommit = prev[0]
        else:
            # This takes care of our very first build.
            parser.write_sum_file (cur_results, builder, branch, rev)
            # If there was no previous baseline, then this run
            # gets the honor.
            if baseline is None:
                baseline = cur_results
            parser.write_baseline (baseline, builder, branch, rev)
            return SUCCESS

        baseline = parser.read_baseline (builder, branch, prevcommit)
        old_sum = parser.read_sum_file (builder, branch, prevcommit)
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

        if istrysched and istrysched == 'yes':
            parser.write_try_build_sum_file (cur_results, builder, branch, rev)
        else:
            parser.write_sum_file (cur_results, builder, branch, rev)
            # If there was no previous baseline, then this run
            # gets the honor.
            if baseline is None:
                baseline = cur_results
            parser.write_baseline (baseline, builder, branch, rev)

        return result
