#
# Copyright (c) 2013 TIBCO Software Inc. All Rights Reserved.
# 
# Use is subject to the terms of the TIBCO license terms accompanying the download of this code. 
# In most instances, the license terms are contained in a file named license.txt.
#

from com.datasynapse.fabric.admin.info import AllocationInfo, ComponentInfo, EngineIdInfo
from com.datasynapse.fabric.util import GridlibUtils, ContainerUtils
from com.datasynapse.fabric.common import RuntimeContextVariable, ActivationInfo
from com.datasynapse.fabric.engine.managedprocess import ManagedProcess
from com.datasynapse.fabric.container import Feature, Container

from com.datasynapse.fabric.admin import AdminManager, ComponentAdmin
from com.datasynapse.fabric.admin.info import GridlibInfo

from jarray import array
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

def doPlugInsInstall(plugins_distro_zip_path, bindir):
    plugins_name = os.path.splitext(plugins_distro_zip_path)[0]
    PLUGINS_ARGS = " -url file://"+ plugins_distro_zip_path + " -install " + plugins_name
    
    if ContainerUtils.isWindows():
        PLUGINS_CMD = os.path.join(bindir,"plugin.bat")
    else:
        PLUGINS_CMD = os.path.join(bindir,"plugin")

    CMD = PLUGINS_CMD + PLUGINS_ARGS
    logInfo("Command to be used : " + CMD)
    try:
        proc = Popen([CMD])
        proc.wait()
        procExitCode = proc.returncode
        if (procExitCode == 0 ):
            logInfo("[ "+ plugins_name + " ]" + " has been succesfully installed")
        else:
            logInfo("[ "+ plugins_name + " ]" + " installation failed, and exited with code " + procExitCode )
    except Exception, err:
        logInfo("Unexpected error: "+ str(sys.exc_info()[0]) +" "+ str(sys.exc_info()[1]))
        
def ElasticNodeStart(bindir, pidfile):
    ELASTIC_ARGS = "-p " + pidfile

    if ContainerUtils.isWindows():
        ELASTIC_CMD = os.path.join(bindir,"elasticsearch.bat ")
        CMD = ELASTIC_CMD + ELASTIC_ARGS
    else:
        ELASTIC_CMD = os.path.join(bindir,"elasticsearch ")
        CMD = ELASTIC_CMD + ELASTIC_ARGS    
    logInfo("StartUp Command to be used : " + CMD)
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
 
####
# undocumented, and untested...for later use
####  
def doGraceFullRestart():
    host = runtimeContext.getVariable('ES_HOST_IP').getValue()
    port = runtimeContext.getVariable('HTTP_PORT').getValue()
    url = "http://"+host+":"+port+"/_cluster/nodes/_local/_restart"
    
    ##params = urllib.urlencode({ 'firstName': 'John','lastName': 'Doe'})
    
    response = urllib2.urlopen(url, data="")
    code = response.code
    response.close
    return code
        
# writes the message in the engine log
def logInfo(msg):
  logger.info("[ElasticSearch_Enabler] " + msg)

