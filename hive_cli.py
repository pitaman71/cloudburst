#!/usr/bin/python

import sys
import os
import socket
import tempfile

sys.path.append('/usr/local/lib/python2.7/site-packages')

import pexpect
import copy
import xml.etree.ElementTree as ElementTree
import argparse
import jsonpickle
import re

class LineNumberingParser(ElementTree.XMLParser):
    def __init__(self,file_name):
        self._file_name = file_name
        ElementTree.XMLParser.__init__(self)

    def _start_list(self, *args, **kwargs):
        # Here we assume the default XML parser which is expat
        # and copy its element position attributes into output Elements
        element = super(self.__class__, self)._start_list(*args, **kwargs)
        element._file_name = self._file_name
        element._start_line_number = self.parser.CurrentLineNumber
        element._start_column_number = self.parser.CurrentColumnNumber
        element._start_byte_index = self.parser.CurrentByteIndex
        return element

    def _end(self, *args, **kwargs):
        element = super(self.__class__, self)._end(*args, **kwargs)
        element._file_name = self._file_name
        element._end_line_number = self.parser.CurrentLineNumber
        element._end_column_number = self.parser.CurrentColumnNumber
        element._end_byte_index = self.parser.CurrentByteIndex
        return element

def defaultEvalContext():
    result = dict()
    result['node'] = dict()
    result['node']['platform'] = sys.platform
    result['node']['uname'] = os.uname()
    result['node']['hostname'] = socket.gethostname()
    result['node']['hostip'] = socket.gethostbyname(socket.gethostname())
    return result

class Solver:
    def __init__(self):
        self.goals = []
        self.result = True

    def hasGoal(self,goal):
        goals = [x for x in self.goals if goal.subsumedBy(x)]
        return len(goals)>0

    def addTopGoalByName(self,goalName,args):
        goal = Goal()
        goal.name = goalName
        goal.cfgTopGoal(args)
        if not self.hasGoal(goal):            
            self.addGoal(goal)

    def addGoal(self,goal):
        self.goals.append(goal)

    def solve(self):
        for goal in self.goals:
            goal.pursue(self)

    def reportError(self,errMsg):
        print 'ERROR: '+errMsg
        self.result = False

class EvalResult:
    def __init__(self,context,xmlExpr):
        self.context=context
        self.errors = []
        self.expr=xmlExpr

    def setValue(self,value):
        self.value = value

    def addError(self,error):
        self.errors.append(error)

    def createError(self,error):
        errMsg = '%s:%d.%d: %s' % (self.expr._file_name,self.expr._start_line_number,self.expr._start_column_number,error)
        self.errors.append(errMsg)

    def isSuccess(self):
        return len(self.errors) == 0

    def isBinaryOperator(self,op):
        return op == 'eq' or op == 'ne' or op == 'gt' or op == 'lt' or op == 'ge' or op == 'le';

    def doBinaryOperator(self,op,a,b):
        if(op == 'eq'):
            self.value = a.value == b.value
        elif(op == 'ne'):
            self.value = a.value != b.value
        elif(op == 'gt'):
            self.value = a.value > b.value
        elif(op == 'lt'):
            self.value = a.value < b.value
        elif(op == 'ge'):
            self.value = a.value >= b.value
        elif(op == 'le'):
            self.value = a.value <= b.value
        else:
            self.createError('Unrecognized operator: '+op)

    def doRvalue(self,text):
        terms = text.split('.')
        self.value = self.context
        residue = ''
        for term in terms:
            if term not in self.value:
                self.createError(term+' is not defined in '+residue)
                return
            residue += '.'
            residue += term
            self.value = self.value[term]

    def doString(self,text):
        self.value = text

    def doDefined(self,a):
        self.value = a.isSuccess()

    def evaluate(self):
        childResults = []
        for child in self.expr:
            sub = EvalResult(self.context,child)
            sub.evaluate()
            childResults.append(sub)

        if args.verbose:
            print 'BEGIN evaluating expression '+ElementTree.tostring(self.expr)

        interpreted = False
        if self.expr.tag == 'op':
            if self.isBinaryOperator(self.expr.get('name')):
                interpreted = True
                if(len(childResults) != 2):
                    self.createError(self.expr,'Wrong number of arguments for operator '+self.expr.get('name'))
                elif (not childResults[0].isSuccess()):
                    self.addError(childResults[0].errors)
                elif (not childResults[1].isSuccess):
                    self.addError(childResults[1].errors)
                else:
                    self.doBinaryOperator(self.expr.get('name'),childResults[0],childResults[1])
        elif self.expr.tag == 'rvalue':
            interpreted = True
            self.doRvalue(self.expr.text)
        elif self.expr.tag == 'string':
            interpreted = True
            self.doString(self.expr.text)
        elif self.expr.tag == 'defined':
            interpreted = True
            if(len(childResults) != 1):
                self.createError(self.expr,'Wrong number of arguments for defined')
            else:
                self.doDefined(childResults[0])

        if not interpreted:
            self.createError(self.expr,'Cannot interpret this expression')

        if args.verbose:
            print 'END   evaluating expression '+ElementTree.tostring(self.expr)+' result: '+(str(self.value) if self.isSuccess() else 'Undefined')


