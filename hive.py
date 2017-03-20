import sys
import os
import shutil
import uuid
import socket
import tempfile
import glob
import urllib
import code
import functools
import json
import task
from subprocess import PIPE, Popen
from threading  import Thread,RLock
import shipper

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

def try_clone_method(obj):
    if isinstance(obj,list):
        result = []
        for item in obj:
            result.append(try_clone_method(item))
        return result
    elif isinstance(obj,dict):
        result = dict()
        for key,value in obj.iteritems():
            result[key] = try_clone_method(value)
        return result
    elif hasattr(obj,'clone'):
        return obj.clone()
    else:
        return obj

import xml.etree.ElementTree as ElementTree
import argparse
import pexpect
import copy
import re

Element = ElementTree.Element

def toBool(rvalue):
    return rvalue != False and rvalue != 0 and rvalue != 'false' and rvalue != 'False' and rvalue != 'FALSE'

def xmlCopy(source):
    target = ElementTree.Element(source.tag)
    target._file_name = source._file_name
    target._start_line_number = source._start_line_number
    target._start_column_number = source._start_column_number
    target._start_byte_index = source._start_byte_index
    if hasattr(source,'text'):
        target.text = source.text
    if hasattr(source,'tail'):
        target.tail = source.tail
    for attrName in source.attrib:
        target.attrib[attrName] = source.attrib[attrName]
    for child in source:
        target.append(xmlCopy(child))
    return target

def xmlTrackDefnPath(elem,parent,xpathSegment):
    elem.parent = parent
    elem.xpathSegment = xpathSegment
#    print 'DEBUG: BEGIN xmlTrackDefnPath %s at %s:%d' % (elem.tag,elem._file_name,elem._start_line_number)
#    if hasattr(elem,'xpathSegment'):
#        defnPath = []
#        xmlGetDefnPath(elem,defnPath)
#        print 'PATH %s' % '/'.join(defnPath)
    if not hasattr(elem,'expected'):
        elem.expected = dict()
    for child in elem:
        if not isinstance(child,Element):
            raise RuntimeError('FATAL: child of XML Element should also be Element but it is %s' % str(child))
        if child.tag not in elem.expected:
            elem.expected[child.tag] = 0
        elem.expected[child.tag] += 1
    actual = dict()
    for child in elem:
        if child.tag not in actual:
            actual[child.tag] = 0
        xpathSegment = None
        if elem.expected[child.tag] == 1:
            xpathSegment = [child.tag]
        else:
            xpathSegment = [child.tag,str(actual[child.tag])]
        actual[child.tag] += 1
        xmlTrackDefnPath(child,elem,xpathSegment)
#    print 'DEBUG: END   xmlTrackDefnPath %s at %s:%d with %s' % (elem.tag,elem._file_name,elem._start_line_number,elem.expected)

def xmlGetDefnPath(elem,defnPath):
    if isinstance(elem,ElementTree.Element):
        if hasattr(elem,'parent'):
            xmlGetDefnPath(elem.parent,defnPath)
        if hasattr(elem,'xpathSegment'):
            for item in elem.xpathSegment:
                defnPath.append(item)
    elif hasattr(elem,'getDefnPath'):
        elem.getDefnPath(defnPath)

def xmlLookupDefnPath(elem,defnPath):
    if len(defnPath) == 0:
        return elem
    nextPath = defnPath
    if isinstance(elem,ElementTree.Element):
        tagName = defnPath[0]
        nextPath = defnPath[1:]
        actual = 0
        if tagName not in elem.expected:
            print 'WARNING: %s:%d (%s) imminent failure because %s is not in %s' % (elem._file_name,elem._start_line_number,elem.tag,tagName,elem.expected)
        if elem.expected[tagName] != 1:
            actual = int(nextPath[0])
            nextPath = nextPath[1:]
        index = 0
        for child in elem:
            if isinstance(child,ElementTree.Element) and child.tag == tagName:
                if index == actual:
                    return lookupRelPath(child,nextPath)
                index += 1
        raise RuntimeError('Unable to locate XML node using path %s after %s with expected=%s' % ('/'.join(defnPath),elem,elem.expected))
    else:
        return lookupRelPath(elem,defnPath)

def lookupRelPath(obj,defnPath):
    if len(defnPath) == 0:
        return obj
#    print 'DEBUG: looking for %s in %s' % (defnPath[0],obj)
    if type(obj) == dict:
        if defnPath[0] not in obj:
            return None
        return lookupRelPath(obj[defnPath[0]],defnPath[1:])
    if type(obj) == list:
        index = int(defnPath[0])
        if index < 0 or index >= len(obj):
            return None
        return lookupRelPath(obj[index],defnPath[1:])
    if hasattr(obj,defnPath[0]):
        return lookupRelPath(getattr(obj,defnPath[0]),defnPath[1:])
    if hasattr(obj,'lookupRelPath'):
        return obj.lookupRelPath(defnPath)
    if isinstance(obj,ElementTree.Element):
        return xmlLookupDefnPath(obj,defnPath)
    raise RuntimeError('Unable to locate Python object using path %s after %s' % ('/'.join(defnPath),obj))

class Definition:
    def __init__(self,xml,agency):
        self.agency = agency
        self.xml = xml

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
        element._start_column_number = self.parser.CurrentColumnNumber+1
        element._start_byte_index = self.parser.CurrentByteIndex
        return element

    def _end(self, *args, **kwargs):
        element = super(self.__class__, self)._end(*args, **kwargs)
        element._file_name = self._file_name
        element._end_line_number = self.parser.CurrentLineNumber
        element._end_column_number = self.parser.CurrentColumnNumber+1
        element._end_byte_index = self.parser.CurrentByteIndex
        return element

class Shipper(shipper.Shipper):
    def __init__(self,solver):
        shipper.Shipper.__init__(self)
        self.solver = solver

    def prepareForMerge(self):
        self.defByName[self.getKey(self.solver)] = self.solver
        self.defOrder.append(self.solver)

    def attributeOrder(self,obj,stack):
        if not isinstance(obj,dict):
            raise RuntimeError('Expected an object of type dict in call to attributeOrder but received %s' % type(obj))

#        if 'programName' in obj:
#            print 'DEBUG: Called attributeOrder for %s' % obj
#            print 'DEBUG: stack is %s' % '\n'.join([str(obj) for obj in stack])

        if len(stack) > 1 and hasattr(stack[len(stack)-2],'attributeOrder'):
            return stack[len(stack)-2].attributeOrder()

#        if 'programName' in obj:
#            print 'DEBUG: Skipping custom attributeOrder for %s' % obj
#            print 'DEBUG: stack is %s' % '\n'.join([str(obj) for obj in stack])
#        else:
#            print 'Skipping attributeOrder for %s' % obj['__type__']
        return shipper.Shipper.attributeOrder(self,obj,stack)

    def hasKey(self,obj):
        if hasattr(obj,'hasDefnPath'):
            return obj.hasDefnPath()
        if hasattr(obj,'getDefnPath'):
            return True
        if isinstance(obj,ElementTree.Element):
            return True
        return False

    def getKey(self,obj):
        defnPath = []
        if isinstance(obj,ElementTree.Element):
            xmlGetDefnPath(obj,defnPath)
        elif hasattr(obj,'getDefnPath'):
            obj.getDefnPath(defnPath)
        return '/'.join(defnPath)

    def lookupKey(self,key):
        obj = shipper.Shipper.lookupKey(self,key)
        if obj != None:
            return obj
        defnPath = key.split('/')
        return self.solver.lookupAbsPath(defnPath)        

    def getType(self,obj):
        if isinstance(obj,ElementTree.Element):
            return 'Element'
        return shipper.Shipper.getType(self,obj)

    def refIsDef(self,stack,attr,toObj):
        fromObj = None
        for index in range(0,len(stack)):
            if fromObj == None:
                rindex = len(stack) - index - 1
                if self.hasKey(stack[rindex]):
                    fromObj = stack[rindex]
        if fromObj != None and hasattr(fromObj,'isDefnAttribute') and fromObj.isDefnAttribute(attr):
            return True
        if toObj.__class__ == ElementTree.Element:
            return toObj.parent == fromObj
        return False

    def mergeMembers(self,target,newMembers):
        if hasattr(target,'mergeMembers'):
            target.mergeMembers(newMembers)
        else:
            shipper.Shipper.mergeMembers(self,target,newMembers)

    def create(self,typeName,rep):
        klass = None
        obj = None
        if hasattr(sys.modules[__name__],typeName):
            klass = getattr(sys.modules[__name__],typeName)
            if klass == Config:
                members = rep['__members__']
                obj = klass(members['name'],members['desc'],self.solver)
            elif klass == ConfigNode:
                members = rep['__members__']
                obj = klass(None,members['name'])
            elif klass == Agent:
                obj = klass(self.solver)
            elif klass == Element:
                members = rep['__members__']
                obj = klass(members['tag'])
            else:
                obj = klass()
        return obj

    def packAsVoid(self,obj):
        return isinstance(obj,RLock().__class__)

class Tabulator:
    def __init__(self):
        self.rows = []

    def makeRows(self,index,obj):
        if isinstance(obj,list):
            j = 0
            for value in obj:
                self.makeRows('%s.%d' % (index,j),value)
                j += 1
        else:
    #        result['type'] = obj.__class__.__name__
            if hasattr(obj,'showAttributeNames'):
                for attrName in obj.showAttributeNames():
                    value = getattr(obj,attrName)
                    if isinstance(value,str) or isinstance(value,int) or isinstance(value,float) or isinstance(value,unicode):
                        self.makeRows('%s.%s' % (index,attrName),value)
            elif hasattr(obj,'__dict__'):
                self.makeRows(index,obj.__dict__)
            elif isinstance(obj,dict):
                for key,value in obj.iteritems():
                    result = dict()
                    result['key'] = '%s.%s' % (index,key)
                    result['value'] = value
                    self.rows.append(result)                    
            elif index != None:
                result = dict()
                result['key'] = index
                result['value'] = obj
                self.rows.append(result)
            else:
                result = dict()
                result['value'] = obj
                self.rows.append(result)

    def addPair(self,key,value):
        self.rows.append(dict(key=key,value=str(value)))

    def add(self,obj):
        if isinstance(obj,dict):
            for key,value in obj.iteritems():
                self.makeRows(key,value)
        elif isinstance(obj,list):
            index = 0
            for item in obj:
                self.makeRows(index,item)
                index += 1
        if hasattr(obj,'showAttributeNames'):
