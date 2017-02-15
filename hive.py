import sys
import os
import uuid
import socket
import tempfile
import glob
import urllib
import code
from subprocess import PIPE, Popen
from threading  import Thread

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x

# BEGIN code from http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()
# END code from http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python

sys.path.append('/usr/local/lib/python2.7/site-packages')

import xml.etree.ElementTree as ElementTree
import argparse
import pexpect
import copy
import jsonpickle
import re

def toBool(rvalue):
    return rvalue != False and rvalue != 0 and rvalue != 'false' and rvalue != 'False' and rvalue != 'FALSE'

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

class ElementTreeWriter:
    def __init__(self):
        self.stack = []
        self.root = None

    def begin(self,tag,attrib=dict()):
        myNode = ElementTree.Element(tag)
        if(len(self.stack)>0):
            self.stack[len(self.stack)-1].append(myNode)
        else:
            self.root = myNode
        for key in attrib.keys():
            myNode.set(key,attrib[key])
        self.stack.append(myNode)        

    def end(self,tag):
        self.stack.pop()

    def object(self,thing):
        self.begin(thing.__class__.__name)
        for attrib,value in thing.__dict__.iteritems():
            self.subordinate(thing,attrib,value)
        self.end(thing.__class__.__name)

    def subordinate(self,parentObj,attribName,thing):
        if type(thing) in (tuple,list):
            # parentObj attribute is a list
            for item in thing:
                self.begin(attribName)
                self.object(item)
                self.end(attribName)
        elif type(thing) in (dict):
            # parentObj attribute is a plain dict
            for key in thing.keys():
                self.begin(attribName,dict(key=key))
                self.object(thing[key])
                self.end(attribName)
        elif __dict__ in thing:
            # parentObj attribute is another object
            self.begin(attribName)
            self.object(thing)
            self.end(attribName)
        else:
            # parentObj attribute is a scalar value
            self.begin(attribName)
            self.stack[len(self.stack)-1].text = thing
            self.end(attribName)

class ElementTreeReader:
    def __init__(self,xmlRoot):
        self.stack = []
        self.root = xmlRoot
        self.named = dict()
        self.unnamed = []

    def parse(self):
        self.parseNode(self.root)

    def isClass(self,className):
        classHandle = getattr(sys.modules[__name__], className)
        return classHandle != None

    def spawnClass(self,className):
        classHandle = getattr(sys.modules[__name__], className)
        if classHandle == None:
            raise RuntimeError('Cannot find class named '+className)
        return classHandle()

    def parseNode(self,node):
        self.stack.append(node)
        obj = self.spawnClass(node.tag)
        self.object(obj)
        self.stack.pop()
        return obj

    def object(self,thing):
        isGlobal = (len(self.stack) == 0)
        isNamed = 'name' in thing
        self.begin(self.__class__.__name)
        for attrib,value in thing.__dict__.iteritems():
            self.subordinate(thing,attrib,value)
        self.end(self.__class__.__name)
        if isNamed:
            self.named[thing]

    def subordinate(self,parentObj,attribName,thing):
        if type(thing) in (tuple,list):
            # parentObj attribute is a list
            for childNode in self.stack[len(self.stack)-1]:
                if childNode.tag == attribName:
                    childObj = parseNode(childNode)
                    thing.append(childObj)
        elif type(thing) in (dict):
            # parentObj attribute is a plain dict
            for childNode in self.stack[len(self.stack)-1]:
                if childNode.tag == attribName:
                    key = childNode.tag
                    value = childNode.get('key')
                    childObj = parseNode(childNode)
                    thing[key] = childObj
        elif __dict__ in thing:
            # parentObj attribute is another object
            self.begin(attribName)
            self.object(thing)
            self.end(attribName)
        else:
            # parentObj attribute is a scalar value
            parentObj.set(attribName,thing)

#    def child(self,thing,attrib):
#        if type(thing) in (tuple,list):
#        elif type(thing) in (dict):
#        elif __dict__ in thing:
#            self.begin(attrib)
#            self.object(thing)
#            self.end(attrib)
#        else
#            self.set(attrib,thing)

class Tabulator:
    def __init__(self):
        self.rows = []

    def addElement(self,xml):
        if xml.tag == 'goalProto':
            row = dict(type=xml.tag,name=xml.get('name'))
            descriptions = xml.findall('describe')
            row['description'] = ''
            for description in descriptions:
                row['description'] = description.text            
            self.rows.append(row)

    def printText(self):
        sizes = dict()
        for row in self.rows:
            for key,value in row.iteritems():
                maxSize = len(key)
                if len(value) > maxSize:
                    maxSize = len(value)

                if key not in sizes:
                    sizes[key] = maxSize
                elif maxSize > sizes[key]:
                    sizes[key] = maxSize

        formatString = '|'
        for key in sizes.keys():
            formatString += ' %%(%s)%ds |' % (key,sizes[key])
        formatString += '\n'

        headerString = '|'
        for key in sizes.keys():
            headerString += (' %%%ds |' % sizes[key]) % key
        headerString += '\n'

        resultString = headerString
        for row in self.rows:
            resultString += formatString % row

        return resultString

class GenericCommand:
    def __init__(self,solver,name):
        self.name = name
        self.config = Config(name,'Solver API command %s' % name,solver)        

    def __len__(self):
        return self.__dict__.__len__()

    def __iter__(self):
        return self.__dict__.__iter__()

class Solver:
    def __init__(self):
        self.name = 'the'
        self.goals = []
        self.goalsByName = dict()
        self.defByTypeThenName = dict()
        self.state = Config('Solver','Solver state',self)
        self.result = True
        self.statementStack = []
        self.stateDefs = []
        self.agents = []

    def parseArgs(self,solverArgs,remainingArgString):
        self.args = solverArgs
        self.remainingArgString = remainingArgString

    def hello(self):
        commandNames = ['list','plan','execute']
        commands = []
        for cmdName in commandNames:
            commands.append(GenericCommand(self,cmdName))
        return commands

    def allocateAgentName(self):
        return str(uuid.uuid4())

    def verboseMode(self,level):
        return self.args.verbose != None and self.args.verbose >= level        

    def goalsMode(self,level):
        return self.args.goals != None and self.args.goals >= level        

    def echoMode(self):
        return self.args.echo != None

    def linesMode(self):
        return self.args.lines != None

    def initialMode(self):
        return self.args.initial != None

    def finalMode(self):
        return self.args.final != None

    def readFile(self,programFile,mandatory=True):
        actualPaths = glob.glob(os.path.expanduser(programFile))
        if len(actualPaths) == 0:
            if mandatory:
                self.createError('Input file does not exist: '+programFile)
            else:
                print('Input file does not exist: '+programFile)

        for actualPath in actualPaths:
            if not os.path.isfile(actualPath):
                if mandatory:
                    self.createError('Input file does not exist: '+actualPath)
                else:
                    print('Input file does not exist: '+actualPath)
            else:
                if self.args.verbose > 0:
                    print 'Reading '+actualPath
                xmlDoc = ElementTree.parse(actualPath,parser=LineNumberingParser(actualPath))
                self.readDefinitions(xmlDoc)

    def readDefinitions(self,xmlDefinitions):
        for element in xmlDefinitions.findall('*'):
            if 'name' in element.attrib:
                self.addDefinition(element)
            else:
                self.createError('%s:%d: attribute name must be present on all top-level XML nodes, which are considered to be Hive definitions' % (element._file_name,element._start_line_number))
            if element.tag == 'variable' or element.tag == 'list' or element.tag == 'struct':
                self.addStateDef(element)

    def addDefinition(self,xmlDefinition):
        typeName = xmlDefinition.tag
        defName = xmlDefinition.get('name')
        if self.args.verbose > 0:
            print 'Definition of %s %s at %s:%d' % (typeName,defName,xmlDefinition._file_name,xmlDefinition._start_line_number)
        if typeName not in self.defByTypeThenName:
            self.defByTypeThenName[typeName] = dict()
        self.defByTypeThenName[typeName][defName] = xmlDefinition

    def addStateDef(self,xmlDef):
        self.stateDefs.append(xmlDef)

    def getDefinitions(self,typeName):
        result = []
        if typeName in self.defByTypeThenName:
            for defName,defElement in self.defByTypeThenName[typeName].iteritems():
                result.append(defElement)
        return result

    def getDefinitionByTypeAndName(self,typeName,defName):
        if typeName in self.defByTypeThenName:
