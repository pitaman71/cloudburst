#!/usr/bin/python
import sys
import traceback
import task
import logging
import datetime

import sys

class Shipper:
    """ Base class for a reversible object packing/unpacking process that can be used to implement object persistence or
    shared consistency. The "pack" operation takes a Python data structure and converts it to a serialization-friendly 
    representation as nested Python lists and dicts, which can then be passed to syntax-specific backend methods such as
    json.dumps(). The "unpack operation" is the inverse, taking a serialization-friendly representation as nested Python
    lists and dicts (which may be sourced from a syntax-specific backend such as json.loads()) and converts it back into a
    Python data structure.

    The origin of this class was limitations of the pickle and jsonpickle Python packages for the case where the data
    structure has a mixture of serialization by value and by reference. Shipper provides an object oriented interface
    that allows dervied classes to intercept the recursive serialization process and decide - possibly based on 
    an application-specific procedure - if the object should be serialized as a value, as an inline defintion, or as
    a reference. 

    The class also provides a debug facility, which can be activated by client code setting Shipper.debugFile to
    point to an output stream such as sys.stderr. 
    """
    def __init__(self,module=None):
        self.status = dict()
        self.pointers = dict()
        self.defByName = dict()
        self.defOrder = []
        self.values = []
        self.defnPathStack = []
        self.serializationLog = logging.getLogger("%s.%s" % (self.__class__.__name__,'serialization'))
        self.module = module
        if module == None:
            self.module = sys.modules[__name__]

    def hasKey(self,obj):
        return False

    def getKey(self,obj):
        return None

    def getType(self,obj):
        return obj.__class__.__name__

    def lookupKey(self,key):
        if key in self.defByName:
#            print 'DEBUG: Found %s = %s' % (key,self.defByName[key])
            return self.defByName[key]
#        print 'DEBUG: Shipper.lookupKey did not find %s' % (key)
        return None

    def refIsDef(self,stack,attr,toObj):
        return False

    def mergeMembers(self,obj,newMembers):
        for key in newMembers:
            obj.__dict__[key] = newMembers[key]

    def addDefinition(self,obj):
        self.defs.append(obj)

    def addValue(self,val):
        self.values.append(val)

    def prepack(self):
        self.pointers = dict()
        for obj in self.values:
            self.prepackObject(obj,True,[],[])

    def reset(self):
        self.pointers = dict()

    def create(self,typeName,rep):
        if not hasattr(self.module,typeName):
            return None
        klass = getattr(self.module, typeName)
        obj = klass()
        return obj

    def packDefinitions(self):
        rep = []
        self.reset()
        for obj in self.defOrder:
            rep.append(self.packObject(obj,True,[]))
        return rep

    def packValues(self):
        """ encodes definitions and values that have been added to this object via calls to addDefinition and addValue
        into dict-list form suitable for serialization"""
        rep = []
        self.reset()
        for obj in self.values:
            rep.append(self.packObject(obj,True,[]))
        return rep

    def unpack(self,rep):
        tmp = self.unpackObject(rep,[])
        self.reset()
        return self.postUnpackObject(tmp,False,[])

    def unpackByType(self,rep,stack,typeName):
        obj = None
        if typeName == 'StackRefType':
            obj = stack[rep['depth']]
        else:
            obj = self.create(typeName,rep)
            if obj == None:
                raise RuntimeError('Cannot locate class definition for %s along path %s' % (typeName,','.join([str(stack[len(stack) - i - 1]) for i in range(0,len(stack))])))
            stack.append(obj)
            members = dict()
            if 'members' in rep:
                for key,value in rep['members'].iteritems():
                    self.debugMessage('unpackObject key %s' % str(key))
                    members[key] = self.unpackObject(value,stack)
            obj.__dict__ = members
            if '__def__' in rep:
                self.defByName[rep['__def__']] = obj
                self.defByOrder.append(obj)
            stack.pop()
        return obj

    def unpackObject(self,rep,stack):
        objType = str(rep)
        if isinstance(rep,dict) and '__type__' in rep:
            objType = rep['__type__']
        myTask = task.Task(('unpackObject of type %s' % objType),logger=self.serializationLog)
        obj = None
        if rep == None:
            pass
        elif type(rep) in (tuple,list):
            obj = []
            stack.append(obj)
            for item in rep:
                obj.append(self.unpackObject(item,stack))
            if type(rep) == tuple:
                obj = tuple(obj)
            stack.pop()
        elif type(rep) == dict:
            if '__ref__' in rep:
#                    print 'REFERENCE %s' % rep['__ref__']
                obj = self.lookupKey(rep['__ref__'])
                if obj == None:
                    obj = rep
            elif '__stack__' in rep:
                selected = len(stack) - int(rep['__stack__'])