#            self.rows.append(dict(key='type',value=obj.__class__.__name__))
            for attrName in obj.showAttributeNames():
                value = getattr(obj,attrName)
                if isinstance(value,str) or isinstance(value,int) or isinstance(value,float) or isinstance(value,unicode):
                    self.rows.append(dict(key=attrName,value=str(value)))
        if hasattr(obj,'state'):
            if obj.state == None:
                print 'Cannot tabulate %s because state is None' % obj
            obj.state.root.tabulate(self,True)

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
                asString = str(value)
                if len(asString) > maxSize:
                    maxSize = len(asString)

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
            tmp = dict()
            for key in sizes.keys():
                if key in row:
                    tmp[key] = row[key]
                else:
                    tmp[key] = ''
            resultString += formatString % tmp

        return resultString

class GenericCommand:
    def __init__(self,solver,name):
        self.name = name
        self.config = Config(name,'Agency API command %s' % name,solver)

    def __len__(self):
        return self.__dict__.__len__()

    def __iter__(self):
        return self.__dict__.__iter__()

class Service:
    def __init__(self,solver):
        self.solver = solver

    def hello(self,agent,data):
        goalProtos = self.solver.getDefinitionsByType('goalProto')
        commands = []
        for goalProto in goalProtos:
            goal = Goal()
            cmdName = goalProto.get('name')
            goal.cfgTopGoal(cmdName,'',agent)
            goal.bindToProto()
            goal.checkPre(True)
            commands.append(goal)
        return commands

    def propose(self,agent,goal):
        agent.addGoal(goal)
        reconfig = goal.checkPre(True)
        if reconfig == True:
            goal.spawn()
            return True
        return reconfig

class Definitions:
    def __init__(self):
        self.byTypeThenName = dict() # locked

    def setParent(self,parent):
        self.parent = parent

    def getDefnPath(self,defnPath):
        self.parent.getDefnPath(defnPath)
        defnPath.append('definitions')

    def addDefinition(self,xmlDefinition):
        typeName = xmlDefinition.tag
        defName = xmlDefinition.get('name')
        xmlTrackDefnPath(xmlDefinition,self,['byTypeThenName',typeName,defName])
        self.elaborate(xmlDefinition)

        xmlDefinition.set('isHiveDef',True)
        if self.parent.verboseMode(1):
            print 'Definition of %s %s at %s:%d' % (typeName,defName,xmlDefinition._file_name,xmlDefinition._start_line_number)
        if typeName not in self.byTypeThenName:
            self.byTypeThenName[typeName] = dict()
        self.byTypeThenName[typeName][defName] = xmlDefinition

    def getDefinitionsByType(self,typeName):
        result = [defn for defn in self.byTypeThenName[typeName].values()]
        return result

    def getDefinitions(self,typeName):
        result = []
        if typeName in self.byTypeThenName:
            for defName,defElement in self.byTypeThenName[typeName].iteritems():
                result.append(defElement)
        return result

    def getDefinitionByTypeAndName(self,typeName,defName):
        result = None
        if typeName in self.byTypeThenName:
#            print 'DEBUG: %d definitions of type %s found' % (len(self.byTypeThenName[typeName].keys()),typeName)
            if defName in self.byTypeThenName[typeName]:
                defn = self.byTypeThenName[typeName][defName]
#                print 'DEBUG: definition of type %s and name %s found at %s:%d' % (typeName,defName,defn._file_name,defn._start_line_number)
                result = defn
        return result

    def getRelPath(self,child,name,relPath):
        self.getDefnPath(relPath)
        if self.state == child:
            relPath.append('state')
            return
        if name != None and name in self.byTypeThenName and self.byTypeThenName[name] == child:
            relPath.append('byTypeThenName')
            relPath.append(name)
            return
        if name != None and name in self.agentByName and self.agentByName[name] == child:
            relPath.append('agentByName')
            relPath.append(name)
            return
        if name != None and name in self.agentByUUID and self.agentByUUID[name] == child:
            relPath.append('agentByUUID')
            relPath.append(name)
            return
        raise RuntimeError('Malformed parent-child relationship parent=Agency name=%s type=%s' % (name,child))

    def afterUnpack(self):
        for typeName,typeDefn in self.byTypeThenName.iteritems():
            for defName,defDefn in typeDefn.iteritems():
#                xmlTrackDefnPath(defDefn,self,['byTypeThenName',typeName,defName])
                self.elaborate(defDefn)

    def elaborate(self,defDefn):
        defName = defDefn.get('name')
        if 'type' not in defDefn.attrib:
            # create Python class definition
            code = '\n'
            code += 'global %s\n' % defName
            code += 'class %s:\n' % defName
            members = dict()
            for child in defDefn:
                if not isinstance(child,Element):
                    raise RuntimeError('Premature elaborate call at %s' % str(child))
                if 'name' in child.attrib:
                    members[child.get('name')] = child
            code += '   def __init__(%s):\n' % (','.join(['self'] + ['arg_%s=None' % memberName for memberName in members.keys()]))
            for memberName in members.keys():
                code += '      self.%s = arg_%s\n' % (memberName,memberName)
            if len(members) == 0:
                code += '      pass\n'
            code += '\n'
            code += '   def clone(self):\n'
            code += '      result = %s()\n' % defName
            for memberName in members.keys():
                code += '      if hasattr(self.%s,\'clone\'):\n' % memberName
                code += '         result.%s = self.%s.clone()\n' % (memberName,memberName)
                code += '      else:\n'
                code += '         result.%s = self.%s\n' % (memberName,memberName)
            if len(members) == 0:
                code += '      pass\n'
            code += '      return result\n'
            code += '\n'

#            print 'DEBUG: defining class\n%s\n' % code
            exec(code)
#            if hasattr(sys.modules[__name__],defName):
#                print 'Compiling class definition for %s succeeded in module %s' % (defName,__name__)

class Agency:
    def __init__(self):
        self.name = 'the'
        self.state = Config('state','Agency state',self) # locked
        self.state.setParent(self)
        self.definitions = Definitions()
        self.definitions.setParent(self)
        self.sourceFiles = []
        self.result = True
        self.statementStack = []
        self.stateDefs = []
        self.agentOrder = []
        self.agentByUUID = dict()
        self.agentByName = dict()
        self.lock = RLock()

    def attributeOrder(self):
        return ['name','sourceFiles','definitions','result','statementStack','stateDefs','agentOrder','state','agentByName','agentByUUID']

    def parseArgs(self,solverArgs,remainingArgString):
        self.args = solverArgs
        self.remainingArgString = remainingArgString

    def start(self):
        self.lock.acquire()
        if self.verboseMode(1):
            print 'BEGIN Agency %s starting' % self.name

        self.publicServerName = None
        if 'SERVER_NAME' in os.environ:
            self.publicServerName = os.environ['SERVER_NAME']
        if self.publicServerName == None or self.publicServerName == '':
            self.publicServerName = socket.getfqdn() 
        self.defnPath = []       
        for segment in os.environ['HOME'].split('/'):
            self.defnPath.append(segment)
        self.defnPath.append('hiveData')
        if not os.path.exists('/'.join(self.defnPath)):
            os.makedirs('/'.join(self.defnPath))
        globs = glob.glob(os.path.expanduser('/'.join(self.defnPath)))
        self.persistentPath = globs[0]
        if os.path.exists('%s/.hive/private.xml' % (os.environ['HOME'])):
            self.readFileXML('%s/.hive/private.xml' % os.environ['HOME'],False)
        if os.path.exists('%s/agency.json' % self.persistentPath):
            self.readState('%s/agency.json' % self.persistentPath)

        if self.verboseMode(1):
            print 'END   Agency %s starting' % self.name
        self.lock.release()

    def persist(self):
        tempFile = '%s/agency.json.in-progress' % self.persistentPath
        finalFile = '%s/agency.json' % self.persistentPath

        if self.verboseMode(1):
            print 'BEGIN Agency %s saving persistent state to %s' % (self.name,self.persistentPath)

        self.lock.acquire()
        fp = open(tempFile,'wt')
        shipper = Shipper(self)
        shipper.addValue(self)
        shipper.prepack()
        print >>fp,json.dumps(shipper.packValues())
        fp.close()
        shutil.move(tempFile,finalFile)
        self.lock.release()

        if self.verboseMode(1):
            print 'END   Agency %s saving persistent state to %s' % (self.name,self.persistentPath)

    def mergeMembers(self,newMembers):
        self.state = newMembers['state']
        self.agentOrder = newMembers['agentOrder']
        self.agentByUUID = newMembers['agentByUUID']
        self.agentByName = newMembers['agentByName']
        for sourceFile in newMembers['sourceFiles']:
            if sourceFile in self.sourceFiles:
                pass
            else:
                self.readFileXML(sourceFile,True)
                self.sourceFiles.append(sourceFile)

    def afterUnpack(self):
        self.definitions.afterUnpack()

    def finish(self):
        if self.verboseMode(1):
            print 'BEGIN Agency %s finishing' % self.name
        self.lock.acquire()
        for agent in self.agentOrder:
            agent.suspend()
        self.persist()
        self.lock.release()
        if self.verboseMode(1):
            print 'END   Agency %s finishing' % self.name

    def getDefnPath(self,defnPath):
        for item in self.defnPath:
            defnPath.append(item)

    def getRelPath(self,child,name,relPath):
        self.getDefnPath(relPath)
        if self.state == child:
            relPath.append('state')
            return
        if name != None and name in self.agentByName and self.agentByName[name] == child:
            relPath.append('agentByName')
            relPath.append(name)
            return
        if name != None and name in self.agentByUUID and self.agentByUUID[name] == child:
            relPath.append('agentByUUID')
            relPath.append(name)
            return
        raise RuntimeError('Malformed parent-child relationship parent=Agency name=%s type=%s' % (name,child))

    def isDefnAttribute(self,attr):
        return attr == 'state' or attr == 'agentByUUID' or attr == 'definitions'

    def lookupPath(self,path):
        result = None
        result = self.lookupAbsPath(path)
        if result == None:
            result = lookupRelPath(self,path)
        return result

    def lookupAbsPath(self,absPath):
        defnPath = []
        self.getDefnPath(defnPath)
