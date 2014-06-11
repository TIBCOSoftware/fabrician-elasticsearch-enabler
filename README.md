==========================================================================
ElasticSearch Enabler Guide
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

Verified ElasticSearch versions
--------------------------------------
The Enabler was originally developed with ElasticSearch version 0.90.2. It has recently been tested with
ElasticSearch version 1.2.1, the latest available ElasticSearch release.

Creating the ElasticSearch Enabler
--------------------------------------
The Enabler Runtime Grid Library is created by building the maven project.
```bash
mvn package
```

Creating the Distribution Grid Library
--------------------------------------
The Distribution Grid Library is created by performing the following steps:
* Download the Elasticsearch binaries from (Note: Replace version 0.90.2 with the ElasticSearch you choose): https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-0.90.2.zip
* Build the maven project with the location of the archive, the archive's base name, the archive type, the 
      operating system target and optionally the version. 
       

*****************************************************************************
NOTE: As of now, only 64-bit linux has been tested !
NOTE: Linux distros being tested : Centos 6.X, DEBIAN 7.X , RHEL 6.X
******************************************************************************
```bash
#Note: Replace version 0.90.2 with the ElasticSearch version you choose
mvn package -Ddistribution.location=/home/you/Downloads/ \
-Ddistribution.type=zip \
-Ddistribution.version=0.90.2 -Ddistribution.os=all
```
The distribution.location path should end in the appropriate path-separator for your operating system (either "/" or "\\")
If running maven on Windows, make sure to to double-escape the backslash path separators for the 
distribution.location property: -Ddistribution.location=C:\\Users\\you\\Downloads\\

or you can do manually :
```bash
#NOTE: Replace version 0.90.2 with the ElasticSearch version you choose
cd src/main/assembly/distribution
wget "https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-0.90.2.zip"
unzip elasticsearch-0.90.2.zip
rm -f elasticsearch-0.90.2.zip
mv elasticsearch-0.90.2 elasticsearch
#String replace ${distribution.version} in grid-library.xml
cat grid-library.xml | sed 's/${distribution.version}/0.90.2/g' > grid-library.tmp; mv grid-library.tmp grid-library.xml
zip -r elasticsearch-0.90.2-distribution.zip elasticsearch-0.90.2 grid-library.xml
```

Then upload this distribution to the Tibco Silver Fabric Manager


Supported Features
--------------------------------------

- [x] ElasticSearch _site plugins detection
- [x] ElasticSearch multicast clustering support
- [x] ElasticSearch unicast clustering support
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

On the engine Configuration in TIBCO SF, you should consider setting this
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


Runtime Context Variables
--------------------------------------
Below are some notable Runtime Context Variables associated with this Enabler.
Take a look at the container.xml file in the src/main/resources/runtime/ subdirectory

****************************************************************************************

Common Variables 
--------------------------------------
(Change as Desired) syntax is : \<Variable Name\> : \<Description\> : \<\Accepted Values\> / [<Default value]
* ES_DATA_DIR : path where the data files are located
```
NOTE: for persistence across engine hosts, it is recommended you
specify a network-mounted directory for this variable.
Changing this might also affect other variables (e.g, CAPTURE_INCLUDES)
```           
* ES_CONF_DIR : path where the conf files are located : [${ES_BASE_DIR}/config]
```
NOTE: for persistence across engine hosts, it is recommended you
specify a network-mounted directory for this variable.
```
* ES_LOG_DIR : path where the logs files are located : [${ES_BASE_DIR}/logs]
```
NOTE: for persistence across engine hosts, it is recommended you
specify a network-mounted directory for this variable.
```
* CLUSTER_NAME : Define the name of the cluster even if a single node is used
* MULTICAST_ENABLED : Define is multicast should be used for Clustering,look at ElasticSearch Clusering how-to for more details : true / [false]
* ES_NODE_TYPE_MASTER : Define if this instance node should be considered as an master : [true] / false
* ES_NODE_TYPE_DATA : Define if this instance node should be considered as an data node : [true] / false
* HTTP_PORT : HTTP port where this elasticsearch node listens for connections or Rest requests : [18000]
* ES_TCP_PORT : port where this elasticsearch node to node communication : [17000]
* ES_MAX_MEM : set the maximum memory for elasticsearch instances : [2048m] 
* ES_MIN_MEM : set the minimum memory for elasticsearch instances : [2048m]
* PORT_RANDOM_MAX_OFFSET : offset to be added on http and tcp port, to enforce uniq (horizontal sclaing and vertical scaling) port usage



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

