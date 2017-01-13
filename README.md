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
    - [x] Goal.plan
    - [x] Goal.pursue
    - [x] Goal.execute 
    - [x] ExprResult
    - [x] hive_cli: shell interface
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] Peer to Peer cloud: hive_daemon
    - [x] hive_agency: factor shared code out of hive_cli
    - [x] class Config: represents initial, partial, proposed, corrected, validated, completed variable state for each Goal
    - [ ] class Invocation 
    - [ ] hive_agency: "hello" command returns agency config
    - [ ] hive_agency: "agents" lists local agents
    - [ ] hive_agency: "programs" lists local programs
    - [ ] hive_agency: "start(programName)" begins a new agent and returns agent detail
    - [ ] hive_agency: "examine(agentName)" returns agent detail
    - [ ] hive_agency: "suspend(agentName)" suspends a running agent and returns agent detail
    - [ ] hive_agency: "resume(agentName)" resumes a suspended agent and returns agent detail
    - [ ] hive_agency: "stop(agentName)" terminates an agent
    - [ ] hive_agency: static authorization (authority, email, capability, lifetime) in permissions.xml
    - [ ] hive_agency: static neighborhood in neighborhood.xml
    - [ ] hive_agency: cache authenticated sessions
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
