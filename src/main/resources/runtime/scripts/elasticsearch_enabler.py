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
from com.datasynapse.fabric.container import ArchiveDetail
from com.datasynapse.fabric.domain.featureinfo import ApplicationLoggingInfo

from com.datasynapse.fabric.admin import AdminManager, ComponentAdmin
from com.datasynapse.fabric.admin.info import GridlibInfo

from jarray import array
from java.lang import StringBuilder
import java.lang.System
from subprocess import Popen, PIPE, STDOUT, call
from java.lang import String


import sys
import stat
import subprocess
import zipfile
import os
import os.path
import getopt
import os
import sys, java, types
import platform
import time
import socket
import fnmatch
import urllib
import urllib2 as urllib2
import shutil
import httplib
import errno
import shlex
import zipfile
import random
import signal
import threading
from urlparse import urlparse

from java.util import Properties

jarpath = runtimeContext.getVariable('CONTAINER_GRIDLIB_DIR').getValue()
sys.path.append(os.path.join(jarpath,"ds_jars", "json-path-0.8.1.jar"))
sys.path.append(os.path.join(jarpath,"ds_jars", "commons-lang-2.6.jar"))
sys.path.append(os.path.join(jarpath,"ds_jars", "json-smart-1.1.1.jar"))
from com.jayway.jsonpath import JsonPath as jpath




sys.setrecursionlimit(1500)
archivesDir = None


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
            
def logInfo(msg):
    logger.info("[ElasticSearch_Enabler] " + msg)
   
def logFiner(msg):
    logger.fine("[ElasticSearch_Enabler] " + msg)
      
def logSevere(msg):
    logger.severe("[ElasticSearch_Enabler] " + msg)

def getVariableValue(name, value=None):
    logFiner("get runtime variable value")
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
    try:
        elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
        if elastic:
            elastic.killNode()
    except:
        type, value, traceback = sys.exc_info()
        logSevere("Unexpected error in ELASTICSEARCH:doShutdown:" + `value`)
    logInfo("doShutdown:Exit")
    
def getContainerRunningConditionPollPeriod():
    return 5000

def isContainerRunning():
    logFiner("isContainerRunning:Enter")
    status = False
    try:
        elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
        health = elastic.getNodeStatus()
        if health == 0:
            status = True
        else:
            status = False
    except:
        type, value, traceback = sys.exc_info()
        logSevere("Unexpected error in ElasticSearch:isContainerRunning:" + `value`)
    logFiner("isContainerRunning:Exit")
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


def createArchiveDetails(archivePaths, running):
    archives = []
    for archivePath in archivePaths:
        archives.append(ArchiveDetail(os.path.basename(archivePath), running, False, ""))
    return archives
        
def containsArchiveDetail(details, archiveName):
    for detail in details:
        if detail.archiveName == archiveName:
            return True
    return False
    
def archiveDetect():
    logInfo("detecting archives")
    archives = []
    if os.path.exists(archivesDir):
        for f in os.listdir(archivesDir):
            name = os.path.basename(f)
            if not containsArchiveDetail(archives, name):
                archives.append(ArchiveDetail(name, False, False, ""))
    return array(archives, ArchiveDetail)

def urlDetect():
    logInfo("detecting urls")
    try:
        elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
        urls = elastic.getPublishedUrls()
    except:
        type, value, traceback = sys.exc_info()
        logSevere("Unexpected error in ElasticSearch:urlDetect:" + `value`)
    
    return array(urls, String)
    
def archiveDeploy(archiveName, archiveLocators):
    logInfo("deploying archive " + archiveName)
    try:
        elastic = getVariableValue("ELASTICSEARCH_NODE_OBJECT")
    except:
        type, value, traceback = sys.exc_info()
        logSevere("Unexpected error in ElasticSearch:archiveDeploy:" + `value`)
    else:
        try:
            elastic.killNode()
        except:
            pass
        else:
            elastic.installPlugins(archiveName, archivesDir)
            elastic.startNode()
    ContainerUtils.retrieveAndConfigureArchiveFile(proxy.container, archiveName, archiveLocators, None)
    logInfo("End of deploying archive " + archiveName)
        

