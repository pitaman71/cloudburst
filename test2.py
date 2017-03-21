#!/usr/bin/python

import os
import sys
import pexpect
import glob
import argparse

commandIndex = 0

parser = argparse.ArgumentParser(description="Hive Command-Line Interpreter")
parser.add_argument('--name',default='jgdemo1')
parser.add_argument('--clean',default=False,action='store_true')
parser.add_argument('--hiveHome',default=os.environ['HIVE_HOME'] if 'HIVE_HOME' in os.environ else '/Volumes/Sandbox/hive')
argObj = parser.parse_args()

args = dict()
args['name'] = argObj.name
args['hiveHome'] = argObj.hiveHome

def run(command):
    global commandIndex
    print 'INVOKE: %s' % command
    (out,rc) = pexpect.run(command,withexitstatus=1,timeout=None,logfile=sys.stdout)
    pexpect.run('cp /Users/pitaman/hiveData/agency.json /Users/pitaman/hiveData/agency.json.%d' % commandIndex)
    if rc != 0:
        raise RuntimeError('Nonzero return code %d: %s' % (rc,command))
    commandIndex += 1

# hive test #1
if argObj.clean:
    for item in glob.glob('/Users/pitaman/hiveData/*'):
        run('rm -f %s' % item)
run('%(hiveHome)s/hive_cli.py load %(hiveHome)s/cassandraExperiment.xml' % args)
run('%(hiveHome)s/hive_cli.py launch %(name)s JanusGraphClusterDemo agent.clusterName=%(name)s agent.ec2Creds=AlanExperoOnEC2 agent.config=JanusGraphClusterDemo' % args)
run('%(hiveHome)s/hive_cli.py -n execute %(name)s setup' % args)
run('%(hiveHome)s/hive_cli.py -n inspect %(name)s' % args)
run('%(hiveHome)s/hive_cli.py -n execute %(name)s start' % args)
