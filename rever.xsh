$PROJECT = $GITHUB_ORG = $GITHUB_REPO = 'xonsh'
$WEBSITE_URL = 'http://xon.sh'
$ACTIVITIES = ['version_bump', 'changelog', 'pytest',
               'sphinx', #'tag', 'pypi', 'conda_forge', 'ghpages', 'ghrelease'
               ]

$VERSION_BUMP_PATTERNS = [
    ('.appveyor.yml', 'version:.*', 'version: $VERSION.{build}'),
    ('xonsh/__init__.py', '__version__\s*=.*', "__version__ = '$VERSION'"),
    ]
$CHANGELOG_FILENAME = 'CHANGELOG.rst'
$CHANGELOG_TEMPLATE = 'TEMPLATE.rst'
$TAG_REMOTE = 'git@github.com:xonsh/xonsh.git'
$TAG_TARGET = 'master'

$GHPAGES_REPO = 'git@github.com:scopatz/xonsh-docs.git'

with open('requirements-tests.txt') as f:
    $DOCKER_CONDA_DEPS = f.read().split()
with open('requirements-docs.txt') as f:
    $DOCKER_CONDA_DEPS += f.read().split()
$DOCKER_CONDA_DEPS = [d.lower() for d in set($DOCKER_CONDA_DEPS)]
$DOCKER_INSTALL_COMMAND = './setup.py install'
$DOCKER_GIT_NAME = 'xonsh'
$DOCKER_GIT_EMAIL = 'xonsh@googlegroups.com'
