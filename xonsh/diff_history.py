"""Tools for diff'ing two xonsh history files in a meaningful fashion."""
from datetime import datetime
from difflib import SequenceMatcher

from xonsh import lazyjson
from xonsh.tools import TERM_COLORS

NO_COLOR = TERM_COLORS['NO_COLOR'].replace('\001', '').replace('\002', '')
RED = TERM_COLORS['RED'].replace('\001', '').replace('\002', '')
GREEN = TERM_COLORS['GREEN'].replace('\001', '').replace('\002', '')
BOLD_RED = TERM_COLORS['BOLD_RED'].replace('\001', '').replace('\002', '')
BOLD_GREEN = TERM_COLORS['BOLD_GREEN'].replace('\001', '').replace('\002', '')

class HistoryDiffer(object):
    """This class helps diff two xonsh history files."""

    def __init__(self, afile, bfile, reopen=False, verbose=False):
        """
        Parameters
        ----------
        afile : file handle or str
            The first file to diff
        bfile : file handle or str
            The second file to diff
        reopen : bool, optional
            Whether or not to reopen the file handles each time. The default here is
            opposite from the LazyJSON default because we know that we will be doing
            a lot of reading so it is best to keep the handles open.
        verbose : bool, optional
            Whether to print a verbose amount of information.
        """
        self.a = lazyjson.LazyJSON(afile, reopen=reopen)
        self.b = lazyjson.LazyJSON(bfile, reopen=reopen)
        self.verbose = verbose
        self.sm = SequenceMatcher(autojunk=False)

    def __del__(self):
        self.a.close()
        self.b.close()

    def __str__(self):
        return self.format()

    def _header_line(self, lj):
        s = lj._f.name if hasattr(lj._f, 'name') else ''
        s += ' (' + lj['sessionid'] + ')'
        s += ' [locked]' if lj['locked'] else ' [unlocked]'
        ts = lj['ts'].load()
        ts0 = datetime.fromtimestamp(ts[0])
        s += ' started: ' + ts0.isoformat(' ')
        if ts[1] is not None:
            ts1 = datetime.fromtimestamp(ts[1])
            s += ' stopped: ' + ts1.isoformat(' ') + ' runtime: ' + str(ts1 - ts0) 
        return s

    def header(self):
        """Computes a header string difference."""
        s = ('{red}--- {aline}{no_color}\n'
             '{green}+++ {bline}{no_color}')
        s = s.format(aline=self._header_line(self.a), bline=self._header_line(self.b),
                     red=RED, green=GREEN, no_color=NO_COLOR)
        return s

    def _envbothdiff(self, in_both, aenv, benv):
        sm = self.sm
        s = ''
        for key in sorted(in_both):
            aval = aenv[key]
            bval = benv[key]
            if aval == bval:
                continue
            aline = RED + '- '
            bline = GREEN + '+ '
            s += '{0!r} in both, but differs\n'.format(key)
            sm.set_seqs(aval, bval)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'replace':
                    aline += BOLD_RED + aval[i1:i2] + RED
                    bline += BOLD_GREEN + bval[j1:j2] + GREEN
                elif tag == 'delete':
                    aline += BOLD_RED + aval[i1:i2] + RED
                elif tag == 'insert':
                    bline += BOLD_GREEN + bval[j1:j2] + GREEN
                elif tag == 'equal':
                    aline += aval[i1:i2]
                    bline += bval[j1:j2]
                else:
                    raise RuntimeError('tag not understood')
            s += aline + NO_COLOR + '\n' + bline + NO_COLOR +'\n\n'
        return s

    def envdiff(self):
        """Computes the difference between the environments."""
        aenv = self.a['env'].load()
        benv = self.b['env'].load()
        akeys = frozenset(aenv)
        bkeys = frozenset(benv)
        in_both = akeys & bkeys
        if len(in_both) == len(akeys) == len(bkeys):
            keydiff = self._envbothdiff(in_both, aenv, benv)
            if len(keydiff) == 0:
                return ''
            in_a = in_b = ''
        else:
            in_a = in_b = ''
            keydiff = self._envbothdiff(in_both, aenv, benv)
        s = 'Environment\n-----------\n' + in_a + keydiff + in_b
        return s

    def format(self):
        """Formats the difference between the two history files."""
        s = self.header()
        ed = self.envdiff()
        if len(ed) > 0:
            s += '\n\n' + ed
        return s.rstrip()


_HD_PARSER = None

def _create_parser():
    global _HD_PARSER
    if _HD_PARSER is not None:
        return _HD_PARSER
    from argparse import ArgumentParser
    p = ArgumentParser('diff-history', description='diffs two xonsh history files')
    p.add_argument('--reopen', dest='reopen', default=False, action='store_true',
                   help='make lazy file loading reopen files each time')
    p.add_argument('-v', '--verbose', dest='verbose', default=False, action='store_true',
                   help='whether to print even more information')
    p.add_argument('a', help='first file in diff')
    p.add_argument('b', help='second file in diff')
    _HD_PARSER = p
    return p


def main(args=None, stdin=None):
    """Main entry point for history diff'ing"""
    parser = _create_parser()
    ns = parser.parse_args(args)
    hd = HistoryDiffer(ns.a, ns.b, reopen=ns.reopen, verbose=ns.verbose)
    print(hd.format())


if __name__ == '__main__':
    main()