#            print 'DEBUG: %d definitions of type %s found' % (len(self.defByTypeThenName[typeName].keys()),typeName)
            if defName in self.defByTypeThenName[typeName]:
                defn = self.defByTypeThenName[typeName][defName]
#                print 'DEBUG: definition of type %s and name %s found at %s:%d' % (typeName,defName,defn._file_name,defn._start_line_number)
                return defn
        return None

    def createError(self,error):
        self.reportError(error)

    def reportError(self,errMsg):
        print 'ERROR: '+errMsg
        self.result = False

    def hasErrors(self):
        return len(self.errors) > 0

    def initialize(self):
        for xml in self.stateDefs:
            position = '%s:%d' % (xml._file_name,xml._start_line_number)
            if self.verboseMode(1):
                print 'BEGIN Processing <state> element at '+position
            self.state.root.initStateNode(self,self.state,xml)
            if self.verboseMode(1) :
                print 'END   Processing <state> element at '+position

#    def terminate(self):
        # nothing to do        

    def beginAgent(self):
        agent = Agent(self);
        self.agents.append(agent)

        if self.args.initial:
            print 'BEGIN INITIAL STATE OF AGENT %s' % agent.name
            print agent.state.details()
            print 'END   INITIAL STATE OF AGENT %s' % agent.name

        return agent

    def endAgent(self,agent):
        if self.args.final:
            print 'BEGIN FINAL STATE OF AGENT %s' % agent.name
            print agent.state.details()
            print 'END   FINAL STATE OF AGENT %s' % agent.name

        self.agents.remove(agent)

class Agent:
    def __init__(self,solver):
        self.solver = solver
        self.goals = []
        self.goalsByName = dict()
        self.statementStack = []
        self.name = solver.allocateAgentName()
        self.state = Config(self.name,'State of Agent '+self.name,solver)
        self.state.root.setupStruct()        
        self.goalIndex = dict()

    def allocateGoalName(self,prefix):
        if prefix not in self.goalIndex:
            self.goalIndex[prefix] = 0
        else:
            self.goalIndex[prefix] += 1
        return '%s.%s.%d' % (self.name,prefix,self.goalIndex[prefix])

    def defaultEvalContext(self,goalName,desc):
        result = Config(goalName,desc,self.solver)
        result.copyFrom(self.solver.state)

        result.initPath('Solver.defaultEvalContext',['host','platform'],sys.platform)
        result.initPath('Solver.defaultEvalContext',['host','uname'],os.uname()[0])
        result.initPath('Solver.defaultEvalContext',['host','hostname'],socket.gethostname())
        result.initPath('Solver.defaultEvalContext',['host','hostip'],socket.gethostbyname(socket.gethostname()))

        return result

    def verboseMode(self,level):
        return self.solver.args.verbose != None and self.solver.args.verbose >= level

    def goalsMode(self,level):
        return self.solver.args.goals != None and self.solver.args.goals >= level

    def echoMode(self):
        return self.solver.args.echo != None

    def linesMode(self):
        return self.solver.args.lines != None

    def initialMode(self):
        return self.solver.args.initial != None

    def finalMode(self):
        return self.solver.args.final != None

    def interpolateInner(self,context,elt,errHandler):
        cmd = ''
        if elt.text:
            cmd += elt.text
        for child in elt:
            if child.tag == 'describe' or child.tag == 'label':
                pass
            elif ElementTree.iselement(child):
                sub = Evaluator(self,context,None)
                sub.setXML(child)
                sub.evaluate()
                if sub.isSuccess():
                    cmd += sub.getStringValue()
                else:
                    for error in sub.errors:
                        errHandler.errors.append(error)
                    cmd += ElementTree.tostring(child)
            else:
                cmd += child.text
            if child.tail:
                cmd += child.tail
#        if elt.tail:
#            cmd += elt.tail
        return cmd

    def beginStatement(self,statement,context):
        self.statementStack.append(statement)
        sourceLoc = ''
        if self.solver.linesMode():
            sourceLoc = '%s:%d ' % (statement._file_name,statement._start_line_number)

        if self.solver.args.narrate:
            descriptions = statement.findall('describe')
            if len(descriptions) > 0:
                evalResult = Evaluator(self,context,None)
                evalResult.setXML(descriptions[0])
                evalResult.evaluate()
                name = ''
                if 'name' in statement.attrib:
                    name = '%s : ' % statement.get('name')
                print "# BEGIN %s%s%s" % (sourceLoc,name,evalResult.value)

    def endStatement(self,statement,context):
        sourceLoc = ''
        if self.solver.linesMode():
            sourceLoc = '%s:%d ' % (statement._file_name,statement._start_line_number)

        if self.solver.args.narrate:
            descriptions = statement.findall('describe')
            if len(descriptions) > 0:
                evalResult = Evaluator(self,context,None)
                evalResult.setXML(descriptions[0])
                evalResult.evaluate()
                name = ''
                if 'name' in statement.attrib:
                    name = '%s : ' % statement.get('name')
                print "# END   %s%s%s" % (sourceLoc,name,evalResult.value)
        self.statementStack.pop()

    def findGoal(self,goalName,goalConfig):
        if goalName in self.goalsByName:
            for goal in self.goalsByName[goalName]:
                if goal.context.covers(goalConfig):
                    return goal
        return None

    def hasGoal(self,goal):
        goals = [x for x in self.goals if goal.subsumedBy(x)]
        return len(goals)>0

    def addTopGoalByName(self,goalName):
        goal = Goal(self)
        goal.cfgTopGoal(goalName,self.solver.remainingArgString)
        if not self.hasGoal(goal):            
            self.addGoal(goal)
        return goal

    def addGoal(self,goal):
        self.goals.append(goal)
        myNode = self.state.root.lookupTermList(True,[goal.name],self)
        otherNode = goal.context.root.lookupTermList(False,['goal'],self)
        myNode.copyFrom(otherNode)

    def solve(self):
        for goal in self.goals:
            goal.pursue()

    def saveGoal(self,goal):
        if goal.name not in self.goalsByName:
            self.goalsByName[goal.name] = []

        self.goalsByName[goal.name].append(goal)

class EvalOutcomes:
    def __init__(self):
        self.value = True

    def setTrue(self):
        self.value = True
        return self

    def setFalse(self):
        self.value = False
        return self

    def setPossible(self):
        self.value = 'possible'
        return self

    def isTrue(self):
        return self.value == True

    def isFalse(self):
        return self.value == False

    def isPossible(self):
        return self.value == 'possible'

    def tostring(self):
        if self.value == True:
            return 'True'
        elif self.value == False:
            return 'False'
        else:
            return 'Possible'

    def __and__(self,other):
        if self.value == False or other.value == False:
            return EvalOutcomes().setFalse()
        elif self.value == 'possible' or other.value == 'possible':
            return EvalOutcomes().setPossible()
        else:
            return EvalOutcomes().setTrue()

    def __or__(self,other):
        if self.value == True or other.value == True:
            return EvalOutcomes().setTrue()
        elif self.value == 'possible' or other.value == 'possible':
            return EvalOutcomes().setPossible()
        else:
            return EvalOutcomes().setFalse()

