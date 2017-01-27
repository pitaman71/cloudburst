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

class Solver:
    def __init__(self,xmlAgentProgram,solverArgs,remainingArgString):
        self.goals = []
        self.goalsByName = dict()
        self.state = Config(xmlAgentProgram.getroot().get('name'),'State of agent '+xmlAgentProgram.getroot().get('name'))
        self.result = True
        self.xmlAgentProgram = xmlAgentProgram
        self.args = solverArgs
        self.remainingArgString = remainingArgString
        self.statementStack = []

    def hasGoal(self,goal):
        goals = [x for x in self.goals if goal.subsumedBy(x)]
        return len(goals)>0

    def addTopGoalByName(self,goalName):
        goal = Goal(self)
        goal.cfgTopGoal(goalName)
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

    def hasErrors(self):
        return len(self.errors) > 0

    def initialize(self):
        for stateNode in self.xmlAgentProgram.findall('state'):
            if self.args.verbose:
                print 'BEGIN Processing <state> element at '+str(stateNode._start_line_number)
            self.state.root.initState(self,stateNode)
            if self.args.verbose:
                print 'END   Processing <state> element at '+str(stateNode._start_line_number)

#    def terminate(self):
        # nothing to do        

    def defaultEvalContext(self,goalName,desc):
        result = Config(goalName,desc)
        result.copyFrom(self.state)

        result.root.initPath('Solver.defaultEvalContext',['host','platform'],sys.platform)
        result.root.initPath('Solver.defaultEvalContext',['host','uname'],os.uname())
        result.root.initPath('Solver.defaultEvalContext',['host','hostname'],socket.gethostname())
        result.root.initPath('Solver.defaultEvalContext',['host','hostip'],socket.gethostbyname(socket.gethostname()))
        return result

    def interpolateInner(self,context,elt):
        cmd = ''
        if elt.text:
            cmd += elt.text
        for child in elt:
            if(ElementTree.iselement(child)):
                sub = Evaluator(self,context)
                sub.setXML(child)
                sub.evaluate()
                if sub.isSuccess():
                    cmd += sub.getRvalue()
                else:
                    cmd += ElementTree.tostring(child)
            else:
                cmd += child.text
            if child.tail:
                cmd += child.tail
