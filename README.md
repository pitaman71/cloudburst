# cloudburst

Use Cases for Cloudburst:
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
    - [x] cli: list, plan, pursue commands
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
    - [ ] install and invoke cloudburst agency on remote node
    - [ ] agent program and state exchange b/w participants
        - [ ] ConfigMonitor, ConfigUpdater python classes
        - [ ] ConfigTransaction, ConfigChange python classes
        - [ ] agency REST SendStateUpdate
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] local management of remote goal dispatch
    - [ ] anticipate remote dispatch
    - [ ] procure peer instances as needed
    - [ ] transmit goal to remote cloudburst daemon
    - [ ] monitor goal progress on remote cloudburst daemon
    - [ ] receive final outcome of remote cloudburst daemon
    - [ ] UC Tested
    - [ ] UC Documented
- [ ] securing peer to peer communication
    - [ ] agency require authentication for node2node
    - [ ] require configured SSL encryption for node2node
- [ ] Web-based Cloudburst Control Center
    - [ ] monitoring agents and goals
        - [ ] browse/inspect running agents
        - [ ] browse/inspect goals per agent
        - [ ] load cloudburst program from file
    - [ ] send and monitor basic commands
        [ ] basic Flask-based RESTful service
        [ ] schema-independent React/Redux front-end
        [ ] ObjectWindow
        [ ] browse commands on CloudburstDashboard.AgentInspector
        [ ] submit command as goal
        [ ] autoconfigure goal
        [ ] edit/resubmit goal
        [ ] browse all goals on CloudburstDashboard.AgentInspector
        [ ] filter/sort goals on CloudburstDashboard.AgentInspector
- [ ] Plan and Graph (comparable to Terraform)
    - [ ] 
- [ ] Snapshots and Checkpoints
    - [ ] Using cloud snapshots to accelerate authoring/debug of instance provisioning recipes
    - [ ] Using Cloudburst programs to construct Docker images
- [ ] Peer to Peer cloud: agency
    - [x] agency: factor shared code out of cloudburst_cli
    - [x] class Config: represents initial, partial, proposed, corrected, validated, completed variable state for each Goal
    - [ ] agency: "hello" command returns agency config
    - [ ] agency: "agents" lists local agents
    - [ ] agency: "programs" lists local programs
    - [ ] agency: "start(programName)" begins a new agent and returns agent detail
    - [ ] agency: "examine(agentName)" returns agent detail
    - [ ] agency: "suspend(agentName)" suspends a running agent and returns agent detail
    - [ ] agency: "resume(agentName)" resumes a suspended agent and returns agent detail
    - [ ] agency: "stop(agentName)" terminates an agent
    - [ ] agency: static authorization (authority, email, capability, lifetime) in permissions.xml
    - [ ] agency: static neighborhood in neighborhood.xml
    - [ ] agency: cache authenticated sessions
- [ ] Resilient Forward Recovery Path: Suspending, Reconfiguring, and Resume Interrupted Goals
    - [ ] failing methods cause goal to be suspended
    - [ ] browse suspended goals on cloudburst dashboard
    - [ ] edit/continue/cancel suspended goal
    - [ ] optional manual correction method for suspended goal
    - [ ] optional automated method for suspended goal
    - [ ] local persistent state backend for agent, goal, solver state
    - [ ] resuming agency operation on restart
    - [ ] state persistence backend
- [ ] Emulating & Integrating POSIX make with Cloudburst
- [ ] Emulating & Integrating Apache Maven with Cloudburst
- [ ] Emulating & Integrating npm with Cloudburst
- [ ] Emulating & Integrating Jenkins with Cloudburst
- [ ] Emulating & Integrating cron with Cloudburst
- [ ] Emulating & Integrating Terraform.io
- [ ] Emulating & Integrating Docker
- [ ] Production Delivery modes
    - [ ] agency: delivery to POSIX host via scp
    - [ ] agency: delivery to POSIX host via rpm package + yum
    - [ ] agency: remote-start local cloudburst daemon via sudo
    - [ ] agency: remote-start remote cloudburst daemon via ssh