class Evaluator:
    def __init__(self,agent,context,pursue):
        self.agent = agent
        self.context=context
        self.errors = []
        self.outcome = EvalOutcomes().setTrue()
        self.tail = ''
        self.pursue = pursue
        self.value = None

    def setXML(self,xmlExpr):
        self.expr=xmlExpr
        self.label = '%s:%d.%d' % (self.expr._file_name,self.expr._start_line_number,self.expr._start_column_number)

    def setString(self,text):
        self.text=text
        self.label = '"%s"' % text

    def setValue(self,value):
        self.outcome = EvalOutcomes().setTrue()
        self.value = value

    def getLvalue(self):
        if isinstance(self.value,ConfigNode):
            return self.value
        else:
            return None

    def getStringValue(self):
        rvalue = self.getRvalue()
        if rvalue != None:
            return str(rvalue)
        elif 'expr' in self.__dict__:
            return ElementTree.tostring(self.expr)
        else:
            return None # this will cause a downstream error

    def getRvalue(self):
        result = None
        if isinstance(self.value,ConfigNode):
            result = self.value.getValue()
        else:
            result = self.value
        return result

    def addError(self,error):
        self.outcome = self.outcome and EvalOutcomes().setFalse()
        if type(error) in (tuple,list):
            for item in error:
                self.errors.append(item)
        else:
            self.errors.append(error)

    def createError(self,error):
        errMsg = '%s: %s' % (self.label,error)
        self.errors.append(errMsg)
        self.outcome.setFalse()

    def isSuccess(self):
        return self.outcome.isTrue()

    def getOutcome(self):
        return self.outcome

    def isUnaryOperator(self,op):
        return op == 'isZero' or op == 'isNotZero' or op == 'not'

    def doUnaryOperator(self,op,a):
        self.outcome = a.outcome
        if(op == 'isZero'):
            self.value = int(a.getRvalue()) == 0
        elif(op == 'isNotZero'):
            self.value = int(a.getRvalue()) != 0
        elif(op == 'not'):
            self.value = not toBool(a.getRvalue())
        else:
            self.createError('Unrecognized operator: '+op)

    def isBinaryOperator(self,op):
        return op == 'eq' or op == 'ne' or op == 'gt' or op == 'lt' or op == 'ge' or op == 'le'

    def doBinaryOperator(self,op,a,b):
        self.outomde = a.outcome and b.outcome
        if(op == 'eq'):
            self.value = a.getRvalue() == b.getRvalue()
        elif(op == 'ne'):
            self.value = a.getRvalue() != b.getRvalue()
        elif(op == 'gt'):
            self.value = a.getRvalue() > b.getRvalue()
        elif(op == 'lt'):
            self.value = a.getRvalue() < b.getRvalue()
        elif(op == 'ge'):
            self.value = a.getRvalue() >= b.getRvalue()
        elif(op == 'le'):
            self.value = a.getRvalue() <= b.getRvalue()
        else:
            self.createError('Unrecognized operator: '+op)

    def doStruct(self,xml):
        self.value = dict()
        for child in xml:
            subResult = Evaluator(self.agent,self.context,self.pursue)
            subResult.setXML(child)
            if 'name' not in subResult:
                subResult.createError('XML child of structure must have attribute \'name\'')
            elif not subResult.isSuccess():
                subResult.createError('Cannot evaluate sub-expression')
            else:
                self.value.set(subResult.name,subResult)
        self.outcome = EvalOutcomes().setTrue()

    def doVariable(self,xml):
        self.value = self.context.root.lookupString(True,xml.get('name'),self)
        self.outcome = EvalOutcomes().setTrue()

    def doDefined(self,a):
        self.value = a.isSuccess() and (a.getLvalue() != None or a.getRvalue() != None)
        if self.agent.verboseMode(1) and not a.isSuccess():
            for error in a.errors:
                print error

    def evaluate(self):
        if 'expr' in self.__dict__:
            self.doXML()
        elif 'text' in self.__dict__:
            self.doText()
        else:
            self.createError('Must call Evaluator.setXML or Evaluator.setString before calling Evaluator.evaluate')

    def doXML(self):
        childResults = []
        if self.expr.text:
            sub = Evaluator(self.agent,self.context,self.pursue)
            sub.setString(self.expr.text)
            sub.doText()
            childResults.append(sub)
        for child in self.expr:
            if child.tag != 'describe' and child.tag != 'label':
                sub = Evaluator(self.agent,self.context,self.pursue)
                sub.setXML(child)
                sub.evaluate()
                childResults.append(sub)
        if self.expr.tail:
            self.tail = self.expr.tail

        if self.agent.verboseMode(2):
            print 'BEGIN evaluating expression '+self.expr.tag+' at '+self.label

        interpreted = False
        if self.expr.tag == 'op':
            if self.isBinaryOperator(self.expr.get('name')):
                interpreted = True
                if(len(childResults) != 2):
                    self.createError('Wrong number of arguments for operator '+self.expr.get('name'))
                elif (not childResults[0].isSuccess()):
                    self.addError(childResults[0].errors)
                elif (not childResults[1].isSuccess()):
                    self.addError(childResults[1].errors)
                else:
                    self.doBinaryOperator(self.expr.get('name'),childResults[0],childResults[1])
            elif self.isUnaryOperator(self.expr.get('name')):
                interpreted = True
                if(len(childResults) != 1):
                    self.createError('Wrong number of arguments for operator '+self.expr.get('name'))
                elif (not childResults[0].isSuccess()):
                    self.addError(childResults[0].errors)
                else:
                    self.doUnaryOperator(self.expr.get('name'),childResults[0])
        elif self.expr.tag == 'get':
            self.value = self.context.root.lookupString(False,self.expr.text,self)
            if self.value == None:
                self.outcome = self.outcome and EvalOutcomes().setFalse()
            else:
                interpreted = True
        elif self.expr.tag == 'set':
            self.value = self.expr.text
            if self.value == None:
                self.outcome = self.outcome and EvalOutcomes().setFalse()
            else:
                interpreted = True
        elif self.expr.tag == 'int':
            if(len(childResults) == 0):
                self.createError('<'+self.expr.tag+'> must always have a child expression')
            else:
                interpreted = True
                self.setValue(int(childResults[0].getRvalue()))
                self.outcome = self.outcome and childResults[0].outcome
        elif self.expr.tag == 'bool':
            if(len(childResults) == 0):
                self.createError('<'+self.expr.tag+'> must always have a child expression')
            else:
                interpreted = True
                self.setValue(toBool(childResults[0].getRvalue()))
                self.outcome = self.outcome and childResults[0].outcome
        elif self.expr.tag == 'string' or self.expr.tag == 'describe' or self.expr.tag == 'code':
            if(len(childResults) == 0):
                self.createError('<'+self.expr.tag+'> must always have a child expression')
            else:
                interpreted = True
                text = ''
                for child in childResults:
                    text += child.getStringValue()
                    if child.tail:
                        text += child.tail
                    self.outcome = self.outcome and child.outcome
                self.setValue(text)
#        elif self.expr.tag == 'struct':
#            interpreted = True
#            self.doDict(self.expr)
        elif self.expr.tag == 'variable':
#            self.doVariable(self.expr)
            if len(childResults) == 0:
                pass
                #self.createError('No child expression to compute the initial value of '+self.expr.get('name'))
            elif not childResults[0].isSuccess():
                self.addError(childResults[0].errors[0])
            else:
                interpreted = True
                self.setValue(childResults[len(childResults)-1].value)
        elif self.expr.tag == 'list':
