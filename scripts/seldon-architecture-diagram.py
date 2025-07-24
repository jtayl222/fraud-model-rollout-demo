from diagrams import Diagram, Cluster, Edge
from diagrams.k8s.compute import Pod, Deployment
from diagrams.k8s.network import Service
from diagrams.k8s.rbac import ServiceAccount
from diagrams.k8s.controlplane import APIServer

# Architecture 1: Operator and scheduler within the same namespace
with Diagram("Architecture 1: Single Namespace Install", show=False, filename="seldon-arch-1", direction="TB"):
    with Cluster("Namespace: fraud-detection"):
        operator1 = Deployment("seldon-operator")
        scheduler1 = Pod("scheduler")
        envoy1 = Service("seldon-mesh\n(envoy)")
        pipeline_gw1 = Service("pipeline-gateway")
        model_gw1 = Service("model-gateway")
        dataflow1 = Pod("dataflow-engine")
        
        models1 = Pod("Models/Servers")
        
        operator1 >> scheduler1
        scheduler1 >> [envoy1, pipeline_gw1, model_gw1, dataflow1]
        [envoy1, model_gw1] >> models1

# Architecture 2: Operator cluster-wide, one scheduler per namespace
with Diagram("Architecture 2: Cluster-wide Operator", show=False, filename="seldon-arch-2", direction="TB"):
    with Cluster("Cluster-wide"):
        operator2 = Deployment("seldon-operator\n(clusterwide=true)")
    
    with Cluster("Namespace: fraud-detection"):
        scheduler2a = Pod("scheduler")
        envoy2a = Service("seldon-mesh")
        pipeline_gw2a = Service("pipeline-gateway")
        model_gw2a = Service("model-gateway")
        dataflow2a = Pod("dataflow-engine")
        models2a = Pod("Models/Servers")
        
    with Cluster("Namespace: recommendation"):
        scheduler2b = Pod("scheduler")
        envoy2b = Service("seldon-mesh")
        pipeline_gw2b = Service("pipeline-gateway")
        model_gw2b = Service("model-gateway")
        dataflow2b = Pod("dataflow-engine")
        models2b = Pod("Models/Servers")
    
    operator2 >> Edge(label="connects to") >> [scheduler2a, scheduler2b]
    scheduler2a >> [envoy2a, pipeline_gw2a, model_gw2a, dataflow2a]
    scheduler2b >> [envoy2b, pipeline_gw2b, model_gw2b, dataflow2b]
    [envoy2a, model_gw2a] >> models2a
    [envoy2b, model_gw2b] >> models2b

# Architecture 3: Operator in namespace, watching fixed namespaces
with Diagram("Architecture 3: Scoped Operator Pattern", show=False, filename="seldon-arch-3", direction="TB"):
    with Cluster("Namespace: seldon-system"):
        operator3 = Deployment("seldon-operator\n(clusterwide=true\nwatchNamespaces=[fraud,rec])")
    
    with Cluster("Namespace: fraud-detection"):
        scheduler3a = Pod("scheduler")
        envoy3a = Service("seldon-mesh")
        pipeline_gw3a = Service("pipeline-gateway")
        model_gw3a = Service("model-gateway")
        dataflow3a = Pod("dataflow-engine")
        models3a = Pod("Models/Servers")
        
    with Cluster("Namespace: recommendation"):
        scheduler3b = Pod("scheduler")
        envoy3b = Service("seldon-mesh")
        pipeline_gw3b = Service("pipeline-gateway")
        model_gw3b = Service("model-gateway")
        dataflow3b = Pod("dataflow-engine")
        models3b = Pod("Models/Servers")
    
    operator3 >> Edge(label="watches") >> [scheduler3a, scheduler3b]
    scheduler3a >> [envoy3a, pipeline_gw3a, model_gw3a, dataflow3a]
    scheduler3b >> [envoy3b, pipeline_gw3b, model_gw3b, dataflow3b]
    [envoy3a, model_gw3a] >> models3a
    [envoy3b, model_gw3b] >> models3b

print("Diagrams created: seldon-arch-1.png, seldon-arch-2.png, seldon-arch-3.png")