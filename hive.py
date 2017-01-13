import sys
import os
import socket
import tempfile

sys.path.append('/usr/local/lib/python2.7/site-packages')

import xml.etree.ElementTree as ElementTree
import argparse
import pexpect
import copy
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

def defaultEvalContext(desc):
    result = Config(desc)
    result.root.lookupTermList(True,['node','platform'],None).setValue(sys.platform)
    result.root.lookupTermList(True,['node','uname'],None).setValue(os.uname())
    result.root.lookupTermList(True,['node','hostname'],None).setValue(socket.gethostname())
    result.root.lookupTermList(True,['node','hostip'],None).setValue(socket.gethostbyname(socket.gethostname()))
    return result

class Solver:
    def __init__(self,xmlDoc,solverArgs,remainingArgString):
        self.goals = []
        self.result = True
        self.xmlDoc = xmlDoc
        self.args = solverArgs
        self.remainingArgString = remainingArgString

    def hasGoal(self,goal):
        goals = [x for x in self.goals if goal.subsumedBy(x)]
        return len(goals)>0

    def addTopGoalByName(self,goalName):
        goal = Goal(self)
        goal.name = goalName
        goal.cfgTopGoal()
        if not self.hasGoal(goal):            
            self.addGoal(goal)

    def addGoal(self,goal):
        self.goals.append(goal)

    def solve(self):
        for goal in self.goals:
            goal.pursue()

    def reportError(self,errMsg):
        print 'ERROR: '+errMsg
        self.result = False

class EvalResult:
    def __init__(self,solver,context,xmlExpr):
        self.solver = solver
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

    def doString(self,text):
        self.value = text

    def doDefined(self,a):
        self.value = a.isSuccess()

    def evaluate(self):
        childResults = []
        for child in self.expr:
            sub = EvalResult(self.solver,self.context,child)
            sub.evaluate()
            childResults.append(sub)

        if self.solver.args.verbose:
            print 'BEGIN evaluating expression '+ElementTree.tostring(self.expr)

        interpreted = False
        if self.expr.tag == 'op':
            if self.isBinaryOperator(self.expr.get('name')):
                interpreted = True
                if(len(childResults) != 2):
                    self.createErrorAt(self.expr,'Wrong number of arguments for operator '+self.expr.get('name'))
                elif (not childResults[0].isSuccess()):
                    self.addError(childResults[0].errors)
                elif (not childResults[1].isSuccess()):
                    self.addError(childResults[1].errors)
                else:
                    self.doBinaryOperator(self.expr.get('name'),childResults[0],childResults[1])
        elif self.expr.tag == 'rvalue':
            interpreted = True
            node = self.context.root.lookupElement(False,self.expr,self)
            if node != None:
                self.value = node.selected
        elif self.expr.tag == 'string':
            interpreted = True
            self.doString(self.expr.text)
        elif self.expr.tag == 'defined':
            interpreted = True
            if(len(childResults) != 1):
                self.createErrorAt(self.expr,'Wrong number of arguments for defined')
            else:
                self.doDefined(childResults[0])

        if not interpreted:
            self.createErrorAt(self.expr,'Cannot interpret this expression')

        if self.solver.args.verbose:
            print 'END   evaluating expression '+ElementTree.tostring(self.expr)+' result: '+(str(self.value) if self.isSuccess() else 'Undefined')