class Goal:
    def __init__(self):
        self.name = ''
        self.proto = None
        self.method = None
        self.variables = []
        self.errors = []
        self.tempFiles = []

    def setProto(self,xmlProto):
        self.proto = xmlProto
        print "Goal "+self.name+" has symbol "+xmlProto.get('symbol')
        self.context[xmlProto.get('symbol')] = dict()
        self.variables = xmlProto.findall('variable')
        parser = argparse.ArgumentParser()
        for variable in self.variables:
            parser.add_argument('--'+variable.get('name'))
        args = parser.parse_args(self.args)
        for variable in self.variables:
            if variable.get('name') in args:
                value = eval('args.'+variable.get('name'))
                if(value != None):
                    path = xmlProto.get('symbol')+'.'+variable.get('name')
                    print path+' = '+value
                    self.setVariable(variable.get('name'),value)

    def setVariable(self,varName,value):
        self.context[self.proto.get('symbol')][varName] = value

    def getVariable(self,varName):
        return self.context[self.proto.get('symbol')][varName]

    def addError(self,error):
        self.errors.append(error)

    def createError(self,xmlDef,error):
        errMsg = '%s:%d.%d: %s' % (xmlDef._file_name,xmlDef._start_line_number,xmlDef._start_column_number,error)
        self.errors.append(errMsg)

    def isSuccess(self):
        return len(self.errors) == 0

    def cfgTopGoal(self,args):
        self.context = defaultEvalContext()
        self.args = args

    def evaluate(self,context,xmlExpr):
        result = EvalResult(context,xmlExpr)
        result.evaluate()
        return result

    def checkPre(self,solver):
        preChecks = self.proto.findall('pre')
        for preCheck in preChecks:
