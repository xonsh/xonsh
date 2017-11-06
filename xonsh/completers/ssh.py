
import os
import subprocess

def get_host_list():
    '''
    Reads ~/.ssh/known_hosts and returns a list of hosts
    '''
    hosts_path = os.path.expanduser('~/.ssh/known_hosts')
    if not os.path.exists(hosts_path):
        return []
    with open(hosts_path, 'r') as hosts_file:
        host_list = []
        for line in hosts_file:
            line = line.split(' ')[0]
            if ',' in line:
                line = line.split(',')
                for item in line:
                    host_list.append(item.split(':')[0].strip('[').strip(']'))
            elif ':' in line:
                host_list.append(line.split(':')[0].strip('[').strip(']'))
            else:
                host_list.append(line)
        return host_list


def complete_ssh(prefix, line, begidx, endidx, ctx):
    '''
    Completes ssh hosts based on contents of ~/.ssh/known_hosts
    '''
    line_len = len(line.split())
    hosts = get_host_list()
    if ssh not in line:
        return
    if prefix in hosts:
        suggestions = [c for c in hosts if c.startswith(prefix)]
        return (suggestions, len(prefix))
    return hosts, len(prefix)