#        print 'DEBUG: trimming common prefixes of %s and %s' % ('/'.join(defnPath),'/'.join(absPath))
        while len(defnPath) > 0 and len(absPath) > 0:
#            print 'DEBUG: "%s" vs. "%s" (%s vs. %s)' % (defnPath[0],absPath[0],type(defnPath[0]),type(absPath[0]))
            if defnPath[0] != absPath[0]:
                return None
            defnPath = defnPath[1:]
            absPath = absPath[1:]
#        print 'DEBUG: after trimming common prefixes we have %s and %s' % ('/'.join(defnPath),'/'.join(absPath))
        return lookupRelPath(self,absPath)

    def allocateAgentName(self):
        return str(uuid.uuid4())

    def verboseMode(self,level):
        return self.args.verbose != None and int(self.args.verbose[0]) >= level        

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

    def readState(self,stateFile):
        if self.verboseMode(1):
            print 'BEGIN Agency %s loading persistent state from %s' % (self.name,self.persistentPath)

        self.lock.acquire()
        fp = open(stateFile,'rt')
        shipper = Shipper(self)
        shipper.prepareForMerge()
        rep = json.load(fp)

        doppel = shipper.unpack(rep)
#        print 'DEBUG: loaded %s' % doppel
        if doppel[0] != self:
            raise RuntimeError('merge failed in Agency.readState')
        fp.close()        
        self.lock.release()

        if self.verboseMode(1):
            print 'END   Agency %s loading persistent state from %s' % (self.name,self.persistentPath)


    def readFileXML(self,programFile,mandatory=True):
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
                if self.verboseMode(1):
                    print 'Reading '+actualPath
                xmlDoc = ElementTree.parse(actualPath,parser=LineNumberingParser(actualPath))
                self.readDefinitions(xmlDoc)
                self.sourceFiles.append(actualPath)

    def readDefinitions(self,xmlDefinitions):
        for element in xmlDefinitions.findall('*'):
            if 'name' in element.attrib:
                self.addDefinition(element)
            else:
                self.createError('%s:%d: attribute name must be present on all top-level XML nodes, which are considered to be Hive definitions' % (element._file_name,element._start_line_number))
            if element.tag == 'variable' or element.tag == 'list' or element.tag == 'struct':
                self.addStateDef(element)

    def appendName(xmlDefn,defnPath):
        defnPath.append(xmlDefn.get('name'))

    def addDefinition(self,xmlDefinition):
        self.lock.acquire()
        self.definitions.addDefinition(xmlDefinition)
        self.lock.release()

    def addStateDef(self,xmlDef):
        if 'type' in xmlDef.attrib:
            self.stateDefs.append(xmlDef)
            position = '%s:%d' % (xmlDef._file_name,xmlDef._start_line_number)
            if self.verboseMode(1):
                print 'BEGIN Processing <state> element at '+position
            self.state.root.initStateNode(self,self.state,xmlDef)
            if self.verboseMode(1) :
                print 'END   Processing <state> element at '+position

    def createError(self,error):
        self.reportError(error)

    def reportError(self,errMsg):
        print 'ERROR: '+errMsg
        self.result = False

    def hasErrors(self):
        return len(self.errors) > 0

#    def terminate(self):
        # nothing to do        

    def inspect(self,target):
        tabulator = Tabulator()
        if hasattr(target,'__dict__'):
            tabulator.addPair('__type__',target.__class__.__name__)
        if hasattr(target,'getDefnPath'):
            defnPath = []
            target.getDefnPath(defnPath)
            tabulator.addPair('__path__','/'.join(defnPath))
        tabulator.add(target)
        return tabulator.printText()

    def beginAgent(self):
        agent = Agent(self);
        self.agentOrder.append(agent)
        self.agentByUUID[agent.uuid] = agent

        if self.args.initial:
            print 'BEGIN INITIAL STATE OF AGENT %s' % agent.name
            print agent.state.details()
            print 'END   INITIAL STATE OF AGENT %s' % agent.name

        return agent

    def renameAgent(self,agent,oldName,newName):
        if oldName != None and oldName in self.agentByName:
            del self.agentByName[oldName]
        self.agentByName[newName] = agent

    def locateAgent(self,agentName):
        if agentName in self.agentByUUID:
            return self.agentByUUID[agentName]
        elif agentName in self.agentByName:
            return self.agentByName[agentName]
        return self.lookupPath(agentName.split('/'))

    def endAgent(self,agent):
        if self.args.final:
            print 'BEGIN FINAL STATE OF AGENT %s' % agent.name
            print agent.state.details()
            print 'END   FINAL STATE OF AGENT %s' % agent.name

        del self.agentByName[agent.name]
        del self.agentByUUID[agent.uuid]

#        for agent in self.agentOrder:
#            print 'Agent %s' % agent
        self.agentOrder.remove(agent)

class Agent:
    def __init__(self,solver):
        self.solver = solver
        self.goals = []
        self.goalsByName = dict()
        self.definitions = Definitions()
        self.definitions.setParent(self)
        self.statementStack = []
        self.uuid = solver.allocateAgentName()
        self.name = self.uuid
        self.programName = None
        self.programDefn = None
        self.state = Config('state','State of Agent '+self.name,solver)
        self.state.setParent(self)
        self.state.root.setupStruct()
        self.state.root.copyFrom(solver.state.root,False)
        self.running = False
        self.goalIndex = dict()
        self.lock = RLock()
        self.tempFiles = []

    def attributeOrder(self):
        return ['solver','definitions','statementStack','uuid','name','running','goalIndex','tempFiles','programName','programDefn','state','goalsByName','goals']

    def __str__(self):
        return '%s "%s" (%s) %s' % (self.__class__.__name__,self.name,self.uuid,self.programName)

    def showAttributeNames(self):
        return ['programName','running','uuid','name']

    def getDefnPath(self,defnPath):
        self.solver.getRelPath(self,self.uuid,defnPath)

    def getRelPath(self,child,name,relPath):
        self.getDefnPath(relPath)
        if self.state == child:
            relPath.append('state')
            return
        if name == None:
            print 'DEBUG: cannot find %s in %s because name is None' % (name,self)
        elif name not in self.goalsByName:
            print 'DEBUG: cannot find %s in %s because name is not on goalsByName' % (name,self)
        elif child not in self.goalsByName[name]:
            print 'DEBUG: cannot find %s in %s because name goalsByName does not match' % (name,self)
            print 'goalsByName[name] = %s' % self.goalsByName[name]
            print 'child             = %s' % child
        else:
            relPath.append('goalsByName')
            relPath.append(name)
            relPath.append(str(self.goalsByName[name].index(child)))
            return
        raise RuntimeError('Malformed parent-child relationship parent=%s name=%s relPath=%s childName=%s goalNames=%s' % (self,name,'/'.join(relPath),child.name,self.goalsByName.keys()))

    def isDefnAttribute(self,attr):
        return attr == 'goalsByName' or attr == 'state' or attr == 'definitions'

    def allocateGoalName(self,prefix):
        if prefix not in self.goalIndex:
            self.goalIndex[prefix] = 0
        else:
            self.goalIndex[prefix] += 1
        return '%s.%s.%d' % (self.uuid,prefix,self.goalIndex[prefix])

    def topGoalContext(self,goal,goalName,desc):
        result = Config(goalName,desc,self.solver)
        result.setParent(goal)
        result.copyFrom(self.state,False)

        result.initPath(['host','platform'],sys.platform)
        result.initPath(['host','uname'],os.uname()[0])
        result.initPath(['host','hostname'],socket.gethostname())
        result.initPath(['host','hostip'],socket.gethostbyname(socket.gethostname()))

        node = result.root.lookupTermList(True,['agent'],self)
        node.copyFrom(self.state.root.lookupTermList(False,['agent'],self))

        if self.verboseMode(2):
            print 'BEGIN configuration computed by Agent.topGoalContext '+goal.name
            print result.details()
            print 'END   configuration computed by Agent.topGoalContext '+goal.name

        return result

    def checkPre(self):
        node = self.state.root.lookupTermList(False,['agent'],self)

        preChecks = self.programDefn.findall('pre')
        isSuccess = True
        failingLvalues = []
        for preCheck in preChecks:
            stmt = preCheck[0]
#            print 'DEBUG: %s:%d <%s> BEGIN checking' % (stmt._file_name,stmt._start_line_number,stmt.tag)
            evalResult = Evaluator(self,self.state,None,False)
            evalResult.setXML(stmt)
            evalResult.evaluate()
#            print 'DEBUG: %s:%d <%s> END   checking' % (stmt._file_name,stmt._start_line_number,stmt.tag)
            if not evalResult.getOutcome().isTrue():
                evalResult.collectLvalues(failingLvalues)
