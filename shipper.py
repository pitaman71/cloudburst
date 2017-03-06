#!/usr/bin/python
import sys
import traceback

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
    def __init__(self):
        self.status = dict()
        self.pointers = dict()
        self.defByName = dict()
        self.defOrder = []
        self.values = []
        self.debugFile = None
        self.defnPathStack = []

    def hasKey(self,obj):
        return False

    def getKey(self,obj):
        return None

    def getType(self,obj):
        return obj.__class__.__name__

    def lookupKey(self,key):
        if key in self.defByName:
            return self.defByName[key]
        return None

    def refIsDef(self,stack,attr,toObj):
        return False

    def mergeMembers(self,obj,newMembers):
        for key in newMembers:
            obj.__dict__[key] = newMembers[key]

    def addDefinition(self,obj):
        self.defs.append(obj)

    def debugMessage(self,message):
        if self.debugFile != None:
            print >>self.debugFile,message

    def addValue(self,val):
        self.values.append(val)

    def prepack(self):
        self.pointers = dict()
        for obj in self.values:
            self.prepackObject(obj,True,[])

    def reset(self):
        self.pointers = dict()

    def create(self,typeName,rep):
        klass = getattr(sys.modules[__name__], typeName)
        obj = klass()

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
        return self.postUnpackObject(tmp,False,[])

    def unpackObject(self,rep,stack):
        self.debugMessage('BEGIN unpackObject of type %s' % type(rep))
        obj = None
        try:
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
                    print 'REFERENCE %s' % rep['__ref__']
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
                    if '__def__' in rep and rep['__def__'] in self.defByName:
                        obj = self.defByName[rep['__def__']]
                    if obj == None:
                        obj = self.create(typeName,rep)
                    if obj == None:
                        raise RuntimeError('Cannot locate class definition for %s' % typeName)
                    stack.append(obj)
                    members = self.unpackObject(rep['__members__'],stack)
                    self.mergeMembers(obj,members)
                    if '__def__' in rep:
                        print 'DEFINE %s' % rep['__def__']
                        self.defByName[rep['__def__']] = obj
                        self.defOrder.append(obj)
                    stack.pop()
                else:
                    obj = dict()
                    stack.append(obj)
                    for key,value in rep.iteritems():
                        self.debugMessage('unpackObject key %s' % str(key))
                        obj[key] = self.unpackObject(value,stack)
                    stack.pop()
            else:
                self.debugMessage('unpackObject value %s' % str(rep))
                obj = rep
        except Exception as e:
            ex_type, ex, tb = sys.exc_info()                
            print 'ERROR: during unpackObject\n%s\n%s' % (str(e),traceback.print_tb(tb))

        self.debugMessage('END   unpackObject of type %s' % type(rep))
        return obj

    def postUnpackObject(self,obj,nextRefIsDef,stack):
        self.debugMessage('BEGIN postUnpackObject(%d) of type %s' % (len(stack),obj.__class__.__name__ if hasattr(obj,'__class__') else type(obj)))

        result = None
        if obj not in stack:
            stack.append(obj)
            try:
                if obj == None:
                    pass
                elif type(obj) in (tuple,list):
                    replacement = []
                    for item in obj:
                        replacement.append(self.postUnpackObject(item,nextRefIsDef,stack))
                    result = replacement
                elif type(obj) == dict:
                    if '__ref__' in rep:
                        the = self.lookupKey(rep['__ref__'])
                        if the == None:
                            raise RuntimeError('Unable to resolve reference %s' % obj)
                        result = the
                    else:
                        replacement = dict()
                        for key,value in obj.iteritems():
                            if self.skipAttribute(stack,key,value):
                                self.debugMessage('postUnpackObject skips key %s' % str(key))
                            else:
                                self.debugMessage('postUnpackObject follows key %s' % str(key))
                                replacement[key] = self.postUnpackObject(value,nextRefIsDef or self.refIsDef(stack,key,value),stack)
                elif self.packAsScalar(obj):
                    self.debugMessage('postUnpackObject value %s' % str(obj))
                    replacement = obj
                    pass
                elif self.hasKey(obj):
                    key = self.getKey(obj)
                    if nextRefIsDef:
                        self.defByName[key] = obj
                        self.defOrder.append(obj)
                        self.debugMessage('postUnpackObject DEF %s' % str(key))
                        result = self.postUnpackObject(obj.__dict__,False,stack)
                    else:
                        self.debugMessage('postUnpackObject REF %s' % str(key))
                        result = obj
                elif id(obj) in self.pointers:
                    raise RuntimeError('Recursion detected on object %s' % obj)
                else:
                    self.pointers[id(obj)] = True
                    self.postUnpackObject(obj.__dict__,False,stack)
                    result= obj
            except Exception as e:
                ex_type, ex, tb = sys.exc_info()                
                print 'ERROR: during postUnpackObject\n%s\n%s' % (str(e),traceback.print_tb(tb))
            stack.pop()
        if result == None:
            raise RuntimeError('Unable to deduce origin of %s' % obj)
        self.debugMessage('END   postUnpackObject(%d) of type %s' % (len(stack),obj.__class__.__name__ if hasattr(obj,'__class__') else type(obj)))
        return result

    def skipAttribute(self,stack,attr,toObj):
        return False

    def packAsScalar(self,obj):
        return isinstance(obj,bool) or isinstance(obj,str) or isinstance(obj,int) or isinstance(obj,float) or isinstance(obj,unicode)

    def prepackObject(self,obj,nextRefIsDef,stack):
        self.debugMessage('BEGIN prepackObject(%d) of type %s' % (len(stack),obj.__class__.__name__ if hasattr(obj,'__class__') else type(obj)))

        if obj not in stack:
            stack.append(obj)
            try:
                if obj == None:
                    pass
                elif type(obj) in (tuple,list):
                    for item in obj:
                        self.prepackObject(item,nextRefIsDef,stack)
                elif type(obj) == dict:
                    for key,value in obj.iteritems():
                        if self.skipAttribute(stack,key,value):
                            self.debugMessage('prepackObject skips key %s' % str(key))
                        else:
                            self.debugMessage('prepackObject follows key %s' % str(key))
                            self.prepackObject(value,nextRefIsDef or self.refIsDef(stack,key,value),stack)
                elif self.packAsScalar(obj):
                    self.debugMessage('prepackObject value %s' % str(obj))
                    pass
                elif self.hasKey(obj):
                    key = self.getKey(obj)
                    if nextRefIsDef:
                        self.defByName[key] = obj
                        self.defOrder.append(obj)
                        self.debugMessage('prepackObject DEF %s' % str(key))
                        self.prepackObject(obj.__dict__,False,stack)
                    else:
                        self.debugMessage('prepackObject REF %s' % str(key))
                elif id(obj) in self.pointers:
                    raise RuntimeError('Recursion detected on object %s' % obj)
                else:
                    self.pointers[id(obj)] = True
                    self.prepackObject(obj.__dict__,False,stack)
            except Exception as e:
                ex_type, ex, tb = sys.exc_info()                
                print 'ERROR: during prepackObject\n%s\n%s' % (str(e),traceback.print_tb(tb))
            stack.pop()
        self.debugMessage('END   prepackObject(%d) of type %s' % (len(stack),obj.__class__.__name__ if hasattr(obj,'__class__') else type(obj)))

    def packObject(self,obj,nextRefIsDef,stack):
        result = None
        self.debugMessage('BEGIN packObject of type %s' % type(obj))

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
            try:
                if obj == None:
                    pass
                elif type(obj) in (tuple,list):
                    result = []
                    self.debugMessage('packObject LIST')
                    for item in obj:
                        result.append(self.packObject(item,nextRefIsDef,stack))
                    if type(obj) == tuple:
                        result = tuple(result)
                elif type(obj) == dict:
                    result = dict()
                    for key,value in obj.iteritems():
                        if self.skipAttribute(stack,key,value):
                            self.debugMessage('packObject skips key %s' % str(key))
                        else:
                            self.debugMessage('packObject follows key %s' % str(key))
                            result[key] = self.packObject(value,nextRefIsDef or self.refIsDef(stack,key,value),stack)
                elif self.packAsScalar(obj):
                    self.debugMessage('packObject value %s' % str(obj))
                    result = obj
                elif not hasattr(obj,'__dict__'):
                    raise RuntimeError('Cannot pack object of type %s' % type(obj))
                elif self.hasKey(obj):
                    key = self.getKey(obj)
                    if not nextRefIsDef:
                        self.debugMessage('packObject REF %s' % str(key))
                        result = dict()
                        result['__ref__']=key
                        result['__type__']=self.getType(obj)
                    else:
                        self.debugMessage('packObject DEF %s' % str(key))
                        result = dict()
                        result['__def__']=key
                        result['__type__']=self.getType(obj)
                        result['__members__'] = self.packObject(obj.__dict__,False,stack)
                elif id(obj) in self.pointers:
                    raise RuntimeError('Recursion detected on object %s' % obj)
                else:
                    self.pointers[id(obj)] = True
                    result = dict()
                    result['__type__']=self.getType(obj)
                    result['__members__'] = self.packObject(obj.__dict__,False,stack)
            except Exception as e:
                ex_type, ex, tb = sys.exc_info()                
                print 'ERROR: during packObject\n%s\n%s' % (str(e),traceback.print_tb(tb))
            stack.pop()
        self.debugMessage('END   packObject of type %s' % (obj.__class__.__name__ if hasattr(obj,'__class__') else type(obj)))
        return result