def doInit(additionalVariables):


    # create the data, tmp, and mysqld directories
    workdir = runtimeContext.getVariable('CONTAINER_WORK_DIR').getValue() 
    basedir = runtimeContext.getVariable('ES_BASE_DIR').getValue()
    eshome = runtimeContext.addVariable(RuntimeContextVariable("ES_HOME", basedir, RuntimeContextVariable.ENVIRONMENT_TYPE, "ElasticSearch Home", False, RuntimeContextVariable.NO_INCREMENT))
    master = runtimeContext.addVariable(RuntimeContextVariable("FIRST_DEPLOYED_MASTER_ADDR", "", RuntimeContextVariable.STRING_TYPE, "Detected Master hostname", False, RuntimeContextVariable.NO_INCREMENT))
    bindir = os.path.join(basedir , "bin")
    
    # We need Java...
    javahome = runtimeContext.getVariable('GRIDLIB_JAVA_HOME').getValue()
    runtimeContext.addVariable(RuntimeContextVariable("JAVA_HOME", javahome, RuntimeContextVariable.ENVIRONMENT_TYPE, "JAVA_HOME", False, RuntimeContextVariable.NO_INCREMENT))
    os.putenv("JAVA_HOME",javahome)
    # Updating PATH variable for dependant enablers or apps running 
    oldpath = os.getenv("PATH")
    path = bindir + ":" + os.path.join(javahome,"bin") + ":" + oldpath
    os.putenv("PATH",path)
    #updating LD_LIBRARY_PATH
    old_ld = os.getenv("LD_LIBRARY_PATH")
    nw_ld = os.path.join(javahome,"jre/lib/amd64/server")+":"+os.path.join(javahome,"jre/lib/amd64/")+":"+os.path.join(javahome,"jre/lib/ext")+":"+os.path.join(javahome,"lib/")
    os.putenv("LD_LIBRARY_PATH",nw_ld)
    runtimeContext.addVariable(RuntimeContextVariable("LD_LIBRARY_PATH", nw_ld, RuntimeContextVariable.ENVIRONMENT_TYPE, "LD_LIBRARY_PATH", False, RuntimeContextVariable.NO_INCREMENT))
    ldpld = os.path.join(javahome,"jre/lib/amd64/libzip.so")
    os.putenv("LD_PRELOAD",ldpld )
    runtimeContext.addVariable(RuntimeContextVariable("LD_PRELOAD", ldpld, RuntimeContextVariable.ENVIRONMENT_TYPE, "LD_PRELOAD", False, RuntimeContextVariable.NO_INCREMENT))
    
    #Setting ES_HOME
    os.putenv("ES_HOME",basedir)
    logdir = runtimeContext.getVariable('ES_LOG_DIR').getValue()
    datadir = runtimeContext.getVariable('ES_DATA_DIR').getValue()
    tempdir = runtimeContext.getVariable('ES_TMP_DIR').getValue()
    confdir = runtimeContext.getVariable('ES_CONF_DIR').getValue()
    plugdir = runtimeContext.getVariable('ES_PLUGINS_DIR').getValue()
 
    pidfile = os.path.join(workdir, "elasticsearch.pid")
    call(["touch", pidfile])
    call(["chmod", "777", pidfile])
    defaultfolders = [logdir, datadir, tempdir , confdir , plugdir]
    logInfo("Creating the necessaries folders")
    for dir in defaultfolders :
        createDir(dir)
    logInfo("Changing permission...")
    call(["chmod", "-fR", "+x", workdir])
    call(["chmod", "-fR", "+x", bindir])
    call(["chmod", "-fR", "+x", datadir])
    call(["chmod", "-fR", "+x", plugdir])
    call(["chmod", "-fR", "+x", confdir])     
    proxy.doInit(additionalVariables)

def doStart():
    ### getting values
    workdir = runtimeContext.getVariable('CONTAINER_WORK_DIR').getValue()
    basedir = runtimeContext.getVariable('ES_BASE_DIR').getValue()
    bindir = os.path.join(basedir , "bin")
    pidfile = os.path.join(workdir, "elasticsearch.pid")
    ### Starting Node
    environ = os.environ.copy()
    args = shlex.split(ElasticNodeStart(bindir, pidfile))
    process = Popen(args,stdout=None,stderr=None,env=environ,shell=True)
    process.wait()
    time.sleep(32)
    logInfo("Start return Code : " + str(process.returncode))
   
def doInstall(info):
    #### Manage HTTP routing
    endpoint = runtimeContext.getVariable('CLUSTER_NAME').getValue()
    try:
        httpinfo.setRouteDirectlyToEndpoints(True)
        httpinfo.setRoutingPrefix(endpoint)
    except Exception, err:
        logInfo("Unexpected error: "+ str(sys.exc_info()[0]) +" "+ str(sys.exc_info()[1]))
            
    #### Manage Plug ins
    archiveinfo = features.get("Archive Management Support")
    enginedir = runtimeContext.getVariable('ENGINE_WORK_DIR').getValue()
    workdir = runtimeContext.getVariable('CONTAINER_WORK_DIR').getValue()
    basedir = runtimeContext.getVariable('ES_BASE_DIR').getValue()
    bindir = os.path.join(basedir , "bin")
    if archiveinfo:
        for i in range(archiveinfo.getArchiveCount()):
            archive = archiveinfo.getArchiveInfo(i)
            archname = archive.getArchiveFilename()
            logInfo("Installing Plugins " + archive.getArchiveFilename())
            archivePath = os.path.join(enginedir, archiveinfo.getArchiveDirectory(), archname)
            try:
                doPlugInsInstall(archivePath, bindir)
            except Exception, err:
                logInfo("Unexpected error: "+ str(sys.exc_info()[0]) +" "+ str(sys.exc_info()[1]))
    proxy.doInstall(info)    

