#!/usr/bin/python

import sys
import cloudburst
import argparse
import xml.etree.ElementTree as ElementTree
import jsonpickle

parser = argparse.ArgumentParser(description="Cloudburst Command-Line Interpreter")
parser.add_argument('--verbose','-v',nargs=1,help='Add an extremely detailed debug trace to stdout')
parser.add_argument('--narrate','-n',action='count',help='Print narrative (concise, easy-to-read, single-line) comments that describe the goals being executed and progress toward completing each')
parser.add_argument('--goals','-g',action='count',help='Print single-line comments that describe the goals being executed including how they are configured')
parser.add_argument('--echo','-e',action='count',help='Echo external commands (e.g. embedded code in shell, python) before and after execution')
parser.add_argument('--lines','-l',action='count',help='Print cloudburst program line numbers with all trace messages')
parser.add_argument('--initial','-i',action='count',help='Print initial state of cloudburst agency after loading programs')
parser.add_argument('--final','-f',action='count',help='Print final state of cloudburst agency after executing/solving goals')
subparsers = parser.add_subparsers(dest='subcommand')

loadCmd = subparsers.add_parser('load',help='Load Cloudburst definitions from file')
loadCmd.add_argument('program',help='file containing a Cloudburst program')

listCmd = subparsers.add_parser('list',help='List all Cloudburst definitions')

inspectCmd = subparsers.add_parser('inspect',help='Inspect agency state')
inspectCmd.add_argument('path',help='path to any agency state object')

planCmd = subparsers.add_parser('plan',help='Compute a plan of action that would be taken to execute a goal without actually running it (dry run).')
planCmd.add_argument('agent',help='Name of the agent itself')
planCmd.add_argument('goal',help='name of the goal to be executed')

executeCmd = subparsers.add_parser('execute',help='Execute a goal')
executeCmd.add_argument('agent',help='Name of the agent itself')
executeCmd.add_argument('goal',help='name of the goal to be executed')

launchCmd = subparsers.add_parser('launch',help='Start an Agent')
launchCmd.add_argument('agent',help='Name of the agent itself')
launchCmd.add_argument('program',help='Name of the <agent> program to launch')

eventCmd = subparsers.add_parser('event',help='Send an event to an Agent')
eventCmd.add_argument('agent',help='Name of the agent itself')
eventCmd.add_argument('event',help='Name of the <event> to execute')

killCmd = subparsers.add_parser('kill',help='Terminate an Agent')
killCmd.add_argument('agent',help='Name of the agent itself')

tup = parser.parse_known_args()
solverArgs = tup[0]

solver = cloudburst.Agency()
solver.parseArgs(solverArgs,tup[1])

solver.start()

success = False

if(solverArgs.subcommand == 'load'):
    solver.readFileXML(solverArgs.program)
    success = True

if(solverArgs.subcommand == 'list'):
    tabulator = cloudburst.Tabulator()
    goalProtos = solver.getDefinitions('goalProto')
    for goalProto in goalProtos:
        tabulator.addElement(goalProto)
    print tabulator.printText()
elif solverArgs.subcommand == 'launch':
    agent = solver.beginAgent()
    success = agent.loadProgram(solverArgs.program,solverArgs.agent)
    if success == True:
        path1 = []
        path2 = []
        solver.getDefnPath(path1)
        agent.getDefnPath(path2)
        path2 = path2[len(path1):]
        print 'Started agent %s' % '/'.join(path2)
    else:
        print success.printText()
        success = False
elif solverArgs.subcommand == 'event':
    agent = solver.locateAgent(solverArgs.agent)
    if agent == None:
        print 'Unable to locate agent named %s' % solverArgs.agent
    goal = agent.doEvent(solverArgs.event,True)
    success = not goal.hasErrors()
elif solverArgs.subcommand == 'kill':
    agent = solver.locateAgent(solverArgs.agent)
    if agent == None:
        print 'Unable to locate agent named %s' % solverArgs.agent
        success = False
    else:
        solver.endAgent(agent)
        success = True
elif solverArgs.subcommand == 'inspect':
    target = solver.locateAgent(solverArgs.path)
    if target == None:
        path = []
    #    solver.getDefnPath(path)
        for segment in solverArgs.path.split('/'):
            path.append(segment)
        target = solver.lookupPath(solverArgs.path)
    if target == None:
        print 'Cannot identify state with path %s' % solverArgs.path
        success = False
    else:
        print solver.inspect(target)
        success = True
elif solverArgs.subcommand == 'plan' or solverArgs.subcommand == 'execute':
    executeMode = solverArgs.subcommand == 'execute'
    agent = solver.locateAgent(solverArgs.agent)
    topGoal = agent.doEvent(solverArgs.goal,executeMode)
    if topGoal != None and not topGoal.isSuccess():
        for error in topGoal.errors:
            print 'ERROR: '+error
    elif solver.verboseMode(1):
        print 'GOAL COMPLETED SUCCESSFULLY'
    if topGoal == None or not topGoal.hasErrors():
        success = True
elif not success:
    print 'No command argument was provided'

solver.finish()

sys.exit(0 if success else 1)