ElasticSearch Unicast Clustering
--------------------------------------
Follow simply this recipe :

1. Create an ElasticSearch Component called let say ElasticPrimary
2. Create and ElasticSearch Component called let say ElasticNodes
3. edit "ElasticNodes" Component to set the variable isPrimaryNode to 'False' (Capital letter matters)
4. create an stack, and add ElasticPrimary, ElasticNodes
5. add and dependency for  ElasticNodes on ElasticPrimary without shutdown

Run the stack

How to play with 
--------------------------------------
TIBCO Silver Fabric will publish access to the cluster thru :
http://\<FullyQualifiedSFinstanceHostname\>:\<SFPort\>/\<ClusterName\>/
this address will be resolved/translated to the endpoint directly (one of the ElasticSearch cluster node)

Cool things to use against ElasticSearch
--------------------------------------
1. take a look at http://www.scrutmydocs.org/, which rely on an elasticsearch cluster for storing, finding, indexing documents
2. You may want to enable : logstash (index and store logs to elasticsearch) and lumberjack (send logs to logstach) and kibana3 as a front end : http://demo.kibana.org/#/dashboard

Testing
--------------------------------------
1. Create an ElasticSearch Component called let say ElasticPrimary
2. Add the Head plugin : http://mobz.github.io/elasticsearch-head/
3. Add the river rss : http://www.pilato.fr/rssriver/
4. Create and ElasticSearch Component called let say ElasticNodes
5. Add the Head plugin : http://mobz.github.io/elasticsearch-head/
6. Add the river rss : http://www.pilato.fr/rssriver/
7. Edit "ElasticNodes" Component to set the variable isPrimaryNode to 'False' (Capital letter matters)
8. Create an stack, and add ElasticPrimary, ElasticNodes
9. Add and dependency for  ElasticNodes on ElasticPrimary without shutdown
10. Run the stack, wait a couple a secs, min to be fully operational
11. Run the following curl commands