#            self.doVariable(self.expr)
            if len(childResults) == 0:
                pass
                #self.createError('No child expression to compute the initial value of '+self.expr.get('name'))
            elif(childResults[0].getLvalue() != None):
                interpreted = True
                self.setValue(childResults[0].getLvalue())
            elif(childResults[0].getRvalue() != None):
                interpreted = True
                self.setValue(childResults[0].getRvalue())
            else:
                interpreted = True
                self.setValue([])
        elif self.expr.tag == 'defined':
            if(len(childResults) != 1):
                self.createError('Wrong number of arguments for defined')
            else:
                self.doDefined(childResults[0])
                interpreted = True
        elif self.expr.tag == 'shell':
            children = self.expr.findall('*')
            lastReturnCode = None
            for child in children:
                if(child.tag == 'send'):
                    cmd = ''
                    cmd += self.agent.interpolateInner(self.context,child,self)
                    cmdList = glob.glob(os.path.expanduser(cmd))
                    if len(cmdList) == 0:
                        cmdList = [cmd]
                        #self.createError('Cannot expand this shell expression:\n%s\n' % cmd)
                    for cmd in cmdList:
                        cmd = re.sub('\s*\n\s*',' ',cmd.strip())                        
                        if self.agent.verboseMode(1):
                            print 'BEGIN shell command: %s' % cmd
                        timeout = None
                        if 'timeout' in child.attrib:
                            timeout = child.get('timeout')
                        lastReturnCode = pexpect.run(cmd,withexitstatus=1,timeout=timeout)
                        if self.agent.verboseMode(1):
                            print "END   shell return code %d command: %s" % (lastReturnCode[1],cmd)                
            valueType = 'isZero'
            if 'value' in self.expr.attrib:
                valueType = self.expr.get('value')
            if lastReturnCode == None:
                interpreted = False
            elif(valueType == 'returnCode'):
                interpreted = True
                self.value = lastReturnCode[1]
            elif(valueType == 'isZero'):
                interpreted = True
                self.value = (lastReturnCode[1] == 0)
        elif self.expr.tag == 'fileTest':
            testType = self.expr.get('type')
            if len(childResults) != 1:
                self.createError('fileTest tag must always have a path as its only child')
            else:
                if self.agent.verboseMode(1):
                    print "TESTING FILE "+childResults[0].value
                if testType == 'exists':
                    interpreted = True
                    self.value = os.path.exists(childResults[0].value)
        elif self.expr.tag == 'python':
            funcName = None
            if 'name' in self.expr.attrib:
                funcName = self.expr.get('name')
            codeBlocks = self.expr.findall('code')
            if funcName != None:
                if len(childResults) != 1:
                    self.createError('python tag must always have a path as its only child')
                else:
                    cmd = 'self.value = %s(\'%s\')' % (funcName,childResults[0].getStringValue())
                    if self.agent.solver.args.plan:
                        print '\n'.join(['PLAN %s' % x for x in cmd.split('\n')])
                        interpreted = True
                    else:
                        if self.agent.echoMode():
                            print "BEGIN <python><code>\n%s\n</code></python>" % cmd
                        exec(cmd)
                        if self.agent.echoMode():
                            print "END   <python><code>\n%s\n</code></python>" % cmd
                        interpreted = True
            elif len(codeBlocks) > 0:
#                print 'DEBUG: %d code blocks' % len(codeBlocks)
                for codeBlock in codeBlocks:
                    sub = Evaluator(self.agent,self.context,self.pursue)
                    sub.setXML(codeBlock)
                    sub.evaluate()
                    if not sub.isSuccess():
                        self.createError('Cannot interpret this <code> block')
                        for error in sub.errors:
                            self.errors.append(error)
                    elif self.agent.solver.args.plan:
                        print '\n'.join(['PLAN %s' % x for x in sub.getStringValue().split('\n')])
                        interpreted = True
                    else:
                        cmd = sub.getStringValue()
                        localContext = dict(locals())
                        self.context.root.configureMapping(localContext)
                        if self.agent.echoMode():
                            print "BEGIN <python><code>\n%s\n</code></python>" % cmd
                        exec(cmd,globals(),localContext)
                        if self.agent.echoMode():
                            print "END   <python><code>\n%s\n</code></python>" % cmd
                        self.setValue(True)
                        interpreted = True
#                code.interact(local=locals())
        elif self.expr.tag == 'goalCompleted':
            goalName = self.expr.get('name')
            goalConfig = Config(goalName,'Example of completed goal',self.agent.solver)
            goalConfig.setup('goal',self.expr)
            foundGoal = self.agent.findGoal(goalName,goalConfig)
            interpreted = True
            if (foundGoal != None):
                self.value = True
                self.outcome = EvalOutcomes().setTrue()
            elif self.pursue != None:
                subgoal = Goal(self.agent)
                subgoal.cfgSubGoal(goalName,self.pursue,self.context,self.expr,self.agent.solver.remainingArgString)
                subgoal.pursue()
                if not subgoal.isSuccess():
                    self.value = False
                else:
                    self.value = True
                    subgoal.context.root.returnStateChildren(self.context.root,stmt)
            else:
                self.value = False
                self.outcome = EvalOutcomes().setPossible()

        if not interpreted and len(self.errors) == 0:
            self.createError('Cannot interpret this expression')

        if self.agent.verboseMode(2):
            print 'END   evaluating expression '+self.expr.tag+' at '+self.label+' with result: '+(self.getStringValue() if self.isSuccess() else self.getOutcome().tostring())


    def doText(self):
        cfgNode = self.context.root.lookupString(False,self.text,None)
        if cfgNode != None:
#            print 'DEBUG: this string was found as variable ref: '+self.text
#            print cfgNode.getPath('.')
#            print self.context.details()
            self.value = cfgNode
        else:
            self.value = self.text

class Goal:
    def __init__(self,agent):
        self.proto = None
        self.method = None
        self.variables = []
        self.errors = []
        self.tempFiles = []
        self.agent = agent
        self.parent = None

    def cfgTopGoal(self,name,remainingArgString):
        self.protoName = name
        self.name = self.agent.allocateGoalName(name)
        self.context = self.agent.defaultEvalContext(name,'Evaluation context for goal '+self.name)
        goalNode = self.context.root.lookupTermList(True,['goal'],None)
        goalNode.setupStruct()
        self.args = remainingArgString

    def cfgSubGoal(self,name,parent,argContext,argXML,remainingArgString):
        self.protoName = name
        self.name = self.agent.allocateGoalName(name)
        self.parent = parent
        self.context = self.agent.defaultEvalContext(name,'Evaluation context for subgoal '+self.name)
        goalNode = self.context.root.lookupTermList(True,['goal'],None)
        goalNode.setupStruct()
        if self.agent.verboseMode(1):
            print 'BEGIN configuring goal %s at %s:%d' % (name,argXML._file_name,argXML._start_line_number)
        goalNode.initStateChildren(self.agent.solver,argContext,argXML)
        if self.agent.verboseMode(1):
            print 'END   configuring goal %s at %s:%d' % (name,argXML._file_name,argXML._start_line_number)

        self.args = remainingArgString

    def setProto(self,xmlProto):
        self.proto = xmlProto

        # allocate state for <variable> tags under <goalProto>
        goalNode = self.context.root.lookupTermList(True,['goal'],self.agent)
        goalNode.initStateChildren(self.agent.solver,self.agent.state,xmlProto)

        # handle state overrides from cmdline
        parser = argparse.ArgumentParser()
        parser.add_argument('assignments',nargs='*')
        goalArgs = parser.parse_args(self.args)
        for assignment in goalArgs.assignments:
            tokens = assignment.split('=')
            if len(tokens) != 2:
                self.createError('Expected goal assignments but instead found command line argument: '+assignment)
            else:
#                print 'DEBUG: parsed command-line assignment of '+tokens[0]+' := '+tokens[1]
                lhs = self.context.root.lookupTermList(False,tokens[0].split('.'),Evaluator(self.agent,self.context,None).setString(tokens[1]))
                rhs = Evaluator(self.agent,self.context,None)
                rhs.setString(tokens[1])
                rhs.evaluate()
                if lhs == None:
                    #self.createError('Unable to evaluate '+tokens[0]+'\n'+self.context.details())
                    True
