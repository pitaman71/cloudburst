#!/usr/bin/python

import sys
import hive
import argparse
import xml.etree.ElementTree as ElementTree

parser = argparse.ArgumentParser(description="Hive Command-Line Interpreter")
parser.add_argument('program',nargs='+')
parser.add_argument('--list',action='store_true')
parser.add_argument('--plan',nargs='?')
parser.add_argument('--pursue',nargs='?')
parser.add_argument('--verbose','-v',action='count')
parser.add_argument('--narrate','-n',action='count')
tup = parser.parse_known_args()
solverArgs = tup[0]

solver = hive.Solver(solverArgs,tup[1])

solver.readFile('~/.hive/private.xml',False)
for programFile in solverArgs.program:
    solver.readFile(programFile)

if(solverArgs.list):
    goalProtos = solver.getDefinitions('goalProto')
    for goalProto in goalProtos:
        print 'goalProto: '+goalProto.get('name')


topGoal = None
if(solverArgs.plan or solverArgs.pursue):
    goalName = ''
    if(solverArgs.plan):
        goalName = solverArgs.plan
    elif(solverArgs.pursue):
        goalName = solverArgs.pursue


    solver.initialize()
    topGoal = solver.addTopGoalByName(goalName)
    solver.solve()
#    solver.terminate()

if topGoal != None and not topGoal.isSuccess():
    for error in topGoal.errors:
        print 'ERROR: '+error
elif solverArgs.verbose > 0:
    print 'GOAL COMPLETED SUCCESSFULLY'

sys.exit(0 if topGoal == None or not topGoal.hasErrors() else 1)

