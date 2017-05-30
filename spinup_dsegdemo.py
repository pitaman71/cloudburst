#!/usr/bin/python

import os
import sys
import pexpect
import glob
import argparse

commandIndex = 0

scriptPath = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser(description="Cloudburst test #2")
parser.add_argument('--name',default='dsegdemo1')
parser.add_argument('--clean',default=False,action='store_true')
argObj = parser.parse_args()

args = dict()
args['name'] = argObj.name
args['cloudburstHome'] = scriptPath
args['extra'] = '-g'

def run(command):
    global commandIndex
    print 'INVOKE: %s' % command
    (out,rc) = pexpect.run(command,withexitstatus=1,timeout=None,logfile=sys.stdout)
    pexpect.run('cp %s/.cloudburst/data/agency.json %s/.cloudburst/data/agency.json.%d' % (os.environ['HOME'],os.environ['HOME'],commandIndex))
    if rc != 0:
        raise RuntimeError('Nonzero return code %d: %s' % (rc,command))
    commandIndex += 1

# cloudburst test #1
if argObj.clean:
    for item in glob.glob('%s/.cloudburst/data/*' % os.environ['HOME']):
        run('rm -f %s' % item)
run('%(cloudburstHome)s/cli.py load %(cloudburstHome)s/graphStacker.xml' % args)
run('%(cloudburstHome)s/cli.py launch %(name)s DSEGClusterDemo agent.clusterName=%(name)s agent.dseCreds=AlanDatastaxCredentials agent.githubCreds=AlanGithubCredentials agent.ec2Creds=AlanExperoOnEC2 agent.config=DSEGDemoClusterConfig' % args)
run('%(cloudburstHome)s/cli.py -n %(extra)s execute %(name)s setup' % args)
run('%(cloudburstHome)s/cli.py -n %(extra)s inspect %(name)s' % args)
run('%(cloudburstHome)s/cli.py -n -e %(extra)s execute %(name)s schema' % args)
run('%(cloudburstHome)s/cli.py -n %(extra)s execute %(name)s start' % args)