class Goal:
    def __init__(self,solver):
        self.name = ''
        self.proto = None
        self.method = None
        self.variables = []
        self.errors = []
        self.tempFiles = []
        self.solver = solver

    def setProto(self,xmlProto):
        self.proto = xmlProto
        print "Goal "+self.name+" has symbol "+xmlProto.get('symbol')
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
                    node = self.context.root.lookupTermList(True,[self.proto.get('symbol'),variable.get('name')],self)
                    node.setValue(value)

    def allocVariable(self,varName):
        node = self.context.root.lookupTermList(True,[self.proto.get('symbol'),varName],self)
        return node

    def setVariable(self,varName,value):
        node = self.context.root.lookupTermList(False,[self.proto.get('symbol'),varName],self)
        node.setValue(value)

    def getVariable(self,varName):
        node = self.context.root.lookupTermList(False,[self.proto.get('symbol'),varName],self)
        return node.getValue()

    def addError(self,error):
        self.errors.append(error)

    def createErrorAt(self,xmlDef,error):
        errMsg = '%s:%d.%d: %s' % (xmlDef._file_name,xmlDef._start_line_number,xmlDef._start_column_number,error)
        self.errors.append(errMsg)

    def createError(self,error):
        self.errors.append(error)

    def isSuccess(self):
        return len(self.errors) == 0

    def cfgTopGoal(self):
        self.context = defaultEvalContext('Evaluation context for goal '+self.name)
        self.args = self.solver.remainingArgString

    def evaluate(self,context,xmlExpr):
        result = EvalResult(self.solver,context,xmlExpr)
        result.evaluate()
        return result

    def checkPre(self):
        preChecks = self.proto.findall('pre')
        for preCheck in preChecks:
#            if args.verbose:
#                print "Checking "+jsonpickle.encode(preCheck)
            self.checkExpr(preCheck)

    def checkExpr(self,preCheck):
        checkResult = self.evaluate(self.context,preCheck[0])
        if not checkResult.isSuccess():
            if(self.solver.args.verbose):
                print "ERROR: While checking <%s>," % preCheck.tag
                for error in checkResult.errors:
                    print "       "+error                        
            self.addError(checkResult.errors)
        elif not checkResult.value:
            self.createErrorAt(preCheck,'Pre check failed '+ElementTree.tostring(preCheck))

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
        result += ', context: '+self.context.toString()
        result += ' }'
        return result

    def pursue(self):
        if(self.solver.args.verbose):
            print 'BEGIN Pursuing this goal: '+self.toString()

        if not self.proto and self.isSuccess():
            protos = self.solver.xmlDoc.findall('goalProto[@name=\''+self.name+'\']')        
            if(len(protos) == 0):
                self.solver.reportError(self.name+' is undefined')
                return
            self.setProto(protos[len(protos)-1])

        if not self.method and self.isSuccess():
            methods = self.solver.xmlDoc.findall('method[@targetGoalType=\''+self.name+'\']')
            if(len(methods) == 0):
                self.solver.reportError(self.name+' has no methods defined')
                return
            methods.reverse()
            if(self.solver.args.verbose):
                print "METHOD SEARCH: "
                for method in methods:
                    print '    '+method.get('name')+' can achieve goal '+self.name
            self.method = methods[len(methods)-1]

        if self.isSuccess():
            self.checkPre()

        if self.isSuccess():
            for stmt in self.method.findall('*'):
                self.execute(stmt)

        if(self.solver.args.verbose):
            if not self.isSuccess():
                for error in self.errors:
                    print 'ERROR: '+error
            print 'END   Pursuing this goal: '+self.toString()+' (success: '+('True' if self.solver.result else 'False')+')'

    def interpolateInner(self,elt):
        cmd = ''
        if elt.text:
            cmd += elt.text
        for child in elt:
            if(ElementTree.iselement(elt)):
                sub = EvalResult(self.solver,self.context,child)
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

    def execute(self,stmt):
        if stmt.tag == 'pre':
            self.checkExpr(stmt)
        elif stmt.tag == 'taskSequence':
            for child in stmt:
                self.execute(child)
        elif stmt.tag == 'task':
            if(self.solver.args.verbose):
                print 'BEGIN Task %s' % stmt.get('name')
            for sub in stmt:
                self.execute(sub)
            if(self.solver.args.verbose):
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

                    if self.solver.args.pursue:
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
                    if self.solver.args.pursue:
                        match = re.search(pattern)
                        if match:
                            self.useMatch(child,match)
            sys.stdout.flush()

        elif stmt.tag == 'tempFile':
            file = tempfile.NamedTemporaryFile(prefix=stmt.get('name'))
            #info = dict()
            #info['file'] = file
            #info['path'] = file.name
            node = self.allocVariable(stmt.get('name'))
            self.setVariable(stmt.get('name'),file.name)
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
        result += ', context: '+self.context.toString()
        result += ' }'

