def test_simple():
  assert 1 + 1 == 2


def test_envionment():
  $USER = 'snail'
  x = 'USER'
  assert x in ${...}
  assert ${'U' + 'SER'} == 'snail'


def test_xonsh_party():
  from xonsh.built_ins import XS
  orig = XS.env.get('XONSH_INTERACTIVE')
  XS.env['XONSH_INTERACTIVE'] = False
  try:
      x = 'xonsh'
      y = 'party'
      out = $(echo @(x + '-' + y)).strip()
      assert out == 'xonsh-party', 'Out really was <' + out + '>, sorry.'
  finally:
      XS.env['XONSH_INTERACTIVE'] = orig
