#!/usr/bin/python

import json
import sys
import os
import time
import cloudburst
import argparse
import inspect
import traceback
import socket
import xml.etree.ElementTree as ElementTree

from flask import Flask, Response, request
from flask import send_from_directory


solver = cloudburst.Agency()

parser = argparse.ArgumentParser(description="Cloudburst Command-Line Interpreter")
parser.add_argument('program',nargs='+')
parser.add_argument('--daemon',action='store_true',help='Run HTTPD Daemon')
parser.add_argument('--list',action='store_true',help='List all Cloudburst definitions')
parser.add_argument('--plan',nargs='?',help='Compute a plan of action that would be taken to execute a goal without actually running it (dry run).')
parser.add_argument('--pickle',nargs=2,help='Configure the goal and pickle the Agent state (for testing)')
parser.add_argument('--unpickle',nargs=1,help='Unpickle the Agent state (for testing)')
parser.add_argument('--execute',nargs='?',help='Execute a goal')
parser.add_argument('--verbose','-v',action='count',help='Add an extremely detailed debug trace to stdout')
parser.add_argument('--narrate','-n',action='count',help='Print narrative (concise, easy-to-read, single-line) comments that describe the goals being executed and progress toward completing each')
parser.add_argument('--goals','-g',action='count',help='Print single-line comments that describe the goals being executed including how they are configured')
parser.add_argument('--echo','-e',action='count',help='Echo external commands (e.g. embedded code in shell, python) before and after execution')
parser.add_argument('--lines','-l',action='count',help='Print cloudburst program line numbers with all trace messages')
parser.add_argument('--initial','-i',action='count',help='Print initial state of cloudburst agency after loading programs')
parser.add_argument('--final','-f',action='count',help='Print final state of cloudburst agency after executing/solving goals')
parser.parse_args('--daemon')
tup = parser.parse_known_args()
solverArgs = tup[0]

solver.parseArgs(solverArgs,tup[1])
agent = None

solver.start()

service = cloudburst.Service(solver)

app = Flask(__name__, static_url_path='%s/cloudburst' % os.path.dirname(sys.argv[0]), static_folder='public')

@app.route('/api/<commandName>', methods=['GET','POST'])
def command_handler(commandName):
    reqData = None
    if request.data != None and request.data != '':
        unpickler = cloudburst.Shipper(solver)
        rep = json.loads(request.data)
        unpickler.debugFile = sys.stderr
        reqData = unpickler.unpack(rep)
        print 'DEBUG: BEGIN request %s' % type(reqData)
        print request.data
        print 'DEBUG: END   request'


    result = getattr(service,commandName).__call__(agent,reqData)
    respData = None
    if result != None:
        pickler = cloudburst.Shipper(solver)
        pickler.debugFile = sys.stderr
        pickler.addValue(result)
        pickler.prepack()
        respData = json.dumps(pickler.packValues())
    print 'DEBUG: BEGIN response %s' % (type(respData))
    print respData
    print 'DEBUG: END   response'
    return Response(
        respData,
        mimetype='application/json',
        headers={
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*'
        }
    )

if __name__ == '__main__':
    agent = solver.beginAgent()
    app.run(port=int(os.environ.get("PORT", 3000)), debug=True)
    solver.endAgent(agent)