#        if elt.tail:
#            cmd += elt.tail
        return cmd

    def beginStatement(self,statement):
        self.statementStack.append(statement)
        if self.args.narrate:
            descriptions = statement.findall('describe')
            if len(descriptions) > 0:
                evalResult = Evaluator(self,self.state)
                evalResult.setXML(descriptions[0])
                evalResult.evaluate()
                print "BEGIN # "+evalResult.value

    def endStatement(self,statement):
        if self.args.narrate:
            descriptions = statement.findall('describe')
            if len(descriptions) > 0:
                evalResult = Evaluator(self,self.state)
                evalResult.setXML(descriptions[0])
                evalResult.evaluate()
                print "END   # "+evalResult.value
        self.statementStack.pop()

    def findGoal(self,goalName,goalConfig):
        if goalName in self.goalsByName:
            for goal in self.goalsByName[goalName]:
                if goal.context.covers(goalConfig):
                    return goal
        return None

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
    def __init__(self,solver,context):
        self.solver = solver
        self.context=context
        self.errors = []
        self.outcome = EvalOutcomes().setTrue()

    def setXML(self,xmlExpr):
        self.expr=xmlExpr
        self.label = '%s:%d.%d' % (self.expr._file_name,self.expr._start_line_number,self.expr._start_column_number)

    def setString(self,text):
        self.text=text
        self.label = '"%s"' % text

    def setValue(self,value):
        self.outcome = EvalOutcomes().setTrue()
        self.value = value

    def getRvalue(self):
        if isinstance(self.value,ConfigNode):
            return self.value.getValue()
        else:
            return self.value

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
            self.value = a.value == 0
        elif(op == 'isNoZero'):
            self.value = a.value != 0
        elif(op == 'not'):
            self.value = not a.value
        else:
            self.createError('Unrecognized operator: '+op)

    def isBinaryOperator(self,op):
        return op == 'eq' or op == 'ne' or op == 'gt' or op == 'lt' or op == 'ge' or op == 'le'

    def doBinaryOperator(self,op,a,b):
        self.outomde = a.outcome and b.outcome
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

    def doStruct(self,xml):
        self.value = dict()
        for child in xml:
            subResult = Evaluator(self.solver,self.context)
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
        self.value = a.isSuccess()
        if self.solver.args.verbose and not a.isSuccess():
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
        for child in self.expr:
            sub = Evaluator(self.solver,self.context)
            sub.setXML(child)
            sub.evaluate()
            childResults.append(sub)
        if len(childResults) == 0 and self.expr.text:
            sub = Evaluator(self.solver,self.context)
            sub.setString(self.expr.text)
            sub.doText()
            childResults.append(sub)

        if self.solver.args.verbose:
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
        elif self.expr.tag == 'rvalue' or self.expr.tag == 'string' or self.expr.tag == 'describe':
            if(len(childResults) == 0):
                self.createError('<'+self.expr.tag+'> must always have a child expression')
            else:
                interpreted = True
                self.setValue(childResults[0].value)
                self.outcome = self.outcome and childResults[0].outcome
        elif self.expr.tag == 'struct':
            interpreted = True
            self.doDict(self.expr)
        elif self.expr.tag == 'variable':
            self.doVariable(self.expr)
            if len(childResults) == 0:
                self.createError('No child expression to compute the initial value of '+self.expr.get('name'))
            elif not childResults[0].isSuccess():
                self.addError(childResults[0].errors[0])
            else:
                interpreted = True
                self.setValue(childResults[len(childResults)-1].value)
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
                    cmd += self.solver.interpolateInner(self.context,child)
                    lastReturnCode = pexpect.run(cmd,withexitstatus=1)
                    if self.solver.args.verbose:
                        print "SHELL RC "+str(lastReturnCode[1])+" FROM "+cmd
            valueType = self.expr.get('value')
            if(valueType == 'returnCode'):
                interpreted = True
                self.value = lastReturnCode[1]
        elif self.expr.tag == 'fileTest':
            testType = self.expr.get('type')
            if len(childResults) != 1:
                self.createError('fileTest tag must always have a path as its only child')
            else:
                if self.solver.args.verbose:
                    print "TESTING FILE "+childResults[0].value
                if testType == 'exists':
                    interpreted = True
                    self.value = os.path.exists(childResults[0].value)
        elif self.expr.tag == 'goalCompleted':
            goalName = self.expr.get('name')
            goalConfig = Config(goalName,'Example of completed goal')
            goalConfig.setup(self.solver,self.expr)
            foundGoal = self.solver.findGoal(goalName,goalConfig)
            interpreted = True
            if (foundGoal != None):
                self.value = True
                self.outcome = EvalOutcomes().setTrue()
            else:
                self.value = False
                self.outcome = EvalOutcomes().setPossible()

        if not interpreted and len(self.errors) == 0:
            self.createError('Cannot interpret this expression')

        if self.solver.args.verbose:
            print 'END   evaluating expression '+self.expr.tag+' at '+self.label+' with result: '+(jsonpickle.encode(self.getRvalue()) if self.isSuccess() else self.getOutcome().tostring())


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
    def __init__(self,solver):
        self.name = ''
        self.proto = None
        self.method = None
        self.variables = []
        self.errors = []
        self.tempFiles = []
        self.solver = solver
        self.parent = None

    def cfgTopGoal(self,name):
        self.name = name
        self.context = self.solver.defaultEvalContext(name,'Evaluation context for goal '+self.name)
        self.args = self.solver.remainingArgString

    def cfgSubGoal(self,name,parent,argContext):
        self.name = name
        self.parent = parent
        self.context = self.solver.defaultEvalContext(name,'Evaluation context for subgoal '+self.name)
        goalNode = self.context.root.lookupTermList(True,['goal'],None)
        goalNode.copyFrom(argContext.root)
        self.args = self.solver.remainingArgString

    def setProto(self,xmlProto):
        self.proto = xmlProto

        # allocate state for <variable> tags under <goalProto>
        self.variables = xmlProto.findall('variable')
        for variable in self.variables:                
            lhs = self.context.root.lookupTermList(True,[self.proto.get('symbol'),variable.get('name')],Evaluator(self.solver,self.context).setXML(variable))
            rhs = Evaluator(self.solver,self.context)
            rhs.setXML(variable)
            rhs.evaluate()
            if lhs != None and rhs != None and rhs.isSuccess():
                lhs.setValue(rhs.value)

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
                lhs = self.context.root.lookupTermList(False,tokens[0].split('.'),Evaluator(self.solver,self.context).setString(tokens[1]))
                rhs = Evaluator(self.solver,self.context)
                rhs.setString(tokens[1])
                rhs.evaluate()
                if lhs == None:
                    #self.createError('Unable to evaluate '+tokens[0]+'\n'+self.context.details())
                    True
