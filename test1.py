#!/usr/bin/python

import os
import sys
import pexpect
import glob

commandIndex = 0

def run(command):
    global commandIndex
    print 'INVOKE: %s' % command
    (out,rc) = pexpect.run(command,withexitstatus=1,timeout=None)
    pexpect.run('cp /Users/pitaman/hiveData/agency.json /Users/pitaman/hiveData/agency.json.%d' % commandIndex)
    print out
    if rc != 0:
        raise RuntimeError('Nonzero return code %d: %s' % (rc,command))
    commandIndex += 1

hiveHome = '/Volumes/Sandbox/hive'
if 'HIVE_HOME' in os.environ:
    hiveHome = os.environ['HIVE_HOME']

# hive test #1
run('rm -f %s' % ' '.join(glob.glob('/Users/pitaman/hiveData/agency.json*')))
run('%s/hive_cli.py load /Volumes/Sandbox/hive/cassandraExperiment.xml' % hiveHome)
run('%s/hive_cli.py launch test1 helloWorld' % hiveHome)
run('%s/hive_cli.py inspect agentByName' % hiveHome)
run('%s/hive_cli.py launch test2 helloWorld' % hiveHome)
run('%s/hive_cli.py inspect test1' % hiveHome)
run('%s/hive_cli.py inspect agentByName' % hiveHome)
run('%s/hive_cli.py kill test2' % hiveHome)
run('%s/hive_cli.py inspect test1' % hiveHome)
run('%s/hive_cli.py inspect agentByName' % hiveHome)
run('%s/hive_cli.py execute test1 start' % hiveHome)
run('%s/hive_cli.py inspect test1' % hiveHome)
run('%s/hive_cli.py plan test1 print' % hiveHome)
run('%s/hive_cli.py -v 2 execute test1 print' % hiveHome)
run('%s/hive_cli.py inspect test1' % hiveHome)
run('%s/hive_cli.py execute test1 print' % hiveHome)
run('%s/hive_cli.py inspect test1' % hiveHome)
run('%s/hive_cli.py execute test1 increment' % hiveHome)
run('%s/hive_cli.py inspect test1' % hiveHome)
run('%s/hive_cli.py execute test1 increment' % hiveHome)
run('%s/hive_cli.py inspect test1' % hiveHome)
#run('%s/hive_cli.py --inspect --agent test1 /Volumes/Sandbox/hive/cassandraExperiment.xml' % hiveHome)

