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

#######
    # add Json support to Jython (External Libs)
    # only jython 2.7 got the json module built-in
    # this is a native java implementation (much faster)
    # didn't find an easier way to do it....sorry
    # jars are loaded from ds_jars, look at the gridlib.xml
    #######
    ######
    # i needed some jpath stuff, to parse efficiently the json response
    # from elasticsearch
    ######
jarpath = runtimeContext.getVariable('CONTAINER_GRIDLIB_DIR').getValue()
sys.path.append(os.path.join(jarpath,"ds_jars", "json-path-0.8.1.jar"))
sys.path.append(os.path.join(jarpath,"ds_jars", "commons-lang-2.6.jar"))
sys.path.append(os.path.join(jarpath,"ds_jars", "json-smart-1.1.1.jar"))
from com.jayway.jsonpath import JsonPath as jpath



#################################################################
# the enabler will do the following steps :
# doinit() : 
# 1 - configure the system shell environment (PATH, LD_LIBRARY_PATH)
# 2 - create all needed directories and files, correct permissions
# 3 - start the node
# 4 - extra configuration if needed (clustering supports, etc...)
# 5 - deploy all provided plugins, discover urls for site plugins
# 6 - check the health of this node
# 7 - get stats
# 8 -  stop nicely this node
#################################################################


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


######
# Find the Distribution Version desired
######
def getElasticSearchVersion():
    ElasticSearchVersionVar = proxy.getContainer().getRuntimeContext().getVariable('ElasticSearch_DISTRIBUTION_VERSION')
    if ElasticSearchVersionVar == None:
        logInfo("${ElasticSearch_DISTRIBUTION_VERSION} is not set. Defaulting to ElasticSearch Version 0.92.2")
        ElasticSearchVersion = "0.92.2"
    else:
        ElasticSearchVersion = ElasticSearchVersionVar.getValue()
        
    return str(ElasticSearchVersion)


#####
# Simple utility function, creates dir if not exists, pass if exists, die if errors
#####

def createDir(directory):
    try:
        os.makedirs(directory)
        logInfo(directory + " has been created")
    except OSError, exc:
        if exc.errno == errno.EEXIST and os.path.isdir(directory):
            pass
        else:
            raise



#####
#ElasticSearch Plugins installation
#Requires the zip file under archives
#####

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
        

 
def ElasticNodeStop(pidfile):
    UNIX_KILL_CMD = "kill -9"
    WIN_KILL_CMD = "TASKKILL /F /PID"
    
    pidf = open(pidfile, "r")
    pids = pidf.readlines()
    pidf.close()
    
    pid = int(pids[0])
    
    if ContainerUtils.isWindows():
        KILL_ARGS = " " + pid
        CMD = WIN_KILL_CMD + KILL_ARGS
    else:
        KILL_ARGS = " " + pid
        CMD = UNIX_KILL_CMD + KILL_ARGS
    logInfo("Shutdown Command to be used : " + CMD)
    return CMD
 

        
###        
# writes the message in the engine log as INFO level
###
def logInfo(msg):
    logger.info("[ElasticSearch_Enabler] " + msg)
###        
# writes the message in the engine log as FINER level
###      
def logFiner(msg):
    logger.finer("[ElasticSearch_Enabler] " + msg)
###        
# writes the message in the engine log as SEVERE level
###        
def logSevere(msg):
    logger.severe("[ElasticSearch_Enabler] " + msg)

def getVariableValue(name, value=None):
    logInfo("get runtime variable value")
    var = runtimeContext.getVariable(name)
    if var != None:
        value = var.value
    
    return value

def doInit(additionalVariables):
    
    logInfo("Entering doInit() ")
    ### create a new instance of elasticsearch class
    elastic = ElasticSearch(additionalVariables)
    ### store class instance object in an RuntimeContextVariable for use accross all methods
    elasticRcv = RuntimeContextVariable("ELASTICSEARCH_NODE_OBJECT", elastic, RuntimeContextVariable.OBJECT_TYPE)
    runtimeContext.addVariable(elasticRcv)
    logInfo("Exiting doInit() ")
    



def doStart():
    
    logInfo("Entering doStart() ")
    
    elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
        
    if elastic:
        elastic.startNode()
        
    logInfo("Exiting doStart() ")
   
def doInstall(info):
    #### Manage HTTP routing
    endpoint = runtimeContext.getVariable('CLUSTER_NAME').getValue()
    try:
        httpinfo = features.get('HTTP Support')
        httpinfo.setRouteDirectlyToEndpoints(True)
        httpinfo.setRoutingPrefix(endpoint)
    except Exception, err:
        logInfo("Unexpected error: "+ str(sys.exc_info()[0]) +" "+ str(sys.exc_info()[1]))
            
    proxy.doInstall(info)

