# hive

Use Cases for Hive:
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
    - [ ] hive_daemon: factor shared code out of hive_cli
    - [ ] hive_daemon: static authorization (authority, email, capability, lifetime) in permissions.xml
    - [ ] hive_daemon: static neighborhood in neighborhood.xml
    - [ ] hive_daemon: cache authenticated sessions
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
