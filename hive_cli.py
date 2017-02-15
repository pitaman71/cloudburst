#!/usr/bin/python

import sys
import hive
import argparse
import xml.etree.ElementTree as ElementTree

parser = argparse.ArgumentParser(description="Hive Command-Line Interpreter")
parser.add_argument('program',nargs='+')
parser.add_argument('--list',action='store_true',help='List all Hive definitions')
parser.add_argument('--plan',nargs='?',help='Compute a plan of action that would be taken to execute a goal without actually running it (dry run).')
parser.add_argument('--execute',nargs='?',help='Execute a goal')
parser.add_argument('--verbose','-v',action='count',help='Add an extremely detailed debug trace to stdout')
parser.add_argument('--narrate','-n',action='count',help='Print narrative (concise, easy-to-read, single-line) comments that describe the goals being executed and progress toward completing each')
parser.add_argument('--goals','-g',action='count',help='Print single-line comments that describe the goals being executed including how they are configured')
parser.add_argument('--echo','-e',action='count',help='Echo external commands (e.g. embedded code in shell, python) before and after execution')
parser.add_argument('--lines','-l',action='count',help='Print hive program line numbers with all trace messages')
parser.add_argument('--initial','-i',action='count',help='Print initial state of hive agency after loading programs')
parser.add_argument('--final','-f',action='count',help='Print final state of hive agency after executing/solving goals')
tup = parser.parse_known_args()
solverArgs = tup[0]

solver = hive.Solver()
solver.parseArgs(solverArgs,tup[1])

solver.readFile('~/.hive/private.xml',False)
for programFile in solverArgs.program:
    solver.readFile(programFile)

if(solverArgs.list):
    tabulator = hive.Tabulator()
    goalProtos = solver.getDefinitions('goalProto')
    for goalProto in goalProtos:
        tabulator.addElement(goalProto)
    print tabulator.printText()

topGoal = None
if(solverArgs.plan or solverArgs.execute):
    goalName = ''
    if(solverArgs.plan):
        goalName = solverArgs.plan
    elif(solverArgs.execute):
        goalName = solverArgs.execute


    solver.initialize()
    agent = solver.beginAgent()

    topGoal = agent.addTopGoalByName(goalName)    
    agent.solve()
#    solver.terminate()
    solver.endAgent(agent)

if topGoal != None and not topGoal.isSuccess():
    for error in topGoal.errors:
        print 'ERROR: '+error
elif solverArgs.verbose > 0:
    print 'GOAL COMPLETED SUCCESSFULLY'

sys.exit(0 if topGoal == None or not topGoal.hasErrors() else 1)