#                elif rhs == None:
#                    self.createError('Unable to evaluate'+tokens[1])
                elif not rhs.isSuccess():
                    self.addError(rhs.errors[0])
                else:
                    lhs.setValue(rhs.value)

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

    def isSuccess(self):
        return len(self.errors) == 0

    def checkPre(self):
        preChecks = self.proto.findall('pre')
        for preCheck in preChecks:
#            if args.verbose:
#                print "Checking "+jsonpickle.encode(preCheck)
            self.checkExpr(preCheck)

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
        evalResult = Evaluator(self.solver,self.context)
        evalResult.setXML(condElement)
        evalResult.evaluate()
        return evalResult.getOutcome()

    def solveConditions(self,condTag,xml):
        conditions = xml.findall(condTag)
        result = True
        for condition in conditions:
            code = self.evalCondition(condition[0])
            if result and code.isPossible():
                if self.solver.args.verbose:
                    print 'PRECONDITION REQUIRES '+condition[0].tag+' '+str(condition._start_line_number)
                subgoals = condition[0].findall('goalCompleted')
                if condition[0].tag == 'goalCompleted':
                    subgoals.append(condition[0])
                for xml in subgoals:
                    if self.solver.args.verbose:
                        print 'PRECONDITION REQUIRES SUBGOALS '+str(condition._start_line_number)
                    goalName = xml.get('name')
                    goalConfig = Config(goalName,'Subgoal configuration')
                    goalConfig.setup(self.solver,xml)
                    subgoal = Goal(self.solver)
                    subgoal.cfgSubGoal(goalName,self,goalConfig)
                    subgoal.pursue()
                    if not subgoal.isSuccess():
                        result = False

        return result

    def checkExpr(self,preCheck):
        checkResult = Evaluator(self.solver,self.context)
        checkResult.setXML(preCheck[0])
        checkResult.evaluate()
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
            print self.context.details()

        if not self.proto and self.isSuccess():
            protos = self.solver.xmlAgentProgram.findall('goalProto[@name=\''+self.name+'\']')        
            if(len(protos) == 0):
                self.solver.reportError(self.name+' is undefined')
                return
            self.setProto(protos[len(protos)-1])

        if self.proto is not None:
            self.solver.beginStatement(self.proto)

        canSkip = False
        posts = self.proto.findall('post')
        if len(posts) > 0:
            canSkip = True
            for post in posts:                
                checkPostBefore = Evaluator(self.solver,self.context)
                checkPostBefore.setXML(post[0])
                checkPostBefore.evaluate()
                canSkip = canSkip and checkPostBefore.value
            if canSkip and self.solver.args.verbose:
                print 'SKIP '+self.toString()+' because postconditions are already satisfied'

        if not canSkip and not self.method and self.isSuccess():
            methods = self.solver.xmlAgentProgram.findall('method[@targetGoalType=\''+self.name+'\']')
            if(len(methods) == 0):
                self.solver.reportError(self.name+' has no methods defined')
                return
            methods.reverse()

            # look for methods for which <pre> is already solved
            dependent = []
            for method in methods:
                if self.method == None:                    
                    code = self.evalConditions('pre',method)
                    if code == True:
                        self.method = method
                        if self.solver.args.verbose:
                            print 'SELECTED '+method.get('name')+' to achieve goal '+self.name
                    elif code == False:
                            print 'REJECTED '+method.get('name')+' to achieve goal '+self.name
                    else:
                        dependent.append(method)
                        if self.solver.args.verbose:
                            print 'QUEUED   '+method.get('name')+' to achieve goal '+self.name

            for method in dependent:
                if self.method == None:                    
                    code = self.solveConditions('pre',method)
                    if code == True:
                        self.method = method
                    elif self.solver.args.verbose:
                        print 'UNSOLVABLE '+method.get('name')+' to achieve goal '+self.name

        if not canSkip and self.isSuccess():
            self.checkPre()

        if not canSkip and self.method != None and self.isSuccess():
            self.solver.beginStatement(self.method)
            for stmt in self.method.findall('*'):
                self.execute(stmt)
            self.solver.endStatement(self.method)

        if self.solver.args.verbose:
            if not self.isSuccess():
                for error in self.errors:
                    print 'ERROR: '+error
            print 'END   Pursuing this goal: '+self.toString()+' (success: '+('True' if self.isSuccess() else 'False')+')'
        if self.proto is not None:
            self.solver.endStatement(self.proto)

    def execute(self,stmt):
        self.solver.beginStatement(stmt)
        if stmt.tag == 'pre':
            self.checkExpr(stmt)
        elif stmt.tag == 'do':
            for child in stmt:
                self.execute(child)
        elif stmt.tag == 'repeat':
            count = None
            for child in stmt:
                if child.tag == 'count':
                    count = Evaluator(self.solver,self.context)
                    count.setXML(child[0])
                    count.evaluate()

            if count != None:
                for index in range(0,int(count.getRvalue())):
                    if self.solver.args.verbose:
                        print 'BEGIN %s[%d]' % (stmt.get('name'),index)
                    for child in stmt:
                        if child.tag != 'count':
                            self.execute(child)
                    if self.solver.args.verbose:
                        print 'END %s[%d]' % (stmt.get('name'),index)
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
                    shellCommand = self.solver.interpolateInner(self.context,child)
                if(child.tag == 'send'):
                    cmd = ''
                    if(shellCommand != None):
                        cmd = shellCommand+' '

                    cmd += self.solver.interpolateInner(self.context,child)

                    if self.solver.args.pursue:
                        print "SYSTEM %s" % cmd
                        lastCommand = pexpect.run(cmd,withexitstatus=1)
                        if(lastCommand[1] != 0):
                            print "ERROR: shell send failed"
                            print lastCommand[0]
                            exit(1)
                        print lastCommand[0]
                    else:
                        print "PLAN  %s" % cmd
                elif(child.tag == 'receive'):
                    cmd = self.solver.interpolateInner(self.context,child)

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
            print >>file, self.solver.interpolateInner(self.context,stmt)
            file.flush()

        self.solver.endStatement(stmt)

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
        if name == None:
            raise 'Cannot use an empty name'
        self.name = name
        self.rootConfig = rootConfig
        self.values = []
        self.selected = None
        self.fields = dict()
        self.elements = []
        self.parent = None

    def copyFrom(self,other):
        for otherVal in other.values:
            self.values.append(otherVal)
        for otherElement in other.elements:
            self.elements.append(otherElement)
        if other.selected != None:
            self.selected = other.selected