#                print 'DEBUG: %s:%d <%s> failed (1)' % (stmt._file_name,stmt._start_line_number,stmt.tag)
            elif evalResult.getRvalue() == None:
                evalResult.collectLvalues(failingLvalues)
#                print 'DEBUG: %s:%d <%s> failed (2)' % (stmt._file_name,stmt._start_line_number,stmt.tag)
            elif evalResult.getRvalue() == False:
                evalResult.collectLvalues(failingLvalues)
#                print 'DEBUG: %s:%d <%s> failed (3)' % (stmt._file_name,stmt._start_line_number,stmt.tag)
            else:
                pass
#                print 'DEBUG: %s:%d <%s> passed' % (stmt._file_name,stmt._start_line_number,stmt.tag)
            isSuccess = isSuccess and evalResult.getOutcome().isTrue() and evalResult.getRvalue()
        if not isSuccess:
            for lvalue in failingLvalues:
                print 'RESET value of '+lvalue.getPath('.')
                lvalue.reconfigure(self.solver.state,'agent')
            controller = ConfigController(self.state)
            return controller
        else:
            return True

    def loadProgram(self,programName,agentName):
        self.programName = programName
        oldName = self.name
        self.name = agentName
        self.solver.renameAgent(self,oldName,agentName)
        if self.verboseMode(1):
            print 'BEGIN Agent %s loading program %s' % (self.name,programName)
        programDefn = self.solver.definitions.getDefinitionByTypeAndName('agent',self.programName)
        if programDefn == None:
            raise RuntimeError('<agent name="%s"/> is undefined' % self.programName)            
        self.programDefn = xmlCopy(programDefn)
        xmlTrackDefnPath(self.programDefn,self,['programDefn'])

        agentNode = self.state.root.lookupTermList(True,['agent'],self)
        agentNode.initStateChildren(self.solver,self.state,self.programDefn)
        self.state.handleStateOverrides(self,self.solver.remainingArgString,False)

        result = self.checkPre()
        if result != True:
            return result
        if self.verboseMode(2):
            print 'BEGIN configuration computed by Agent.loadProgram '+self.name
            print self.state.details()
            print 'END   configuration computed by Agent.loadProgram '+self.name
            print 'END   Agent %s loading program %s' % (self.name,self.programName)

        for stmt in self.programDefn.findall('*'):
            if 'name' in stmt.attrib:
                self.definitions.addDefinition(stmt)

        return result

    def doEvent(self,eventName,executeMode):
        if self.programDefn == None:
            raise RuntimeError('Agent %s has no program loaded' % self.name)
#        print 'BEGIN Agent %s %s %s' % (self.name,'execute' if executeMode else 'plan',eventName)
        topGoal = self.addTopGoalByName(eventName)
        topGoal.pursue(executeMode)
        topGoal.context.root.returnStateChildren(self.state.root,self.programDefn)
#        print 'END   Agent %s %s %s' % (self.name,'execute' if executeMode else 'plan',eventName)
        return topGoal

    def verboseMode(self,level):
        return self.solver.args.verbose != None and self.solver.args.verbose[0] >= level

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
                sub = Evaluator(self,context,None,False)
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
                evalResult = Evaluator(self,context,None,False)
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
                evalResult = Evaluator(self,context,None,False)
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
        goal = Goal()
        goal.cfgTopGoal(goalName,self.solver.remainingArgString,self)
#        if not self.hasGoal(goal):            
        self.addGoal(goal)
        return goal

    def addGoal(self,goal):
        self.lock.acquire()
        self.goals.append(goal)
        goal.agent = self
#        print 'DEBUG: Goal has properties: %s' % str(goal.__dict__)
        myNode = self.state.root.lookupTermList(True,[goal.name],self)
        otherNode = goal.context.root.lookupTermList(False,['goal'],self)
        myNode.copyFrom(otherNode)
        if goal.name not in self.goalsByName:
            self.goalsByName[goal.name] = []
        self.goalsByName[goal.name].append(goal)
        self.lock.release()

    def suspend(self):
        for goal in self.goals:
            if not isinstance(goal,Goal):
                print 'DEBUG: expected Goal but found %s' % goal
            goal.suspend()
        for file in self.tempFiles:
            file.close()
        self.tempFiles = []

    def getDefinitions(self,typeName):
        result = []
        result += self.solver.definitions.getDefinitions(typeName)
        result += self.definitions.getDefinitions(typeName)
        return result

    def getDefinitionByTypeAndName(self,typeName,defName):
        result = self.definitions.getDefinitionByTypeAndName(typeName,defName)
        if result == None:
            result = self.solver.definitions.getDefinitionByTypeAndName(typeName,defName)
        return result


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
    def __init__(self,agent,context,pursue,executeMode):
        self.agent = agent
        self.context=context
        self.errors = []
        self.outcome = EvalOutcomes().setTrue()
        self.tail = ''
        self.pursue = pursue
        self.value = None
        self.executeMode = executeMode

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
        result = self.value
        while isinstance(result,ConfigWrap):
            result = result.deref()
        while isinstance(result,ConfigNode):
            if result.assigned != None:
                result = result.assigned
            else:
                result = result.getValue()
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
        return op in ['eq','ne','gt','lt','ge','le','add','sub','mul','div','mod']

    def doBinaryOperator(self,op,a,b):
        self.outcome = a.outcome and b.outcome
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
        elif(op == 'add'):
            self.value = a.getRvalue() + b.getRvalue()
        elif(op == 'sub'):
            self.value = a.getRvalue() - b.getRvalue()
        elif(op == 'mul'):
            self.value = a.getRvalue() * b.getRvalue()
        elif(op == 'div'):
            self.value = a.getRvalue() / b.getRvalue()
        elif(op == 'mod'):
            self.value = a.getRvalue() % b.getRvalue()
        else:
            self.createError('Unrecognized operator: '+op)

    def doStruct(self,xml):
        self.value = dict()
        for child in xml:
            subResult = Evaluator(self.agent,self.context,self.pursue,self.executeMode)
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
        self.value = a.isSuccess() and (a.getRvalue() != None)
        if self.agent.verboseMode(1) and not a.isSuccess():
            for error in a.errors:
                print error

    def collectLvalues(self,lvalues):
        if 'expr' in self.__dict__:
#            print 'ENTER collectLvalues %s %s' % (self.expr.tag,self.label)
            for child in self.expr:
                if child.tag != 'describe' and child.tag != 'label':
                    sub = Evaluator(self.agent,self.context,self.pursue,self.executeMode)
                    sub.setXML(child)
                    sub.collectLvalues(lvalues)
            if self.expr.tag == 'get' or self.expr.tag == 'set':
                lvalue = self.context.root.lookupString(False,self.expr.text,self)
                if lvalue not in lvalues:
                    lvalues.append(lvalue)
#            print 'EXIT collectLvalues %s %s' % (self.expr.tag,self.label)

    def evaluate(self):
        if 'expr' in self.__dict__:
            self.doXML()
        elif 'text' in self.__dict__:
            self.doText()
        else:
            self.createError('Must call Evaluator.setXML or Evaluator.setString before calling Evaluator.evaluate')

    def doXML(self):
        myTask = None
        if 'debug' in self.expr.attrib:
            myTask = task.Task('%s: evaluating expression %s' % (self.label,self.expr.tag))
        else:
            myTask = task.Task('%s: evaluating expression %s' % (self.label,self.expr.tag),logger=None)
        childResults = []
        if self.expr.text:
            sub = Evaluator(self.agent,self.context,self.pursue,self.executeMode)
            sub.setString(self.expr.text)
            sub.doText()
            childResults.append(sub)
        childCount = 0
        for child in self.expr:
            childCount += 1
            if child.tag != 'describe' and child.tag != 'label':
                sub = Evaluator(self.agent,self.context,self.pursue,self.executeMode)
                sub.setXML(child)
                sub.evaluate()
                childResults.append(sub)
        if self.expr.tail:
            self.tail = self.expr.tail

        interpreted = False
        if self.expr.tag == 'op':
            if self.isBinaryOperator(self.expr.get('name')):
                interpreted = True
                if(len(childResults) != 2):
                    myTask.error('Wrong number of arguments for operator '+self.expr.get('name'))
                elif (not childResults[0].isSuccess()):
                    myTask.error(childResults[0].errors)
                elif (not childResults[1].isSuccess()):
                    myTask.error(childResults[1].errors)
                else:
                    self.doBinaryOperator(self.expr.get('name'),childResults[0],childResults[1])
            elif self.isUnaryOperator(self.expr.get('name')):
                interpreted = True
                if(len(childResults) != 1):
                    myTask.error('Wrong number of arguments for operator '+self.expr.get('name'))
                elif (not childResults[0].isSuccess()):
                    myTask.error(childResults[0].errors)
                else:
                    self.doUnaryOperator(self.expr.get('name'),childResults[0])
        elif self.expr.tag == 'get':
            try:
                self.value = self.context.root.lookupString(False,self.expr.text,self)
                if self.value == None:
                    self.outcome = self.outcome and EvalOutcomes().setFalse()
            except Exception as e:
                raise RuntimeError('%s:%d - (%s) %s' % (self.expr._file_name,self.expr._start_line_number,self.expr.text,str(e)))
            interpreted = True
        elif self.expr.tag == 'set':
