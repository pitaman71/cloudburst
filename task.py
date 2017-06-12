#!/usr/bin/python

import datetime
import logging

class Task:
	def __init__(self,purpose=None,logMethod=None):
		self.purpose = purpose
		self.startTime = datetime.datetime.now()
		self.endTime = None
		self.unitsExpected = dict()
		self.unitsConsumed = dict()
		self.logMethod = logMethod

		self.warnings = []
		self.errors = []
		self.returnValue = None

		self.status = 'BEGIN'
		if logMethod != None:
			logMethod(str(self))
		self.status = 'RUN'

	def __del__(self):
		self.endTime = datetime.datetime.now()
		self.status = 'END  '
		if self.logMethod != None:
			self.logMethod(str(self))		
		self.status = 'DONE'

	def expectUnits(self,unitType,unitCount):
		self.unitsExpected[unitType] = unitCount
		self.unitsConsumed[unitType] = 0

	def consumeUnits(self,unitType,unitCount):
		self.unitsConsumed[unitType] += unitCount

	def start(self):
		self.startTime = datetime.datetime.now()

	def finish(self):
		self.endTime = datetime.datetime.now()
		self.status = 'END'

	def returns(self,value):
		self.returnValue = value
		return value

	def info(self,message):
		asString = '\n'.join(message) if isinstance(message,list) else str(message)
		asList   = message if isinstance(message,list) else [str(message)]
		if self.logMethod:
			self.logMethod(asString)

	def warning(self,message):
		asString = '\n'.join(message) if isinstance(message,list) else str(message)
		asList   = message if isinstance(message,list) else [str(message)]
		if self.logMethod:
			self.logMethod(asString)
		self.warnings += asList

	def error(self,message):
		asString = '\n'.join(message) if isinstance(message,list) else str(message)
		asList   = message if isinstance(message,list) else [str(message)]
		if self.logMethod:
			self.logger(asString)
		self.errors += asList

	def reportUnit(self,unit,now):
		result = '%5s %s' % (self.status,self.purpose)
		result += ' | %d/%d %s' % (self.unitsConsumed[unit],self.unitsExpected[unit],unit)
		result += ' | %lf%% complete' % (100.0*self.unitsConsumed[unit]/self.unitsExpected[unit])
		if self.startTime != None:
			result += ' | %lf %s/second' % (self.unitsConsumed[unit]/(now - self.startTime).total_seconds(),unit)
		return result

	def __str__(self):
		result = None
		now = self.endTime
		if now == None:
			now = datetime.datetime.now()
		if len(self.unitsExpected.keys()) == 0:
			result = '%s %s' % (self.status,self.purpose)
		else:
			minUnit = None
			minCompletion = None
			for unit,consumed in self.unitsConsumed.iteritems():
				completion = float(consumed) / self.unitsExpected[unit]
				if minUnit == None or minCompletion < completion:
					minCompletion = completion
					minUnit = unit
			result = self.reportUnit(minUnit,now)
		if self.returnValue != None:
			result = '%s RETURNS %s' % (result,self.returnValue)
		return result

	def details(self):
		result = ''
		now = self.endTime
		if now == None:
			now = datetime.datetime.now()
		if len(self.unitsExpected.keys()) == 0:
			result = '%s %s' % (self.status,self.purpose)		
		for unit,consumed in self.unitsConsumed.iteritems():
			result += self.reportUnit(unit,now)
		return result
