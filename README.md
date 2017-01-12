# hive

Use Cases for Hive:
* Creating a cloud software product from a collection of node-level software components
* Cluster-wide goal-oriented dataflow integration
* Retrofitting a cloud service interface onto existing (node-local) programs
* Inventory of software, hardware, and data assets across a cluster
* Cloud-provider portability 
* Automating heterogenous builds
* Multiplatform testing
* Provisioning heterogenous arrays of cloud instances

Features:
* Step by step monitoring and control
* Interactive repair for interrupted/failed objectives

- [ ] Distributed Recipes: explicit ssh prefix
    - [x] hive_cli: list command
    - [x] hive_cli: plan command
    - [x] hive_cli: execute command
    - [x] hive_cli: expression interpretation
    - [x] hive_cli: shell interface
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] Peer to Peer cloud: hive_daemon
    - [ ] hived: factor shared code out of hive_cli
    - [ ] hived: static authorization (authority, email, capability, lifetime) in permissions.xml
    - [ ] hived: static neighborhood in neighborhood.xml
    - [ ] hived: cache authenticated sessions
- [ ] Distributed Recipes: dynamically provisioning EC2 instances
- [ ] Distributed Recipes: direct and indirect recipes
    - [ ] goal.pursue should automatically select local or remote recipe
    - [ ] transmit goal to remote hive daemon
    - [ ] monitor goal progress on remote hive daemon
    - [ ] receive final outcome of remote hive daemon
- [ ] Emulating POSIX make with Hive
- [ ] Emulating Jenkins with Hive
- [ ] Forward Path: Resumable Exception Goals
- [ ] Production Delivery modes
    - [ ] hive_daemon: delivery to POSIX host via scp
    - [ ] hive_daemon: delivery to POSIX host via rpm package + yum
    - [ ] hive: remote-start local hive daemon via sudo
    - [ ] hive: remote-start remote hive daemon via ssh
