# Functions for manipulating .sum summary files.

import re
import os.path
from StringIO import StringIO
# Necessary for ordered dictionaries.  We use them when the order or
# the tests matters to us.
from collections import OrderedDict
import lzma

# Helper regex for parse_sum_line.
sum_matcher = re.compile('^(.?(PASS|FAIL)): (.*)$')
racy_file_matcher = re.compile ('^(gdb\..*)')

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
    def parse_sum_line(self, out_dict, line, is_racy_file = False):
        global sum_matcher

        line = line.rstrip()
        if not is_racy_file:
            # Removing special XFAIL comment added by script.
            m = re.match(sum_matcher, line)
        else:
            m = re.match (racy_file_matcher, line)

        if m:
            if is_racy_file:
                # On racy.sum files, there is no result to parse.
                result = 'NONE'
                test_name = m.group (1)
            else:
                result = m.group (1)
                test_name = m.group (3)
            # Remove tail parentheses
            test_name = re.sub ('(\s+)?\(.*$', '', test_name)
            if result not in out_dict[1].keys ():
                out_dict[1][result] = set ()
            if test_name in out_dict:
                i = 2
                while True:
                    nname = test_name + ' <<' + str(i) + '>>'
                    if nname not in out_dict:
                        break
                    i = i + 1
                test_name = nname
            # Add the testname to the dictionary...
            out_dict[0][test_name] = result
            # and to the set.
            out_dict[1][result].add (test_name)

    def _write_sum_file(self, sum_dict, builder, rev, filename, header = None, istry):
        global gdb_web_base

        if istry:
            bdir = os.path.join (gdb_web_base, builder, 'try', rev[:2], rev)
        else:
            bdir = os.path.join (gdb_web_base, builder, rev[:2], rev)

        if not os.path.exists (bdir):
            old_umask = os.umask (0022)
            os.makedirs (bdir)
            os.umask (old_umask)
        fname = os.path.join (bdir, filename)
        keys = sum_dict[0].keys ()
        mode = 'w'
        old_umask = os.umask (0133)
        if header:
            with open (fname, 'w') as f:
                f.write (header)
            mode = 'a'
        with open (fname, mode) as f:
            for k in keys:
                f.write (sum_dict[0][k] + ': ' + k + '\n')
        os.umask (old_umask)

    def write_sum_file(self, sum_dict, builder, branch, rev, istry):
        self._write_sum_file (sum_dict, builder, rev, 'gdb.sum', istry = istry)

    def write_try_build_sum_file (self, sum_dict, builder, branch, rev):
        self._write_sum_file (sum_dict, builder, rev, 'trybuild_gdb.sum',
                              header = "### THIS SUM FILE WAS GENERATED BY A TRY BUILD ###\n\n",
                              istry = True)

    def write_baseline(self, sum_dict, builder, branch, rev, istry):
        self._write_sum_file(sum_dict, builder, rev, 'baseline',
                             header = "### THIS BASELINE WAS LAST UPDATED BY COMMIT %s ###\n\n" % rev,
                             istry = istry)

    # Read a .sum file.
    # The builder name is BUILDER.
    # The base file name is given in FILENAME.  This should be a git
    # revision; to read the baseline file for a branch, use `read_baseline'.
    # Returns a dictionary holding the .sum contents, or None if the
    # file did not exist.
    def _read_sum_file(self, builder, branch, rev, filename,
                       is_racy_file = False, is_xfail_file = False):
        global gdb_web_base

        if is_xfail_file:
            fname = os.path.join (gdb_web_base, builder, 'xfails', branch, filename)
        else:
            fname = os.path.join (gdb_web_base, builder, rev[:2], rev, filename)
        result = []
        # result[0] is the OrderedDict containing all the tests
        # and results.
        result.append (OrderedDict ())
        # result[1] is a dictionary containing sets of tests
        result.append (dict ())

        if os.path.exists (fname):
            with open (fname, 'r') as f:
                for line in f:
                    self.parse_sum_line (result, line,
                                         is_racy_file = is_racy_file)
        elif os.path.exists (fname + '.xz'):
            f = lzma.LZMAFile (fname, 'r')
            for line in f:
                self.parse_sum_line (result, line,
                                     is_racy_file = is_racy_file)
            f.close ()
        else:
            return None
        return result

    def read_sum_file (self, builder, branch, rev):
        return self._read_sum_file (builder, branch, rev, 'gdb.sum')

    def read_baseline(self, builder, branch, rev):
        return self._read_sum_file (builder, branch, rev, 'baseline')

    def read_xfail (self, builder, branch):
        return self._read_sum_file (builder, branch, None, 'xfail', is_xfail_file = True)

    def read_old_sum_file (self, builder, branch, rev):
        return self._read_sum_file (builder, branch, rev, 'previous_gdb.sum')

    # Parse some text as a .sum file and return the resulting
    # dictionary.
    def read_sum_text (self, text, is_racy_file = False):
        cur_file = StringIO (text)
        cur_results = []
        cur_results.append (OrderedDict ())
        cur_results.append (dict ())
        for line in cur_file.readlines ():
            self.parse_sum_line (cur_results, line,
                                 is_racy_file = is_racy_file)
        return cur_results

    # Parse some text as the racy.sum file and return the resulting
    # dictionary.
    def read_racy_sum_text (self, text):
        return self.read_sum_text (text, is_racy_file = True)

    # Compute regressions between RESULTS and BASELINE on BUILDER.
    # BASELINE will be modified if any new PASSes are seen.
    # Returns a regression report, as a string.
    def compute_regressions (self, builder, branch, results, old_res):
        our_keys = results[0].keys ()
        result = ''
        xfails = self.read_xfail (builder, branch)
        if xfails is None:
            xfails = {}
        else:
            xfails = xfails[0]
        for key in our_keys:
            # An XFAIL entry means we have an unreliable test.
            if key in xfails:
                continue
            # A transition to PASS means we should update the baseline.
            if results[0][key] == 'PASS':
                if key not in old_res[0] or old_res[0][key] != 'PASS':
                    old_res[0][key] = 'PASS'
                continue
            # A regression is just a transition to FAIL.
            if results[0][key] != 'FAIL':
                continue
            if key not in old_res[0]:
                result = result + 'new FAIL: ' + key + '\n'
            elif old_res[0][key] != 'FAIL':
                result = result + old_res[0][key] + ' -> FAIL: ' + key + '\n'
        return result