class Command:
    def getName():
        raise NotImplementedError 

    def getProto():
        raise NotImplementedError 

class ConfigNode:    
    def __init__(self,rootConfig,name):
        self.name = name
        self.rootConfig = rootConfig
        self.values = []
        self.selected = None
        self.fields = dict()
        self.elements = []

    def setValue(self,value):
        self.selected = value

    def getValue(self):
        return self.selected        

    def setParent(self,parent):
        self.parent = parent

    def getPath(self,char):
        result = ''
        if self.parent:
            result += self.parent.getPath()
            result += char
        result += self.name
        return result

    def lookupElement(self,create,xmlExpr,errHandler):
        if(len(xmlExpr) == 0):
            return self.lookupString(create,xmlExpr.text,errHandler)
        elif xmlExpr.tag == 'getField':
            lvalue = self.lookupElement(create,xmlExpr[0])
            if lvalue == None:
                return None
            elif xmlExpr.get('name') not in self.fields:
                if create:
                    newNode = ConfigNode(self.rootConfig,xmlExpr.get('name'))
                    newNode.setParent(self)
                    self.fields[xmlExpr.get('name')] = newNode
                elif errHandler:
                    errHandler.createErrorAt(xmlExpr,'No field named '+xmlExpr.get('name'))
                    return None
            return lvalue.fields[xmlExpr.get('name')]
        elif xmlExpr.tag == 'getElement':
            lvalue = self.lookupElement(create,xmlExpr[0])
            if lvalue == None:
                return None
            elif len(self.fields) < xmlExpr.get('index'):
                if create:
                    newNode = ConfigNode(self.rootConfig,xmlExpr.get('name'))
                    newNode.setParent(self)
                    self.elements[xmlExpr.get('index')] = newNode
                elif errHandler:
                    errHandler.createErrorAt(xmlExpr,'No element with index '+xmlExpr.get('index'))
                    return None
            return lvalue.elements[xmlExpr.get('index')]

    def lookupString(self,create,pathString,errHandler):
        pathTerms = pathString.split('.')
        return self.lookupTermList(create,pathTerms,errHandler)

    def lookupTermList(self,create,pathTerms,errHandler):
        result = None
        if(len(pathTerms) == 0):
            result = self
        else:
            if pathTerms[0] not in self.fields:
                if create:
                    newNode = ConfigNode(self.rootConfig,pathTerms[0])
                    newNode.setParent(self)
                    self.fields[pathTerms[0]] = newNode
                elif errHandler:
                    errHandler.createError('No field named '+pathTerms[0])
                    return None

            result = self.fields[pathTerms[0]].lookupTermList(create,pathTerms[1:],errHandler)
        return result

class Config:
    def __init__(self,desc):
        self.root = ConfigNode(self,'')
        self.desc = desc

    def setup(self,xmlProto):
        for var in xmlProto.findall('variable'):
            node = self.root.lookupElement(True,var,None)
            node.setupXML(var)

    def toString(self):
        return self.desc

class Invocation:
    def __init__(self,command):
        self.command = command
        self.series = []
        self.state = 'init'

    def default(self):
        first = Config('Default context for '+self.toString())
        first.setup(self.command.xmlProto)
        self.series.push(first)

    def top(self):
        return self.series[len(self.series)-1]

    def propose(self,config):
        self.series.push(config.correct())

    def undo(self):
        self.series.pop()