#                elif rhs == None:
#                    self.createError('Unable to evaluate'+tokens[1])
                elif not rhs.isSuccess():
#                    print 'DEBUG: cannot assign '+lhs.getPath('.')+' := '+jsonpickle.encode(rhs.getValue())
                    self.addError(rhs.errors[0])
                else:
#                    print 'DEBUG: assign '+lhs.getPath('.')+' := '+jsonpickle.encode(rhs.getValue())
                    lhs.setValue(rhs.value)

        if self.agent.verboseMode(1):
            print 'BEGIN configuration computed by Goal.setProto '+self.name
            print self.context.details()
            print 'END   configuration computed by Goal.setProto '+self.name
                    


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
        if type(error) in (tuple,list):
            for item in error:
                self.errors.append(item)
        else:
            self.errors.append(error)

    def createErrorAt(self,xmlDef,error):
        errMsg = '%s:%d.%d: %s' % (xmlDef._file_name,xmlDef._start_line_number,xmlDef._start_column_number,error)
        self.errors.append(errMsg)

    def createError(self,error):
        self.errors.append(error)

    def hasErrors(self):
        return len(self.errors) != 0

    def isSuccess(self):
        return len(self.errors) == 0

    def checkPre(self):
        preChecks = self.proto.findall('pre')
        for preCheck in preChecks:
#            if args.verbose:
#                print "Checking "+jsonpickle.encode(preCheck)
            self.checkExpr(preCheck)
        if not self.isSuccess():
            self.context.reconfigure(self.agent.solver.state,'goal')
            controller = ConfigController(self.context)
            self.addError(controller.printText())

    def checkPost(self):
        preChecks = self.proto.findall('pre')
        for preCheck in preChecks:
#            if args.verbose:
#                print "Checking "+jsonpickle.encode(preCheck)
            self.checkExpr(preCheck)

    def evalConditions(self,condTag,xml):
        result = EvalOutcomes()
        result.setTrue()
        conditions = xml.findall(condTag)
        for condition in conditions:
            result = result and self.evalCondition(condition[0])
        return result

    def evalCondition(self,condElement):
        evalResult = Evaluator(self.agent,self.context,None)
        evalResult.setXML(condElement)
        evalResult.evaluate()
        if(evalResult.getOutcome().isTrue()):
            return EvalOutcomes().setTrue() if toBool(evalResult.getRvalue()) else EvalOutcomes().setFalse()
        else:
            return evalResult.getOutcome()

    def solveConditions(self,condTag,xml):
        conditions = xml.findall(condTag)
        result = True
        for condition in conditions:
            code = self.evalCondition(condition[0])
            if result and code.isPossible():
                if self.agent.verboseMode(1):
                    print 'PRECONDITION REQUIRES '+condition[0].tag+' '+str(condition._start_line_number)
                subgoals = condition[0].findall('goalCompleted')
                if condition[0].tag == 'goalCompleted':
                    subgoals.append(condition[0])
                for xml in subgoals:
                    if self.agent.verboseMode(1):
                        print 'PRECONDITION REQUIRES SUBGOALS '+str(condition._start_line_number)
                    goalName = xml.get('name')
                    goalConfig = Config(goalName,'Subgoal configuration',self.agent.solver)
                    goalConfig.setup('goal',xml)
                    subgoal = Goal(self.agent)
                    subgoal.cfgSubGoal(goalName,self,self.context,xml,self.agent.solver.remainingArgString)
                    subgoal.pursue()
                    if not subgoal.isSuccess():
                        result = False

        return result

    def checkExpr(self,preCheck):
        checkResult = Evaluator(self.agent,self.context,None)
        checkResult.setXML(preCheck[0])
        checkResult.evaluate()
        if not checkResult.isSuccess():
            if self.agent.verboseMode(1) and len(checkResult.errors) > 0:
                print "ERROR: While checking <%s>," % preCheck.tag
                for error in checkResult.errors:
                    print "       "+error                        
            for error in checkResult.errors:
                self.addError(error)
        elif not toBool(checkResult.getRvalue()):
            self.createErrorAt(preCheck,'Pre check failed '+ElementTree.tostring(preCheck))

    def subsumedBy(self, other):
        if(self.protoName != other.protoName):
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
        result += self.name
        result += '('
        result += self.context.toString()
        result += ')'
        if self.proto is not None:
            result += ' %s:%d' % (self.proto._file_name,self.proto._start_line_number)
        if self.method is not None:
            result += ' %s:%d' % (self.method._file_name,self.method._start_line_number)
        return result

    def pursue(self):
        if self.agent.goalsMode(1):
            print '# BEGIN Pursuing this goal: '+self.toString()
            if self.agent.verboseMode(1):
                print self.context.details()

        if not self.proto and self.isSuccess():
            if self.agent.verboseMode(1):
                print 'Searching for prototype for goal '+self.protoName
            proto = self.agent.solver.getDefinitionByTypeAndName('goalProto',self.protoName)        
            if(proto == None):
                self.createError('No defintion found for goalProto with name '+self.protoName)
                return
            self.setProto(proto)
            if self.agent.verboseMode(1):
                print 'Goal %s uses prototype %s at %s:%d' % (self.name,self.proto.get('name'),self.proto._file_name,self.proto._start_line_number)

        if self.proto is not None:
            self.agent.beginStatement(self.proto,self.context)

        canSkip = False
        posts = self.proto.findall('post')
        if self.agent.solver.args.execute and len(posts) > 0:
            canSkip = True
            for post in posts:                
                checkPostBefore = Evaluator(self.agent,self.context,None)
                checkPostBefore.setXML(post[0])
                checkPostBefore.evaluate()
                canSkip = canSkip and checkPostBefore.value
            if canSkip and self.agent.verboseMode(1):
                print 'SKIP '+self.toString()+' because postconditions are already satisfied'

        if not canSkip and not self.method and self.isSuccess():
            methods = self.agent.solver.getDefinitions('method')
            if(len(methods) == 0):
                self.createError(self.name+' has no methods defined')
                return
            methods.reverse()

            # look for methods for which <pre> is already solved
            dependent = []
            for method in methods:
                if self.method == None:
                    if method.get('targetGoalType') == self.protoName:
                        code = self.evalConditions('pre',method)
                        if code.isTrue():
                            self.method = method
                            if self.agent.verboseMode(1):
                                print 'SELECTED '+method.get('name')+' to achieve goal '+self.name
                        elif code.isFalse():
                            if self.agent.verboseMode(1):
                                print 'REJECTED '+method.get('name')+' to achieve goal '+self.name
                        else:
                            dependent.append(method)
                            if self.agent.verboseMode(1):
                                print 'QUEUED   '+method.get('name')+' to achieve goal '+self.name

            for method in dependent:
                if self.method == None:                    
                    code = self.solveConditions('pre',method)
                    if code == True:
                        self.method = method
                    elif self.agent.verboseMode(1):
                        print 'UNSOLVABLE '+method.get('name')+' to achieve goal '+self.name

            if self.method == None:
                self.createError('No method found to solve %s' % self.toString())

        if not canSkip and self.isSuccess():
            self.checkPre()

        if not canSkip and self.method != None and self.isSuccess():
            self.agent.beginStatement(self.method,self.context)
            for stmt in self.method.findall('*'):
                self.execute(stmt)
            self.agent.endStatement(self.method,self.context)

        if self.agent.goalsMode(1):
            if not self.isSuccess():
                for error in self.errors:
                    print 'Goal failed b/c of error: '+error
            print '# END   Pursuing this goal: '+self.toString()+' (success: '+('True' if self.isSuccess() else 'False')+')'
            if self.agent.verboseMode(1):
                print self.context.details()
        if self.proto is not None:
            self.agent.endStatement(self.proto,self.context)

    def execute(self,stmt):
        self.execute_r(self.context.root.lookupTermList(True,['goal'],self),stmt)

    def execute_r(self,contextPre,stmt):
        self.agent.beginStatement(stmt,self.context)
        context = contextPre
        if 'name' in stmt.attrib:
            context = context.lookupTermList(True,[stmt.get('name')],self)
            if stmt.tag == 'struct' or stmt.tag == 'goalCompleted' or stmt.tag == 'goalProto':
                context.setupStruct()
            if self.agent.verboseMode(1):
                print 'ENTER CONTEXT '+context.getPath('.')
        if stmt.tag == 'pre':
            self.checkExpr(stmt)
        elif stmt.tag == 'label':
            context = context.lookupTermList(True,[stmt.get('name')],self)
            context.setupStruct()
        elif stmt.tag == 'find':
            starts = []
            ambigStarts = False
            for child in stmt:
                if child.tag == 'in':
                    grandchildren = child.findall('*')
                    evaluator = Evaluator(self.agent,self.context,self)
                    evaluator.setXML(grandchildren[0])
                    evaluator.evaluate()
                    if not evaluator.isSuccess():
                        for error in evaluator.errors:
                            self.createErrorAt(child,error)
                    else:
                        start = evaluator.getRvalue()
                        if start != None:
                            starts.append(evaluator.getRvalue())
                        elif self.agent.solver.args.execute:
                            self.createErrorAt(child,'<in> expression could not be evaluated')
                        else:
                            ambigStarts = True
                elif child.tag == 'do':
                    if ambigStarts:
                        if self.agent.verboseMode(1):
                            print 'BEGIN find/do at (possible) item with symbol %s' % stmt.get('symbol')
                        self.execute_r(context,child)
                        if self.agent.verboseMode(1):
                            print 'END   find/do at (possible) item with symbol %s' % stmt.get('symbol')
                    else:
                        if self.agent.verboseMode(1):
                            print 'find/do begins with %d search starting points' % len(starts)
                        for start in starts:
                            if self.agent.verboseMode(1):
                                print 'BEGIN find/do at starting point %s' % str(start)
                            for item in start:
                                if self.agent.verboseMode(1):
                                    print 'BEGIN find/do at item %s' % str(item)
                                symbol = self.context.root.lookupTermList(True,[stmt.get('symbol')],self)
                                ConfigWrap(symbol).assign(item)
                                self.execute_r(context,child)
                                if self.agent.verboseMode(1):
                                    print 'END   find/do at item %s' % str(item)
                            if self.agent.verboseMode(1):
                                print 'END   find/do at starting point %s' % str(start)
        elif stmt.tag == 'do':
            for child in stmt:
                if self.isSuccess():
                    self.execute_r(context,child)
                else:
                    print 'WARNING: find/do is skipping statement at %s:%d because a previous statement failed' % (child._file_name,child._start_line_number)
                    print '\n'.join(self.errors)
        elif stmt.tag == 'repeat':
            count = None
            for child in stmt:
                if child.tag == 'count':
                    count = Evaluator(self.agent,self.context,self)
                    count.setXML(child[0])
                    count.evaluate()

            if count != None:
                for index in range(0,int(count.getRvalue())):
                    if self.agent.verboseMode(1):
                        print 'BEGIN %s[%d]' % (stmt.get('name'),index)
                    for child in stmt:
                        if child.tag != 'count':
                            if self.isSuccess():
                                self.execute_r(context,child) # !! wrong, should have subcontext with index defined
                    if self.agent.verboseMode(1):
                        print 'END %s[%d]' % (stmt.get('name'),index)
        elif stmt.tag == 'task':
            if self.agent.verboseMode(1):
                print 'BEGIN Task %s' % stmt.get('name')
            for sub in stmt:
                if self.isSuccess():
                    self.execute_r(context,sub)
            if self.agent.verboseMode(1):
                print 'END   Task %s' % stmt.get('name')
        elif stmt.tag == 'shell':
            sys.stdout.flush()
            children = stmt.findall('*')
            lastCommand = (None,None)
            shellCommand = None
            for child in children:
                if(child.tag == 'command'):
                    shellCommand = self.agent.interpolateInner(self.context,child,self)
                if(child.tag == 'send'):
                    cmd = ''
                    if(shellCommand != None):
                        cmd = shellCommand+' '

                    cmd += self.agent.interpolateInner(self.context,child,self)
                    cmdList = glob.glob(os.path.expanduser(cmd))
                    if len(cmdList) == 0:
                        cmdList = [cmd]

                    for cmd in cmdList:
                        if self.hasErrors():
                            print "ERRORS %s" % cmd
                        elif self.agent.solver.args.execute:
                            if(shellCommand != None):
                                cmd = re.sub('\s*\n\s*',' ',cmd.strip())

                            if self.agent.echoMode():
                                print "BEGIN <shell><send>%s</send></shell>" % cmd

