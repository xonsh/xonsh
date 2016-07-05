

assert 1 + 1 == 2


$USER = 'snail'

x = 'USER'
assert x in ${...}
assert ${'U' + 'SER'} == 'snail'


echo "Yoo hoo"
$(echo $USER)

x = 'xonsh'
y = 'party'
out = $(echo @(x + ' ' + y))
assert out == 'xonsh party\n'
