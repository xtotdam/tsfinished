#!/usr/bin/python3

import os, sys
import subprocess as sp
from datetime import timedelta, datetime
from pprint import pformat
import logging
import json
import argparse

import smtplib
from email.message import EmailMessage


logging.basicConfig(
    format='%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s -- %(message)s',
    filename='tsfinished.log',
    level=logging.INFO
)


def transform_range_or_pass(s):
    '''
    transforms expanded ranges of numbers back into compressed representation
    e.g. 1 2 3 4 5 -> {1..5}
    on fail returns argument
    '''
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


def parse_input(argv):
    jobid, error, outfile, command = argv

    # queue length
    jobs_queued = sp.check_output([C['TS'], '-l']).decode('utf-8').count('queued')

    # job info
    ji = sp.check_output([C['TS'], '-i', jobid]).decode('utf-8').split('\n')
    ji = list(filter(bool, ji))

    ### JI:
    # 0 'Environment:'
    # 1 TS_ENV
    # 2 command         argv[3]
    # 3 slots
    # 4 enqueue time
    # 5 start time
    # 6 running time

    cwd = ji[1]

    # human readable time
    time = ji[-1].split(': ')[-1][:-1]
    ji[-1] = ji[-1] + '  ({})'.format(str(timedelta(seconds=float(time))))

    # compress ranges
    cparts = command.split(':::')
    for i in range(len(cparts)):
        cparts[i] = transform_range_or_pass(cparts[i].strip())
    command = ' ::: '.join(cparts)

    ji = '\n'.join(ji[3:])

    error_message = ''
    if error != '0':
        error_message = 'Error occured!'

    output = '''\
    Exit status: {error} {error_message}
    {ji}
    {jobs_queued} job{s} left

    Hostname: {hostname}
    CWD: {cwd}
    {command}
    '''.format(jobid=jobid, error=error, ji=ji.strip(), error_message=error_message,
        jobs_queued=jobs_queued, cwd=cwd, command=command, hostname=hostname,
        s='s' if jobs_queued != 1 else '')

    subject = '[TS] finished job {jobid} - {jobs_queued} left - {hostname}'.format(
        jobid=jobid, jobs_queued=jobs_queued, hostname=os.uname()[1])

    return subject, output


def send_gmail(creds, subject, message):
    msg = EmailMessage()

    msg['Subject'] = subject
    msg['From'] = creds['username']
    msg['To'] = creds['recipients']
    msg.set_content(message + '\n\n---\nSent by robot;)')

    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.ehlo()
    server.login(creds['username'], creds['password'])
    server.send_message(msg)
    server.quit()



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Task spooler notifoer')
    parser.add_argument('-n', '--dry-run', action='store_true', help='Send test letter') # true if passed
    args = parser.parse_args()

    C = json.load(open('settings.json', 'r'))

    if args.dry_run:
        send_gmail(C['gmail'], 'subject', 'message')
        exit()

    logging.debug(sys.version)
    logging.debug(str(sys.argv))

    subject, message = parse_input(sys.argv[1:])
    logging.info(subject)
    logging.info(message)

    send_gmail(C['gmail'], subject, message)