###
# In case you want to do any particular action when uninstalling..
###
def doUninstall():
    logInfo("doUninstall()")

###
# Shutdown and wait for the enabler to gracefully shutdown
###
def doShutdown():
    logInfo("Shutting down this node")
    try:
        elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
        elastic.stopNode()
    except:
        type, value, traceback = sys.exc_info()
        logSevere("Unexpected error in ElasticSearch:stopNode:" + `value`)
    
# running condition
def getContainerRunningConditionPollPeriod():
    return 5000


def isContainerRunning():
    logInfo("Checking if the Enabler is running")
    status = None
    try:
        elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
        health = elastic.getNodeStatus()
        if health == 0:
            status = True
        else:
            status = False
    except:
        type, value, traceback = sys.exc_info()
        logSevere("Unexpected error in ElasticSearch:getNodeStatus:" + `value`)            
    
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






def runCommand(commandline, stdin=None, stdout=None, expectedReturnCodes=None, suppressOutput=None, shell=None):

    if (expectedReturnCodes == None): expectedReturnCodes = [0]
    if (suppressOutput == None): suppressOutput = False
    if (shell == None): shell = False
    stderr = None
    if (suppressOutput):
        stdout=PIPE
        stderr=PIPE
    else:
        logInfo("Running command [" + commandline + "]")
            
    if shell:
        args = commandline
    else:
        args = shlex.split(commandline)

    #os.unsetenv("LD_LIBRARY_PATH")
    #os.unsetenv("LD_PRELOAD")

    if stdin == None:
        p = Popen(args, stdout=stdout, stdin=None, stderr=stderr, shell=shell)
        output = p.communicate()
    else:
        p = Popen(args, stdout=stdout, stdin=PIPE, stderr=stderr, shell=shell)
        output = p.communicate(input=stdin)
    
    outputlist = [p.returncode]

    for item in output:
        outputlist.append(item)

    if (outputlist[0] in expectedReturnCodes ):
        if not (suppressOutput):
            logInfo(" Command return code was [" + str(outputlist[0]) + "]")
            printStdoutPipe(stdout, outputlist)
    else:
        
        logInfo(" Return code " + str(outputlist[0]) +
                                               " was not in list of expected return codes" + str(expectedReturnCodes))
        if (suppressOutput):
            logInfo(" Command was [" + commandline + "]")

        printStdoutPipe(stdout, outputlist)

    ContainerUtils.getLogger(proxy).finer(" exiting runCommand(). Returning outputlist:" + (str(outputlist)))
    return outputlist

def printStdoutPipe(stdout, outputlist):

    if (stdout == PIPE):
        logInfo(" Command STDOUT:")
        print outputlist[1]

class ElasticSearch:
    
    def __init__(self, additionalVariables):
        # Get some usefull variables...
        
        self.__workdir = getVariableValue('CONTAINER_WORK_DIR')
        self.__basedir = getVariableValue('ES_BASE_DIR')
        self.__eshome = runtimeContext.addVariable(RuntimeContextVariable("ES_HOME", self.__basedir, RuntimeContextVariable.ENVIRONMENT_TYPE, "ElasticSearch Home", False, RuntimeContextVariable.NO_INCREMENT))
        self.__master = runtimeContext.addVariable(RuntimeContextVariable("FIRST_DEPLOYED_MASTER_ADDR", "", RuntimeContextVariable.STRING_TYPE, "Detected Master hostname", False, RuntimeContextVariable.NO_INCREMENT))
        self.__bindir = os.path.join(self.__basedir , "bin")
        self.__enginedir = getVariableValue('ENGINE_WORK_DIR')
        
        
        
        # We need Java...
        self.__javahome = getVariableValue('GRIDLIB_JAVA_HOME')
        runtimeContext.addVariable(RuntimeContextVariable("JAVA_HOME", self.__javahome, RuntimeContextVariable.ENVIRONMENT_TYPE, "JAVA_HOME", False, RuntimeContextVariable.NO_INCREMENT))
        os.putenv("JAVA_HOME",self.__javahome)
        # Updating PATH variable for dependant enablers or apps running
        oldpath = os.getenv("PATH")
        path = self.__bindir + ":" + os.path.join(self.__javahome,"bin") + ":" + oldpath
        os.putenv("PATH",path)
        #updating LD_LIBRARY_PATH
        old_ld = os.getenv("LD_LIBRARY_PATH")
        nw_ld = os.path.join(self.__javahome,"jre/lib/amd64/server")+":"+os.path.join(self.__javahome,"jre/lib/amd64/")+":"+os.path.join(self.__javahome,"jre/lib/ext")+":"+os.path.join(self.__javahome,"lib/")
        os.putenv("LD_LIBRARY_PATH",nw_ld)
        runtimeContext.addVariable(RuntimeContextVariable("LD_LIBRARY_PATH", nw_ld, RuntimeContextVariable.ENVIRONMENT_TYPE, "LD_LIBRARY_PATH", False, RuntimeContextVariable.NO_INCREMENT))
        ldpld = os.path.join(self.__javahome,"jre/lib/amd64/libzip.so")
        os.putenv("LD_PRELOAD",ldpld )
        runtimeContext.addVariable(RuntimeContextVariable("LD_PRELOAD", ldpld, RuntimeContextVariable.ENVIRONMENT_TYPE, "LD_PRELOAD", False, RuntimeContextVariable.NO_INCREMENT))
        
        #Setting ES_HOME
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
        for dir in defaultfolders :
            createDir(dir)
            call(["chmod", "-fR", "+x", dir])
            
    def startNode(self):
        
        #### Manage Plug ins
