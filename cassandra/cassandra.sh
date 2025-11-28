#!/bin/bash

# Set JVM heap size
echo "-Xms256M" >> /apache-cassandra-5.0.6/conf/jvm-server.options
echo "-Xmx256M" >> /apache-cassandra-5.0.6/conf/jvm-server.options

# Configure Cassandra with this node's hostname
sed -i "s/^listen_address:.*/listen_address: "`hostname`"/" /apache-cassandra-5.0.6/conf/cassandra.yaml
sed -i "s/^rpc_address:.*/rpc_address: "`hostname`"/" /apache-cassandra-5.0.6/conf/cassandra.yaml

# Set seed nodes for cluster discovery
sed -i "s/- seeds:.*/- seeds: db-1,db-2,db-3/" /apache-cassandra-5.0.6/conf/cassandra.yaml

# Start Cassandra in foreground mode
/apache-cassandra-5.0.6/bin/cassandra -R

# Keep container running
sleep infinity