#            self.value = self.expr.text
            node = self.context.root.lookupString(True,self.expr.text,self)
            self.value = '.'.join(node.getPath('.').split('.')[1:])
            if self.value == None:
                self.outcome = self.outcome and EvalOutcomes().setFalse()
            else:
                interpreted = True
        elif self.expr.tag == 'int':
            if(len(childResults) == 0):
                myTask.error('<'+self.expr.tag+'> must always have a child expression')
            else:
                interpreted = True
                self.setValue(int(childResults[0].getRvalue()))
                self.outcome = self.outcome and childResults[0].outcome
        elif self.expr.tag == 'bool':
            if(len(childResults) == 0):
                myTask.error('<'+self.expr.tag+'> must always have a child expression')
            else:
                interpreted = True
                self.setValue(toBool(childResults[0].getRvalue()))
                self.outcome = self.outcome and childResults[0].outcome
        elif self.expr.tag == 'string' or self.expr.tag == 'describe' or self.expr.tag == 'code' or self.expr.tag == 'send':
            if(len(childResults) == 0):
                myTask.error('<'+self.expr.tag+'> must always have a child expression')
            else:
                interpreted = True
                text = ''
                for child in childResults:
                    text += child.getStringValue()
                    text += child.tail
                    self.outcome = self.outcome and child.outcome
                self.setValue(text)
#        elif self.expr.tag == 'struct':
#            interpreted = True
#            self.doDict(self.expr)
        elif self.expr.tag == 'variable':
#            self.doVariable(self.expr)
            if len(childResults) == 0:
                myTask.error('There is no child expression to compute the initial value of '+self.expr.get('name'))
            elif not childResults[0].isSuccess():
                myTask.error('Failed to use child expression to compute the initial value of '+self.expr.get('name'))
                for error in childResults[0].errors:
                    myTask.error(error)
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
        elif self.expr.tag == 'update':
            if(len(childResults) != 2):
                myTask.error('Wrong number of arguments for assign')
            else:
                target = childResults[0].getLvalue()
                source = childResults[1].getRvalue()
                if target == None:
                    myTask.error('assign needs two arguments the first of which should be a legal assignment target such as <set>')
                if source == None:
                    myTask.error('assign needs two arguments the second of which should be a legal assignment source such as <get>')
                if source != None and target != None:
                    target.setValue(source)
                    self.setValue(True)
                    interpreted = True
        elif self.expr.tag == 'defined':
            if(len(childResults) != 1):
                myTask.error('Wrong number of arguments for defined')
            else:
                self.doDefined(childResults[0])
                interpreted = True
        elif self.expr.tag == 'shell':
            children = self.expr.findall('*')
            lastReturnCode = None
            for child in children:
                if(child.tag == 'send'):
                    sub = Evaluator(self.agent,self.context,self.pursue,self.executeMode)
                    sub.setXML(child)
                    sub.evaluate()
                    if not sub.isSuccess():
                        myTask.error('Cannot evaluate <send>')
                    else:
                        cmd = sub.getStringValue()
                        cmdList = glob.glob(os.path.expanduser(cmd))
                        if len(cmdList) == 0:
                            cmdList = [cmd]
                            #self.createError('Cannot expand this shell expression:\n%s\n' % cmd)
                        for cmd in cmdList:
                            cmd = re.sub('\s*\n\s*',' ',cmd.strip())                        
                            if self.agent.echoMode():
                                print "BEGIN <shell><send>%s</send></shell>" % cmd
                            timeout = None
                            if 'timeout' in child.attrib:
                                timeout = child.get('timeout')
                            lastReturnCode = pexpect.run(cmd,withexitstatus=1,timeout=timeout)
                            if self.agent.echoMode():
                                print "END   <shell><send>%s</send></shell>" % cmd
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
                myTask.error('fileTest tag must always have a path as its only child')
            else:
                if self.agent.verboseMode(1):
                    print "TESTING FILE "+childResults[0].value
                if testType == 'exists':
                    interpreted = True
                    self.value = os.path.exists(childResults[0].value)
        elif self.expr.tag == 'tempFile':
            name = self.expr.get('name')
            file = None
            if name != None:
                file = tempfile.NamedTemporaryFile(prefix=name,delete=False)
            else:
                file = tempfile.NamedTemporaryFile(delete=False)
            #info = dict()
            #info['file'] = file
            #info['path'] = file.name
            self.agent.tempFiles.append(file)
            print >>file, self.agent.interpolateInner(self.context,self.expr,self)
            file.flush()
            interpreted = True
            self.value = file.name
        elif self.expr.tag == 'python':
            funcName = None
            if 'name' in self.expr.attrib:
                funcName = self.expr.get('name')
            codeBlocks = self.expr.findall('code')
            if funcName != None:
                if len(childResults) != 1:
                    myTask.error('python tag must always have a path as its only child')
                else:
                    cmd = 'self.value = %s(\'%s\')' % (funcName,childResults[0].getStringValue())
                    if not self.executeMode:
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
                    sub = Evaluator(self.agent,self.context,self.pursue,self.executeMode)
                    sub.setXML(codeBlock)
                    sub.evaluate()
                    if not sub.isSuccess():
                        myTask.error('Cannot interpret this <code> block')
                        for error in sub.errors:
                            self.errors.append(error)
                    elif not self.executeMode:
                        raise RuntimeError('GOTCHA')
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
            goalConfig = Config('context','Example of completed goal',self.agent.solver)
            goalConfig.setup('goal',self.expr)
            foundGoal = self.agent.findGoal(goalName,goalConfig)
            interpreted = True
            if (foundGoal != None):
                self.value = True
                self.outcome = EvalOutcomes().setTrue()
            elif self.pursue != None:
                subgoal = Goal()
                subgoal.cfgSubGoal(goalName,self.pursue,self.context,self.expr,self.agent.solver.remainingArgString,self.agent)
                self.agent.addGoal(subgoal)
                subgoal.pursue(self.executeMode)
                self.value = subgoal.isSuccess()
                subgoal.context.root.returnStateChildren(self.context.root,stmt)
            else:
                self.value = False
                self.outcome = EvalOutcomes().setPossible()
        else:
            myTask.error('Illegal tag for XML expression %s' % self.expr.tag)

        if not interpreted and len(myTask.errors) == 0:
            raise RuntimeError('%s: Unable to interpret expression\n%s' % (self.label,'\n'.join(myTask.errors)))

#        if self.expr.tag == 'variable':
#            print ('%s:%d result of %s lvalue %s rvalue %s of type %s' % (self.expr._file_name,self.expr._start_line_number,self.expr.tag,self.getLvalue(),self.getRvalue(),self.value.__class__.__name__))

    def doText(self):
        self.value = self.text

