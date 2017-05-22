#!/usr/bin/python

import os
import sys
import pexpect
import glob
import argparse

parser = argparse.ArgumentParser(description="Cloudburst test #1")
parser.add_argument('--clean',default=False,action='store_true')
parser.add_argument('--cloudburstHome',default=os.environ['CLOUDBURST_HOME'] if 'CLOUDBURST_HOME' in os.environ else os.path.dirname(sys.argv[0]))
argObj = parser.parse_args()

commandIndex = 0

def run(command):
    global commandIndex
    print 'INVOKE: %s' % command
    (out,rc) = pexpect.run(command,withexitstatus=1,timeout=None)
    pexpect.run('cp %s/.cloudburst/data/agency.json %s/.cloudburst/data/agency.json.%d' % (os.environ['HOME'],os.environ['HOME'],commandIndex))
    print out
    if rc != 0:
        raise RuntimeError('Nonzero return code %d: %s' % (rc,command))
    commandIndex += 1

# cloudburst test #1
if argObj.clean:
    for item in glob.glob('%s/.cloudburst/data/*' % os.environ['HOME']):
        run('rm -f %s' % item)
run('%s/cli.py load %s/cassandraExperiment.xml' % (argObj.cloudburstHome,argObj.cloudburstHome))
run('%s/cli.py launch test1 helloWorld' % argObj.cloudburstHome)
run('%s/cli.py inspect agentByName' % argObj.cloudburstHome)
run('%s/cli.py launch test2 helloWorld' % argObj.cloudburstHome)
run('%s/cli.py inspect test1' % argObj.cloudburstHome)
run('%s/cli.py inspect agentByName' % argObj.cloudburstHome)
run('%s/cli.py kill test2' % argObj.cloudburstHome)
run('%s/cli.py inspect test1' % argObj.cloudburstHome)
run('%s/cli.py inspect agentByName' % argObj.cloudburstHome)
run('%s/cli.py execute test1 start' % argObj.cloudburstHome)
run('%s/cli.py inspect test1' % argObj.cloudburstHome)
run('%s/cli.py plan test1 printFile' % argObj.cloudburstHome)
run('%s/cli.py execute test1 printFile' % argObj.cloudburstHome)
run('%s/cli.py inspect test1' % argObj.cloudburstHome)
run('%s/cli.py execute test1 printFile' % argObj.cloudburstHome)
run('%s/cli.py inspect test1' % argObj.cloudburstHome)
run('%s/cli.py execute test1 increment' % argObj.cloudburstHome)
run('%s/cli.py inspect test1' % argObj.cloudburstHome)
run('%s/cli.py execute test1 increment' % argObj.cloudburstHome)
run('%s/cli.py inspect test1' % argObj.cloudburstHome)

