"""Tools for diff'ing two xonsh history files in a meaningful fashion."""

import datetime
import difflib
import itertools

from xonsh.color_tools import COLORS
from xonsh.lib.lazyjson import LazyJSON

# intern some strings
REPLACE_S = "replace"
DELETE_S = "delete"
INSERT_S = "insert"
EQUAL_S = "equal"


def bold_str_diff(a, b, sm=None):
    if sm is None:
        sm = difflib.SequenceMatcher()
    aline = COLORS.RED + "- "
    bline = COLORS.GREEN + "+ "
    sm.set_seqs(a, b)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == REPLACE_S:
            aline += COLORS.BOLD_RED + a[i1:i2] + COLORS.RED
            bline += COLORS.BOLD_GREEN + b[j1:j2] + COLORS.GREEN
        elif tag == DELETE_S:
            aline += COLORS.BOLD_RED + a[i1:i2] + COLORS.RED
        elif tag == INSERT_S:
            bline += COLORS.BOLD_GREEN + b[j1:j2] + COLORS.GREEN
        elif tag == EQUAL_S:
            aline += a[i1:i2]
            bline += b[j1:j2]
        else:
            raise RuntimeError("tag not understood")
    return aline + COLORS.RESET + "\n" + bline + COLORS.RESET + "\n"


def redline(line):
    return f"{COLORS.RED}- {line}{COLORS.RESET}\n"


def greenline(line):
    return f"{COLORS.GREEN}+ {line}{COLORS.RESET}\n"


def highlighted_ndiff(a, b):
    """Returns a highlighted string, with bold characters where different."""
    s = ""
    sm = difflib.SequenceMatcher()
    sm.set_seqs(a, b)
    linesm = difflib.SequenceMatcher()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == REPLACE_S:
            for aline, bline in itertools.zip_longest(a[i1:i2], b[j1:j2]):
                if bline is None:
                    s += redline(aline)
                elif aline is None:
                    s += greenline(bline)
                else:
                    s += bold_str_diff(aline, bline, sm=linesm)
        elif tag == DELETE_S:
            for aline in a[i1:i2]:
                s += redline(aline)
        elif tag == INSERT_S:
            for bline in b[j1:j2]:
                s += greenline(bline)
        elif tag == EQUAL_S:
            for aline in a[i1:i2]:
                s += "  " + aline + "\n"
        else:
            raise RuntimeError("tag not understood")
    return s