def archiveStart(archiveName):
    logInfo("starting archive " + archiveName)
    archiveFile = os.path.join(archivesDir, archiveName)
    archiveFiles = [ archiveFile ]
    signatures = [ "java.lang.String" ]
    return ArchiveActivationInfo(archiveName, "")
    
def archiveStop(archiveName, archiveId, properties):
    logInfo("stopping archive " + archiveName)
    archiveFile = os.path.join(archivesDir, archiveName)
    archiveFiles = [ archiveFile ]
    signatures = [ "java.lang.String" ]   
        
def archiveUndeploy(archiveName, properties):
    logInfo("undeploying archive " + archiveName)
    archiveFile = os.path.join(archivesDir, archiveName)
    logInfo("Deleting " + archiveFile)
    os.remove(archiveFile)

class ElasticSearch:
    
    def __init__(self, additionalVariables):
        logInfo("__init__:Enter")
        self.__workdir = getVariableValue('CONTAINER_WORK_DIR')
        self.__basedir = getVariableValue('ES_BASE_DIR')
        self.__eshome = self.__basedir
        self.lock = threading.Lock()
        runtimeContext.addVariable(RuntimeContextVariable("ES_HOME", self.__basedir, RuntimeContextVariable.ENVIRONMENT_TYPE, "ElasticSearch Home", False, RuntimeContextVariable.NO_INCREMENT))
        
        
        self.__bindir = os.path.join(self.__basedir , "bin")
        self.__enginedir = getVariableValue('ENGINE_WORK_DIR')
        self.__javahome = getVariableValue('GRIDLIB_JAVA_HOME')
        #try do chmod to java home, just in case
        if sys.platform.lower().find('win') != 0:
            java_file_path = os.path.join(self.__javahome, 'bin/java')
            try:
                java_file_mode = os.stat(java_file_path).st_mode
                if stat.S_IXUSR & java_file_mode == 0 :
                    subprocess.call(["chmod", "-R", "0755", self.__javahome])
            except OSError:
                pass
        
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
        runtimeContext.addVariable(RuntimeContextVariable("LD_PRELOAD", self.__UnixPreLoad, RuntimeContextVariable.ENVIRONMENT_TYPE, "LD_PRELOAD", False, RuntimeContextVariable.NO_INCREMENT))
        runtimeContext.addVariable(RuntimeContextVariable("JAVA_HOME", self.__javahome, RuntimeContextVariable.ENVIRONMENT_TYPE, "JAVA_HOME", False, RuntimeContextVariable.NO_INCREMENT))
        
        os.putenv("ES_HOME",self.__basedir)
        
        self.__logdir = getVariableValue('ES_LOG_DIR')
        self.__datadir = getVariableValue('ES_DATA_DIR')
        self.__tempdir = getVariableValue('ES_TMP_DIR')
        self.__confdir = getVariableValue('ES_CONF_DIR')
        self.__plugdir = getVariableValue('ES_PLUGINS_DIR')

        self.__hostIp = getVariableValue('ES_HOST_IP')
        self.__httpPort = getVariableValue('HTTP_PORT')
        self.__tcpPort = getVariableValue('ES_TCP_PORT')
        
        self.__httpPortInt = int(self.__httpPort)
        self.__maxRandom = int(getVariableValue('PORT_RANDOM_MAX_OFFSET'))
        self.__randomnum = int(random.randint(1,self.__maxRandom))
        self.__tcpPortInt = int(self.__tcpPort)
        
        #generate unique TCP port :
        self.__tcpPort = str(self.__tcpPortInt + self.__randomnum)
        runtimeContext.addVariable(RuntimeContextVariable("ES_TCP_PORT", self.__tcpPort, RuntimeContextVariable.STRING_TYPE, "TCP PORT Random Number", False, RuntimeContextVariable.NO_INCREMENT))
        #generate unique Http Port :
        self.__httpPort = str(self.__httpPortInt + self.__randomnum)
        
        self.__baseUrl = self.__hostIp+":"+self.__tcpPort
        self.__baseUrlHttp = "http://"+self.__hostIp+":"+self.__httpPort
        runtimeContext.addVariable(RuntimeContextVariable("HTTP_PORT", self.__httpPort, RuntimeContextVariable.STRING_TYPE, "HTTP PORT Random Number", False, RuntimeContextVariable.NO_INCREMENT))
        self.__master = getVariableValue('isPrimaryNode')
        if self.__master == "True":
            runtimeContext.addVariable(RuntimeContextVariable("EXPORTED_CLUSTER_ENDPOINT", "", RuntimeContextVariable.STRING_TYPE, "Master Endpoint for Clustering", False, RuntimeContextVariable.NO_INCREMENT))
            runtimeContext.addVariable(RuntimeContextVariable("MASTER_ENDPOINT", self.__baseUrl, RuntimeContextVariable.STRING_TYPE, "Master Endpoint for Clustering", True, RuntimeContextVariable.NO_INCREMENT))
        else:
            self.__myMasterEndpoint = getVariableValue('MASTER_ENDPOINT')
            runtimeContext.addVariable(RuntimeContextVariable("EXPORTED_CLUSTER_ENDPOINT", self.__myMasterEndpoint, RuntimeContextVariable.STRING_TYPE, "Master Endpoint for Clustering", False, RuntimeContextVariable.NO_INCREMENT))
        self.__httpRoutePrefix = getVariableValue("CLUSTER_NAME")
        self.__prefix = "/" + self.__httpRoutePrefix 
        runtimeContext.addVariable(RuntimeContextVariable("HTTP_PREFIX", self.__prefix, RuntimeContextVariable.STRING_TYPE, "PREFIX", False, RuntimeContextVariable.NO_INCREMENT))
        self.__pidfile = os.path.join(self.__workdir, "elasticsearch.pid")
        
        self.__toggleCheck = False
        
        #generate unique Node Name :
        
        self.__hostname = getVariableValue("ENGINE_USERNAME")
        self.__nodeName = "ElasticSearch-"+self.__hostname+"-"+str(self.__hostIp).replace(".","_")+":"+self.__httpPort+"-Node"
        runtimeContext.addVariable(RuntimeContextVariable("NODE_NAME", self.__nodeName, RuntimeContextVariable.STRING_TYPE, "Auto Generated Node Name", False, RuntimeContextVariable.NO_INCREMENT))
        
        call(["touch", self.__pidfile])
        call(["chmod", "777", self.__pidfile])
        defaultfolders = [self.__logdir, self.__datadir, self.__tempdir , self.__confdir , self.__plugdir, self.__bindir]
        logInfo("Creating the necessaries folders")
        for dir in defaultfolders:
            createDir(dir)
            call(["chmod", "-fR", "+x", dir])
    
    def extract(self, zipfilepath, extractiondir):
        UnZipFile().extract(zipfilepath, extractiondir)
    
    def startNode(self):
        logInfo("startNode:Enter")
        self.__environ = os.environ.copy()
        ### Starting Node
        self.__ELASTIC_ARGS = "-f -Des.pidfile=" + self.__pidfile
        if ContainerUtils.isWindows():
            self.__ELASTIC_CMD = os.path.join(self.__bindir, "elasticsearch.bat ")
        else:
            self.__ELASTIC_CMD = os.path.join(self.__bindir, "elasticsearch ")
        self.__CMD = self.__ELASTIC_CMD + self.__ELASTIC_ARGS
        logInfo("StartUp Command to be used : " + self.__CMD)
        args = shlex.split(self.__CMD)
        process = Popen(args,stdout=None,stderr=None,env=self.__environ,shell=False)
        time.sleep(20)
        logInfo("Start return Code : " + str(process.returncode))
        logInfo("finding the archivesDir")
        global archivesDir
        archiveMgmtFeature = ContainerUtils.getFeatureInfo("Archive Management Support", proxy.container, proxy.container.currentDomain)
        archivesDir = os.path.join(self.__enginedir, archiveMgmtFeature.archiveDirectory)
        logInfo("Found archives dir " + archivesDir)
        self.__toggleCheck = True
        logInfo("startNode:Exit")
             
    def stopNode(self):
        self.__endpoint = "/_cluster/nodes/_local/_shutdown"
        self.__response = self.jsonRequest(self.__endpoint, "")
        if len(self.__response) > 0:
            logInfo("Shutdown Response" + str(self.__response))
        self.__toggleCheck = False

    def getPublishedUrls(self):
        self.__urls = []
        self.__endpoint = "/_nodes/_local/plugin"
        logInfo("Retrieving plugins URL")
        if self.__toggleCheck:
            self.__response = self.jsonRequest(self.__endpoint, None)
            if len(self.__response) > 0:
                self.__contextUrls = jpath.read(self.__response, "$.nodes.*.plugins.url")
                for self.__contextUrl in self.__contextUrls:
                    logInfo("Adding context : " + str(self.__contextUrl))
                    self.__urls.append(str(self.__contextUrl))
            self.__urls.append("/") #default context       
        return self.__urls
        
    def killNode(self):
        logInfo('stopping node gently first')
        self.__toggleCheck = False
        self.stopNode()
        logInfo("Node will be killed...")
        self.__pidf = open(self.__pidfile, "r")
        self.__pids = self.__pidf.readlines()
        self.__pidf.close()
        self.__pid = int(self.__pids[0])
        
        os.kill(self.__pid, signal.SIGKILL)
        logInfo("kill pid : " + str(self.__pid))
        time.sleep(5)
                
    def getStatistic(self, __statname):
        #split stats path
        self.__stat = __statname.split(":")          
        self.__indexname = self.__stat[0]
        self.__keyname = self.__stat[1]
        logFiner("Getting Statistics for : "+__statname)    
        self.__statvalue = 0.0
        self.__endpoint = "/_nodes/_local/"+self.__indexname+"/stats"
        if self.__toggleCheck:
            self.__response = self.jsonRequest(self.__endpoint, None)
            if len(self.__response) > 0:
                if len(self.__stat) > 2:
                    self.__subkeyname = self.__stat[2]
                    self.__statvalue = jpath.read(self.__response, "$.nodes.*."+self.__indexname+"."+self.__keyname+"."+self.__subkeyname)
                else:
                    self.__statvalue = jpath.read(self.__response, "$.nodes.*."+self.__indexname+"."+self.__keyname)
                     
        return str(self.__statvalue[0])
         
    def doGraceFullRestart(self):
        self.__url = "http://"+self.__hostIp+":"+self.__httpPort+"/_cluster/nodes/_local/_restart"        
        self.__response = urllib2.urlopen(self.__url, data="")
        self.__code = self.__response.code
        self.__response.close()
        return self.__code
    
    def installPlugins(self, archivename, archivepath):
        logInfo("Installing Plugin : " + archivename)
        self.__archiveFile = os.path.join(archivepath , archivename)
        if os.path.exists(self.__archiveFile):
            self.extract(self.__archiveFile, self.__plugdir)
        else:
            logInfo("Archive not Found ! at : " + self.__archiveFile)
  
    def getNodeStatus(self):
        logFiner("getNodeStatus:Enter")
        self.__returnStatus = 0
        self.__endpoint = "/_nodes/_local"
        logInfo("Active checking is set to : " + str(self.__toggleCheck))
        if self.__toggleCheck:
            self.__resp = self.jsonRequest(self.__endpoint, None)
            if len(self.__resp) > 0:
                self.__status = jpath.read(self.__resp, "$.ok")
                logFiner("status : "+ str(self.__status))
                if (self.__status):
                    logFiner("Node status is OK")
                    self.__returnStatus = 0
                else:
                    logInfo("Node status is KO")
                    self.__returnStatus = 1
            else:
                logInfo("Node status is KO and Unreachable")
                self.__returnStatus = 1
        else:
            self.__returnStatus = 0
        
        logFiner("getNodeStatus:Exit")
        return self.__returnStatus
    
    def installActivationInfo(self, info):
        #logInfo("install activation info")
        self.__httpinfo = features.get('HTTP Support')
        self.__httpinfo.setRouteDirectlyToEndpoints(True)
        self.__httpinfo.setRoutingPrefix(self.__prefix)
        self.__httpinfo.addRelativeUrl("/")
    
    def jsonRequest(self, endpoint, data=None):
          self.lock.acquire()
          try:
	    return self.jsonRequest1(endpoint, data)
          finally:
            self.lock.release()


    def jsonRequest1(self, endpoint, data=None):
        logFiner("JsonRequest:Enter")
        self.__url = urlparse(self.__baseUrlHttp+str(endpoint))
        self.__headers = {'Accept': 'application/json', 'Content-Type': 'application/json; charset=UTF-8'}
        logFiner("JsonRequest:urlparse:url:"+  str(self.__url.geturl()))
        self.__domain = self.__url.netloc
        self.__path = self.__url.path
        self.__json = None
        self.__conn = None
        self.__response = None
        try:
            logFiner("JsonRequest:conn():url: "+  self.__url.geturl() + " on domain : " + self.__domain)
            self.__conn = httplib.HTTPConnection(self.__domain)
            self.__conn.connect()
        except httplib.HTTPException, ex:
            logFiner("JsonRequest:conn():Failure")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logFiner("HTTPException :" + str(ex) + ":" + str(exc_type))
        else:
            logFiner("JsonRequest:conn():Success")
            if data != None:
#                data as to be data = {'{""}'}
                self.__body = urllib.urlencode(data)
                try:
                    logFiner("JsonRequest:conn():Request:POST")
                    self.__conn.request('POST', self.__path, self.__body, self.__headers)
                except httplib.HTTPException, ex:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    logFiner("HTTPException :" + str(ex) + ":" + str(exc_type))
                else:
                    self.__response = self.__conn.getresponse()
            else:
                try:
                    logFiner("JsonRequest:conn():Request:GET")
                    self.__conn.request('GET', self.__path, None, self.__headers)
                except httplib.HTTPException, ex:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    logFiner("HTTPException :" + str(ex) + ":" + str(exc_type))
                else:
                    logFiner("JsonRequest:conn():Request:Success")
                    self.__response = self.__conn.getresponse()
                    logFiner("JsonRequest:conn():getResponse:Success")
                    logFiner("Response Reason, Response Status : " + str(self.__response.reason) + " : " + str(self.__response.status))
        
        if self.__response.status == 200:
            self.__json = self.__response.read()
            self.__conn.close()    
        logFiner("JsonRequest:Exit")
        return self.__json

class UnZipFile:
    def __init__(self, verbose = False, percent = 10):
        self.verbose = verbose
        self.percent = percent
        
    def extract(self, file, dir):
        if not dir.endswith(':') and not os.path.exists(dir):
            os.mkdir(dir)

        zf = zipfile.ZipFile(file)

        # create directory structure to house files
        self._createstructure(file, dir)

        num_files = len(zf.namelist())
        percent = self.percent
        divisions = 100 / percent
        perc = int(num_files / divisions)

        # extract files to directory structure
        for i, name in enumerate(zf.namelist()):

            if self.verbose == True:
                print "Extracting %s" % name
            elif perc > 0 and (i % perc) == 0 and i > 0:
                complete = int (i / perc) * percent
                print "%s%% complete" % complete

            if not name.endswith('/'):
                outfile = open(os.path.join(dir, name), 'wb')
                outfile.write(zf.read(name))
                outfile.flush()
                outfile.close()


    def _createstructure(self, file, dir):
        self._makedirs(self._listdirs(file), dir)


    def _createdir(self, basedir, dir):
        """ Create any parent directories that don't currently exist """
        index = dir.rfind('/')
        if index > 0:
            dir = dir[0:index]
            curdir = os.path.join(basedir, dir)
            if not os.path.exists(curdir):
                self._createdir(basedir, curdir)
                os.mkdir(dir)
            else:
                return 
        else:
            curdir = os.path.join(basedir, dir)
            if not os.path.exists(curdir):
                os.mkdir(curdir)
            
            
    def _makedirs(self, directories, basedir):
        """ Create any directories that don't currently exist """
        for dir in directories:
            curdir = os.path.join(basedir, dir)
            if not os.path.exists(curdir):
                self._createdir(basedir, curdir)

    def _listdirs(self, file):
        """ Grabs all the directories in the zip structure
        This is necessary to create the structure before trying
        to extract the file to it. """
        zf = zipfile.ZipFile(file)

        dirs = []

        for name in zf.namelist():
            if name.endswith('/'):
                dirs.append(name)
            else:
                index = name.rfind('/')
                if index > 0:
                    index = index + 1
                    name = name[0:index]
                    dirs.append(name)

        dirs.sort()
        return dirs

            
            

