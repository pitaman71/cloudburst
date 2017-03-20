#!/usr/bin/python

import os
import sys
import pexpect
import glob

commandIndex = 0

def run(command):
    global commandIndex
    print 'INVOKE: %s' % command
    (out,rc) = pexpect.run(command,withexitstatus=1,timeout=None,logfile=sys.stdout)
    pexpect.run('cp /Users/pitaman/hiveData/agency.json /Users/pitaman/hiveData/agency.json.%d' % commandIndex)
    if rc != 0:
        raise RuntimeError('Nonzero return code %d: %s' % (rc,command))
    commandIndex += 1

hiveHome = '/Volumes/Sandbox/hive'
if 'HIVE_HOME' in os.environ:
    hiveHome = os.environ['HIVE_HOME']

# hive test #1
run('rm -f %s' % ' '.join(glob.glob('/Users/pitaman/hiveData/*')))
run('%s/hive_cli.py load %s/cassandraExperiment.xml' % (hiveHome,hiveHome))
run('%s/hive_cli.py launch jgdemo1 JanusGraphClusterDemo agent.clusterName=jgdemo1 agent.ec2Creds=AlanExperoOnEC2 agent.config=JanusGraphClusterDemo' % hiveHome)
run('%s/hive_cli.py -n execute jgdemo1 setup' % hiveHome)
run('%s/hive_cli.py -n inspect jgdemo1' % hiveHome)
run('%s/hive_cli.py -n execute jgdemo1 start' % hiveHome)