#            print 'copyFrom '+self.getPath('.')+' := '+other.getPath('.')+' == '+jsonpickle.encode(self.selected)
        for key,field in other.fields.iteritems():
            if key not in self.fields:
                self.fields[key] = ConfigNode(self.rootConfig,key)
                self.fields[key].setParent(self)
            self.fields[key].copyFrom(other.fields[key])

    def details(self):
        result = ''
        result += '%s = %s\n' % (self.getPath('.'),self.getValue())
        for key,field in self.fields.iteritems():
            result += field.details()
        return result


    def initState(self,solver,xml):
        if xml.tag == 'struct' or xml.tag == 'state' or xml.tag == 'goalCompleted':
#            if self.getValue() == None:
#                struct = dict()
#                self.setValue(struct)
#                print 'initState sets '+self.getPath('.')+' to new struct'
#            else:
#                struct = self.getValue()
            for child in xml:
                childName = child.get('name')
                if childName != None:
                    node = self.lookupTermList(True,[childName],solver)
                    node.initState(solver,child)
#                struct[child.get('name')] = node.getValue()
        elif xml.tag == 'variable':
            if xml.text != '':
                result = Evaluator(solver,solver.state)
                result.setXML(xml)
                result.evaluate()
                if not result.isSuccess():
                    print 'Unable to interpret this XML expression: '+result.errors[0]
                else:
                    self.setValue(result.value)

    def initPath(self,method,symbolPath,value):
        configNode = self.lookupTermList(True,symbolPath,None)