class Goal:
    def __init__(self):
        self.proto = None
        self.method = None
        self.variables = []
        self.errors = []
        self.agent = None
        self.parent = None

    def __str__(self):
        return '%s "%s"' % (self.__class__.__name__,self.name)

    def attributeOrder(self):
        return ['protoName','name','proto','method','agent','parent','variables','context','errors']

    def getDefnPath(self,defnPath):
        self.agent.getRelPath(self,self.name,defnPath)

    def isDefnAttribute(self,attr):
        return attr == 'context'

    def cfgTopGoal(self,name,remainingArgString,agent):
        self.agent = agent
        self.protoName = name
        self.name = self.agent.allocateGoalName(name)
        self.context = self.agent.topGoalContext(self,'context','Evaluation context for goal '+self.name)
        goalNode = self.context.root.lookupTermList(True,['goal'],None)
        goalNode.setupStruct()
        self.args = remainingArgString

    def cfgSubGoal(self,name,parent,argContext,argXML,remainingArgString,agent):
        self.agent = agent
        self.protoName = name
        self.name = self.agent.allocateGoalName(name)
        self.parent = parent

        self.context = Config(name,'State of SubGoal '+self.name,agent.solver)
        self.context.setParent(self)
        self.context.root.setupStruct()
        self.context.root.lookupTermList(True,['agent'],None).copyFrom(argContext.root.lookupTermList(True,['agent'],None))

        goalNode = self.context.root.lookupTermList(True,['goal'],None)
        goalNode.reset()
        goalNode.setupStruct()
        if self.agent.verboseMode(1):
            print 'BEGIN configuring subgoal %s at %s:%d' % (name,argXML._file_name,argXML._start_line_number)
        goalNode.initStateChildren(self.agent.solver,argContext,argXML)
        if self.agent.verboseMode(1):
            print 'END   configuring subgoal %s at %s:%d' % (name,argXML._file_name,argXML._start_line_number)

        self.args = remainingArgString
        self.bindToProto()

    def setProto(self,xmlProto):
        self.proto = xmlProto

        # allocate state for <variable> tags under <goalProto>
        goalNode = self.context.root.lookupTermList(True,['goal'],self.agent)
        goalNode.initStateChildren(self.agent.solver,self.agent.state,xmlProto)
        self.context.handleStateOverrides(self.agent,self.args,False)

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

    def checkPre(self,reconfigure = False):
        preChecks = self.proto.findall('pre')
        for preCheck in preChecks:
            self.checkExpr(preCheck)
        if not self.isSuccess():
            if reconfigure:
                self.context.reconfigure(self.agent.solver.state,'goal')
                controller = ConfigController(self.context)
                self.addError(controller.printText())
                return controller
            else:
                return False
        else:
            return True

    def checkPost(self):
        preChecks = self.proto.findall('pre')
        for preCheck in preChecks:
            self.checkExpr(preCheck)

    def evalConditions(self,condTag,xml):
        result = EvalOutcomes()
        result.setTrue()
        conditions = xml.findall(condTag)
        for condition in conditions:
            result = result and self.evalCondition(condition[0])
        return result

    def evalCondition(self,condElement):
        evalResult = Evaluator(self.agent,self.context,None,False)
        evalResult.setXML(condElement)
        evalResult.evaluate()
        if(evalResult.getOutcome().isTrue()):
            return EvalOutcomes().setTrue() if toBool(evalResult.getRvalue()) else EvalOutcomes().setFalse()
        else:
            return evalResult.getOutcome()

    def solveConditions(self,condTag,xml,executeMode):
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
                    goalConfig = Config('context','Subgoal configuration',self.agent.solver)
                    goalConfig.setup('goal',xml)
                    subgoal = Goal()
                    subgoal.cfgSubGoal(goalName,self,self.context,xml,self.agent.solver.remainingArgString,self.agent)
                    self.agent.addGoal(subgoal)
                    print 'DEBUG: BEGIN precondition %s' % subgoal.name
                    subgoal.pursue(executeMode)
                    print 'DEBUG: END   precondition %s' % subgoal.name
                    if not subgoal.isSuccess():
                        result = False

        return result

    def checkExpr(self,preCheck):
        if self.agent.verboseMode(1):
            print 'BEGIN checking <%s> at %s:%d' % (preCheck[0].tag,preCheck[0]._file_name,preCheck[0]._start_line_number)

        success = True
        checkResult = Evaluator(self.agent,self.context,None,False)
        checkResult.setXML(preCheck[0])
        checkResult.evaluate()
        if not checkResult.isSuccess():
            success = False
            if self.agent.verboseMode(1) and len(checkResult.errors) > 0:
                print "ERROR: While checking <%s>," % preCheck.tag
                for error in checkResult.errors:
                    print "       "+error                        
            for error in checkResult.errors:
                self.addError(error)
        elif not toBool(checkResult.getRvalue()):
            self.createErrorAt(preCheck,'Pre check failed '+ElementTree.tostring(preCheck))
            success = False
        if self.agent.verboseMode(1):
            print 'END   checking <%s> at %s:%d success: %s' % (preCheck[0].tag,preCheck[0]._file_name,preCheck[0]._start_line_number,'True' if success else 'False')

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

    def bindToProto(self):
        if self.proto == None:
            if self.agent.verboseMode(1) or self.agent.goalsMode(1):
                print 'Searching for prototype for goal '+self.protoName
            proto = None
            proto = self.agent.getDefinitionByTypeAndName('goalProto',self.protoName)
            if(proto == None):
                self.createError('No defintion found for goalProto with name %s' % self.protoName)
                self.createError(self.toString())
                return
            self.setProto(proto)
            if self.agent.verboseMode(1) or self.agent.goalsMode(1):
                print 'Goal %s uses prototype %s at %s:%d' % (self.name,self.proto.get('name'),self.proto._file_name,self.proto._start_line_number)

    def pursue(self,executeMode):
        if self.agent.goalsMode(1):
            print '# BEGIN Pursuing this goal: '+self.toString()
            if self.agent.verboseMode(1):
                print self.context.details()

        if self.proto == None and self.isSuccess():
            self.bindToProto()

        if self.proto is not None:
            self.agent.beginStatement(self.proto,self.context)

        canSkip = False
        if self.isSuccess() and executeMode:
            posts = self.proto.findall('post')
            if len(posts) > 0:
                canSkip = True
                for post in posts:                
                    checkPostBefore = Evaluator(self.agent,self.context,None,executeMode)
                    checkPostBefore.setXML(post[0])
                    checkPostBefore.evaluate()
                    canSkip = canSkip and checkPostBefore.value
            if canSkip and self.agent.verboseMode(1):
                print 'SKIP '+self.toString()+' because postconditions are already satisfied'

        if not canSkip and not self.method and self.isSuccess():
            methods = self.agent.getDefinitions('method')
            if self.agent.programDefn != None:
                methods += self.agent.programDefn.findall('method')
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
                    code = self.solveConditions('pre',method,executeMode)
                    if code == True:
                        self.method = method
                    elif self.agent.verboseMode(1):
                        print 'UNSOLVABLE '+method.get('name')+' to achieve goal '+self.name

            if self.method == None:
                self.createError('No method found to solve %s' % self.toString())

        if self.agent.goalsMode(1):
            print '# RESUME Pursuing this goal after preconditions solved: '+self.toString()+' (success: '+('True' if self.isSuccess() else 'False')+' canSkip:'+('True' if canSkip else 'False')+')'

        if not canSkip and self.isSuccess():
            ready = self.checkPre(True)
            if ready != True:
                self.createError(ready.printText())

        if not canSkip and self.method != None and self.isSuccess():
            self.agent.beginStatement(self.method,self.context)
            for stmt in self.method.findall('*'):
                self.execute(stmt,executeMode)
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

    def execute(self,stmt,executeMode):
        self.execute_r(self.context.root.lookupTermList(True,['goal'],self),stmt,executeMode)

    def execute_r(self,contextPre,stmt,executeMode):
        self.agent.beginStatement(stmt,self.context)
        context = contextPre
        if 'name' in stmt.attrib:
            context = context.lookupTermList(True,[stmt.get('name')],self)
            if stmt.tag == 'struct' or stmt.tag == 'goalCompleted' or stmt.tag == 'goalProto':
                context.setupStruct()
            if self.agent.verboseMode(1):
                print 'ENTER CONTEXT '+context.getFullPath('.')
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
                    evaluator = Evaluator(self.agent,self.context,self,executeMode)
                    evaluator.setXML(grandchildren[0])
                    evaluator.evaluate()
                    if not evaluator.isSuccess():
                        for error in evaluator.errors:
                            self.createErrorAt(child,error)
                    else:
                        start = evaluator.getRvalue()
                        if start != None:
                            starts.append(evaluator.getRvalue())
                        elif self.executeMode:
                            self.createErrorAt(child,'<in> expression could not be evaluated')
                        else:
                            ambigStarts = True
                elif child.tag == 'do':
                    if ambigStarts:
                        if self.agent.verboseMode(1):
                            print 'BEGIN find/do at (possible) item with symbol %s' % stmt.get('symbol')
                        self.execute_r(context,child,executeMode)
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
                                self.execute_r(context,child,executeMode)
                                if self.agent.verboseMode(1):
                                    print 'END   find/do at item %s' % str(item)
                            if self.agent.verboseMode(1):
                                print 'END   find/do at starting point %s' % str(start)
        elif stmt.tag == 'do':
            for child in stmt:
                if self.isSuccess():
                    self.execute_r(context,child,executeMode)
                else:
                    print 'WARNING: find/do is skipping statement at %s:%d because a previous statement failed' % (child._file_name,child._start_line_number)
                    print '\n'.join(self.errors)
        elif stmt.tag == 'repeat':
            count = None
            for child in stmt:
                if child.tag == 'count':
                    count = Evaluator(self.agent,self.context,self,executeMode)
                    count.setXML(child[0])
                    count.evaluate()

            if count != None:
                for index in range(0,int(count.getRvalue())):
                    if self.agent.verboseMode(1):
                        print 'BEGIN %s[%d]' % (stmt.get('name'),index)
                    for child in stmt:
                        if child.tag != 'count':
                            if self.isSuccess():
                                self.execute_r(context,child,executeMode) # !! wrong, should have subcontext with index defined
                    if self.agent.verboseMode(1):
                        print 'END %s[%d]' % (stmt.get('name'),index)
        elif stmt.tag == 'task':
            if self.agent.verboseMode(1):
                print 'BEGIN Task %s' % stmt.get('name')
            for sub in stmt:
                if self.isSuccess():
                    self.execute_r(context,sub,executeMode)
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
                    cmd = self.agent.interpolateInner(self.context,child,self)
                    cmdList = glob.glob(os.path.expanduser(cmd))
                    if len(cmdList) == 0:
                        cmdList = [cmd]

                    for cmd in cmdList:
                        if self.hasErrors():
                            pass
                        elif executeMode:
                            if(shellCommand != None):
                                cmd = re.sub('\s*\n\s*',';',cmd.strip())

                            if self.agent.echoMode():
                                print "BEGIN <shell><send>%s%s</send></shell>" % (shellCommand+' ' if shellCommand != None else '',cmd)

#                            scriptFile = tempfile.NamedTemporaryFile(prefix='script')
                            timeout = None
                            if 'timeout' in child.attrib:
                                timeout = child.get('timeout')

                            if(shellCommand != None):
                                lastCommand = pexpect.run(shellCommand+' '+cmd,withexitstatus=1,timeout=timeout)
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
                                lines = lastCommand[0].split('\n')
                                for line in lines:
                                    self.createErrorAt(child,line.decode('utf8'))
                            if self.agent.echoMode():
                                print "END   <shell><send>%s%s</send></shell>" % (shellCommand+' ' if shellCommand != None else '',cmd)
                        else:   
                            raise RuntimeError('GOTCHA')
                            print "PLAN  %s" % cmd
                elif(child.tag == 'receive'):
                    cmd = self.agent.interpolateInner(self.context,child,self)

                    print "EXPECT %s" % cmd
                    if self.hasErrors():
                        print "ERRORS %s" % cmd
                    elif executeMode:
                        match = re.search(pattern)
                        if match:
                            self.useMatch(child,match)
            sys.stdout.flush()

        elif stmt.tag == 'op' or stmt.tag == 'get' or stmt.tag == 'python' or stmt.tag == 'tempFile' or stmt.tag == 'update':
            evaluator = Evaluator(self.agent,self.context,None,executeMode)
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
            subgoal = Goal()
            subgoal.cfgSubGoal(goalName,self,self.context,stmt,self.agent.solver.remainingArgString,self.agent)
            self.agent.addGoal(subgoal)
            subgoal.pursue(executeMode)
            if not subgoal.isSuccess():
                print 'DEBUG: not copying return values beause goal failed'
                for error in subgoal.errors:
                    print error
                result = False
            else:
                subgoal.context.root.returnStateChildren(self.context.root,stmt)
        else:
            if self.agent.verboseMode(1):
                print 'SKIP tag %s which is neither a statement nor an expression' % stmt.tag

        if 'name' in stmt.attrib:
            if self.agent.verboseMode(1):
                print 'RETURN CONTEXT '+contextPre.getPath('.')

#        print 'DEBUG: state after %s:%d\n%s' % (stmt._file_name,stmt._start_line_number,self.context.details())
        self.agent.endStatement(stmt,self.context)

    def spawnThread(self):
        thread = Thread(functools.partial(self.pursue,self=self))

    def suspend(self):
        pass

