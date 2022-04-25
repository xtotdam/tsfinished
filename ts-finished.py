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


def parse_input(jobid, error, outfile, command):
    # queue length
    try:
        jobs_queued = sp.check_output([C['TS'], '-l'], timeout=5).decode('utf-8').count('queued')
    except sp.TimeoutExpired:
        logging.error('Timeout expired trying to get number of queued jobs')


    # job info
    try:
        ji = sp.check_output([C['TS'], '-i', jobid]).decode('utf-8').split('\n')
    except sp.TimeoutExpired:
        logging.error('Timeout expired trying to get job information')
    ji = list(filter(bool, ji))

    ### JI:
    # 0 'Environment:'
    # 1 TS_ENV
    # 2 exit status     argv[1]
    # 3 command         argv[3]
    # 4 slots
    # 5 enqueue time
    # 6 start time
    # 7 end time
    # 8 running time

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
        jobs_queued=jobs_queued, cwd=cwd, command=command, hostname=os.uname()[1],
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
    parser.add_argument('jobid', type=str)
    parser.add_argument('error', type=str)
    parser.add_argument('outfile', type=str)
    parser.add_argument('command', type=str)
    args = parser.parse_args()

    C = json.load(open('settings.json', 'r'))

    if args.dry_run:
        send_gmail(C['gmail'], 'subject', 'message')
        exit()

    logging.debug(sys.version)
    logging.debug(str(sys.argv))
    logging.debug(args)

    subject, message = parse_input(args.jobid, args.error, args.outfile, args.command)
    logging.info(subject)
    logging.info(message)

    send_gmail(C['gmail'], subject, message)