#        print method+' sets '+configNode.getPath('.')+' to '+jsonpickle.encode(value)
        configNode.setValue(value)

    def setValue(self,value):
        if isinstance(value,ConfigNode):
#            print 'DEBUG: copy '+value.getPath('.')+' to '+self.getPath('.')
            self.copyFrom(value)
        else:
            self.selected = value

    def getValue(self):
        return self.selected        

    def setParent(self,parent):
        self.parent = parent

    def getPath(self,char):
        result = ''
        if self.parent:
            result += self.parent.getPath(char)
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
        if pathString == '':
            raise RuntimeError('pathString is empty')
        pathTerms = pathString.split('.')
        return self.lookupTermList(create,pathTerms,errHandler)

    def lookupTermList(self,create,pathTerms,errHandler):
        result = None
#        print 'DEBUG: BEGIN lookupTermList path: '+self.getPath('.')+' remainder: '+'.'.join(pathTerms)
        if(len(pathTerms) == 0):
            result = self
#            print 'DEBUG: no more path terms'
        else:
            if pathTerms[0] == '':
                raise RuntimeError('empty field name')
            if pathTerms[0] not in self.fields:
#                print 'DEBUG: field '+pathTerms[0]+' is missing from '+self.getPath('.')
                if create:
                    newNode = ConfigNode(self.rootConfig,pathTerms[0])
                    newNode.setParent(self)
                    self.fields[pathTerms[0]] = newNode
                elif errHandler:
                    errHandler.createError('No field named '+pathTerms[0]+' in expression '+self.getPath('.')+' fields include '+(','.join(self.fields.keys())))
                    return None
                else:
#                    print 'DEBUG: END lookupTermList path: '+self.getPath('.')+' remainder: '+'.'.join(pathTerms)
                    return None

#            print 'DEBUG: found field named '+pathTerms[0]
            result = self.fields[pathTerms[0]].lookupTermList(create,pathTerms[1:],errHandler)
#        print 'DEBUG: END lookupTermList path: '+self.getPath('.')+' remainder: '+'.'.join(pathTerms)
        return result

class Config:
    def __init__(self,name,desc):
        self.root = ConfigNode(self,name)
        self.desc = desc

    def setup(self,solver,xmlProto):
        self.root.initState(solver,xmlProto)

    def toString(self):
        return self.desc

    def details(self):
        return self.root.details()

    def copyFrom(self,other):
        self.root.copyFrom(other.root)

class Invocation:
    def __init__(self,command):
        self.command = command
        self.series = []
        self.state = 'init'

    def default(self):
        first = Config(self.command,'Default context for '+self.toString())
        first.setup(self.command.xmlProto)
        self.series.append(first)

    def top(self):
        return self.series[len(self.series)-1]

    def propose(self,config):
        self.series.append(config.correct())

    def undo(self):
        self.series.pop()