class HistoryDiffer:
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
        self.a = LazyJSON(afile, reopen=reopen)
        self.b = LazyJSON(bfile, reopen=reopen)
        self.verbose = verbose
        self.sm = difflib.SequenceMatcher(autojunk=False)

    def __del__(self):
        self.a.close()
        self.b.close()

    def __str__(self):
        return self.format()

    def _header_line(self, lj):
        s = lj._f.name if hasattr(lj._f, "name") else ""
        s += " (" + lj["sessionid"] + ")"
        s += " [locked]" if lj.get("locked", False) else " [unlocked]"
        if lj.get("ts"):
            ts = lj["ts"].load()
            ts0 = datetime.datetime.fromtimestamp(ts[0])
            s += " started: " + ts0.isoformat(" ")
            if ts[1] is not None:
                ts1 = datetime.datetime.fromtimestamp(ts[1])
                s += " stopped: " + ts1.isoformat(" ") + " runtime: " + str(ts1 - ts0)
        return s

    def header(self):
        """Computes a header string difference."""
        s = "{red}--- {aline}{reset}\n" "{green}+++ {bline}{reset}"
        s = s.format(
            aline=self._header_line(self.a),
            bline=self._header_line(self.b),
            red=COLORS.RED,
            green=COLORS.GREEN,
            reset=COLORS.RESET,
        )
        return s

    def _env_both_diff(self, in_both, aenv, benv):
        sm = self.sm
        s = ""
        for key in sorted(in_both):
            aval = aenv[key]
            bval = benv[key]
            if aval == bval:
                continue
            s += f"{key!r} is in both, but differs\n"
            s += bold_str_diff(aval, bval, sm=sm) + "\n"
        return s

    def _env_in_one_diff(self, x, y, color, xid, xenv):
        only_x = sorted(x - y)
        if len(only_x) == 0:
            return ""
        if self.verbose:
            xstr = ",\n".join([f"    {key!r}: {xenv[key]!r}" for key in only_x])
            xstr = "\n" + xstr
        else:
            xstr = ", ".join([f"{key!r}" for key in only_x])
        in_x = "These vars are only in {color}{xid}{reset}: {{{xstr}}}\n\n"
        return in_x.format(xid=xid, color=color, reset=COLORS.RESET, xstr=xstr)

    def envdiff(self):
        """Computes the difference between the environments."""
        if (not self.a.get("env")) or (not self.b.get("env")):
            return ""
        aenv = self.a["env"].load()
        benv = self.b["env"].load()
        akeys = frozenset(aenv)
        bkeys = frozenset(benv)
        in_both = akeys & bkeys
        if len(in_both) == len(akeys) == len(bkeys):
            keydiff = self._env_both_diff(in_both, aenv, benv)
            if len(keydiff) == 0:
                return ""
            in_a = in_b = ""
        else:
            keydiff = self._env_both_diff(in_both, aenv, benv)
            in_a = self._env_in_one_diff(
                akeys, bkeys, COLORS.RED, self.a["sessionid"], aenv
            )
            in_b = self._env_in_one_diff(
                bkeys, akeys, COLORS.GREEN, self.b["sessionid"], benv
            )
        s = "Environment\n-----------\n" + in_a + keydiff + in_b
        return s

    def _cmd_in_one_diff(self, inp, i, xlj, xid, color):
        s = "cmd #{i} only in {color}{xid}{reset}:\n"
        s = s.format(i=i, color=color, xid=xid, reset=COLORS.RESET)
        lines = inp.splitlines()
        lt = "{color}{pre}{reset} {line}\n"
        s += lt.format(color=color, reset=COLORS.RESET, line=lines[0], pre=">>>")
        for line in lines[1:]:
            s += lt.format(color=color, reset=COLORS.RESET, line=line, pre="...")
        if not self.verbose:
            return s + "\n"
        out = xlj["cmds"][0].get("out", "Note: no output stored")
        s += out.rstrip() + "\n\n"
        return s

    def _cmd_out_and_rtn_diff(self, i, j):
        s = ""
        aout = self.a["cmds"][i].get("out", None)
        bout = self.b["cmds"][j].get("out", None)
        if aout is None and bout is None:
            # s += 'Note: neither output stored\n'
            pass
        elif bout is None:
            aid = self.a["sessionid"]
            s += f"Note: only {COLORS.RED}{aid}{COLORS.RESET} output stored\n"
        elif aout is None:
            bid = self.b["sessionid"]
            s += f"Note: only {COLORS.GREEN}{bid}{COLORS.RESET} output stored\n"
        elif aout != bout:
            s += "Outputs differ\n"
            s += highlighted_ndiff(aout.splitlines(), bout.splitlines())
        else:
            pass
        artn = self.a["cmds"][i]["rtn"]
        brtn = self.b["cmds"][j]["rtn"]
        if artn != brtn:
            s += f"Return vals {COLORS.RED}{artn}{COLORS.RESET} & {COLORS.GREEN}{brtn}{COLORS.RESET} differ\n"
        return s

    def _cmd_replace_diff(self, i, ainp, aid, j, binp, bid):
        s = (
            "cmd #{i} in {red}{aid}{reset} is replaced by \n"
            "cmd #{j} in {green}{bid}{reset}:\n"
        )
        s = s.format(
            i=i,
            aid=aid,
            j=j,
            bid=bid,
            red=COLORS.RED,
            green=COLORS.GREEN,
            reset=COLORS.RESET,
        )
        s += highlighted_ndiff(ainp.splitlines(), binp.splitlines())
        if not self.verbose:
            return s + "\n"
        s += self._cmd_out_and_rtn_diff(i, j)
        return s + "\n"

    def cmdsdiff(self):
        """Computes the difference of the commands themselves."""
        aid = self.a["sessionid"]
        bid = self.b["sessionid"]
        ainps = [c["inp"] for c in self.a["cmds"]]
        binps = [c["inp"] for c in self.b["cmds"]]
        sm = self.sm
        sm.set_seqs(ainps, binps)
        s = ""
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == REPLACE_S:
                zipper = itertools.zip_longest
                for i, ainp, j, binp in zipper(
                    range(i1, i2), ainps[i1:i2], range(j1, j2), binps[j1:j2]
                ):
                    if j is None:
                        s += self._cmd_in_one_diff(ainp, i, self.a, aid, COLORS.RED)
                    elif i is None:
                        s += self._cmd_in_one_diff(binp, j, self.b, bid, COLORS.GREEN)
                    else:
                        self._cmd_replace_diff(i, ainp, aid, j, binp, bid)
            elif tag == DELETE_S:
                for i, inp in enumerate(ainps[i1:i2], i1):
                    s += self._cmd_in_one_diff(inp, i, self.a, aid, COLORS.RED)
            elif tag == INSERT_S:
                for j, inp in enumerate(binps[j1:j2], j1):
                    s += self._cmd_in_one_diff(inp, j, self.b, bid, COLORS.GREEN)
            elif tag == EQUAL_S:
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    odiff = self._cmd_out_and_rtn_diff(i, j)
                    if len(odiff) > 0:
                        h = (
                            "cmd #{i} in {red}{aid}{reset} input is the same as \n"
                            "cmd #{j} in {green}{bid}{reset}, but output differs:\n"
                        )
                        s += h.format(
                            i=i,
                            aid=aid,
                            j=j,
                            bid=bid,
                            red=COLORS.RED,
                            green=COLORS.GREEN,
                            reset=COLORS.RESET,
                        )
                        s += odiff + "\n"
            else:
                raise RuntimeError("tag not understood")
        if len(s) == 0:
            return s
        return "Commands\n--------\n" + s

    def format(self):
        """Formats the difference between the two history files."""
        s = self.header()
        ed = self.envdiff()
        if len(ed) > 0:
            s += "\n\n" + ed
        cd = self.cmdsdiff()
        if len(cd) > 0:
            s += "\n\n" + cd
        return s.rstrip()
