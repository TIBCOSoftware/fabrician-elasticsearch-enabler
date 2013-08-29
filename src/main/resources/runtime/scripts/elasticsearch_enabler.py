#
# Copyright (c) 2013 TIBCO Software Inc. All Rights Reserved.
# 
# Use is subject to the terms of the TIBCO license terms accompanying the download of this code. 
# In most instances, the license terms are contained in a file named license.txt.
#

from com.datasynapse.fabric.admin.info import AllocationInfo, ComponentInfo, EngineIdInfo, FabricEngineInfo, ComponentAllocationEntryInfo
from com.datasynapse.fabric.util import GridlibUtils, ContainerUtils
from com.datasynapse.fabric.common import RuntimeContextVariable, ActivationInfo
from com.datasynapse.fabric.engine.managedprocess import ManagedProcess
from com.datasynapse.fabric.container import Feature, Container
from com.datasynapse.gridserver.admin import Property
from com.datasynapse.fabric.common import ArchiveActivationInfo

from com.datasynapse.fabric.admin import AdminManager, ComponentAdmin
from com.datasynapse.fabric.admin.info import GridlibInfo

from jarray import array
from java.lang import StringBuilder
import java.lang.System
from subprocess import Popen, PIPE, STDOUT, call

import os
import sys, java, types
import platform
import time
import socket
import fnmatch
import urllib
import urllib2, httplib
import shutil
import errno
import shlex
from java.util import Properties

jarpath = runtimeContext.getVariable('CONTAINER_GRIDLIB_DIR').getValue()
sys.path.append(os.path.join(jarpath,"ds_jars", "json-path-0.8.1.jar"))
sys.path.append(os.path.join(jarpath,"ds_jars", "commons-lang-2.6.jar"))
sys.path.append(os.path.join(jarpath,"ds_jars", "json-smart-1.1.1.jar"))
from com.jayway.jsonpath import JsonPath as jpath


sys.setrecursionlimit(1500)


#######
# Add Enabler Dependancies
#######

def getDynamicGridlibDependencies():
    logInfo("Beginning getDynamicGridlibDependencies()")
    ELASTIC_VERSION = getElasticSearchVersion()
    logInfo("ElasticSearch Distribution version is [" + str(ELASTIC_VERSION) + "]")
    defaultDomainGridlib = GridlibInfo()
    defaultDomainGridlib.name = "default-domain-type"
    logInfo("Adding ElasticSearch distribution dependency")
    gridlib = GridlibInfo()
    gridlib.name = "elasticsearch-distribution"
    gridlib.version = str(ELASTIC_VERSION)
    logInfo("Exiting getDynamicGridlibDependencies()")
    return array([gridlib, defaultDomainGridlib], GridlibInfo)


def getElasticSearchVersion():
    ElasticSearchVersionVar = proxy.getContainer().getRuntimeContext().getVariable('ElasticSearch_DISTRIBUTION_VERSION')
    if ElasticSearchVersionVar == None:
        logInfo("${ElasticSearch_DISTRIBUTION_VERSION} is not set. Defaulting to ElasticSearch Version 0.90.2")
        ElasticSearchVersion = "0.90.2"
    else:
        ElasticSearchVersion = ElasticSearchVersionVar.getValue()   
    return str(ElasticSearchVersion)


def createDir(directory):
    try:
        os.makedirs(directory)
        logInfo(directory + " has been created")
    except OSError, exc:
        if exc.errno == errno.EEXIST and os.path.isdir(directory):
            pass
        else:
            raise

def doPlugInsInstall(plugins_distro_zip_path, bindir, plugdir ):
    plugins_name = os.path.splitext(plugins_distro_zip_path)[0]
    PLUGINS_ARGS = " -url file://"+ plugins_distro_zip_path + " -install " + plugdir
    
    if ContainerUtils.isWindows():
        PLUGINS_CMD = os.path.join(bindir,"plugin.bat")
    else:
        PLUGINS_CMD = os.path.join(bindir,"plugin")

    CMD = PLUGINS_CMD + PLUGINS_ARGS
    logInfo("Command to be used : " + CMD)
    return CMD
            
