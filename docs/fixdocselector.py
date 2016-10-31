import os
import jinja2

from collections import namedtuple, defaultdict


env = jinja2.Environment()
fsl = jinja2.DictLoader({"customsidebar.html":
"""
{# need this comment line to be sure versionsselector is on its own line #}
<!--versionselector-->
{% if versions|length > 1 %}
    <div role="note" aria-label="source link">
        <h3>Versions</h3>
        <ul class="this-page-menu">
            {%- for k,v in versions.items() %}
            <li><a href="{{baseurl}}/{{k}}/{{v}}" rel="nofollow">{{version_names[k] if k in version_names else k}}</a></li>
            {%- endfor %}
        </ul>
    </div>
{%- endif %}
<!--versionselector-end-->
"""})
#fsl = jinja2.FileSystemLoader('_templates_overwrite')
tpl = fsl.load(env, 'customsidebar.html')

Info = namedtuple('Info', ('version', 'path'))

def get_info(path):
    """
    For a give path, extract the version, and the relative-url for the documentation.
    """
    _path, file = os.path.split(path)
    dirs = _path.split(os.sep)
    version,*rest = dirs
    return Info(version, '/'.join((*rest,file)))


def gather(paths):
    """
    Given a list of path, gather information into a mapping.
    """
    results = defaultdict(lambda: [])
    for p in paths:
        current = get_info(p)
        results[current.path].append(current.version)
        
    return results


def get_versions(existings):
    """
    Given gathered path, get all existing versions.
    """
    versions = set()
    for k,v in existings.items():
        versions = versions.union(v)
    return versions


def make_links(existings, versions):
    """
    With the maping file-url<->existing-version create a mapping
    file-url<-> Other-Url if exist, other url is replaced by index.html
    if said page does not exits.
    """
    links = defaultdict(lambda:{})
    for k,ve in existings.items():
        for v in versions:
            if v in ve:
                links[k][v]= '/'.join((v,k))
            else:
                links[k][v]= '/'.join((v,'index.html'))
                print('page', k , 'does not exist in version', v, 'and will link to the index')
    return links
    
    

def _patch(lines, versions=None, baseurl='http://xon.sh', version_names=None):
    version_names = version_names or {}
    for l in lines:
        if l.strip() == '<!--versionselector-->':
            yield l
            while l.strip() != '<!--versionselector-end-->':
                l = next(lines)
            yield from tpl.render(versions=versions, baseurl=baseurl, version_names=version_names).splitlines()
        else:
            yield l
            

def patchfile(path, links, version_names=None):
    with open(path) as f:
        data= f.read()
    if '<!--versionselector-->' not in data:
        return
    
    lines = data.splitlines()
    
    new_lines = list(_patch(iter(lines), versions=links, version_names=version_names))
    
    with open(path,'w') as f:
        f.write('\n'.join(new_lines))

