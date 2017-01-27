#!/usr/bin/python

import sys
import hive
import argparse
import xml.etree.ElementTree as ElementTree

parser = argparse.ArgumentParser(description="Hive Command-Line Interpreter")
parser.add_argument('program')
parser.add_argument('--list',action='store_true')
parser.add_argument('--plan',nargs='?')
parser.add_argument('--pursue',nargs='?')
parser.add_argument('--verbose','-v',action='count')
parser.add_argument('--narrate','-n',action='count')
tup = parser.parse_known_args()
solverArgs = tup[0]
if solverArgs.verbose > 0:
    print 'Reading program from '+solverArgs.program
xmlDoc = ElementTree.parse(solverArgs.program,parser=hive.LineNumberingParser(solverArgs.program))

if(solverArgs.list):
    goalProtos = xmlDoc.findall('goalProto')
    for goalProto in goalProtos:
        print 'goalProto: '+goalProto.get('name')


topGoal = None
if(solverArgs.plan or solverArgs.pursue):
    goalName = ''
    if(solverArgs.plan):
        goalName = solverArgs.plan
    elif(solverArgs.pursue):
        goalName = solverArgs.pursue

    solver = hive.Solver(xmlDoc,solverArgs,tup[1])

    solver.initialize()
    topGoal = solver.addTopGoalByName(goalName)
    solver.solve()
#    solver.terminate()

if solverArgs.verbose > 0:
    print 'Done'

sys.exit(0 if topGoal == None or not topGoal.hasErrors() else 1)

