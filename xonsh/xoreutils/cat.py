import os
import sys


def _cat_single_file(opts, fname, stdin, out, err):
    global line_count
    if fname == '-':
        f = stdin
    elif os.path.isdir(fname):
        print("cat: {}: Is a directory.".format(fname), file=err)
        return True
    elif not os.path.isfile(fname):
        print("cat: {}: No such file or directory.".format(fname), file=err)
        return True
    else:
        f = open(fname, 'rb')
        sep = os.linesep.encode()
        last_was_blank = False
        while True:
            _r = r = f.readline()
            if r == b'':
                break
            if r.endswith(sep):
                _r = _r[:-len(sep)]
            this_one_blank = _r == b''
            if last_was_blank and this_one_blank and opts['squeeze_blank']:
                continue
            last_was_blank = this_one_blank
            if (not this_one_blank) and opts['number']:
                _r = b"%6d %s" % (line_count, _r)
                line_count += 1
            if opts['show_ends']:
                _r = b'%s$' % _r
            try:
                print(_r.decode('unicode_escape'), flush=True, file=out)
            except:
                pass
        return False


def cat(args, stdin, stdout, stderr):
    global line_count
    opts = _parse_args(args)

    line_count = 1
    errors = False
    if len(args) == 0:
        args = ['-']
    for i in args:
        errors = _cat_single_file(opts, i, stdin, stdout, stderr) or errors

    return int(errors)


def _parse_args(args):
    out = {'number': False, 'squeeze_blank': False, 'show_ends': False}
    if '-b' in args:
        args.remove('-b')
        out['number'] = True
    if '-E' in args:
        args.remove('-E')
        out['show_ends'] = True
    if '-s' in args:
        args.remove('-s')
        out['squeeze_blank'] = True

    return out
