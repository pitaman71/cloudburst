#!/usr/bin/python

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

    def hasKey(self,obj):
        return False

    def getKey(self,obj):
        return None

    def getType(self,obj):
        return obj.__class__.__name__

    def lookupKey(self,key):
        return None

    def doInline(self,fromObj,attr,toObj):
        return False

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
        return self.unpackObject(rep,[])

    def unpackObject(self,rep,stack):
        self.debugMessage('BEGIN unpackObject of type %s' % type(rep))
        obj = None
        try:
            if rep == None:
                pass
            elif '__ref__' in rep:
                obj = self.lookupKey(rep['__ref__'])
            elif '__type__' in rep:
                typeName = rep['__type__']
                if typeName == 'StackRefType':
                    obj = stack[rep['depth']]
    #            elif not hasattr(sys.modules[__name__], typeName):
                elif not hasattr(hive, typeName):
                    raise RuntimeError('Cannot locate class definition for %s' % typeName)
                else:
                    obj = self.create(typeName,rep)
                    stack.append(obj)
                    members = dict()
                    for key,value in rep['members'].iteritems():
                        self.debugMessage('unpackObject key %s' % str(key))
                        members[key] = self.unpackObject(value,stack)
                    obj.__dict__ = members
                    if '__def__' in rep:
                        self.defByName[rep['__def__']] = obj
                        self.defByOrder.append(obj)
                    stack.pop()
            elif type(rep) in (tuple,list):
                obj = []
                stack.append(obj)
                for item in rep:
                    obj.append(self.unpackObject(item,stack))
                if type(rep) == tuple:
                    obj = tuple(obj)
                stack.pop()
            elif type(rep) == dict:
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

    def prepackObject(self,obj,isBase,stack):
        self.debugMessage('BEGIN prepackObject of type %s' % type(obj))
        self.debugMessage('      value %s' % str(obj))

        if obj not in stack:
            stack.append(obj)
            try:
                if obj == None:
                    pass
                elif type(obj) in (tuple,list):
                    for item in obj:
                        self.prepackObject(item,isBase,stack)
                elif type(obj) == dict:
                    for key,value in obj.iteritems():
                        self.debugMessage('prepackObject key %s' % str(key))
                        self.prepackObject(value,isBase,stack)
                elif not hasattr(obj,'__dict__'):
                    self.debugMessage('prepackObject value %s' % str(obj))
                    pass
                elif self.hasKey(obj):
                    key = self.getKey(obj)
                    if key not in self.defByName:
                        self.defByName[key] = obj
                        self.prepackObject(obj,False,stack)
                        self.defOrder.append(obj)
                    if not isBase:
                        self.debugMessage('prepackObject REF %s' % str(key))
                    else:
                        self.debugMessage('prepackObject DEF %s' % str(key))
                        for key,value in obj.__dict__.iteritems():
                            self.prepackObject(value,isBase and self.doInline(obj,key,value),stack)
                elif obj in self.pointers:
                    raise RuntimeError('Recursion detected on object %s' % obj)
                else:
                    self.pointers[obj] = True
                    for key,value in obj.__dict__.iteritems():
                        self.prepackObject(value,False,stack)
            except Exception as e:
                ex_type, ex, tb = sys.exc_info()                
                print 'ERROR: during prepackObject\n%s\n%s' % (str(e),traceback.print_tb(tb))
            stack.pop()
        self.debugMessage('END   prepackObject of type %s' % type(obj))

    def packObject(self,obj,isBase,stack):
        result = None
        self.debugMessage('BEGIN packObject of type %s' % type(obj))

        if obj in stack:
            result = dict(type="StackRefType",depth=stack.index(obj))
        else:
            stack.append(obj)
            try:
                if obj == None:
                    pass
                elif type(obj) in (tuple,list):
                    result = []
                    self.debugMessage('packObject LIST')
                    for item in obj:
                        result.append(self.packObject(item,isBase,stack))
                    if type(obj) == tuple:
                        result = tuple(result)
                elif type(obj) == dict:
                    result = dict()
                    for key,value in obj.iteritems():
                        self.debugMessage('packObject key %s' % str(key))
                        sys.stderr.flush()
                        result[key] = self.packObject(value,isBase,stack)
                elif not hasattr(obj,'__dict__'):
                    self.debugMessage('packObject value %s' % str(obj))
                    sys.stderr.flush()
                    result = obj
                elif self.hasKey(obj):
                    key = self.getKey(obj)
                    if not isBase:
                        self.debugMessage('packObject REF %s' % str(key))
                        result = dict()
                        result['__ref__']=key
                        result['__type__']=self.getType(obj)
                    else:
                        self.debugMessage('packObject DEF %s' % str(key))
                        result = dict()
                        result['__def__']=key
                        result['__type__']=self.getType(obj)
                        result['members'] = dict()
                        for key,value in obj.__dict__.iteritems():
                            result['members'][key] = self.packObject(value,isBase and self.doInline(obj,key,value),stack)
                elif obj in self.pointers:
                    raise RuntimeError('Recursion detected on object %s' % obj)
                else:
                    self.pointers[obj] = True
                    result = dict()
                    result['__type__']=self.getType(obj)
                    result['members'] = dict()
                    for key,value in obj.__dict__.iteritems():
                        result['members'][key] = self.packObject(value,isBase and self.doInline(obj,key,value),stack)
            except Exception as e:
                ex_type, ex, tb = sys.exc_info()                
                print 'ERROR: during packObject\n%s\n%s' % (str(e),traceback.print_tb(tb))
            stack.pop()
        self.debugMessage('END   packObject of type %s' % type(obj))
        return result