```bash
curl -L -XPUT 'http://\<FullyQualifiedSFinstanceHostname\>:\<SFPort\>/\<ClusterName\>/nytimes/' -d '{}'
```
```bash
curl -L -XPUT 'http://\<FullyQualifiedSFinstanceHostname\>:\<SFPort\>/\<ClusterName\>/nytimes/page/_mapping' -d '{
"page" : {
    "properties" : {
      "title" : {"type" : "string"},
      "description" : {"type" : "string"},
      "author" : {"type" : "string"},
      "link" : {"type" : "string"}
    }
  }
}'
```
```bash
curl -L -XPUT 'http://\<FullyQualifiedSFinstanceHostname\>:\<SFPort\>/\<ClusterName\>/_river/nytimes/_meta' -d '{
"type": "rss",
  "rss": {
    "feeds" : [ {
        "name": "nytimes",
        "url": "http://www.nytimes.com/services/xml/rss/nyt/NYRegion.xml",
	"update_rate": 30000,
	"ignore_ttl": true
        }
    ]
  }
}'
```
```bash
curl -L -XGET 'http://\<FullyQualifiedSFinstanceHostname\>:\<SFPort\>/\<ClusterName\>/nytimes/_search?q=dogs'
```
You should get something like this :
```json
{

    took: 2
    timed_out: false
    _shards: {
        total: 5
        successful: 5
        failed: 0
    }
    hits: {
        total: 1
        max_score: 0.09321462
        hits: [
            {
                _index: nytimes
                _type: page
                _id: c4506023-c9d3-3bb9-bd7c-800f28e4d93b
                _score: 0.09321462
                _source: {
                    feedname: nytimes
                    title: City Room: New York Today: 7 Million Miles
                    author: By ANDY NEWMAN
                    description: What you need to know for Wednesday: New York goes the distance on Citi Bikes, a big lead for Bill de Blasio and a parade of dogs.<img width='1' height='1' src='http://rss.nytimes.com/c/34625/f/640367/s/3162a69f/sc/22/mf.gif' border='0'/><br clear='all'/><div class='mf-viral'><table border='0'><tr><td valign='middle'><a href="http://share.feedsportal.com/share/twitter/?u=http%3A%2F%2Fcityroom.blogs.nytimes.com%2F2013%2F09%2F18%2Fnew-york-today-7-million-miles%2F%3Fpartner%3Drss%26emc%3Drss&t=City+Room%3A+New+York+Today%3A+7+Million+Miles" target="_blank"><img src="http://res3.feedsportal.com/social/twitter.png" border="0" /></a>&nbsp;<a href="http://share.feedsportal.com/share/facebook/?u=http%3A%2F%2Fcityroom.blogs.nytimes.com%2F2013%2F09%2F18%2Fnew-york-today-7-million-miles%2F%3Fpartner%3Drss%26emc%3Drss&t=City+Room%3A+New+York+Today%3A+7+Million+Miles" target="_blank"><img src="http://res3.feedsportal.com/social/facebook.png" border="0" /></a>&nbsp;<a href="http://share.feedsportal.com/share/linkedin/?u=http%3A%2F%2Fcityroom.blogs.nytimes.com%2F2013%2F09%2F18%2Fnew-york-today-7-million-miles%2F%3Fpartner%3Drss%26emc%3Drss&t=City+Room%3A+New+York+Today%3A+7+Million+Miles" target="_blank"><img src="http://res3.feedsportal.com/social/linkedin.png" border="0" /></a>&nbsp;<a href="http://share.feedsportal.com/share/gplus/?u=http%3A%2F%2Fcityroom.blogs.nytimes.com%2F2013%2F09%2F18%2Fnew-york-today-7-million-miles%2F%3Fpartner%3Drss%26emc%3Drss&t=City+Room%3A+New+York+Today%3A+7+Million+Miles" target="_blank"><img src="http://res3.feedsportal.com/social/googleplus.png" border="0" /></a>&nbsp;<a href="http://share.feedsportal.com/share/email/?u=http%3A%2F%2Fcityroom.blogs.nytimes.com%2F2013%2F09%2F18%2Fnew-york-today-7-million-miles%2F%3Fpartner%3Drss%26emc%3Drss&t=City+Room%3A+New+York+Today%3A+7+Million+Miles" target="_blank"><img src="http://res3.feedsportal.com/social/email.png" border="0" /></a></td></tr></table></div><br/><br/><a href="http://da.feedsportal.com/r/176964385415/u/89/f/640367/c/34625/s/3162a69f/sc/22/rc/1/rc.htm"><img src="http://da.feedsportal.com/r/176964385415/u/89/f/640367/c/34625/s/3162a69f/sc/22/rc/1/rc.img" border="0"/></a><br/><a href="http://da.feedsportal.com/r/176964385415/u/89/f/640367/c/34625/s/3162a69f/sc/22/rc/2/rc.htm"><img src="http://da.feedsportal.com/r/176964385415/u/89/f/640367/c/34625/s/3162a69f/sc/22/rc/2/rc.img" border="0"/></a><br/><a href="http://da.feedsportal.com/r/176964385415/u/89/f/640367/c/34625/s/3162a69f/sc/22/rc/3/rc.htm"><img src="http://da.feedsportal.com/r/176964385415/u/89/f/640367/c/34625/s/3162a69f/sc/22/rc/3/rc.img" border="0"/></a><br/><br/><a href="http://da.feedsportal.com/r/176964385415/u/89/f/640367/c/34625/s/3162a69f/a2.htm"><img src="http://da.feedsportal.com/r/176964385415/u/89/f/640367/c/34625/s/3162a69f/a2.img" border="0"/></a><img width="1" height="1" src="http://pi.feedsportal.com/r/176964385415/u/89/f/640367/c/34625/s/3162a69f/a2t.img" border="0"/>
                    link: http://cityroom.blogs.nytimes.com/2013/09/18/new-york-today-7-million-miles/?partner=rss&emc=rss
                    publishedDate: 2013-09-18T16:02:34.000Z
                    source: null
                    river: nytimes
                }
            }
        ]
    }

}
```
