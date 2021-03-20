#!/usr/bin/python3

import os, sys
import subprocess as sp
from datetime import timedelta
from pathlib import Path

from config import Config as C

sys.stderr = open('err.log', 'w')
sys.stdout = open('out.log', 'w')

jobid, error, outfile, command = sys.argv[1:]

# queue length
jobs_queued = sp.check_output([C.TS, '-l']).decode('utf-8').count('queued')

# job info
ji = sp.check_output([C.TS, '-i', jobid]).decode('utf-8').split('\n')
ji = list(filter(bool, ji))

cwd = ji[1]

# human readable time
time = ji[-1].split(': ')[-1][:-1]
ji[-1] = ji[-1] + '  ({})'.format(str(timedelta(seconds=float(time))))


def transform_range_or_pass(s):
    only_digits = s.replace(' ', '').isdecimal()
    two_or_more = len(s.split()) >= 2
    if not (only_digits and two_or_more):
        return s
    else:
        try:
            parts = list(map(int, s.split()))
        except:
            return s

        diffs = set([t - s for s, t in zip(parts, parts[1:])])
        if len(diffs) == 1:
            diff = list(diffs)[0]
            if diff == 1:
                return '{{{}..{}}}'.format(parts[0], parts[-1])
            else:
                return '{{{}..{}..{}}}'.format(parts[0], parts[-1], diff)
        else:
            return s


cparts = command.split(':::')
for i in range(len(cparts)):
    cparts[i] = transform_range_or_pass(cparts[i].strip())
command = ' ::: '.join(cparts)

ji = '\n'.join(ji[3:])

output = '''\
-------------------------------
[TS] finished job {jobid}

Exit status: {error}
{ji}
{jobs_queued} job{s} left

CWD: {cwd}
{command}
-------------------------------
'''.format(jobid=jobid, error=error, ji=ji.strip(),
    jobs_queued=jobs_queued, cwd=cwd, command=command,
    s='s' if jobs_queued != 1 else '')

print(output)



p = sp.Popen([
    'python', 'matrix-nio-send/matrix-nio-send.py',
    '-t', 'matrix-nio-send' + os.sep + C.credentials,
    ],
    stdout=sp.PIPE, stdin=sp.PIPE, stderr=sp.STDOUT)

p.communicate(input=output.encode('utf-8'))
