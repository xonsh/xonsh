# I am a test module.
$ALIASES['echo'] = lambda args, stdin=None: print(' '.join(args))

$WAKKA = "jawaka"
x = $(echo "hello mom" $WAKKA)