#                    print 'DEBUG: stack seeking type %s' % rep['__type__']
#                    for index in range(0,len(stack)):
#                        print 'DEBUG: stack[%d] = %s %s' % (index,stack[index],'SELECTED' if index == selected else '')
                obj = stack[selected]
            elif '__type__' in rep:
                typeName = rep['__type__']
                obj = None
                created = False
                if '__def__' in rep and rep['__def__'] in self.defByName:
                    obj = self.defByName[rep['__def__']]
                if obj == None:
                    obj = self.create(typeName,rep)
                    created = True
                if obj == None:
                    raise RuntimeError('Cannot locate class definition for %s' % (typeName))
                stack.append(obj)
                if created and hasattr(obj,'beforeUnpack'):
                    created.beforeUnpack()
                members = self.unpackObject(rep['__members__'],stack)
                self.mergeMembers(obj,members)
                if '__def__' in rep:
#                        print 'DEFINE %s' % rep['__def__']
                    self.defByName[rep['__def__']] = obj
                    self.defOrder.append(obj)
                if obj != None and hasattr(obj,'afterUnpack'):
                    obj.afterUnpack()
                stack.pop()
            else:
                obj = dict()
                stack.append(obj)
                keyOrder = self.attributeOrder(rep,stack)
                for key in keyOrder:
                    value = rep[key]
                    myTask.info('unpackObject key %s' % str(key))
                    obj[key] = self.unpackObject(value,stack)
                stack.pop()
        else:
            myTask.info('unpackObject value %s' % str(rep))
            obj = rep

        return obj

    def postUnpackObject(self,obj,nextRefIsDef,stack):
        objType = (obj.__class__.__name__ if hasattr(obj,'__class__') else type(obj))
#        myTask = task.Task(('postUnpackObject of type %s' % objType),logger=self.serializationLog)
        myTask = task.Task('postUnpackObject of type %s' % objType,logger=True)

        result = None
        stack.append(obj)

        if obj == None:
            pass
        elif type(obj) in (tuple,list):
            result = []
            for item in obj:
                result.append(self.postUnpackObject(item,nextRefIsDef,stack))
        elif type(obj) == dict:
            if '__ref__' in obj:
#                print 'DEBUG: cross reference %s' % obj['__ref__']
                the = self.lookupKey(obj['__ref__'])
                if the == None:
                    raise RuntimeError('Unable to resolve reference %se' % obj)
                myTask.info('postUnpackObject resolved %s to %s' % (obj['__ref__'],the))
                result = the
                if id(result) not in self.pointers:
                    self.pointers[id(result)] = True
                    stack.append(the)
                    self.postUnpackObject(result.__dict__,False,stack)
                    stack.pop()
            else:
                result = dict()
                keyOrder = self.attributeOrder(obj,stack)
                if 'lock' in keyOrder:
                    raise RuntimeError('ERROR: lock is in keyOrder for %s\n*** %s' % (obj,'\n*** '.join([str(obj) for obj in stack])))
                for key in keyOrder:
                    value = obj[key]
                    myTask.info('postUnpackObject follows key %s' % str(key))
                    result[key] = self.postUnpackObject(value,nextRefIsDef or self.refIsDef(stack,key,value),stack)
        elif self.packAsScalar(obj):
            myTask.info('postUnpackObject value %s' % str(obj))
            result = obj
        elif self.hasKey(obj):
            myTask.info('postUnpackObject REF/DEF %s' % str(self.getKey(obj)))
            result = obj
            if id(result) not in self.pointers:
                stack.append(result)
                self.pointers[id(result)] = True
                newMembers = self.postUnpackObject(result.__dict__,False,stack)
                for key,value in newMembers.iteritems():
                    result.__dict__[key] = value
                stack.pop()
        elif id(obj) not in self.pointers:
            self.pointers[id(obj)] = True
            self.postUnpackObject(obj.__dict__,False,stack)
            result = obj
        else:
            result = obj

        stack.pop()
        if result == None and obj != None:
            raise RuntimeError('Unable to cross-reference %s' % obj)
        return result

    def attributeOrder(self,obj,stack):
        return obj.keys()

    def packAsVoid(self,obj):
        return False

    def packAsScalar(self,obj):
        return isinstance(obj,bool) or isinstance(obj,str) or isinstance(obj,int) or isinstance(obj,float) or isinstance(obj,unicode) or isinstance(obj,datetime.datetime)

    def prepackObject(self,obj,nextRefIsDef,stack,keyStack):
        objType = (obj.__class__.__name__ if hasattr(obj,'__class__') else type(obj))
        myTask = task.Task('prepackObject of type %s' % objType,logger=self.serializationLog)
        if objType == 'ResourceModel':
            message = 'ResourceModel object serialized\n'
            for i in range(0,len(stack)):
                message += '    value %s\n' % (stack[len(stack)-i-1])
            raise RuntimeError(message)

        if id(obj) not in [id(item) for item in stack]:
            stack.append(obj)
            if obj == None:
                pass
            elif type(obj) in (tuple,list):
                index = 0
                for item in obj:
                    self.prepackObject(item,nextRefIsDef,stack,keyStack+[index])
                    index += 1
            elif type(obj) == dict:
                keyOrder = self.attributeOrder(obj,stack)
                for key in keyOrder:
                    value = obj[key]
                    myTask.info('prepackObject follows key %s' % str(key))
                    self.prepackObject(value,nextRefIsDef or self.refIsDef(stack,key,value),stack,keyStack+[key])
            elif self.packAsVoid(obj):
                myTask.info('prepackObject void %s' % str(obj).decode('utf8'))
                pass
            elif self.packAsScalar(obj):
                myTask.info('prepackObject value %s' % str(obj).decode('utf8'))
                pass
            elif self.hasKey(obj):
                key = self.getKey(obj)
                if nextRefIsDef:
                    self.defByName[key] = obj
                    self.defOrder.append(obj)
                    myTask.info('prepackObject DEF %s' % str(key))
                    self.prepackObject(obj.__dict__,False,stack,keyStack+[key])
                else:
                    myTask.info('prepackObject REF %s' % str(key))
            elif id(obj) in self.pointers:
                pass
