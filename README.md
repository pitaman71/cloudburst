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
    - [x] hive_cli: list, plan, pursue commands
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] Execution Modes
    - [x] list goal prototypes
    - [x] plan goal
    - [x] pursue/execute goal
    - [x] narrate mode
    - [x] verbose mode
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] Recursive (local) prerequisite goals
    - [x] goalCompleted expression
    - [x] configuring prerequisite goals
    - [x] recursively executing prerequsite goals
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] Auto configuration of command goals
    - [x] class Tabulator to print goal names and descriptions
    - [x] reconfigure() methods to compute config options from state
    - [x] ConfigController to print suggested config options in command-line syntax
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] Distributed Recipes: dynamically provisioning robust EC2 instances
    - [x] enhanced Cassandra provisioning recipes using ec2 api to obtain instances
    - [x] ProvisionEC2Cluster recipe for procuring EC2 instance for Datastax cluster
    - [x] find/in/do task statements
    - [x] goalCompleted as an executable statement (spawned subgoal)
    - [x] using <set> and <get> as lvalue and rvalue in <python><code> blocks
    - [ ] install and invoke hive agency on remote node
    - [ ] agent program and state exchange b/w participants
        - [ ] ConfigMonitor, ConfigUpdater python classes
        - [ ] ConfigTransaction, ConfigChange python classes
        - [ ] hive_agency REST SendStateUpdate
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] local management of remote goal dispatch
    - [ ] anticipate remote dispatch
    - [ ] procure peer instances as needed
    - [ ] transmit goal to remote hive daemon
    - [ ] monitor goal progress on remote hive daemon
    - [ ] receive final outcome of remote hive daemon
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] securing peer to peer communication
    - [ ] hive_agency require authentication for node2node
    - [ ] require configured SSL encryption for node2node
- [ ] Web-based Hive Control Center
    - [ ] monitoring agents and goals
        - [ ] browse/inspect running agents
        - [ ] browse/inspect goals per agent
        - [ ] load hive program from file
    - [ ] send and monitor basic commands
        [ ] basic Flask-based RESTful service
        [ ] schema-independent React/Redux front-end
        [ ] ObjectWindow
        [ ] browse commands on HiveDashboard.AgentInspector
        [ ] submit command as goal
        [ ] autoconfigure goal
        [ ] edit/resubmit goal
        [ ] browse all goals on HiveDashboard.AgentInspector
        [ ] filter/sort goals on HiveDashboard.AgentInspector
- [ ] Plan and Graph (comparable to Terraform)
    - [ ] 
- [ ] Snapshots and Checkpoints
    - [ ] Using cloud snapshots to accelerate authoring/debug of instance provisioning recipes
    - [ ] Using Hive programs to construct Docker images
- [ ] Peer to Peer cloud: hive_daemon
    - [x] hive_agency: factor shared code out of hive_cli
    - [x] class Config: represents initial, partial, proposed, corrected, validated, completed variable state for each Goal
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
- [ ] Resilient Forward Recovery Path: Suspending, Reconfiguring, and Resume Interrupted Goals
    - [ ] failing methods cause goal to be suspended
    - [ ] browse suspended goals on hive dashboard
    - [ ] edit/continue/cancel suspended goal
    - [ ] optional manual correction method for suspended goal
    - [ ] optional automated method for suspended goal
    - [ ] local persistent state backend for agent, goal, solver state
    - [ ] resuming agency operation on restart
    - [ ] state persistence backend
- [ ] Emulating & Integrating POSIX make with Hive
- [ ] Emulating & Integrating Apache Maven with Hive
- [ ] Emulating & Integrating npm with Hive
- [ ] Emulating & Integrating Jenkins with Hive
- [ ] Emulating & Integrating cron with Hive
- [ ] Emulating & Integrating Terraform.io
- [ ] Emulating & Integrating Docker
- [ ] Production Delivery modes
    - [ ] hive_daemon: delivery to POSIX host via scp
    - [ ] hive_daemon: delivery to POSIX host via rpm package + yum
    - [ ] hive: remote-start local hive daemon via sudo
    - [ ] hive: remote-start remote hive daemon via ssh
