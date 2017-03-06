#!/usr/bin/python

import sys
import hive
import argparse
import xml.etree.ElementTree as ElementTree
import jsonpickle

parser = argparse.ArgumentParser(description="Hive Command-Line Interpreter")
parser.add_argument('program',nargs='*')
parser.add_argument('--list',action='store_true',help='List all Hive definitions')
parser.add_argument('--plan',nargs='?',help='Compute a plan of action that would be taken to execute a goal without actually running it (dry run).')
parser.add_argument('--pickle',nargs=2,help='Configure the goal and pickle the Agent state (for testing)')
parser.add_argument('--unpickle',nargs=1,help='Unpickle the Agent state (for testing)')
parser.add_argument('--execute',nargs='?',help='Execute a goal')
parser.add_argument('--start',nargs='?',help='Start an Agent')
parser.add_argument('--event',nargs='?',help='Send an event to an Agent')
parser.add_argument('--agent',nargs='?',help='Name of Agent')
parser.add_argument('--kill',nargs='?',help='Terminate an Agent')
parser.add_argument('--inspect',nargs='?',help='Inspect any Agency state by URL')
parser.add_argument('--verbose','-v',action='count',help='Add an extremely detailed debug trace to stdout')
parser.add_argument('--narrate','-n',action='count',help='Print narrative (concise, easy-to-read, single-line) comments that describe the goals being executed and progress toward completing each')
parser.add_argument('--goals','-g',action='count',help='Print single-line comments that describe the goals being executed including how they are configured')
parser.add_argument('--echo','-e',action='count',help='Echo external commands (e.g. embedded code in shell, python) before and after execution')
parser.add_argument('--lines','-l',action='count',help='Print hive program line numbers with all trace messages')
parser.add_argument('--initial','-i',action='count',help='Print initial state of hive agency after loading programs')
parser.add_argument('--final','-f',action='count',help='Print final state of hive agency after executing/solving goals')
tup = parser.parse_known_args()
solverArgs = tup[0]

if solverArgs.unpickle:
    ifp = open(solverArgs.unpickle[0],'rt')
    solver = jsonpickle.decode(ifp.read())
    solverArgs.unpickle = None
    solverArgs.plan = solver.args.pickle[0]
    solver.parseArgs(solverArgs,tup[1])
else:
    solver = hive.Agency()
    solver.parseArgs(solverArgs,tup[1])

solver.start()
solver.initialize()

if(solverArgs.list):
    tabulator = hive.Tabulator()
    goalProtos = solver.getDefinitions('goalProto')
    for goalProto in goalProtos:
        tabulator.addElement(goalProto)
    print tabulator.printText()

success = False

if solverArgs.start:
    agent = solver.beginAgent()
    agent.loadProgram(solverArgs.start)
    path1 = []
    path2 = []
    solver.getDefnPath(path1)
    agent.getDefnPath(path2)
    path2 = path2[len(path1):]
    print 'Started agent %s' % '/'.join(path2)
    success = True
elif solverArgs.event:
    if solverArgs.agent == None:
        raise RuntimeError('--agent <name> must also be provided when using --event')
    agent = solver.locateAgent(solverArgs.agent)
    if agent == None:
        raise RuntimeError('Unable to locate agent named %s' % solverArgs.agent)
    goal = agent.doEvent(solverArgs.event)
    success = not goal.hasErrors()
elif solverArgs.kill:
    agent = solver.locateAgent(solverArgs.kill)
    if agent == None:
        raise RuntimeError('Unable to locate agent named %s' % solverArgs.kill)
    solver.endAgent(agent)
    success = True
elif solverArgs.inspect:
    path = []
    solver.getDefnPath(path)
    for segment in solverArgs.inspect.split('/'):
        path.append(segment)
    target = solver.lookupAbsPath(path)
    if target == None:
        print 'Cannot identify state with path %s' % solverArgs.inspect
        success = False
    else:
        tabulator = hive.Tabulator()
        tabulator.add(target)
        print tabulator.printText()
        success = True
elif solverArgs.pickle or solverArgs.unpickle or solverArgs.plan or solverArgs.execute:
    topGoal = None
    goalName = ''
    if(solverArgs.plan):
        goalName = solverArgs.plan
    elif(solverArgs.pickle):
        goalName = solverArgs.pickle[0]
    elif(solverArgs.execute):
        goalName = solverArgs.execute

    agent = solver.beginAgent()

    if solverArgs.pickle or solverArgs.plan or solverArgs.execute:
        topGoal = agent.addTopGoalByName(goalName)    

    if solverArgs.plan or solverArgs.execute:
        agent.solve()
    elif solverArgs.pickle:
        ofp = open(solverArgs.pickle[1],'wt')
        ofp.write(jsonpickle.encode(solver))
        ofp.close()

#    solver.terminate()
    solver.endAgent(agent)

    if topGoal != None and not topGoal.isSuccess():
        for error in topGoal.errors:
            print 'ERROR: '+error
    elif solverArgs.verbose > 0:
        print 'GOAL COMPLETED SUCCESSFULLY'
    if topGoal == None or not topGoal.hasErrors():
        success = True

solver.finish()

sys.exit(0 if success else 1)

