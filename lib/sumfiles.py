# Functions for manipulating .sum summary files.

import re
import os.path
from StringIO import StringIO

# Helper regex for parse_sum_line.
sum_matcher = re.compile('^(.?(PASS|FAIL)): (.*)$')

# You must call set_web_base at startup to set this.
gdb_web_base = None

def set_web_base(arg):
    global gdb_web_base
    gdb_web_base = arg
    if not os.path.isdir(gdb_web_base):
        # If the parent doesn't exist, we're confused.
        # So, use mkdir and not makedirs.
        os.mkdir(gdb_web_base, 0755)

def get_web_base ():
    global gdb_web_base
    return gdb_web_base

class DejaResults(object):
    def __init__(self):
        object.__init__(self)

    # Parse a single line from a .sum file.
    # Uniquify the name, and put the result into OUT_DICT.
    # If the line does not appear to be about a test, ignore it.
    def parse_sum_line(self, out_dict, line):
        global sum_matcher
        line = line.rstrip()
        m = re.match(sum_matcher, line)
        if m:
            result = m.group(1)
            test_name = m.group(3)
            if test_name in out_dict:
                i = 2
                while True:
                    nname = test_name + ' <<' + str(i) + '>>'
                    if nname not in out_dict:
                        break
                    i = i + 1
                test_name = nname
            out_dict[test_name] = result

    def _write_sum_file(self, sum_dict, subdir, rev_or_branch, filename,
                        header = None):
        global gdb_web_base
        if not rev_or_branch:
            bdir = os.path.join (gdb_web_base, subdir)
        else:
            bdir = os.path.join (gdb_web_base, subdir, rev_or_branch)
        if not os.path.isdir (bdir):
            os.makedirs (bdir, 0755)
        fname = os.path.join (bdir, filename)
        keys = sum_dict.keys ()
        keys.sort ()
        mode = 'w'
        if header:
            with open (fname, 'w') as f:
                f.write (header)
            mode = 'a'
        with open (fname, mode) as f:
            for k in keys:
                f.write (sum_dict[k] + ': ' + k + '\n')

    def write_sum_file(self, sum_dict, builder, branch):
        self._write_sum_file (sum_dict, builder, None, 'gdb.sum')

    def write_baseline(self, sum_dict, builder, branch, rev):
        self._write_sum_file(sum_dict, builder, None, 'baseline',
                             header = "### THIS BASELINE WAS LAST UPDATED BY COMMIT %s ###\n\n" % rev)

    # Read a .sum file.
    # The builder name is BUILDER.
    # The base file name is given in FILENAME.  This should be a git
    # revision; to read the baseline file for a branch, use `read_baseline'.
    # Returns a dictionary holding the .sum contents, or None if the
    # file did not exist.
    def _read_sum_file(self, subdir, rev_or_branch, filename):
        global gdb_web_base
        if not rev_or_branch:
            fname = os.path.join (gdb_web_base, subdir, filename)
        else:
            fname = os.path.join (gdb_web_base, subdir, rev_or_branch, filename)
        if os.path.exists (fname):
            result = {}
            with open (fname, 'r') as f:
                for line in f:
                    self.parse_sum_line (result, line)
        else:
            result = None
        return result

    def read_sum_file (self, builder, branch):
        return self._read_sum_file (builder, None, 'gdb.sum')

    def read_baseline(self, builder, branch):
        return self._read_sum_file (builder, None, 'baseline')

    def read_xfail (self, builder, branch):
        return self._read_sum_file (builder, os.path.join ('xfails', branch),
                                    'xfail')

    def read_old_sum_file (self, builder, branch):
        return self._read_sum_file (builder, None, 'previous_gdb.sum')

    # Parse some text as a .sum file and return the resulting
    # dictionary.
    def read_sum_text (self, text):
        cur_file = StringIO (text)
        cur_results = {}
        for line in cur_file.readlines ():
            self.parse_sum_line (cur_results, line)
        return cur_results

    # Compute regressions between RESULTS and BASELINE on BUILDER.
    # BASELINE will be modified if any new PASSes are seen.
    # Returns a regression report, as a string.
    def compute_regressions (self, builder, branch, results, baseline):
        our_keys = results.keys ()
        our_keys.sort ()
        result = ''
        xfails = self.read_xfail (builder, branch)
        if xfails is None:
            xfails = {}
        for key in our_keys:
            # An XFAIL entry means we have an unreliable test.
            if key in xfails:
                continue
            # A transition to PASS means we should update the baseline.
            if results[key] == 'PASS':
                if key not in baseline or baseline[key] != 'PASS':
                    baseline[key] = 'PASS'
            # A regression is just a transition to FAIL.
            if results[key] != 'FAIL':
                continue
            if key not in baseline:
                result = result + 'new FAIL: ' + key + '\n'
            elif baseline[key] != 'FAIL':
                result = result + baseline[key] + ' -> FAIL: ' + key + '\n'
        return result