#                            scriptFile = tempfile.NamedTemporaryFile(prefix='script')
                            timeout = None
                            if 'timeout' in child.attrib:
                                timeout = child.get('timeout')

                            if(shellCommand != None):
                                lastCommand = pexpect.run(cmd,withexitstatus=1,timeout=timeout)
                            else:
                                scriptFile = open('tempScript','wt')
                                print >>scriptFile, cmd
                                scriptFile.flush()
                                scriptFile.close()

                                if self.agent.verboseMode(1):
                                    print 'SCRIPT is stored in temporary aux file %s' % scriptFile.name

                                lastCommand = pexpect.run('/bin/bash %s' % scriptFile.name,withexitstatus=1,timeout=timeout)

                            if self.agent.verboseMode(1):
                                print lastCommand[0]
                            if 'name' in child.attrib:
                                stdoutVar = context.lookupTermList(True,[child.get('name'),'stdout'],self)
                                rcVar = context.lookupTermList(True,[child.get('name'),'rc'],self)
                                stdoutVar.setValue(lastCommand[0])
                                rcVar.setValue(lastCommand[1])
                            onFail = 'stop'
                            if 'onFail' in child.attrib:
                                onFail = child.get('onFail')
                            if lastCommand[1] != 0 and onFail != 'ignore':
                                self.createErrorAt(child,'COMMAND RC=%d : %s' % (lastCommand[1],cmd))
                                lines = '\n'.split(lastCommand[0])
                                for line in lines:
                                    self.createErrorAt(child,line)
                            if self.agent.echoMode():
                                print "END   <shell><send>%s</send></shell>" % cmd
                        else:
                            print "PLAN  %s" % cmd
                elif(child.tag == 'receive'):
                    cmd = self.agent.interpolateInner(self.context,child,self)

                    print "EXPECT %s" % cmd
                    if self.hasErrors():
                        print "ERRORS %s" % cmd
                    elif self.agent.solver.args.execute:
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
            print >>file, self.agent.interpolateInner(self.context,stmt,self)
            file.flush()
        elif stmt.tag == 'op' or stmt.tag == 'get' or stmt.tag == 'python':
            evaluator = Evaluator(self.agent,self.context,None)
            evaluator.setXML(stmt)
            evaluator.evaluate()
            if not evaluator.isSuccess():
                self.createErrorAt(stmt,'Expected hive statement or expression')
                for error in evaluator.errors:
                    self.errors.append(error)
            elif toBool(evaluator.getRvalue()) != True:
                self.createErrorAt(stmt,'Statement failed to execute or expression returned zero/False')                
        elif stmt.tag == 'goalCompleted':
            goalName = stmt.get('name')