class Command:
    def getName():
        raise NotImplementedError 

    def getProto():
        raise NotImplementedError 

class ConfigWrap:
    def __init__(self,node,createMode=False):
        self.__dict__['__node__'] = node
        self.__dict__['createMode'] = createMode

    def __len__(self):
        myNode = self.__dict__['__node__']
        return len(myNode.elements)

    def __getitem__(self,key):
        myNode = self.__dict__['__node__']
        sub = myNode.getElement(key)
        return ConfigWrap(sub,self.__dict__['createMode'])

    def __setitem__(self,key,value):
        myNode = self.__dict__['__node__']
        sub = myNode.getElement(key)
        ConfigWrap(sub,self.__dict__['createMode']).assign(value)

    def setCreateMode(self):
        self.__dict__['createMode'] = True

    def assign(self,value):
        myNode = self.__dict__['__node__']
        if myNode.rootConfig.solver.verboseMode(1):
            print 'ConfigWrap.assign %s := %s' % (myNode.getFullPath('.'),str(value))
        myNode.setValue(value)

    def deref(self):
        return self.__dict__['__node__']

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
        myNode = self.__dict__['__node__']
        sub = myNode.lookupTermList(self.__dict__['createMode'],[attr],myNode.rootConfig.solver)
        if isinstance(sub,ConfigNode):
            return ConfigWrap(sub,self.__dict__['createMode'])
        return sub

    def __setattr__(self,attr,value):
        myNode = self.__dict__['__node__']
        sub = myNode.lookupTermList(self.__dict__['createMode'],[attr],myNode.rootConfig.solver)
        if isinstance(sub,ConfigNode):
            ConfigWrap(sub,self.__dict__['createMode']).assign(value)

class ConfigNode:    
    def __init__(self,rootConfig,name):
        if name == None:
            raise RuntimeError('Cannot use an empty name')
        self.name = name
        self.rootConfig = rootConfig
        self.values = []
        self.selected = None
        self.assigned = None
        self.fields = None
        self.elements = None
        self.parent = None
        self.typeName = None

    def isDefnAttribute(self,attr):
        return attr == 'fields' or attr == 'elements'

    def hasDefnPath(self):
        if self.parent != None:
            return self.parent.hasDefnPath()
        else:
            return self.rootConfig.hasDefnPath()

    def getDefnPath(self,defnPath):
        if self.parent != None:
            self.parent.getDefnPath(defnPath)
        else:
            self.rootConfig.getDefnPath(defnPath)
        defnPath.append(self.name)

    def lookupRelPath(self,defnPath):
        if len(defnPath) == 0:
            return self
        if self.elements != None and defnPath[0] in self.elements:
            return self.elements[defnPath[0]].lookupRelPath(defnPath[1:])
        if self.fields != None and defnPath[0] in self.fields:
            return self.fields[defnPath[0]].lookupRelPath(defnPath[1:])
        raise RuntimeError('Unable to locate ConfigNode after %s using sufix path %s' % (self.getPath('.'),'.'.join(defnPath)))

    def afterUnpack(self):
        if id(self.assigned) == id(self):
            raise RuntimeError('FATAL: ConfigNode.assigned points to self')            

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
        return "%s %s" % (self.__class__.__name__,self.getFullPath('.'))

    def reset(self):
        self.selected = None
        self.assigned = None
        self.fields = None
        self.elements = None

    def configureMapping(self,mapping):
        for key,value in self.fields.iteritems():
            mapping[key] = ConfigWrap(value)

    def copyFrom(self,other,doAssign=True):
        self.reset()
        if id(self) == id(other):
            raise RuntimeError('FATAL: copyFrom from self to self (%s to %s)' % (self.getFullPath('.'),other.getFullPath('.')))
        if isinstance(other,ConfigWrap):
            other = other.node
        if not isinstance(other,ConfigNode):
            raise RuntimeError('FATAL: copyFrom source is not a ConfigNode %s' % other.__dict__)
        if doAssign:
            self.assigned = other
        elif self.assigned != None:
            self.assigned.copyFrom_r(other)
        self.copyFrom_r(other)

    def copyFrom_r(self,other):
#        print 'DEBUG: BEGIN ConfigNode.copyFrom(%s.%s <= %s.%s)' % (self.rootConfig.parent,self.getPath('.'),other.rootConfig.parent,other.getPath('.'))
        for otherVal in other.values:
            self.values.append(otherVal)
        if other.elements != None:
            if self.elements == None:
                self.elements = []
            for otherElement in other.elements:
                self.elements.append(try_clone_method(otherElement))
        if other.selected != None:
            self.selected = try_clone_method(other.selected)
        if other.fields != None:
            if self.fields == None:
                self.fields = dict()
            for key,field in other.fields.iteritems():
                if key not in self.fields:
                    self.fields[key] = ConfigNode(self.rootConfig,key)
                    self.fields[key].setParent(self)
                self.fields[key].copyFrom_r(other.fields[key])
            self.typeName = other.typeName
#        print 'DEBUG: END   ConfigNode.copyFrom(%s.%s <= %s.%s)' % (self.rootConfig.name,self.getPath('.'),other.rootConfig.name,other.getPath('.'))

    def summary(self):
        if isinstance(self.getValue(),ConfigNode):
            lvalue = self.getValue()
            result = ''
            while lvalue != None and isinstance(lvalue,ConfigNode):
                if lvalue.assigned != None:
                    lvalue = lvalue.assigned
                else:
                    result += '%s = %s (%s)\n' % (self.getFullPath('.'),lvalue.getFullPath('.'),lvalue.typeName if lvalue.typeName != None else '?')
                    lvalue = lvalue.getValue()
            result += '%s = %s (%s)\n' % (self.getFullPath('.'),lvalue,self.typeName if self.typeName != None else '?')
            return result
        else:
            return '%s = %s (%s)\n' % (self.getFullPath('.'),self.getValue(),self.typeName if self.typeName != None else '?')

    def details(self,recursive=True):
        result = self.summary()        
        if self.fields != None:
            for key,field in self.fields.iteritems():
                result += field.summary()
                if recursive:
                    result += field.details()
        if self.elements != None:
            for item in self.elements:
                result += item.summary()
                if recursive:
                    result += item.details()
        return result

    def tabulateSummary(self,result):
        lvalue = self
        while isinstance(lvalue,ConfigNode) and lvalue.assigned != None:
            lvalue = lvalue.assigned
        if lvalue.selected != None:
            result.makeRows(self.getPath('.'),lvalue.selected)
        return result

    def tabulate(self,result,recursive=True):
#        print 'DEBUG: BEGIN toDict(%s)' % self.getPath('.')
        self.tabulateSummary(result)
        if self.fields != None:
            for key,field in self.fields.iteritems():
#                print 'DEBUG: enter field %s' % key
                if recursive:
                    field.tabulate(result,recursive)
                else:
                    field.tabulateSummary(result)
        if self.elements != None:
            index = 0
            for item in self.elements:
#                print 'DEBUG: enter element %d' % index
                if recursive:
                    item.tabulate(result,recursive)
                else:
                    item.tabulateSummary(result)
                index += 1
#        print 'DEBUG: END   toDict(%s)' % self.getPath('.')
        return result

    def setupStruct(self):
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
        if self.assigned != None:
            self.assigned.initStateChildren(solver,context,xml)
            return

        if solver.verboseMode(1):
            print "BEGIN initState(%s) at %s:%d" % (self.getPath('.'),xml._file_name,xml._start_line_number)
        if xml.tag == 'struct' or xml.tag == 'goalCompleted' or xml.tag == 'goalProto' or xml.tag == 'agent' or xml.tag == 'event' or xml.tag == 'method':
#            if self.getValue() == None:
#                struct = dict()
#                self.setValue(struct)
#                print 'initState sets '+self.getPath('.')+' to new struct'
#            else:
#                struct = self.getValue()
            self.setupStruct()
            if solver.verboseMode(1):
                print 'initStateChildren creates struct at %s' % (self.getFullPath('.'))
            for child in xml:
                childName = child.get('name')
                if childName != None:
                    self.initStateNode(solver,context,child)
