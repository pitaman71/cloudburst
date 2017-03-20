#!/usr/bin/python

import datetime
import logging

class Task:
	def __init__(self,purpose=None,logger=None):
		self.purpose = purpose
		self.startTime = None
		self.endTime = None
		self.unitsExpected = dict()
		self.unitsConsumed = dict()
		self.warnings = []
		self.errors = []
		self.status = 'READY'
		if logger == True:
			self.logger = logging.getLogger()
		else:
			self.logger = logger
		self.startTime = datetime.datetime.now()
		self.status = 'BEGIN'
		if self.logger:
			self.logger.info(str(self))
		self.status = 'RUN'

	def __del__(self):
		self.endTime = datetime.datetime.now()
		self.status = 'END  '
		if self.logger:
			self.logger.info(str(self))
		self.status = 'DONE'

	def expectUnits(self,unitType,unitCount):
		self.unitsExpected[unitType] = unitCount
		self.unitsConsumed[unitType] = 0

	def consumeUnits(self,unitType,unitCount):
		self.unitsConsumed[unitType] += unitCount

	def info(self,message):
		asString = '\n'.join(message) if isinstance(message,list) else str(message)
		asList   = message if isinstance(message,list) else [str(message)]
		if self.logger:
			self.logger.info(asString)

	def warning(self,message):
		asString = '\n'.join(message) if isinstance(message,list) else str(message)
		asList   = message if isinstance(message,list) else [str(message)]
		if self.logger:
			self.logger.warning(asString)
		self.warnings += asList

	def error(self,message):
		asString = '\n'.join(message) if isinstance(message,list) else str(message)
		asList   = message if isinstance(message,list) else [str(message)]
		if self.logger:
			self.logger.error(asString)
		self.errors += asList

	def reportUnit(self,unit,now):
		result = '%s %s' % (self.status,self.purpose)
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