#        logInfo("Checking if there is any plugins to deploy...")
#        archiveinfo = features.get("Archive Management Support")
        
        self.__environ = os.environ.copy()
        
#        
#        if archiveinfo:
#            for i in range(archiveinfo.getArchiveCount()):
#                archive = archiveinfo.getArchiveInfo(i)
#                archname = archive.getArchiveFilename()
#                logInfo("Installing Plugins " + archive.getArchiveFilename())
#                archivePath = os.path.join(enginedir, archiveinfo.getArchiveDirectory(), archname)
#                try:
#                    args = shlex.split(doPlugInsInstall(archivePath, bindir, plugdir))
#                    process = Popen(args,stdout=None,stderr=None,env=environ,shell=True)
#                    process.wait()
#                except Exception, err:
#                    logInfo("Unexpected error: "+ str(sys.exc_info()[0]) +" "+ str(sys.exc_info()[1]))
        ### Starting Node
        self.__ELASTIC_ARGS = "-p " + self.__pidfile
        if ContainerUtils.isWindows():
            self.__ELASTIC_CMD = os.path.join(self.__bindir,"elasticsearch.bat ")
            self.__CMD = self.__ELASTIC_CMD + self.__ELASTIC_ARGS
        else:
            self.__ELASTIC_CMD = os.path.join(self.__bindir,"elasticsearch ")
            self.__CMD = self.__ELASTIC_CMD + self.__ELASTIC_ARGS
        logInfo("StartUp Command to be used : " + self.__CMD)
        args = shlex.split(self.__CMD)
        process = Popen(args,stdout=None,stderr=None,env=self.__environ,shell=True)
        process.wait()
        time.sleep(5)
        logInfo("Start return Code : " + str(process.returncode))
        
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
            # i should probably do something with the result otherwise... just remove it
            dataRaw = self.__f.read()
            self.__f.close()
    ###
    # Retrieve enabler metrics for indices
    ###
    def getStatistic(self, __statname):
        #split stats path
        self.__stat = __statname.split(":")
        self.__shortpath = False
                
        self.__indexname = self.__stat[0]
        self.__keyname = self.__stat[1]
                
        if len(self.__stat) > 2:
            self.__subkeyname = self.__stat[2]
            self.__shortpath = False
        else:
            self.__shortpath = True
                
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
            if (self.__shortpath):
                self.__statvalue = jpath.read(self.__dataRaw, "$.nodes.*."+self.__indexname+"."+self.__keyname)
            else:
                self.__statvalue = jpath.read(self.__dataRaw, "$.nodes.*."+self.__indexname+"."+self.__keyname+"."+self.__subkeyname)
            f.close()
                     
        return str(self.__statvalue[0])
         
    ####
    # undocumented, and untested...for later use (for 0.94 ?)
    ####
    def doGraceFullRestart(self):
        self.__url = "http://"+self.__hostIp+":"+self.__httpPort+"/_cluster/nodes/_local/_restart"
        
        ##params = urllib.urlencode({ 'firstName': 'John','lastName': 'Doe'})
        
        self.__response = urllib2.urlopen(self.__url, data="")
        self.__code = self.__response.code
        self.__response.close()
        return self.__code
     
    ###
    # Retrieve Status of this instance
    ###
    def getNodeStatus(self):
        self.__returnStatus = 0
        self.__url = "http://"+self.__hostIp+":"+self.__httpPort+"/_nodes/_local"
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
        
        return self.__returnStatus