#            goalConfig = Config(goalName,'Subgoal configuration',self.agent.solver)
#            goalConfig.setup('goal',stmt)
            subgoal = Goal(self.agent)
            subgoal.cfgSubGoal(goalName,self,self.context,stmt,self.agent.solver.remainingArgString)
            subgoal.pursue()
            if not subgoal.isSuccess():
                result = False
            else:
                subgoal.context.root.returnStateChildren(self.context.root,stmt)
        else:
            if self.agent.verboseMode(1):
                print 'SKIP tag %s which is neither a statement nor an expression' % stmt.tag

        if 'name' in stmt.attrib:
            if self.agent.verboseMode(1):
                print 'RETURN CONTEXT '+contextPre.getPath('.')
        self.agent.endStatement(stmt,self.context)

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

class ConfigWrap:
    def __init__(self,node):
        self.__dict__['node'] = node

    def __len__(self):
        myNode = self.__dict__['node']
        return len(myNode.elements)

    def __getitem__(self,key):
        myNode = self.__dict__['node']
        sub = myNode.getElement(key)
        return ConfigWrap(sub)

    def __setitem__(self,attr,value):
        myNode = self.__dict__['node']
        sub = myNode.getElement(key)
        ConfigWrap(sub).assign(value)

    def assign(self,value):
        myNode = self.__dict__['node']
        if myNode.rootConfig.solver.verboseMode(1):
            print 'ConfigWrap.assign %s := %s' % (myNode.getPath('.'),str(value))

#        if isinstance(value,object):
#            for key,value in value.__dict__.iteritems():
#                myNode.setAttr(key,value,True)
#        elif type(value) in (tuple,list):
#            index = 0
#            for item in value:
#                myNode.setElement(index,item,True)
#                index += 1
#        else:
        myNode.setValue(value)

    def __getattr__(self,attr):
        myNode = self.__dict__['node']
        sub = myNode.getAttr(attr)
        if isinstance(sub,ConfigNode):            
            return ConfigWrap(sub)
        return sub

    def __setattr__(self,attr,value):
        myNode = self.__dict__['node']
        sub = myNode.getAttr(attr)
        ConfigWrap(sub).assign(value)

class ConfigNode:    
    def __init__(self,rootConfig,name):
        if name == None:
            raise 'Cannot use an empty name'
        self.name = name
        self.rootConfig = rootConfig
        self.values = []
        self.selected = None
        self.assigned = None
        self.fields = None
        self.elements = None
        self.parent = None
        self.typeName = None

    def __len__(self):
        if self.elements != None and len(self.elements) > 0:
           return len(self.elements)
        elif self.fields != None and len(self.fields.keys()) > 0:
            return len(self.fields.keys())
        else:
            return 0

    def __iter__(self):
        if self.elements != None and len(self.elements) > 0:
            return self.elements.__iter__()
        elif self.fields != None and len(self.fields) > 0:
            return self.fields.iteritems()
        else:
            return [].__iter__()

    def __str__(self):
        return self.getPath('.')

    def reset(self):
        self.selected = None
        self.assigned = None
        self.fields = None
        self.elements = None

    def configureMapping(self,mapping):
        for key,value in self.fields.iteritems():
            mapping[key] = ConfigWrap(value)

    def copyFrom(self,other):
        self.assigned = other
        self.copyFrom_r(other)

    def copyFrom_r(self,other):
#        print 'DEBUG: BEGIN ConfigNode.copyFrom('+self.getPath('.')+' <= '+other.getPath('.')+')'
        for otherVal in other.values:
            self.values.append(otherVal)
        if other.elements != None:
            if self.elements == None:
                self.elements = []
            for otherElement in other.elements:
                self.elements.append(otherElement)
        if other.selected != None:
            self.selected = other.selected
#            print 'copyFrom '+self.getPath('.')+' := '+other.getPath('.')+' == '+jsonpickle.encode(self.selected)
        if other.fields != None:
            if self.fields == None:
                self.fields = dict()
            for key,field in other.fields.iteritems():
                if key not in self.fields:
                    self.fields[key] = ConfigNode(self.rootConfig,key)
                    self.fields[key].setParent(self)
                self.fields[key].copyFrom(other.fields[key])
            self.typeName = other.typeName
 #       print 'DEBUG: END   ConfigNode.copyFrom('+self.getPath('.')+' <= '+other.getPath('.')+')'

    def details(self,recursive=True):
        result = ''
        if not isinstance(self.getValue(),ConfigNode):
            result += '%s = %s (%s)\n' % (self.getPath('.'),self.getValue(),self.typeName if self.typeName != None else '?')
        if recursive:
            if self.fields != None:
                for key,field in self.fields.iteritems():
                    result += field.details()
            if self.elements != None:
                for item in self.elements:
                    result += item.details()
        return result


    def setupStruct(self):
        if self.getPath('.') == 'setupCassandraNode.goal.dataStaxYumRepo':
            raise RuntimeError('GOTCHA')
        if self.fields == None:
            self.fields = dict()

    def setupList(self):
        if self.elements == None:
            self.elements = []

    def initStateNode(self,solver,context,xml):
        if xml.tag == 'struct':
            self.setupStruct()
        elif xml.tag == 'list':
            self.setupList()
        node = self.lookupTermList(True,[xml.get('name')],solver)
        node.initStateChildren(solver,context,xml)
        return node

    def initStateChildren(self,solver,context,xml):
        if solver.args.verbose > 0:
            print "BEGIN initState(%s) at %s:%d" % (self.getPath('.'),xml._file_name,xml._start_line_number)
        if xml.tag == 'struct' or xml.tag == 'goalCompleted' or xml.tag == 'goalProto':
#            if self.getValue() == None:
#                struct = dict()
#                self.setValue(struct)
#                print 'initState sets '+self.getPath('.')+' to new struct'
#            else:
#                struct = self.getValue()
            self.setupStruct()
            for child in xml:
                childName = child.get('name')
                if childName != None:
                    self.initStateNode(solver,context,child)
#                struct[child.get('name')] = node.getValue()
        elif xml.tag == 'variable' or xml.tag == 'list':
            if xml.tag == 'list':
                self.setupList()
            if len(xml) > 0 or xml.text:
                result = Evaluator(solver,context,None)
                result.setXML(xml)
                result.evaluate()
                if not result.isSuccess():
                    print 'Unable to interpret this XML expression: '+result.errors[0]
                elif result.getLvalue() != None:
                    self.copyFrom(result.getLvalue())
                elif result.getRvalue() != None:
                    self.setValue(result.getRvalue())

        if 'type' in xml.attrib:
            self.typeName = xml.get('type')

        if solver.args.verbose > 0:
            print "END   initState(%s) at %s:%d" % (self.getPath('.'),xml._file_name,xml._start_line_number)

    def returnStateChildren(self,otherNode,xml):
        if self.rootConfig.solver.verboseMode(2):
            print "BEGIN returnState(%s,%s) at %s:%d" % (self.getPath('.'),otherNode.getPath('.'),xml._file_name,xml._start_line_number)

        for myChild in xml:
            myChildName = myChild.get('name')
            if myChildName != None:
                for otherChild in myChild:
                    if otherChild.tag == 'get' or otherChild.tag == 'set':
                        myNode = self.lookupTermList(False,['goal',myChildName],self.rootConfig.solver)
                        otherNode2 = otherNode.lookupString(False,otherChild.text,self.rootConfig.solver)
                        otherNode2.reset()
                        otherNode2.copyFrom(myNode)

        if self.rootConfig.solver.verboseMode(2):
            print "END   returnState(%s,%s) at %s:%d" % (self.getPath('.'),otherNode.getPath('.'),xml._file_name,xml._start_line_number)


    def getAttr(self,attr):
        if self.fields == None:
            if self.selected != None:
                return getattr(self.selected,attr)
            raise RuntimeError('%s is not defined as a struct with attributes to get' % self.getPath('.'))
        return self.fields[attr]

    def setAttr(self,attr,value,alloc=False):
        if self.fields == None:
            raise RuntimeError('%s is not defined as a struct with attributes to set' % self.getPath('.'))
        if attr not in self.fields and alloc:
            newNode = ConfigNode(self.rootConfig,attr)
            newNode.setParent(self)
            self.fields[attr] = newNode
        self.fields[attr].setValue(value)

    def getElement(self,key):
        if self.elements == None:
            raise RuntimeError('%s is not defined as a list with elements' % self.getPath('.'))
        return self.elements[key]

    def setElement(self,key,value):
        if self.elements == None:
            raise RuntimeError('%s is not defined an array' % getPath('.'))
        self.elements[key].setValue(value)

    def setValue(self,value):
        if isinstance(value,ConfigNode):
            if self.rootConfig.solver.args.verbose > 0:
                print 'ConfigNode.setValue copies '+value.getPath('.')+' to '+self.getPath('.')
            self.copyFrom(value)
        else:
            if self.rootConfig.solver.args.verbose > 0:
                print 'ConfigNode.setValue assigns '+self.getPath('.')+' to '+str(value)
            self.selected = value

    def getValue(self):
        if self.assigned:
            return self.assigned
        elif self.elements != None:
            return self.elements
        elif self.fields != None:
            return self.fields
        return self.selected        

    def setParent(self,parent):
        self.parent = parent

    def getPath(self,char,prefixNode=None,absolute=True):
        result = ''
        if self != prefixNode:
            if self.parent:
                if self.parent.parent or absolute:
                    result += self.parent.getPath(char,prefixNode,absolute)
                    result += char
            result += self.name
        return result

    def lookupString(self,create,pathString,errHandler):
        if pathString == '':
            raise RuntimeError('pathString is empty')
        pathTerms = pathString.split('.')
        return self.lookupTermList(create,pathTerms,errHandler)

    def lookupTermList(self,create,pathTerms,errHandler):
        result = None
        if self.rootConfig.solver.verboseMode(2):
            print 'BEGIN lookupTermList path: '+self.getPath('.')+' remainder: '+'.'.join(pathTerms)
        if(len(pathTerms) == 0):
            result = self
