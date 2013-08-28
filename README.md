==========================================================================
ElasticSearch 0.90.2  Enabler Guide
==========================================================================
Introduction
--------------------------------------
A Silver Fabric Enabler allows an external application or application platform, 
such as a J2EE application server to run in a TIBCO Silver Fabric software 
environment. In Silver Fabric 4.1, we introduced the **Scripting Container** feature
to accelerate the development of new enablers and enable customers to customize
existing enablers for site-specific requirements.  This document describes what is
involved in developing a reasonably full-featured ElasticSearch enabler using jython.

Installation
--------------------------------------
The ElasticSearch Enabler consists of an Enabler Runtime Grid Library and a Distribution 
Grid Library. The Enabler Runtime contains information specific to a Silver Fabric 
version that is used to integrate the Enabler, and the Distribution contains a binary 
distribution of ElasticSearch used for the Enabler. Installation of the ElasticSearch Enabler 
involves copying these Grid Libraries to the 
SF_HOME/webapps/livecluster/deploy/resources/gridlib directory on the Silver Fabric Broker. 

Creating the ElasticSearch Enabler
--------------------------------------
The Enabler Runtime Grid Library is created by building the maven project.
```bash
mvn package
```

Creating the Distribution Grid Library
--------------------------------------
The Distribution Grid Library is created by performing the following steps:
* Download the Elasticsearch binaries from https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-0.90.2.zip
* Build the maven project with the location of the archive, the archive's base name, the archive type, the 
      operating system target and optionally the version. 
       

*****************************************************************************
NOTE: As of now, only 64-bit linux has been tested !
******************************************************************************
```bash
mvn package -Ddistribution.location=/home/you/Downloads/ \
-Ddistribution.basename=elasticsearch-0.90.2 \
-Ddistribution.type=zip \
-Ddistribution.version=0.90.2 -Ddistribution.os=all
```
The distribution.location path should end in the appropriate path-separator for your operating system (either "/" or "\\")
If running maven on Windows, make sure to to double-escape the backslash path separators for the 
distribution.location property: -Ddistribution.location=C:\\Users\\you\\Downloads\\

or you can do manually :

```bash
cd src/main/assembly/distribution
wget "https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-0.90.2.zip"
unzip elasticsearch-0.90.2.zip
rm -f elasticsearch-0.90.2.zip
mv elasticsearch-0.90.2 elasticsearch
zip -r elasticsearch-0.90.2-distribution.zip elasticsearch-0.90.2 grid-library.xml
```

Then upload this distribution to the Tibco Silver Fabric Manager


Supported Features
--------------------------------------

- [ ] ElasticSearch _site plugins detection
- [x] ElasticSearch multicast clustering support
- [ ] ElasticSearch unicast clustering support
- [x] ElasticSearch statistics support
- [x] ElasticSearch offline plugins support


Engines requirements
--------------------------------------
Make sure to increase the number of open files descriptors on the machine (or for the user running elasticsearch). Setting it to 32k or even 64k is recommended.
```bash
# run this when loading the user profile
ulimit -l unlimited
# or you could edit this file /etc/security/limits.conf
    <USERNAME> soft nofile 32000
    <USERNAME> hard nofile 32000
```

On the engine Configuration in TIBCO SF, you shoul consider setting this
```bash
set -XX:+CMSClassUnloadingEnabled  -XX:MaxPermSize=256m
set JVM HEAP from 192 mb to 512 mb
```
What about plug-ins
--------------------------------------

This enabler supports archives, plugins in .zip format will be considered as archive.

simply zip each plugins (folder) under your plugins directory installation

```bash
cd $ES_HOME/plugins
zip -r HQ.zip HQ
```

They will be :
- automatically installed and deployed
- automatically updating URL to reach them

NOTE TO MYSELF = As of 01/08/2013 - this is not yet fully, really implemented, just announced as a teaser ;-) 
- HTTP routing will be updated to let you access to them (wherever they are _site or _plugs)
- url detection and update
- other fun stuff
- plugins installation

Runtime Context Variables
--------------------------------------
Below are some notable Runtime Context Variables associated with this Enabler.
Take a look at the container.xml file in the src/main/resources/runtime/ subdirectory

****************************************************************************************

Common Variables 
--------------------------------------
(Change as Desired)
* ES_DATA_DIR : path where the data files are located; 
			NOTE: for persistence across engine hosts, it is recommended you
                  specify a network-mounted directory for this variable.
                  Changing this might also affect other variables (e.g, CAPTURE_INCLUDES)              

* HTTP_PORT : port where this elasticsearch node listens for connections
* ES_CONF_DIR : path where the conf files are located;
		      NOTE: for persistence across engine hosts, it is recommended you
                  specify a network-mounted directory for this variable.
* ES_LOG_DIR : path where the logs files are located;
			NOTE: for persistence across engine hosts, it is recommended you
                  specify a network-mounted directory for this variable.
* CLUSTER_NAME : Define the name of the cluster even if a single node is used

Power Variables 
--------------------------------------
(Change If You Know What You're Doing)
* CAPTURE_INCLUDES : common capture stuff, currently it includes everything
                  under the standard data directory

Internal Variables 
--------------------------------------
(Don't Change Unless Absolutely Needed)
* ES_BASE_DIR : path where elasticsearch resides after installation - change
                  CONTAINER_WORK_DIR instead

* ES_HOST_IP : IP address where this instance listens for connections


****************************************************************************************

How to play with 
--------------------------------------
TIBCO Silver Fabric will publish access to the cluster thru :
http://\<FullyQualifiedSFinstanceHostname\>:\<SFPort\>/\<ClusterName\>/
this address will be resolved/translated to the endpoint directly (one of the ElasticSearch cluster node)

Cool things to use against ElasticSearch
--------------------------------------
You could take a look at http://www.scrutmydocs.org/, which rely on an elasticsearch cluster for storing, finding, indexing documents