###
# In case you want to do any particular action when uninstalling..
###
def doUninstall():
    print "doUninstall"    

###
# Shutdown and wait for the enabler to gracefully shutdown
### 
def doShutdown():
    host = runtimeContext.getVariable('ES_HOST_IP').getValue()
    port = runtimeContext.getVariable('HTTP_PORT').getValue()
    endpoint = "/_cluster/nodes/_local/_shutdown"
    url = "http://"+host+":"+port+endpoint
    req = urllib2.Request(url, data="")
    logInfo("shutdown : "+ url)
    f = urllib2.urlopen(req)
    dataRaw = f.read()
    f.close()
#   status = response.status
#    if ( status == 200 ):
#        logInfo("Node status is OK")
#        returnStatus = 0
#    else :
#        logInfo("Node status is KO")
#        logInfo("Error Status : "+ str(status) + " with reason : " + response.reason)
#        returnStatus = 1
#    bindir = os.path.join(basedir , "bin")
#    pidfile = os.path.join(workdir, "elasticsearch.pid")
#    runCommand(ElasticNodeStop(pidfile), shell=True)
#    begin = System.currentTimeMillis()
#    proxy.doShutdown()
#    proxy.getContainer().waitForShutdown(begin)
    
# running condition
def getContainerRunningConditionPollPeriod():
    return 5000


def isContainerRunning():
    logInfo("Checking if the Enabler is running")
    status = getNodeStatus()
    if status == 0:
        return True
    else:
        return False
####
# Return Running Conditions Errors
####
def getComponentRunningConditionErrorMessage():
    return "ElasticCache Node failure"

###
# Retrieve enabler metrics for indices
###
def getStatistic(statName):

    VarName = statName.rsplit(":", 1)[1]
    KeyName = statName.rsplit(":", 1)[0]
    logInfo("Getting Statistics for : "+KeyName+"."+VarName)    
    statValue = 0.0
    host = runtimeContext.getVariable('ES_HOST_IP').getValue()
    port = runtimeContext.getVariable('HTTP_PORT').getValue()
    url = "http://"+host+":"+port+"/_nodes/_local/indices/stats"
    ##params = urllib.urlencode({ 'firstName': 'John','lastName': 'Doe'})
    logInfo("Retrieving stat from : " + url)
    req = urllib2.Request(url, None, {'Content-Type': 'application/json'})
    f = urllib2.urlopen(req)
    dataRaw = f.read()
    statValue = jpath.read(dataRaw, "$.nodes.*.indices."+KeyName+"."+VarName)
    f.close() 
    return str(statValue[0])

###
# Retrieve Status of this instance
###
def getNodeStatus():
    returnStatus = 0
    host = runtimeContext.getVariable('ES_HOST_IP').getValue()
    port = runtimeContext.getVariable('HTTP_PORT').getValue()
    url = "http://"+host+":"+port+"/_nodes/_local"
    req = urllib2.Request(url, None, {'Content-Type': 'application/json'})
    logInfo("Retrieving Status from : "+ url)
    f = urllib2.urlopen(req)
    dataRaw = f.read()
    status = jpath.read(dataRaw, "$.ok")
    logInfo("status : "+ str(status[0]))
    if (status):
        logInfo("Node status is OK")
        returnStatus = 0
    else :
        logInfo("Node status is KO")
        returnStatus = 1
    
    return returnStatus

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

        
           
     