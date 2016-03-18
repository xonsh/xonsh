def pwd(args, stdin, stdout, stderr):
    print(__xonsh_env__['PWD'], file=stdout)