#                struct[child.get('name')] = node.getValue()
        elif xml.tag == 'variable' or xml.tag == 'list':
            if xml.tag == 'list':
                self.setupList()
            if len(xml) > 0 or xml.text:
                result = Evaluator(solver,context,None,False)
                result.setXML(xml)
                result.evaluate()
                if not result.isSuccess():
                    print 'Unable to interpret this XML expression: '+result.errors[0]
                elif result.getLvalue() != None:
                    if solver.verboseMode(1):
                        print 'initStateChildren assigns %s to lvalue %s' % (self.getFullPath('.'),result.getLvalue())
                    self.copyFrom(result.getLvalue())
                elif result.getRvalue() != None:
                    if solver.verboseMode(1):
                        print 'initStateChildren assigns %s to rvalue %s' % (self.getFullPath('.'),result.getRvalue())
                    self.setValue(result.getRvalue())

        if 'type' in xml.attrib:
            self.typeName = xml.get('type')

        if solver.verboseMode(1):
            print "END   initState(%s) at %s:%d" % (self.getPath('.'),xml._file_name,xml._start_line_number)

    def returnStateChildren(self,otherNode,xml):
        traceMode = self.rootConfig.solver.verboseMode(2)
        if traceMode:
            print "BEGIN returnState(from %s to %s) at %s:%d" % (self.getFullPath('.'),otherNode.getFullPath('.'),xml._file_name,xml._start_line_number)

        for myChild in xml:
            myChildName = myChild.get('name')
            if myChildName != None:
                if traceMode:
                    print '    returning %s' % myChildName
                for otherChild in myChild:
                    if otherChild.tag == 'get' or otherChild.tag == 'set':
                        if traceMode:
                            print '    found %s at %s:%d' % (otherChild.tag,otherChild._file_name,otherChild._start_line_number)
                        myNode = self.lookupTermList(False,['goal',myChildName],self.rootConfig.solver)
                        if traceMode:
                            print '    myNode is %s' % (myNode)
                        otherNode2 = otherNode.lookupString(False,otherChild.text,self.rootConfig.solver)
                        if traceMode:
                            print '    otherNode2 is %s' % (otherNode2)
                        if id(otherNode2) != id(myNode):
                            otherNode2.reset()
                            otherNode2.copyFrom(myNode,False)

        if traceMode:
            print "END   returnState(%s,%s) at %s:%d" % (self.getPath('.'),otherNode.getPath('.'),xml._file_name,xml._start_line_number)


    def getAttr(self,attr):
        if self.assigned != None:
            return self.assigned.getAttr(attr)
        elif hasattr(self,attr):
            return getattr(self,attr)
        elif self.fields != None and attr in self.fields:
            return self.fields[attr]
        elif hasattr(self.selected,attr):
            return getattr(self.selected,attr)
        else:
            raise 'Attribute %s is undefined in %s' % (attr,self.getFullPath('.'))

    def setAttr(self,attr,value,alloc=False):
        if self.assigned != None:
            self.assigned.setAttr(attr,value,alloc)
        if self.fields != None:
            if attr not in self.fields and alloc:
                newNode = ConfigNode(self.rootConfig,attr)
                newNode.setParent(self)
                self.fields[attr] = newNode
            self.fields[attr].setValue(value)
        return setattr(self.selected,attr)

    def getElement(self,key):
        if self.selected != None:
            if isinstance(self.selected,dict):
                return self.selected[key]
            elif hasattr(self.selected,key):
                return getattr(self.selected,key)
            else:
                raise 'getElement : Attribute %s is undefined in %s' % (attr,self.getFullPath('.'))
        if self.elements == None:
            raise RuntimeError('%s is not defined as a list with elements' % self.getPath('.'))
        return self.elements[key]

    def setElement(self,key,value):
        if self.selected != None:
            if isinstance(self.selected,dict):
                self.selected[key] = value
            else:
                setattr(self.selected,key,value)
        if self.elements == None:
            raise RuntimeError('%s is not defined an array' % getPath('.'))
        self.elements[key].setValue(value)

    def setValue(self,value):
        if id(value) == id(self):
            raise RuntimeError('FATAL ERROR: assigned ConfigNode to itself')
        if isinstance(value,ConfigNode):
            if self.rootConfig.solver.verboseMode(1):
                print 'ConfigNode.setValue copies '+value.getPath('.')+' to '+self.getPath('.')
            self.copyFrom(value)
        else:
            if self.rootConfig.solver.verboseMode(1):
                print 'ConfigNode.setValue assigns '+self.getFullPath('.')+' to '+str(value)
            if value == 'JanusGraphClusterDemo':
                raise RuntimeError('GOTCHA!')
            self.selected = value
            if self.assigned != None:
                if self.rootConfig.solver.verboseMode(1):
                    print 'ConfigNode.setValue delegates from %s to %s' % (self.getPath('.'),self.assigned.getPath('.'))
                self.assigned.setValue(value)

    def getValue(self):
        if self.assigned != None:
            return self.assigned
        elif self.elements != None:
            return self.elements
        elif self.fields != None:
            return self.fields
        return self.selected

    def setParent(self,parent):
        self.parent = parent

    def getFullPath(self,char):
        parentName = "?"
        if self.rootConfig != None and self.rootConfig.parent != None:
            parentName = self.rootConfig.parent.name
        result = '%s:%s' % (parentName,self.getPath(char))
        return result

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
        tmpLocals = dict()
#        if self.assigned != None:
#            print 'WARNING: %s is assigned to %s' % (self.getFullPath('.'),self.assigned.getFullPath('.'))
        for key in self.fields.keys():
#            print '    local %s' % key
#            print self.fields[key].details()
            tmpLocals[key] = ConfigWrap(self.fields[key],create)
#        print 'DEBUG: evaluating (%s) in %s' % (pathString,self.getFullPath('.'))
        result = eval(pathString,dict(),tmpLocals)
#        print 'DEBUG: eval returned %s' % result
        if isinstance(result,ConfigWrap):
            result = result.deref()
        return result

    def lookupTermList(self,create,pathTerms,errHandler):
        result = None
        traceMode = self.rootConfig.solver.verboseMode(2)
#        traceMode = True
        if self.assigned != None:
            if traceMode:
                print 'lookupTermList follows from %s to %s' % (self.getFullPath('.'),self.assigned.getFullPath('.'))
            return self.assigned.lookupTermList(create,pathTerms,errHandler)

        if traceMode:
            print 'BEGIN lookupTermList create: '+str(create)+' path: '+self.getFullPath('.')+' remainder: '+'.'.join(pathTerms)
        if(len(pathTerms) == 0):
            result = self
#            print 'DEBUG: no more path terms'
        elif pathTerms[0] == '':
            if errHandler != None: errHandler.createError('empty field name at %s' % self.getPath('.'))
        elif len(pathTerms) == 1 and self.selected != None:
            if isinstance(self.selected,dict):
                result = self.selected[pathTerms[0]]
            elif hasattr(self.selected,pathTerms[0]):
                result = getattr(self.selected,pathTerms[0])
            elif errHandler != None: errHandler.createError('%s is neither a dict nor an object but is %s' % (self.getPath('.'),self.selected))
        else:
            if self.fields == None:
                if create:
                    self.fields = dict()
                else:
                    if errHandler != None: errHandler.createError('%s is not configured as struct with any fields while looking for field %s' % (self.getPath('.'),pathTerms[0]))
            if self.fields != None and pathTerms[0] not in self.fields:
                if self.rootConfig.solver.verboseMode(1):
                    print 'DEBUG: field '+pathTerms[0]+' is missing from '+self.getPath('.')
                if create:
                    newNode = ConfigNode(self.rootConfig,pathTerms[0])
                    newNode.setParent(self)
                    self.fields[pathTerms[0]] = newNode
                    if len(pathTerms) > 1:
                        newNode.setupStruct()
                elif errHandler != None:
                    raise RuntimeError('No field named '+pathTerms[0]+' in expression '+self.getFullPath('.')+' fields include '+(','.join(self.fields.keys())))
                else:
                    if self.rootConfig.solver.verboseMode(1):
                        print 'END lookupTermList path: %s remainder: %s result: None' % (self.getPath('.'),'.'.join(pathTerms))
                    return None

#            print 'DEBUG: found field named '+pathTerms[0]
            if self.fields != None:
                result = self.fields[pathTerms[0]].lookupTermList(create,pathTerms[1:],errHandler)
        if traceMode:
            print 'END lookupTermList create: '+str(create)+' path: %s remainder: %s result: %s' % (self.getFullPath('.'),'.'.join(pathTerms),result)
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
        if self.selected != None or self.assigned != None:
            return
        elif len(self.values) > 0:
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
        if name == None:
            raise RuntimeError('Cannot use name=None')
        self.name = name
        self.root = ConfigNode(self,'root')
        self.desc = desc
        self.solver = solver
        self.parent = None

    def setup(self,name,xmlProto):
        self.root.initStateChildren(self.solver,self.solver.state,xmlProto)
#        print 'DEBUG: initial state of %s is:\n%s' % (self.desc,self.details())

    def setParent(self,parent):
        self.parent = parent

    def isDefnAttribute(self,attr):
        return attr == 'root'

    def hasDefnPath(self):
        return self.parent != None

    def getDefnPath(self,defnPath):
        if self.parent != None:
            self.parent.getDefnPath(defnPath)
        defnPath.append(self.name)

    def lookupRelPath(self,defnPath):
        if len(defnPath) == 0:
            return self
        if defnPath[0] == 'root':
            return self.root.lookupRelPath(defnPath[1:])
        raise RuntimeError('Unable to locate ConfigNode after %s using sufix path %s' % (self,'.'.join(defnPath)))

    def handleStateOverrides(self,agent,args,executeMode):
        # handle state overrides from cmdline
        errors = []
        parser = argparse.ArgumentParser()
        parser.add_argument('assignments',nargs='*')
        goalArgs = parser.parse_args(args)
        for assignment in goalArgs.assignments:
            tokens = assignment.split('=')
            if len(tokens) != 2:
                errors += ['Expected goal assignments but instead found command line argument: '+assignment]
#                print 'DEBUG: skipped command-line argument '+assignment
            else:
#                print 'DEBUG: parsed command-line assignment of '+tokens[0]+' := '+tokens[1]
                evaluator = Evaluator(agent,self,None,executeMode).setString(tokens[1])
                lhs = self.root.lookupTermList(False,tokens[0].split('.'),evaluator)
                asRef = None
                try:
                    asRef = self.root.lookupString(False,tokens[1],evaluator)
                except Exception as e:
                    pass
                if asRef == None:
                    try:
                        asRef = self.solver.state.root.lookupString(False,tokens[1],evaluator)
                    except Exception as e:
                        pass
                if lhs == None:
                    True
                elif asRef != None:
                    lhs.copyFrom(asRef)
                else:
                    lhs.setValue(tokens[1])

        if agent.verboseMode(1):
            if len(errors) > 0:
                print 'ERROR: %s' % '\n'.join(errors)

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

    def copyFrom(self,other,doAssign=True):
        self.root.copyFrom(other.root,doAssign)

    def reconfigure(self,stateConfig,prefix):
#        print 'DEBUG: BEGIN Config.reconfigure'
        self.root.lookupTermList(False,[prefix],None).reconfigure(stateConfig,self.root.lookupTermList(False,[prefix],None))
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

    def initPath(self,symbolPath,value):
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