#            print 'DEBUG: no more path terms'
        elif pathTerms[0] == '':
            if errHandler != None: errHandler.createError('empty field name at %s' % self.getPath('.'))
        elif self.fields == None:
            if len(pathTerms) == 1 and self.selected != None and isinstance(self.selected,object):
                return getattr(self.selected,pathTerms[0])
            if errHandler != None: errHandler.createError('%s is not configured as struct with any fields while looking for field %s' % (self.getPath('.'),pathTerms[0]))
        else:
            if pathTerms[0] not in self.fields:
#                print 'DEBUG: field '+pathTerms[0]+' is missing from '+self.getPath('.')
                if create:
                    newNode = ConfigNode(self.rootConfig,pathTerms[0])
                    newNode.setParent(self)
                    self.fields[pathTerms[0]] = newNode
                    if len(pathTerms) > 1:
                        newNode.setupStruct()
                elif errHandler != None:
                    errHandler.createError('No field named '+pathTerms[0]+' in expression '+self.getPath('.')+' fields include '+(','.join(self.fields.keys())))
                    return None
                else:
                    if self.rootConfig.solver.args.verbose:
                        print 'END lookupTermList path: '+self.getPath('.')+' remainder: '+'.'.join(pathTerms)
                    return None

#            print 'DEBUG: found field named '+pathTerms[0]
            result = self.fields[pathTerms[0]].lookupTermList(create,pathTerms[1:],errHandler)
        if self.rootConfig.solver.verboseMode(2):
            print 'END lookupTermList path: '+self.getPath('.')+' remainder: '+'.'.join(pathTerms)
            print self.details(False)
        return result

    def reconfigure(self,stateConfig,prefixNode):
 #       if self.typeName == None:
 #           print 'DEBUG: path has no type %s' % self.getPath('.')
        if self.typeName != None and self.selected == None:
 #           print 'DEBUG: path %s needs configuration type %s' % (self.getPath('.'),self.typeName)
            self.values = stateConfig.findCandidatesByTypeName(self.typeName)
        if len(self.values) == 0:
            if self.fields != None:
                for key,field in self.fields.iteritems():
                    field.reconfigure(stateConfig,prefixNode)
            if self.elements != None:
                for element in self.elements:
                    element.reconfigure(stateConfig,prefixNode)

    def findCandidatesByTypeName(self,typeName,values):
#        print 'DEBUG: checking path %s for type %s' % (self.getPath('.'),typeName)
        if self.typeName == typeName:
 #           print 'DEBUG: found path %s has type %s' % (self.getPath('.'),typeName)
            values.append(self.getPath('.',absolute=False))
        if self.fields != None:
            for key,field in self.fields.iteritems():
                field.findCandidatesByTypeName(typeName,values)
        if self.elements != None:
            for element in self.elements:
                element.findCandidatesByTypeName(typeName,values)

    def tallyOptions(self,options):
        if len(self.values) > 0:
            options[self.getPath('.',absolute=False)] = self.values
        if self.fields != None:
            for key,field in self.fields.iteritems():
                field.tallyOptions(options)
        if self.elements != None:
            for element in self.elements:
                element.tallyOptions(options)

    def tallyAssigns(self,options):
        if self.selected != None:
            options[self.getPath('.',absolute=False)] = self.selected
        elif self.assigned != None:
            options[self.getPath('.',absolute=False)] = self.assigned
        elif len(self.values) > 0:
            pass

        if self.assigned == None:
            if self.fields != None:
                for key,field in self.fields.iteritems():
                    field.tallyAssigns(options)
            if self.elements != None:
                for element in self.elements:
                    element.tallyAssigns(options)

    def isDefined(self):
        return self.selected != None or self.elements != None or self.fields != None or self.assigned != None

class Config:
    def __init__(self,name,desc,solver):
        self.root = ConfigNode(self,name)
        self.desc = desc
        self.solver = solver

    def setup(self,name,xmlProto):
        self.root.initStateChildren(self.solver,self.solver.state,xmlProto)
#        print 'DEBUG: initial state of %s is:\n%s' % (self.desc,self.details())

    def toString(self):
        goalNode = self.root.lookupTermList(False,['goal'],None)
        if goalNode == None:
            return ''

        options = dict()
        goalNode.tallyAssigns(options)
        count = 0
        result = ''
        for path,value in options.iteritems():
            if count != 0:
                result += ','
            lines = str(value).split('\n')
            if len(lines) == 0:
                lines = ['']
            result += '%s=%s' % (path,lines[0])
            count += 1
        return result

    def details(self):
        return self.root.details()

    def copyFrom(self,other):
        self.root.copyFrom(other.root)

    def reconfigure(self,stateConfig,prefix):
#        print 'DEBUG: BEGIN Config.reconfigure'
        self.root.lookupTermList(False,['goal'],None).reconfigure(stateConfig,self.root.lookupTermList(False,[prefix],None))
#        print 'DEBUG: END   Config.reconfigure'

    def findCandidatesByTypeName(self,typeName):
#        print 'DEBUG: looking for candidates of type %s' % typeName
        values = []
        self.root.findCandidatesByTypeName(typeName,values)
        return values

    def tallyOptions(self):
        options = dict()
        self.root.tallyOptions(options)
        return options

    def initPath(self,method,symbolPath,value):
        configNode = self.root.lookupTermList(True,symbolPath,None)
        configNode.setValue(value)

class ConfigController:
    def __init__(self,config):
        self.config = config

    def printText(self):
#        print 'DEBUG: ConfigController.printText called'
        result = 'Additional options must be configured with the command line. Try these suggestions:\n'
        options = self.config.tallyOptions()
#        print 'DEBUG: %d options returned' % len(options)
        for path in options.keys():
            result += 'Choose One:\n'
            for value in options[path]:
                result += '     %s=%s\n' % (path,value)
            result += '\n'
        return result