#            if args.verbose:
#                print "Checking "+jsonpickle.encode(preCheck)
            self.checkExpr(preCheck,solver)

    def checkExpr(self,preCheck,solver):
        checkResult = self.evaluate(self.context,preCheck[0])
        if not checkResult.isSuccess():
            if(args.verbose):
                print "ERROR: While checking <%s>," % preCheck.tag
                for error in checkResult.errors:
                    print "       "+error                        
            self.addError(checkResult.errors)
        elif not checkResult.value:
            self.createError(preCheck,'Pre check failed '+ElementTree.tostring(preCheck))

    def subsumedBy(self, other):
        if(self.name != other.name):
            return False
        if(('variables' in self) != ('variables' in other)):
            return False
        else:
            for var in self.variables:
                if var not in other.variables:
                    return False
                elif self.variables[var] != other.variables[var]:
                    return False
            return True

    def toString(self):
        result = ''
        result += '{ name: '+self.name
        if self.proto is not None:
            result += ', proto: '+self.proto.get('name')
        if self.method is not None:
            result += ', method: '+self.method.get('name')
        result += ', context: '+jsonpickle.encode(self.context)
        result += ' }'
        return result

    def pursue(self,solver):
        if(args.verbose):
            print 'BEGIN Pursuing this goal: '+self.toString()

        if not self.proto and self.isSuccess():
            protos = xmlDoc.findall('goalProto[@name=\''+self.name+'\']')        
            if(len(protos) == 0):
                solver.reportError(self.name+' is undefined')
                return
            self.setProto(protos[len(protos)-1])

        if not self.method and self.isSuccess():
            methods = xmlDoc.findall('method[@targetGoalType=\''+self.name+'\']')
            if(len(methods) == 0):
                solver.reportError(self.name+' has no methods defined')
                return
            methods.reverse()
            if(args.verbose):
                print "METHOD SEARCH: "
                for method in methods:
                    print '    '+method.get('name')+' can achieve goal '+self.name
            self.method = methods[len(methods)-1]

        if self.isSuccess():
            self.checkPre(solver)

        if self.isSuccess():
            for stmt in self.method.findall('*'):
                self.execute(stmt,solver)

        if(args.verbose):
            if not self.isSuccess():
                for error in self.errors:
                    print 'ERROR: '+error
            print 'END   Pursuing this goal: '+self.toString()+' (success: '+('True' if solver.result else 'False')+')'

    def interpolateInner(self,elt):
        cmd = ''
        if elt.text:
            cmd += elt.text
        for child in elt:
            if(ElementTree.iselement(elt)):
                sub = EvalResult(self.context,child)
                sub.evaluate()
                if sub.isSuccess():
                    cmd += sub.value
                else:
                    cmd += ElementTree.tostring(child)
            else:
                cmd += child.text
            if child.tail:
                cmd += child.tail
        if elt.tail:
            cmd += elt.tail
        return cmd

    def execute(self,stmt,solver):
        if stmt.tag == 'pre':
            self.checkExpr(stmt,solver)
        elif stmt.tag == 'taskSequence':
            for child in stmt:
                self.execute(child,solver)
        elif stmt.tag == 'task':
            if(args.verbose):
                print 'BEGIN Task %s' % stmt.get('name')
            for sub in stmt:
                self.execute(sub,solver)
            if(args.verbose):
                print 'END   Task %s' % stmt.get('name')
        elif stmt.tag == 'shell':
            sys.stdout.flush()
            children = stmt.findall('*')
            lastCommand = (None,None)
            shellCommand = None
            for child in children:
                if(child.tag == 'command'):
                    shellCommand = self.interpolateInner(child)
                if(child.tag == 'send'):
                    cmd = ''
                    if(shellCommand != None):
                        cmd = shellCommand+' '

                    cmd += self.interpolateInner(child)

                    if args.pursue:
                        print "SYSTEM %s" % cmd
                        lastCommand = pexpect.run(cmd,withexitstatus=1)
                        if(lastCommand[1] != 0):
                            print "ERROR: shell send failed"
                            print lastCommand[0]
                            exit(1)
                        print lastCommand[0]
                    else:
                        print "PLAN   %s" % cmd
                elif(child.tag == 'receive'):
                    cmd = self.interpolateInner(child)

                    print "EXPECT %s" % cmd
                    if args.pursue:
                        match = re.search(pattern)
                        if match:
                            self.useMatch(child,match)
            sys.stdout.flush()

        elif stmt.tag == 'tempFile':
            file = tempfile.NamedTemporaryFile(prefix=stmt.get('name'))
            info = dict()
            info['file'] = file
            info['path'] = file.name
            self.setVariable(stmt.get('name'),info)
            self.tempFiles.append(file)
            print >>file, self.interpolateInner(stmt)
            file.flush()

class Task:
    def __init__(self,goal):
        self.name = ''
        self.goal = goal
        self.errors = []

    def toString(self):
        result = ''
        result += '{ name: '+self.name
        if self.goal is not None:
            result += ', goal: '+self.goal.toString()
        result += ', context: '+jsonpickle.encode(self.context)
        result += ' }'

parser = argparse.ArgumentParser(description="Hive Command-Line Interpreter")
parser.add_argument('program')
parser.add_argument('--list',action='store_true')
parser.add_argument('--plan',nargs='?')
parser.add_argument('--pursue',nargs='?')
parser.add_argument('-v','--verbose',action='store_true')
tup = parser.parse_known_args()
args = tup[0]
if(args.verbose):
    print 'Reading program from '+args.program
xmlDoc = ElementTree.parse(args.program,parser=LineNumberingParser(args.program))

if(args.list):
    goalProtos = xmlDoc.findall('goalProto')
    for goalProto in goalProtos:
        print 'goalProto: '+goalProto.get('name')

if(args.plan or args.pursue):
    goalName = ''
    if(args.plan):
        goalName = args.plan
        args.verbose = True
    elif(args.pursue):
        goalName = args.pursue

    solver = Solver()
    solver.addTopGoalByName(goalName,tup[1])
    solver.solve()

if(args.verbose):
    print 'Done'
