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


    # get job info
    try:
        ji = sp.check_output([C['TS'], '-i', jobid]).decode('utf-8').split('\n')
    except sp.TimeoutExpired:
        logging.error('Timeout expired trying to get job information')
    ji = list(filter(bool, ji))

    ### JI:
    # 0 'Environment:'
    # 1 TS_ENV
    # 2 command         argv[3]
    # 3 slots
    # 4 enqueue time
    # 5 start time
    # 6 running time

    # parse job info
    cwd = ji[1]
    slots_required = ji[3].split(': ')[-1].strip()
    enqueue_time = ji[4].split(': ')[-1].strip()
    start_time = ji[5].split(': ')[-1].strip()
    running_time = ji[6].split(': ')[-1].strip()
    now_time = datetime.now().strftime("%a %b %d %H:%M:%S %Y")

    # human readable running time
    h_running_time = str(timedelta(seconds=float(running_time[:-1])))

    # compress ranges
    cparts = command.split(':::')
    for i in range(len(cparts)):
        cparts[i] = transform_range_or_pass(cparts[i].strip())
    command = ' ::: '.join(cparts)

    error_message = ''
    if error != '0':
        error_message = 'Error occured!'

    output = '''\
Enqueue time: {enqueue_time} ({slots_required} slots used)
Start time: {start_time}
Finish time: {now_time}
Running time: {running_time} ({h_running_time})
{jobs_queued} job{s} left

Exit status: {error} {error_message}

Hostname: {hostname}
CWD: {cwd}

{command}'''.format(error=error, error_message=error_message,
    jobs_queued=jobs_queued, s='s' if jobs_queued != 1 else '',
    enqueue_time=enqueue_time, slots_required=slots_required,
    start_time=start_time, now_time=now_time, running_time=running_time, h_running_time=h_running_time,
    cwd=cwd, command=command, hostname=os.uname()[1])

    subject = '[TS] finished job #{jobid} - {jobs_queued} left - {hostname}'.format(
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

    try:
        C = json.load(open('settings.json', 'r'))
    except FileNotFoundError:
        logging.error('settings.json not found!')
        exit()

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