#                raise RuntimeError('Recursion detected on object %s\nprev = %s\nnew = %s' % (obj,self.pointers[id(obj)],','.join([str(item) for item in keyStack])))
            else:
                self.pointers[id(obj)] = ','.join([str(item) for item in keyStack])
                if not hasattr(obj,'__dict__'):
                    print 'WARNING: this object is not really an object! %s' % obj
                else:
                    self.prepackObject(obj.__dict__,False,stack,keyStack)
            stack.pop()

    def packObject(self,obj,nextRefIsDef,stack):
        objType = (obj.__class__.__name__ if hasattr(obj,'__class__') else type(obj))
        myTask = task.Task(('packObject of type %s' % objType),logger=self.serializationLog)
        result = None

        if not hasattr(obj,'getDefnPath'):
            pass
        elif len(self.defnPathStack) == 0:
            obj.getDefnPath(self.defnPathStack)

        if obj in stack:
            result = dict()
            result['__type__'] = self.getType(obj)
            result['__stack__']=len(stack) - stack.index(obj)
        else:
            stack.append(obj)
            if obj == None:
                pass
            elif type(obj) in (tuple,list):
                result = []
                myTask.info('packObject LIST')
                index = 0
                for item in obj:
                    result.append(self.packObject(item,nextRefIsDef or self.refIsDef(stack,str(index),item),stack))
                    index += 1
                if type(obj) == tuple:
                    result = tuple(result)
            elif type(obj) == dict:
                result = dict()
                keyOrder = self.attributeOrder(obj,stack)
                for key in keyOrder:
                    value = obj[key]
                    myTask.info('packObject follows key %s' % str(key))
                    result[key] = self.packObject(value,nextRefIsDef or self.refIsDef(stack,key,value),stack)
            elif self.packAsVoid(obj):
                myTask.info('packObject void %s' % str(obj).decode('utf8'))
                result = None
            elif self.packAsScalar(obj):
                myTask.info('packObject value %s' % str(obj).decode('utf8'))
                result = obj
            elif not hasattr(obj,'__dict__'):
                raise RuntimeError('Cannot pack object of type %s' % type(obj))
            elif self.hasKey(obj):
                key = self.getKey(obj)
                if not nextRefIsDef:
                    myTask.info('packObject REF %s' % str(key))
                    result = dict()
                    result['__ref__']=key
                    result['__type__']=self.getType(obj)
                else:
                    myTask.info('packObject DEF %s' % str(key))
                    result = dict()
                    result['__def__']=key
                    result['__type__']=self.getType(obj)
                    result['__members__'] = self.packObject(obj.__dict__,False,stack)
            elif id(obj) in self.pointers:
                myTask.info('skip object of type %s' % (obj.__class__.__name__ if hasattr(obj,'__class__') else type(obj)))
                pass
#                    raise RuntimeError('Recursion detected on object %s' % obj)
            else:
                self.pointers[id(obj)] = True
                result = dict()
                result['__type__']=self.getType(obj)
                result['__members__'] = self.packObject(obj.__dict__,False,stack)
            stack.pop()
        return result