def logInfo(msg):
    logger.info("[ElasticSearch_Enabler] " + msg)
   
def logFiner(msg):
    logger.fine("[ElasticSearch_Enabler] " + msg)
      
def logSevere(msg):
    logger.severe("[ElasticSearch_Enabler] " + msg)

def getVariableValue(name, value=None):
    logInfo("get runtime variable value")
    var = runtimeContext.getVariable(name)
    if var != None:
        value = var.value 
    return value

def doInit(additionalVariables):
    logInfo("doInit:Enter")
    elastic = ElasticSearch(additionalVariables)
    elasticRcv = RuntimeContextVariable("ELASTICSEARCH_NODE_OBJECT", elastic, RuntimeContextVariable.OBJECT_TYPE)
    runtimeContext.addVariable(elasticRcv)
    logInfo("doInit:Exit")
    
def doStart():
    logInfo("doStart:Enter")
    try:
        elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")      
        if elastic:
            elastic.startNode()
    except:
        type, value, traceback = sys.exc_info()
        logSevere("Unexpected error in ELASTICSEARCH:doStart:" + `value`)
    logInfo("doStart:Exit")

def doInstall(info):
    logInfo("doInstall:Enter")
    try:
       elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
       if elastic:
            elastic.installActivationInfo(info)
    except:
        type, value, traceback = sys.exc_info()
        logSevere("Unexpected error in ELASTICSEARCH:doInstall:" + `value`)
        
    logInfo("doInstall:Exit")
    
def doUninstall():
    logInfo("doUninstall")

def doShutdown():
    logInfo("doShutdown:Enter")
    elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
    elastic.stopNode()
    logInfo("doShutdown:Enter")
    
def getContainerRunningConditionPollPeriod():
    return 5000

def isContainerRunning():
    logInfo("isContainerRunning:Enter")
    status = False
    elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
    health = elastic.getNodeStatus()
    if health == 0:
        status = True
    else:
        status = False
    logInfo("isContainerRunning:Exit")             
    return status
####
# Return Running Conditions Errors
####
def getComponentRunningConditionErrorMessage():
    return "ElasticCache Node failure"



def getStatistic(statName):
    stat = None
    try:
        elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
        stat = elastic.getStatistic(statName)
    except:
        type, value, traceback = sys.exc_info()
        logSevere("Unexpected error in ElasticSearch:getStatistic:" + `value`)
    return stat

class ElasticSearch:
    
    def __init__(self, additionalVariables):
        logInfo("__init__:Enter")
        self.__workdir = getVariableValue('CONTAINER_WORK_DIR')
        self.__basedir = getVariableValue('ES_BASE_DIR')
        self.__eshome = runtimeContext.addVariable(RuntimeContextVariable("ES_HOME", self.__basedir, RuntimeContextVariable.ENVIRONMENT_TYPE, "ElasticSearch Home", False, RuntimeContextVariable.NO_INCREMENT))
        self.__master = runtimeContext.addVariable(RuntimeContextVariable("FIRST_DEPLOYED_MASTER_ADDR", "", RuntimeContextVariable.STRING_TYPE, "Detected Master hostname", False, RuntimeContextVariable.NO_INCREMENT))
        self.__bindir = os.path.join(self.__basedir , "bin")
        self.__enginedir = getVariableValue('ENGINE_WORK_DIR')
        self.__javahome = getVariableValue('GRIDLIB_JAVA_HOME')
        
        os.putenv("JAVA_HOME", self.__javahome)
        
        self.__path = os.getenv("PATH")
        self.__UnixPath = self.__bindir + ":" + os.path.join(self.__javahome, "bin") + ":" + self.__path
        os.putenv("PATH", self.__UnixPath)
        
        self.__ldd = os.getenv("LD_LIBRARY_PATH")
        self.__UnixLibPath = self.__ldd +":"+ os.path.join(self.__javahome, "jre/lib/amd64/server")+":"+os.path.join(self.__javahome, "jre/lib/amd64/")+":"+os.path.join(self.__javahome, "jre/lib/ext")+":"+os.path.join(self.__javahome,"lib/")
        os.putenv("LD_LIBRARY_PATH", self.__UnixLibPath)
    
        self.__UnixPreLoad = os.path.join(self.__javahome, "jre/lib/amd64/libzip.so")
        os.putenv("LD_PRELOAD", self.__UnixPreLoad )
        runtimeContext.addVariable(RuntimeContextVariable("LD_LIBRARY_PATH", self.__UnixLibPath, RuntimeContextVariable.ENVIRONMENT_TYPE, "LD_LIBRARY_PATH", False, RuntimeContextVariable.NO_INCREMENT))
        runtimeContext.addVariable(RuntimeContextVariable("LD_PRELOAD", ldpld, RuntimeContextVariable.ENVIRONMENT_TYPE, "LD_PRELOAD", False, RuntimeContextVariable.NO_INCREMENT))
        runtimeContext.addVariable(RuntimeContextVariable("JAVA_HOME", self.__javahome, RuntimeContextVariable.ENVIRONMENT_TYPE, "JAVA_HOME", False, RuntimeContextVariable.NO_INCREMENT))
        
        os.putenv("ES_HOME",self.__basedir)
        
        self.__logdir = getVariableValue('ES_LOG_DIR')
        self.__datadir = getVariableValue('ES_DATA_DIR')
        self.__tempdir = getVariableValue('ES_TMP_DIR')
        self.__confdir = getVariableValue('ES_CONF_DIR')
        self.__plugdir = getVariableValue('ES_PLUGINS_DIR')
        
        self.__hostIp = getVariableValue('ES_HOST_IP')
        self.__httpPort = getVariableValue('HTTP_PORT')
     
        self.__pidfile = os.path.join(self.__workdir, "elasticsearch.pid")
        
        call(["touch", self.__pidfile])
        call(["chmod", "777", self.__pidfile])
        defaultfolders = [self.__logdir, self.__datadir, self.__tempdir , self.__confdir , self.__plugdir, self.__bindir]
        logInfo("Creating the necessaries folders")
        for dir in defaultfolders:
            createDir(dir)
            call(["chmod", "-fR", "+x", dir])
            
            
    def startNode(self):
        logInfo("startNode:Enter")
        self.__environ = os.environ.copy()
        ### Starting Node
        self.__ELASTIC_ARGS = "-p " + self.__pidfile
        if ContainerUtils.isWindows():
            self.__ELASTIC_CMD = os.path.join(self.__bindir, "elasticsearch.bat ")
        else:
            self.__ELASTIC_CMD = os.path.join(self.__bindir, "elasticsearch ")
        self.__CMD = self.__ELASTIC_CMD + self.__ELASTIC_ARGS
        logInfo("StartUp Command to be used : " + self.__CMD)
        args = shlex.split(self.__CMD)
        process = Popen(args,stdout=None,stderr=None,env=self.__environ,shell=True)
        process.wait()
        time.sleep(5)
        logInfo("Start return Code : " + str(process.returncode))
        logInfo("startNode:Exit")
        
    def stopNode(self):
        self.__endpoint = "/_cluster/nodes/_local/_shutdown"
        self.__url = "http://"+self.__hostIp+":"+self.__httpPort+self.__endpoint
        self.__req = urllib2.Request(self.__url, data="")
        logInfo("shutdown request at : "+ self.__url)
        try:
            self.__f = urllib2.urlopen(self.__req)
        except IOError, e:
            if hasattr(e, 'reason'):
                logInfo("Failed to reach the server")
                logInfo("Reason :" + str(e.reason))
            elif hasattr(e, 'code'):
                logInfo("The server couldn\'t fullfill the request.")
                logInfo("Error code :" + str(e.code))
        else:
            dataRaw = self.__f.read()
            self.__f.close()

    def getStatistic(self, __statname):
        #split stats path
        self.__stat = __statname.split(":")          
        self.__indexname = self.__stat[0]
        self.__keyname = self.__stat[1]
        logFiner("Getting Statistics for : "+__statname)    
        self.__statvalue = 0.0
        self.__url = "http://"+self.__hostIp+":"+self.__httpPort+"/_nodes/_local/"+self.__indexname+"/stats"
        logFiner("Retrieving stat from : " + self.__url)
        self.__req = urllib2.Request(self.__url, None, {'Content-Type': 'application/json'})
        try:
            f = urllib2.urlopen(self.__req)
        except IOError, e:
            if hasattr(e, 'reason'):
                logInfo("Failed to reach the server")
                logInfo("Reason :" + str(e.reason))
            elif hasattr(e, 'code'):
                logInfo("The server couldn\'t fullfill the request.")
                logInfo("Error code :" + str(e.code))
                logInfo("Error with the URL ?, probably the index is unsupported ??")
                logInfo("Supported values for statistic index: indices,os,fs,http,jvm,process,thread_pool,transport,network")
        else:
            self.__dataRaw = f.read()
            if len(self.__stat) > 2:
                self.__subkeyname = self.__stat[2]
                self.__statvalue = jpath.read(self.__dataRaw, "$.nodes.*."+self.__indexname+"."+self.__keyname+"."+self.__subkeyname)
            else:
                self.__statvalue = jpath.read(self.__dataRaw, "$.nodes.*."+self.__indexname+"."+self.__keyname)
            f.close()
                     
        return str(self.__statvalue[0])
         
    def doGraceFullRestart(self):
        self.__url = "http://"+self.__hostIp+":"+self.__httpPort+"/_cluster/nodes/_local/_restart"        
        self.__response = urllib2.urlopen(self.__url, data="")
        self.__code = self.__response.code
        self.__response.close()
        return self.__code
     
    def getNodeStatus(self):
        logInfo("getNodeStatus:Enter")
        self.__returnStatus = 0
        self.__url = "http://"+self.__hostIp+":"+self.__httpPortt+"/_nodes/_local"
        self.__req = urllib2.Request(self.__url, None, {'Content-Type': 'application/json'})
        logFiner("Retrieving Status from : "+ self.__url)
        try:
            self.__f = urllib2.urlopen(self.__req)
        except IOError, e:
            if hasattr(e, 'reason'):
                logInfo("Failed to reach the server")
                logInfo("Reason :" + str(e.reason))
            elif hasattr(e, 'code'):
                logInfo("The server couldn\'t fullfill the request.")
                logInfo("Error code :" + str(e.code))
        else:
            self.__dataRaw = self.__f.read()
            self.__status = jpath.read(self.__dataRaw, "$.ok")
            self.__f.close()
            logFiner("status : "+ str(self.__status))
            if (self.__status):
                logFiner("Node status is OK")
                self.__returnStatus = 0
            else :
                logFiner("Node status is KO")
                self.__returnStatus = 1
        
        logInfo("getNodeStatus:Enter")
        return self.__returnStatus
    
    def installActivationInfo(self, info):
        #logInfo("install activation info")
        self.__httpRoutePrefix = getVariableValue("CLUSTER_NAME")
        self.__httpinfo = features.get('HTTP Support')
        self.__httpinfo.setRouteDirectlyToEndpoints(True)
        self.__prefix = "/elasticsearch/" + self.__httpRoutePrefix 
        self.__httpinfo.setRoutingPrefix(self.__prefix)
        self.__httpinfo.addRelativeUrl("/")
        


            
            
   